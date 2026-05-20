"""
Background tasks for processing CSV/API imports.
Uses pandas for data processing and scikit-learn for deduplication.
"""
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from background_task import background
from apps.jobs.models import JobVacancy, JobCategory
from apps.ingestion.models import DataSource, IngestionJob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@background(schedule=1)
def process_csv_upload(ingestion_job_id, column_mapping, trust_score=95, auto_approve=True):
    """
    Process uploaded CSV file in background.
    Uses pandas for efficient CSV parsing.
    """
    try:
        ingestion_job = IngestionJob.objects.get(id=ingestion_job_id)
        ingestion_job.status = IngestionJob.Status.PROCESSING
        ingestion_job.started_at = timezone.now()
        ingestion_job.save()
        
        # Read CSV with pandas
        file_path = ingestion_job.uploaded_file.path
        df = pd.read_csv(file_path)
        
        ingestion_job.total_records = len(df)
        ingestion_job.save()
        
        # Rename columns based on mapping
        # column_mapping format: {"CSV Column": "model_field"}
        rename_dict = {csv_col: db_field for csv_col, db_field in column_mapping.items()}
        df.rename(columns=rename_dict, inplace=True)
        
        # Process in batches for memory efficiency
        batch_size = 100
        jobs_created = 0
        jobs_updated = 0
        errors = []
        
        for start_idx in range(0, len(df), batch_size):
            batch = df.iloc[start_idx:start_idx + batch_size]
            
            for _, row in batch.iterrows():
                try:
                    job_data = prepare_job_data(row, trust_score, auto_approve)
                    
                    # Check for duplicates
                    existing = check_duplicate_job(job_data)
                    
                    if existing:
                        # Update existing job
                        for key, value in job_data.items():
                            if key != 'posted_by' and key != 'source_type':
                                setattr(existing, key, value)
                        existing.save()
                        jobs_updated += 1
                    else:
                        # Create new job
                        JobVacancy.objects.create(**job_data)
                        jobs_created += 1
                        
                except Exception as e:
                    errors.append(f"Row {start_idx + _}: {str(e)}")
                    ingestion_job.failed_records += 1
            
            ingestion_job.processed_records = min(start_idx + batch_size, len(df))
            ingestion_job.created_records = jobs_created
            ingestion_job.updated_records = jobs_updated
            ingestion_job.save()
        
        # Mark as completed
        ingestion_job.status = IngestionJob.Status.COMPLETED
        ingestion_job.completed_at = timezone.now()
        if errors:
            ingestion_job.error_log = "\n".join(errors[:100])  # Store first 100 errors
        ingestion_job.save()
        
    except Exception as e:
        ingestion_job.status = IngestionJob.Status.FAILED
        ingestion_job.completed_at = timezone.now()
        ingestion_job.error_log = str(e)
        ingestion_job.save()
        raise


def prepare_job_data(row, trust_score, auto_approve):
    """
    Prepare job data from CSV/API row.
    Only includes fields that have actual data - no fake defaults.
    """
    # Parse expiry date - this is the ONLY safe default
    expiry_date = None
    raw_expiry = row.get('expiry_date')
    if raw_expiry and not pd.isna(raw_expiry):
        if isinstance(raw_expiry, str):
            try:
                expiry_date = pd.to_datetime(raw_expiry).date()
            except:
                pass
        else:
            expiry_date = raw_expiry
    
    if not expiry_date:
        expiry_date = timezone.now().date() + timezone.timedelta(days=30)
    
    # Clean skills
    skills = row.get('required_skills', '')
    if pd.isna(skills):
        skills = ''
    else:
        skills = str(skills).strip()
    
    # Map job type - ONLY if provided
    job_type_map = {
        'full time': 'FT', 'full-time': 'FT', 'permanent': 'FT',
        'part time': 'PT', 'part-time': 'PT',
        'contract': 'CT', 'temporary': 'CT',
        'internship': 'IN', 'intern': 'IN',
        'remote': 'RM', 'work from home': 'RM',
        'hybrid': 'HY',
        'freelance': 'FL'
    }
    
    job_type = None
    job_type_str = str(row.get('job_type', '')).lower().strip()
    if job_type_str:
        job_type = job_type_map.get(job_type_str)
    
    # Map experience level - ONLY if provided
    exp_map = {
        'entry': 'ENTRY', 'junior': 'JUNIOR', 'mid': 'MID',
        'senior': 'SENIOR', 'lead': 'LEAD'
    }
    
    experience_level = None
    exp_str = str(row.get('experience_level', '')).lower().strip()
    if exp_str:
        experience_level = exp_map.get(exp_str)
    
    # Location - only take what's provided
    city = str(row.get('city', '')).strip()
    location_display = str(row.get('location_display', '')).strip()
    
    # If no city but has location, use location as city
    if not city:
        loc = str(row.get('location', '')).strip()
        if loc:
            city = loc
    
    # If no location_display but has city, use city
    if not location_display and city:
        location_display = city
    
    # Build the base job data
    job_data = {
        'title': str(row.get('title', 'Untitled Position')).strip(),
        'company_name': str(row.get('company_name', 'Unknown Company')).strip(),
        'description': str(row.get('description', '')).strip(),
        'required_skills': skills,
        'expiry_date': expiry_date,
        'source_type': JobVacancy.SourceType.ADMIN_CSV,
        'trust_score': trust_score,
        'is_approved': auto_approve,
    }
    
    # Only add optional fields if they have actual values
    if job_type:
        job_data['job_type'] = job_type
    
    if experience_level:
        job_data['experience_level'] = experience_level
    
    if city:
        job_data['city'] = city
    
    if location_display:
        job_data['location_display'] = location_display
    
    # Application URL - only if valid
    app_url = row.get('application_url')
    if app_url and not pd.isna(app_url):
        app_url_str = str(app_url).strip()
        if app_url_str and app_url_str.startswith('http'):
            job_data['application_url'] = app_url_str
    
    # Application Email - only if valid
    app_email = row.get('application_email')
    if app_email and not pd.isna(app_email):
        app_email_str = str(app_email).strip()
        if app_email_str and '@' in app_email_str:
            job_data['application_email'] = app_email_str
    
    # Years of experience - only if provided and positive
    years_exp = row.get('years_of_experience_required', 0)
    if years_exp and not pd.isna(years_exp):
        try:
            years_int = int(years_exp)
            if years_int > 0:
                job_data['years_of_experience_required'] = years_int
        except (ValueError, TypeError):
            pass
    
    # Required qualifications - only if provided
    qualifications = row.get('required_qualifications', '')
    if qualifications and not pd.isna(qualifications):
        qual_str = str(qualifications).strip()
        if qual_str:
            job_data['required_qualifications'] = qual_str
    
    # Requirements and responsibilities
    requirements = row.get('requirements', '')
    if requirements and not pd.isna(requirements):
        req_str = str(requirements).strip()
        if req_str:
            job_data['requirements'] = req_str
    
    responsibilities = row.get('responsibilities', '')
    if responsibilities and not pd.isna(responsibilities):
        resp_str = str(responsibilities).strip()
        if resp_str:
            job_data['responsibilities'] = resp_str
    
    # Remote flag
    is_remote = row.get('is_remote', False)
    if is_remote and not pd.isna(is_remote):
        if str(is_remote).lower() in ['true', 'yes', '1', 'remote']:
            job_data['is_remote'] = True
    
    # Company website
    company_website = row.get('company_website', '')
    if company_website and not pd.isna(company_website):
        web_str = str(company_website).strip()
        if web_str and web_str.startswith('http'):
            job_data['company_website'] = web_str
    
    return job_data


def check_duplicate_job(job_data):
    """
    Check for duplicate jobs using text similarity.
    Prevents duplicate entries from multiple sources.
    """
    # First check exact match on title and company
    exact_match = JobVacancy.objects.filter(
        title__iexact=job_data['title'],
        company_name__iexact=job_data['company_name'],
        is_approved=True
    ).first()
    
    if exact_match:
        return exact_match
    
    # If no exact match, check for similar jobs
    similar_jobs = JobVacancy.objects.filter(
        company_name__iexact=job_data['company_name'],
        is_approved=True
    )[:10]  # Limit to 10 for performance
    
    if similar_jobs:
        # Use TF-IDF for similarity check
        job_titles = [job.title for job in similar_jobs]
        job_titles.append(job_data['title'])
        
        vectorizer = TfidfVectorizer().fit_transform(job_titles)
        vectors = vectorizer.toarray()
        
        # Compare last vector (new job) with others
        for i in range(len(vectors) - 1):
            similarity = cosine_similarity([vectors[-1]], [vectors[i]])[0][0]
            if similarity > 0.85:  # 85% similarity threshold
                return similar_jobs[i]
    
    return None


