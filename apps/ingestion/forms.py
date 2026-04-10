"""
Forms for data ingestion from Admin Dashboard.
"""
from django import forms
from .models import DataSource, IngestionJob
import json


class DataSourceForm(forms.ModelForm):
    """Form for creating/editing data sources."""
    
    field_mapping_display = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control',
            'placeholder': '{\n  "Job Title": "title",\n  "Company": "company_name",\n  "Skills": "required_skills"\n}'
        }),
        help_text="JSON mapping of source fields to model fields"
    )
    
    class Meta:
        model = DataSource
        fields = [
            'name', 'source_type', 'url', 'api_key', 'api_secret',
            'auth_type', 'sync_frequency', 'is_active',
            'default_trust_score', 'auto_approve'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control'}),
            'api_secret': forms.PasswordInput(attrs={'class': 'form-control'}),
            'auth_type': forms.Select(attrs={'class': 'form-select'}),
            'sync_frequency': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_trust_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'auto_approve': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_field_mapping_display(self):
        """Validate JSON format."""
        mapping_str = self.cleaned_data.get('field_mapping_display')
        if not mapping_str:
            return {}
        
        try:
            mapping = json.loads(mapping_str)
            if not isinstance(mapping, dict):
                raise forms.ValidationError('Mapping must be a JSON object')
            return mapping
        except json.JSONDecodeError:
            raise forms.ValidationError('Invalid JSON format')
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.field_mapping = self.cleaned_data.get('field_mapping_display', {})
        if commit:
            instance.save()
        return instance


class CSVUploadForm(forms.ModelForm):
    """Form for manual CSV file upload with column mapping."""
    
    column_mapping = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 8,
            'class': 'form-control',
            'placeholder': '{\n  "Job Title": "title",\n  "Company Name": "company_name",\n  "Required Skills": "required_skills",\n  "Location": "city",\n  "Job Type": "job_type",\n  "Experience": "experience_level",\n  "Description": "description",\n  "Expiry Date": "expiry_date"\n}'
        }),
        help_text="Map CSV column names to database fields (JSON format)"
    )
    
    class Meta:
        model = IngestionJob
        fields = ['uploaded_file']
        widgets = {
            'uploaded_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv'
            })
        }
    
    def clean_column_mapping(self):
        """Validate column mapping JSON."""
        mapping_str = self.cleaned_data.get('column_mapping')
        if not mapping_str:
            raise forms.ValidationError('Column mapping is required')
        
        try:
            mapping = json.loads(mapping_str)
            
            # Required fields
            required = ['title', 'company_name']
            mapped_values = list(mapping.values())
            
            for field in required:
                if field not in mapped_values:
                    raise forms.ValidationError(f"'{field}' must be mapped to a CSV column")
            
            return mapping
            
        except json.JSONDecodeError:
            raise forms.ValidationError('Invalid JSON format')


class CSVColumnPreviewForm(forms.Form):
    """
    Form to preview CSV columns and allow mapping.
    Used in the two-step upload process.
    """
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )