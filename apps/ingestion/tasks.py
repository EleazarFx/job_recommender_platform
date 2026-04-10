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
    Prepare job data from CSV row.
    Handles data cleaning and normalization.
    """
    # Parse expiry date
    expiry_date = row.get('expiry_date')
    if pd.isna(expiry_date) or not expiry_date:
        expiry_date = timezone.now().date() + timezone.timedelta(days=30)
    elif isinstance(expiry_date, str):
        try:
            expiry_date = pd.to_datetime(expiry_date).date()
        except:
            expiry_date = timezone.now().date() + timezone.timedelta(days=30)
    
    # Clean skills
    skills = row.get('required_skills', '')
    if pd.isna(skills):
        skills = ''
    
    # Map job type
    job_type_map = {
        'full time': 'FT', 'full-time': 'FT', 'permanent': 'FT',
        'part time': 'PT', 'part-time': 'PT',
        'contract': 'CT', 'temporary': 'CT',
        'internship': 'IN', 'intern': 'IN',
        'remote': 'RM', 'work from home': 'RM',
        'hybrid': 'HY',
        'freelance': 'FL'
    }
    
    job_type_str = str(row.get('job_type', '')).lower().strip()
    job_type = job_type_map.get(job_type_str, 'FT')
    
    # Map experience level
    exp_map = {
        'entry': 'ENTRY', 'junior': 'JUNIOR', 'mid': 'MID',
        'senior': 'SENIOR', 'lead': 'LEAD'
    }
    exp_str = str(row.get('experience_level', '')).lower().strip()
    experience_level = exp_map.get(exp_str, 'ENTRY')
    
    return {
        'title': str(row.get('title', 'Untitled Position')),
        'company_name': str(row.get('company_name', 'Unknown Company')),
        'description': str(row.get('description', '')),
        'required_skills': skills,
        'experience_level': experience_level,
        'job_type': job_type,
        'city': str(row.get('city', row.get('location', ''))),
        'location_display': str(row.get('location_display', row.get('location', ''))),
        'expiry_date': expiry_date,
        'source_type': JobVacancy.SourceType.ADMIN_CSV,
        'trust_score': trust_score,
        'is_approved': auto_approve,
        'application_url': str(row.get('application_url', '')) if not pd.isna(row.get('application_url')) else None,
        'application_email': str(row.get('application_email', '')) if not pd.isna(row.get('application_email')) else None,
        'years_of_experience_required': int(row.get('years_of_experience_required', 0)) if not pd.isna(row.get('years_of_experience_required', 0)) else 0,
    }


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
    """Parse API response item based on field mapping."""
    job_data = {}
    
    for target_field, source_path in field_mapping.items():
        # Handle nested paths like "company.name"
        value = item
        for key in source_path.split('.'):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                value = None
                break
        
        if value is not None:
            job_data[target_field] = value
    
    # Set defaults for missing fields
    if 'expiry_date' not in job_data:
        job_data['expiry_date'] = timezone.now().date() + timezone.timedelta(days=30)
    
    return job_data