@background(schedule=1)
def fetch_api_data(data_source_id):
    """
    Fetch data from API endpoint and process.
    Supports JSON APIs with authentication.
    """
    try:
        data_source = DataSource.objects.get(id=data_source_id)
        
        # Create ingestion job record
        ingestion_job = IngestionJob.objects.create(
            data_source=data_source,
            status=IngestionJob.Status.PROCESSING,
            started_at=timezone.now()
        )
        
        # Prepare headers
        headers = {'Content-Type': 'application/json'}
        if data_source.auth_type == 'BEARER' and data_source.api_key:
            headers['Authorization'] = f"Bearer {data_source.api_key}"
        
        # Make request
        response = requests.get(
            data_source.url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        # Parse JSON
        data = response.json()
        
        # Handle different response structures
        if isinstance(data, dict):
            # Try common patterns
            items = data.get('data') or data.get('jobs') or data.get('results') or []
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError("Unexpected API response format")
        
        ingestion_job.total_records = len(items)
        ingestion_job.save()
        
        # Process items
        jobs_created = 0
        for item in items:
            try:
                job_data = parse_api_item(item, data_source.field_mapping)
                
                # Skip if no title or company - essential fields
                if not job_data.get('title') or not job_data.get('company_name'):
                    ingestion_job.failed_records += 1
                    continue
                
                job_data['source_type'] = JobVacancy.SourceType.ADMIN_API
                job_data['trust_score'] = data_source.default_trust_score
                job_data['is_approved'] = data_source.auto_approve
                
                # Check for duplicates
                if not check_duplicate_job(job_data):
                    JobVacancy.objects.create(**job_data)
                    jobs_created += 1
            
            except Exception as e:
                ingestion_job.failed_records += 1
        
        # Mark as completed
        ingestion_job.status = IngestionJob.Status.COMPLETED
        ingestion_job.completed_at = timezone.now()
        ingestion_job.created_records = jobs_created
        ingestion_job.save()
        
        # Update data source
        data_source.last_sync = timezone.now()
        data_source.last_sync_status = 'SUCCESS'
        data_source.save()
        
    except Exception as e:
        # Handle errors
        data_source.last_sync = timezone.now()
        data_source.last_sync_status = 'FAILED'
        data_source.save()
        
        if 'ingestion_job' in locals():
            ingestion_job.mark_failed(str(e))
        raise


def parse_api_item(item, field_mapping):
    """
    Parse API response item based on field mapping.
    Only includes fields that the API actually provides with real values.
    """
    job_data = {}

    # --- Normalizers / sanitizers to prevent misleading injected tokens ---
    valid_job_type_codes = {'FT', 'PT', 'CT', 'IN', 'RM', 'HY', 'FL'}
    valid_experience_level_codes = {'ENTRY', 'JUNIOR', 'MID', 'SENIOR', 'LEAD'}

    job_type_labels = {
        'full time', 'part time', 'contract', 'internship', 'remote', 'work from home', 'hybrid', 'freelance',
        'full-time', 'part-time'
    }

    def _clean_str(v):
        return str(v).strip()

    def normalize_job_type(raw):
        """
        Accept only job_type enum codes (FT/PT/CT/IN/RM/HY/FL).
        Ignore misleading labels like 'Full Time'.
        """
        s = _clean_str(raw)
        if not s:
            return None

        code = s.upper()
        if code in valid_job_type_codes:
            return code

        # Incoming might be a label; do not coerce to code to avoid wrong mappings.
        # (If admins want coercion, they can map API field directly to the enum codes.)
        if s.lower().strip() in job_type_labels:
            return None

        return None

    def normalize_experience_level(raw):
        """
        Accept only experience_level enum codes (ENTRY/JUNIOR/MID/SENIOR/LEAD).
        Ignore misleading labels like 'Experience(0 - 2 yrs)'.
        """
        s = _clean_str(raw)
        if not s:
            return None

        code = s.upper()
        if code in valid_experience_level_codes:
            return code

        # Common injected patterns, including: Experience(0 - 2 yrs)
        s_l = s.lower().replace(' ', '')
        if s_l.startswith('experience(') and 'yrs' in s_l:
            return None

        # Also ignore if it contains known range markers
        if '0-2' in s_l and 'yrs' in s_l:
            return None

        return None

    def normalize_country(raw):
        """
        Country is only allowed to be 'Malawi'. Anything else is ignored.
        """
        s = _clean_str(raw)
        if not s:
            return None
        if s.lower() == 'malawi':
            return 'Malawi'
        return None

    def normalize_city_or_district(raw):
        """
        City/district must not be polluted by job-type labels or experience range labels.
        Returns cleaned city/district string or None to ignore.
        """
        s = _clean_str(raw)
        if not s:
            return None

        s_norm = s.replace('\n', ' ').strip()
        s_lower = s_norm.lower().strip()

        # Hard ignore obvious injected labels
        if s_lower in job_type_labels:
            return None

        if s_lower.startswith('experience(') and 'yrs' in s_lower:
            return None

        if 'experience' in s_lower and 'yrs' in s_lower:
            return None

        # Guard against concatenated location strings (e.g., "USA, Malawi") being injected into city
        # Keep city text only if it's reasonably short and doesn't look like "Country, Malawi" injection.
        if len(s_norm) > 100:
            return None

        # If contains a clear country delimiter pattern and includes "Malawi", ignore.
        if ',' in s_norm and 'malawi' in s_lower:
            # If admins truly want "Lilongwe, Malawi", they should put it into location_display and/or city+country correctly.
            return None

        return s_norm

    def normalize_location_display(raw):
        """
        location_display should not contain injected job-type/experience labels.
        If it looks polluted, ignore and let JobVacancy.save() rebuild it.
        """
        s = _clean_str(raw)
        if not s:
            return None

        s_lower = s.lower().strip()

        # Reject if it contains known injected tokens
        if any(label in s_lower for label in job_type_labels):
            return None
        if 'experience(' in s_lower and 'yrs' in s_lower:
            return None
        if 'experience' in s_lower and 'yrs' in s_lower:
            return None

        # Keep it short enough for display; otherwise ignore.
        if len(s) > 255:
            return None

        return s

    for source_path, target_field in field_mapping.items():
        value = item
        for key in source_path.split('.'):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break

        # Skip None, empty strings, empty lists, and "Any" values
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        if str(value).strip() in ['Any', 'any', 'None', 'null', '']:
            continue

        # Handle tags/lists - convert to comma-separated string
        if isinstance(value, list):
            value = ', '.join([str(v) for v in value if str(v).strip()])

        # Apply field-specific normalization to prevent misleading injected labels
        if target_field == 'job_type':
            cleaned = normalize_job_type(value)
            if cleaned:
                job_data[target_field] = cleaned
            continue

        if target_field == 'experience_level':
            cleaned = normalize_experience_level(value)
            if cleaned:
                job_data[target_field] = cleaned
            continue

        if target_field == 'country':
            cleaned = normalize_country(value)
            if cleaned:
                job_data[target_field] = cleaned
            continue

        if target_field in ('city', 'district'):
            cleaned = normalize_city_or_district(value)
            if cleaned:
                job_data[target_field] = cleaned
            continue

        if target_field == 'location_display':
            cleaned = normalize_location_display(value)
            if cleaned:
                job_data[target_field] = cleaned
            continue

        # Default behavior for all other fields
        job_data[target_field] = value

    # Only set expiry date - the ONLY safe default
    if 'expiry_date' not in job_data:
        job_data['expiry_date'] = timezone.now().date() + timezone.timedelta(days=30)

    # DO NOT set defaults for anything else
    return job_data

