import pandas as pd
import json
import requests
from typing import Dict, Any, List, Union, Optional, Tuple
from pathlib import Path
import numpy as np
import os
import glob
import uuid
import re
from datetime import datetime
from sqlmodel import Session, select

class StorageManager:
    """Manages the storage structure for evaluation data."""

    def __init__(self, base_storage_path: str = "storage"):
        self.base_path = Path(base_storage_path)
        self.users_path = self.base_path / "users"
        self.audits_path = self.base_path / "audits"

    def get_user_output_path(self, user_id: str, audit_id: str = None) -> Path:
        """
        Get user's output evaluation input directory.
        New structure: storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/input
        """
        if audit_id:
            return self.audits_path / f"audit_{audit_id}" / "users" / user_id / "output_evaluation" / "input"
        # Fallback for cases without audit_id (shouldn't normally happen)
        return self.users_path / user_id / "output_evaluation" / "input"

    def get_user_output_evaluation_path(self, user_id: str, audit_id: str) -> Path:
        """
        Get user's output evaluation output directory for a specific audit.
        New structure: storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/output
        """
        return self.audits_path / f"audit_{audit_id}" / "users" / user_id / "output_evaluation" / "output"

    def get_audit_input_path(self, audit_id: str) -> Path:
        """
        Get audit input directory.
        New structure: storage/audits/audit_{audit_id}/input
        """
        return self.audits_path / f"audit_{audit_id}" / "input"

    def get_audit_results_path(self, audit_id: str) -> Path:
        """
        Get audit results.csv path (no output folder, results at audit root).
        New structure: storage/audits/audit_{audit_id}/results.csv
        """
        return self.audits_path / f"audit_{audit_id}" / "results.csv"
    
    def generate_output_filename(self, dataset_name: str, file_extension: str = "csv") -> str:
        """Generate a unique output filename with hash."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_hash = str(uuid.uuid4())[:8]
        return f"{dataset_name}_{timestamp}_{unique_hash}.{file_extension}"
    
    def discover_files_in_path(self, path: Path, file_patterns: List[str] = None) -> List[Dict[str, Any]]:
        """Discover files in a given path with optional patterns."""
        if not path.exists():
            return []
        
        if file_patterns is None:
            file_patterns = ["*.csv", "*.json", "*.xlsx", "*.txt", "*.wav", "*.mp3", "*.pdf", "*.docx", "*.html"]
        
        discovered_files = []
        
        for pattern in file_patterns:
            for file_path in path.glob(pattern):
                file_info = self._analyse_file(file_path)
                discovered_files.append(file_info)
        
        return discovered_files
    
    def _analyse_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyse a file and extract metadata."""
        file_info = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix.lower(),
            'file_size': file_path.stat().st_size if file_path.exists() else 0,
            'created_time': datetime.fromtimestamp(file_path.stat().st_ctime) if file_path.exists() else None,
            'file_type': self._determine_file_type(file_path),
            'data': None,
            'metadata': {}
        }
        
        # Extract hash/ID from filename if present
        filename_parts = file_path.stem.split('_')
        if len(filename_parts) > 1:
            file_info['metadata']['extracted_id'] = filename_parts[-1]
            file_info['metadata']['base_name'] = '_'.join(filename_parts[:-1])
        
        return file_info
    
    def _determine_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension."""
        extension = file_path.suffix.lower()
        
        type_mapping = {
            '.csv': 'structured_data',
            '.json': 'structured_data',
            '.xlsx': 'structured_data',
            '.xls': 'structured_data',
            '.txt': 'text',
            '.html': 'text',
            '.htm': 'text',
            '.xml': 'text',
            '.md': 'text',
            '.wav': 'audio',
            '.mp3': 'audio',
            '.mp4': 'audio',
            '.m4a': 'audio',
            '.flac': 'audio',
            '.pdf': 'document',
            '.docx': 'document',
            '.doc': 'document'
        }
        
        return type_mapping.get(extension, 'unknown')


class InputFileMetadataManager:
    """Manages metadata labels for input files like race, gender, age, etc."""

    def __init__(self, base_storage_path: str = "storage"):
        self.base_path = Path(base_storage_path)
        self.users_path = self.base_path / "users"
        self.audits_path = self.base_path / "audits"
        self.metadata_sources = {
            'filename_patterns': [],
            'metadata_files': [],
            'directory_structure': [],
            'external_mappings': {},
            'storage_service_config': None
        }

    def get_user_output_path(self, user_id: str, audit_id: str = None) -> Path:
        """
        Get user's output evaluation input directory.
        New structure: storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/input
        """
        if audit_id:
            return self.audits_path / f"audit_{audit_id}" / "users" / user_id / "output_evaluation" / "input"
        # Fallback for cases without audit_id (shouldn't normally happen)
        return self.users_path / user_id / "output_evaluation" / "input"

    def get_user_output_evaluation_path(self, user_id: str, audit_id: str) -> Path:
        """
        Get user's output evaluation output directory for a specific audit.
        New structure: storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/output
        """
        return self.users_path / "users" / user_id / "output_evaluation" /  f"audit_{audit_id}" / "output"

    def get_audit_input_path(self, audit_id: str) -> Path:
        """
        Get audit input directory.
        New structure: storage/audits/audit_{audit_id}/input
        """
        return self.audits_path / f"audit_{audit_id}" / "input"

    def get_audit_results_path(self, audit_id: str) -> Path:
        """
        Get audit results.csv path (no output folder, results at audit root).
        New structure: storage/audits/audit_{audit_id}/results.csv
        """
        return self.audits_path / f"audit_{audit_id}" / "results.csv"
    
    def configure_storage_service(self, storage_service_config: Dict[str, Any]):
        """Configure external storage service for metadata."""
        self.metadata_sources['storage_service_config'] = storage_service_config
    
    def add_filename_pattern(self, pattern: str, metadata_fields: Dict[str, str]):
        """Add a filename pattern to extract metadata."""
        self.metadata_sources['filename_patterns'].append({
            'pattern': re.compile(pattern),
            'fields': metadata_fields
        })
    
    def add_metadata_file(self, file_path: str, file_type: str = 'csv', 
                         key_column: str = 'file_name', metadata_columns: List[str] = None):
        """Add a metadata file that maps files to their metadata."""
        self.metadata_sources['metadata_files'].append({
            'file_path': file_path,
            'file_type': file_type,
            'key_column': key_column,
            'metadata_columns': metadata_columns
        })
    
    def add_directory_structure_mapping(self, pattern: str, metadata_fields: Dict[str, str]):
        """Add directory structure pattern to extract metadata."""
        self.metadata_sources['directory_structure'].append({
            'pattern': re.compile(pattern),
            'fields': metadata_fields
        })
    
    def add_external_mapping(self, mapping_dict: Dict[str, Dict[str, Any]]):
        """Add external mapping of file identifiers to metadata."""
        self.metadata_sources['external_mappings'].update(mapping_dict)
    
    def fetch_metadata_from_storage_service(self, file_identifier: str) -> Dict[str, Any]:
        """Fetch metadata from external storage service."""
        config = self.metadata_sources['storage_service_config']
        if not config:
            return {}
        
        try:
            if config['service_type'] == 'api':
                return self._fetch_from_api(file_identifier, config)
        except Exception as e:
            print(f"Warning: Could not fetch metadata from storage service: {e}")
        
        return {}
    
    def _fetch_from_api(self, file_identifier: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch metadata from API service."""
        base_url = config['base_url']
        endpoint = config['endpoints']['get_file_metadata'].format(file_id=file_identifier)
        
        headers = {}
        if 'auth_token' in config:
            headers['Authorization'] = f"Bearer {config['auth_token']}"
        
        response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json().get('metadata', {})
    
    def extract_metadata_from_filename(self, file_name: str) -> Dict[str, Any]:
        """Extract metadata from filename using patterns."""
        metadata = {}
        
        for pattern_info in self.metadata_sources['filename_patterns']:
            match = pattern_info['pattern'].match(file_name)
            if match:
                for group_name, field_name in pattern_info['fields'].items():
                    if group_name in match.groupdict():
                        value = match.group(group_name)
                        # Try to convert to appropriate type
                        try:
                            metadata[field_name] = int(value)
                        except ValueError:
                            try:
                                metadata[field_name] = float(value)
                            except ValueError:
                                # Clean up gender/race values
                                if field_name == 'gender':
                                    metadata[field_name] = 'Female' if value.upper() in ['F', 'FEMALE'] else 'Male'
                                else:
                                    metadata[field_name] = value
                break
        
        return metadata
    
    def extract_metadata_from_path(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from file path using directory structure patterns."""
        metadata = {}
        
        for structure_info in self.metadata_sources['directory_structure']:
            match = structure_info['pattern'].search(file_path)
            if match:
                for group_name, field_name in structure_info['fields'].items():
                    if group_name in match.groupdict():
                        metadata[field_name] = match.group(group_name)
                break
        
        return metadata
    
    def load_metadata_files(self) -> Dict[str, Dict[str, Any]]:
        """Load all metadata files and return combined mapping."""
        combined_mapping = {}
        
        for metadata_file in self.metadata_sources['metadata_files']:
            file_path = metadata_file['file_path']
            file_type = metadata_file['file_type']
            key_column = metadata_file['key_column']
            metadata_columns = metadata_file['metadata_columns']
            
            try:
                if file_type == 'csv':
                    df = pd.read_csv(file_path)
                elif file_type == 'excel':
                    df = pd.read_excel(file_path)
                elif file_type == 'json':
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    df = pd.DataFrame(data)
                else:
                    continue
                
                for _, row in df.iterrows():
                    file_key = row[key_column]
                    file_metadata = {}
                    
                    columns_to_extract = metadata_columns if metadata_columns else [
                        col for col in df.columns if col != key_column
                    ]
                    
                    for col in columns_to_extract:
                        if col in row and pd.notna(row[col]):
                            file_metadata[col] = row[col]
                    
                    combined_mapping[file_key] = file_metadata
                    
            except Exception as e:
                print(f"Warning: Could not load metadata file {file_path}: {e}")
        
        return combined_mapping
    
    def get_file_metadata(self, file_path: str, file_name: str) -> Dict[str, Any]:
        """Get complete metadata for a file from all sources."""
        metadata = {}

        # 1. Extract from filename patterns
        filename_metadata = self.extract_metadata_from_filename(file_name)
        metadata.update(filename_metadata)

        # 2. Extract from directory structure
        path_metadata = self.extract_metadata_from_path(file_path)
        metadata.update(path_metadata)

        # 3. Load from metadata files
        file_mappings = self.load_metadata_files()
        # Try exact match first
        if file_name in file_mappings:
            metadata.update(file_mappings[file_name])
        else:
            # Try matching by base name (without extension)
            # e.g., example_1.html matches example_1.txt in metadata
            base_name = Path(file_name).stem
            for mapped_name, mapped_metadata in file_mappings.items():
                mapped_base_name = Path(mapped_name).stem
                if base_name == mapped_base_name:
                    metadata.update(mapped_metadata)
                    break

        # 4. Check external mappings
        if file_name in self.metadata_sources['external_mappings']:
            metadata.update(self.metadata_sources['external_mappings'][file_name])

        # 5. Fetch from storage service
        storage_metadata = self.fetch_metadata_from_storage_service(file_name)
        metadata.update(storage_metadata)

        return metadata


# ========================================
# INTEGRATION FUNCTIONS
# ========================================

def parse_storage_location(location: str, storage_manager: StorageManager) -> Tuple[str, Dict[str, Any]]:
    """Parse storage location and return actual path with metadata."""
    location_info = {
        'location_type': 'absolute',
        'user_id': None,
        'audit_id': None,
        'subdirectory': None
    }

    if location.startswith("user:"):
        parts = location.replace("user:", "").split("/")
        user_id = parts[0]
        audit_id = parts[1] if len(parts) > 1 else None
        subdirectory = parts[2] if len(parts) > 2 else "input"

        # New format: user:user_id/audit_id/input or user:user_id/audit_id/output
        # Maps to: storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/input
        if audit_id and subdirectory in ["input", "output"]:
            if subdirectory == "input":
                actual_path = str(storage_manager.get_user_output_path(user_id, audit_id))
            else:
                actual_path = str(storage_manager.get_user_output_evaluation_path(user_id, audit_id))

            location_info.update({
                'location_type': 'user',
                'user_id': user_id,
                'audit_id': audit_id,
                'subdirectory': subdirectory
            })
        else:
            # Fallback for old format (should be rare)
            if len(parts) == 1:
                subdirectory = "output_evaluation/input"
            else:
                subdirectory = "/".join(parts[1:])

            actual_path = str(storage_manager.users_path / user_id / subdirectory)

            location_info.update({
                'location_type': 'user',
                'user_id': user_id,
                'subdirectory': subdirectory
            })

    elif location.startswith("audit:"):
        parts = location.replace("audit:", "").split("/")
        audit_id = parts[0]
        subdirectory = parts[1] if len(parts) > 1 else "input"

        # New structure: storage/audits/audit_{audit_id}/input
        # Results at: storage/audits/audit_{audit_id}/results.csv (no output folder)
        if subdirectory == "input":
            actual_path = str(storage_manager.get_audit_input_path(audit_id))
        elif subdirectory == "output":
            # For results.csv access
            actual_path = str(storage_manager.get_audit_results_path(audit_id))
        else:
            # Custom subdirectory
            actual_path = str(storage_manager.audits_path / f"audit_{audit_id}" / subdirectory)

        location_info.update({
            'location_type': 'audit',
            'audit_id': audit_id,
            'subdirectory': subdirectory
        })

    else:
        actual_path = location

    return actual_path, location_info


def apply_datatypes_to_df(df: pd.DataFrame, datatypes_info: Dict[str, Any]) -> pd.DataFrame:
    """Apply datatypes to DataFrame based on metadata."""
    if not datatypes_info:
        return df
    
    df_copy = df.copy()
    
    for col, type_str in datatypes_info.items():
        if col in df_copy.columns:
            try:
                if type_str.lower() in ['int', 'integer']:
                    df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce').astype('Int64')
                elif type_str.lower() in ['float', 'double']:
                    df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                elif type_str.lower() in ['bool', 'boolean']:
                    df_copy[col] = df_copy[col].astype(bool)
                elif type_str.lower() in ['datetime', 'timestamp']:
                    df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
                elif type_str.lower() in ['json', 'dict']:
                    def parse_json_safe(x):
                        if isinstance(x, str):
                            try:
                                return json.loads(x)
                            except:
                                return x
                        return x
                    df_copy[col] = df_copy[col].apply(parse_json_safe)
                else:
                    df_copy[col] = df_copy[col].astype(str)
            except Exception as e:
                print(f"Warning: Could not convert column {col} to {type_str}: {e}")
    
    return df_copy


def load_structured_data_file(file_info: Dict[str, Any], datatypes_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load structured data files and return list of data entries."""
    file_path = Path(file_info['file_path'])
    file_extension = file_info['file_extension']
    entries = []
    
    try:
        if file_extension == '.csv':
            df = pd.read_csv(file_path)
            df = apply_datatypes_to_df(df, datatypes_info)
            
            for idx, row in df.iterrows():
                entry = file_info.copy()
                entry['data'] = row.to_dict()
                entry['metadata'].update({
                    'row_number': idx + 1,
                    'total_rows': len(df),
                    'source_file': file_path.name
                })
                entries.append(entry)
        
        elif file_extension == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            if isinstance(json_data, list):
                for i, item in enumerate(json_data):
                    entry = file_info.copy()
                    entry['data'] = item
                    entry['metadata'].update({
                        'entry_number': i + 1,
                        'total_entries': len(json_data),
                        'source_file': file_path.name
                    })
                    entries.append(entry)
            else:
                entry = file_info.copy()
                entry['data'] = json_data
                entry['metadata'].update({
                    'entry_number': 1,
                    'total_entries': 1,
                    'source_file': file_path.name
                })
                entries.append(entry)
        
        elif file_extension in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
            df = apply_datatypes_to_df(df, datatypes_info)
            
            for idx, row in df.iterrows():
                entry = file_info.copy()
                entry['data'] = row.to_dict()
                entry['metadata'].update({
                    'row_number': idx + 1,
                    'total_rows': len(df),
                    'source_file': file_path.name
                })
                entries.append(entry)
    
    except Exception as e:
        error_entry = file_info.copy()
        error_entry['metadata']['error'] = str(e)
        entries.append(error_entry)
    
    return entries


def load_text_file(file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load text files - returns entire file content as a single entry (not split by lines)."""
    file_path = Path(file_info['file_path'])
    entries = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Return the entire file content as a single entry
        # This is important for documents like Annif text files where the full text should be analyzed
        entry = file_info.copy()
        entry['data'] = {
            'text': content.strip(),
            'prompt': content.strip(),
            'content': content.strip()
        }
        entry['metadata'].update({
            'total_lines': len(content.split('\n')),
            'source_file': file_path.name,
            'character_count': len(content),
            'word_count': len(content.split())
        })
        entries.append(entry)

    except Exception as e:
        error_entry = file_info.copy()
        error_entry['metadata']['error'] = str(e)
        entries.append(error_entry)
    
    return entries


def enhance_file_info_with_metadata(file_info: Dict[str, Any], 
                                  metadata_manager: InputFileMetadataManager) -> Dict[str, Any]:
    """
    *** INTEGRATION POINT ***
    This function enhances your existing file_info with metadata labels.
    """
    file_path = file_info['file_path']
    file_name = file_info['file_name']
    
    # Get metadata from all sources
    file_metadata = metadata_manager.get_file_metadata(file_path, file_name)
    
    # Add to existing metadata
    if 'metadata' not in file_info:
        file_info['metadata'] = {}
    
    file_info['metadata'].update(file_metadata)
    
    # Also add as direct fields for easier access
    for key, value in file_metadata.items():
        file_info[f'label_{key}'] = value
    
    return file_info


def discover_input_data_with_metadata(location: str, datatypes_info: Dict[str, Any],
                                    storage_manager: StorageManager,
                                    metadata_manager: InputFileMetadataManager) -> List[Dict[str, Any]]:
    """
    *** MAIN INTEGRATION FUNCTION ***
    Enhanced version of your discover_input_data function that includes metadata.
    """
    actual_path, location_info = parse_storage_location(location, storage_manager)
    path = Path(actual_path)

    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {actual_path}")
    
    all_entries = []
    
    if path.is_file():
        # Single file
        file_info = storage_manager._analyse_file(path)
        file_info['metadata'].update(location_info)
        
        # *** METADATA ENHANCEMENT ***
        file_info = enhance_file_info_with_metadata(file_info, metadata_manager)
        
        if file_info['file_type'] == 'structured_data':
            entries = load_structured_data_file(file_info, datatypes_info)
        elif file_info['file_type'] == 'text':
            entries = load_text_file(file_info)
        else:
            entries = [file_info]
        
        all_entries.extend(entries)
    
    elif path.is_dir():
        # Directory with multiple files
        discovered_files = storage_manager.discover_files_in_path(path)

        for file_info in discovered_files:
            # Skip metadata.csv files - they are used for enrichment only, not as input data
            if file_info['file_name'].lower() == 'metadata.csv':
                continue

            file_info['metadata'].update(location_info)

            # *** METADATA ENHANCEMENT ***
            file_info = enhance_file_info_with_metadata(file_info, metadata_manager)

            if file_info['file_type'] == 'structured_data':
                entries = load_structured_data_file(file_info, datatypes_info)
            elif file_info['file_type'] == 'text':
                entries = load_text_file(file_info)
            else:
                entries = [file_info]

            all_entries.extend(entries)
    
    return all_entries


def save_output_data(output_df: pd.DataFrame, location: str, storage_manager: StorageManager, dataset_name: str = "evaluation"):
    """Save output data to the specified storage location."""
    actual_path, _ = parse_storage_location(location, storage_manager)

    # Check if location is a directory path (no file extension) or doesn't end with a valid extension
    path_obj = Path(actual_path)
    has_extension = path_obj.suffix.lower() in ['.csv', '.json', '.xlsx', '.parquet']

    if not has_extension:
        # Location is a directory - add output.csv filename
        file_extension = 'csv'
        if len(output_df) > 10000:
            file_extension = 'parquet'

        # Use simple "output.csv" filename for consistency
        filename = f"output.{file_extension}"
        actual_path = str(path_obj / filename)

    output_path = Path(actual_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    file_extension = output_path.suffix.lower()

    if file_extension == '.csv':
        output_df.to_csv(actual_path, index=False)
    elif file_extension == '.json':
        output_df.to_json(actual_path, orient='records', indent=2)
    elif file_extension in ['.xlsx', '.xls']:
        output_df.to_excel(actual_path, index=False)
    elif file_extension == '.parquet':
        output_df.to_parquet(actual_path, index=False)
    else:
        actual_path = str(output_path.with_suffix('.csv'))
        output_df.to_csv(actual_path, index=False)

    return actual_path