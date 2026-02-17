# Storage

The Upload API provides endpoints for managing file uploads in the AI Pipeline system. It supports different storage types for auditors and audit instigators with proper organization and security.

## Storage Management

The system implements a hierarchical storage structure to organize files based on their purpose and ownership:

### Storage Types

#### New Storage Structure (Current)

All audit-related data is now organized under the audit directory:

```
storage/
└── audits/
    └── audit_{audit_id}/
        ├── input/                              # Audit-level input files
        │   ├── metadata.csv
        │   └── audio_files.wav
        ├── results.csv                         # Results at audit root (no output folder)
        └── users/                              # User-specific evaluation data
            └── {user_id}/
                └── output_evaluation/
                    ├── input/                  # User uploaded files
                    │   ├── metadata.csv
                    │   └── test_audio.wav
                    └── output/                 # User generated outputs
                        └── output.csv
```

**Key Changes:**
- ✅ All user evaluation data is now under `audits/audit_{audit_id}/users/{user_id}/`
- ✅ No separate `output/` folder for audits - results stored in `results.csv` at audit root
- ✅ Better organization: all audit-related data in one place

#### Storage Locations

**User Output Evaluation Data:**
```
storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/input/
```

**Database Storage:**
- Table: `OutputEvaluationData`
- Field: `location` - stores the full path to the uploaded file
- Mapping: `MappingOutputEvaluationUser` - links output evaluation data to user audits

**Audit Input Data:**
```
storage/audits/audit_{audit_id}/input/
```

**Database Storage:**
- Input: `InputDatasetMetadata.location` - stores path to input directory

**Audit Results:**
```
storage/audits/audit_{audit_id}/results.csv
```

### File Naming Convention

All uploaded files are automatically renamed to prevent conflicts:
```
{original_filename_stem}_{unique_id}.{extension}
```

Example: `dataset.csv` becomes `dataset_a1b2c3d4.csv`

## Authentication

All endpoints require authentication. The current user is automatically determined from the authentication token.

## Supported File Types

The following file extensions are supported:
- `.csv` - Comma-separated values
- `.json` - JSON data files
- `.xlsx` - Excel spreadsheets
- `.txt` - Text files
- `.parquet` - Parquet data files
- `.pdf` - PDF documents (audit endpoints only)
- `.wav` - Audio files for SAM

## API Endpoints

### Dataset Upload Endpoints (User Evaluation Data)

#### Upload Single Dataset

**Endpoint**: `POST /api/v1/upload/dataset/{audit_id}/single`

Upload a single dataset file for output evaluation.

**Parameters**:
- `audit_id` (path, integer, required): The audit ID to associate the upload with
- `file` (form-data, file, required): The file to upload

**Storage Location**: `storage/audits/audit_{audit_id}/users/{user_id}/output_evaluation/input/`

**Request Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/upload/dataset/1/single" \
     -H "Authorization: Bearer {token}" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@dataset.csv"
```

**Response Example**:
```json
{
  "message": "Dataset uploaded successfully",
  "filename": "dataset_a1b2c3d4.csv",
  "original_filename": "dataset.csv",
  "file_size": 1024,
  "file_path": "storage/audits/audit_1/users/456/output_evaluation/input/dataset_a1b2c3d4.csv",
  "content_type": "text/csv",
  "storage_type": "output_evaluation"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid file type
- `404 Not Found`: User not associated with the audit
- `500 Internal Server Error`: Upload failed

---

#### Upload Multiple Datasets

**Endpoint**: `POST /api/v1/upload/dataset/{audit_id}/multiple`

Upload multiple dataset files simultaneously. If `metadata.csv` is included, it will automatically create underlying features from the headers.

**Parameters**:
- `audit_id` (path, integer, required): The audit ID to associate uploads with
- `files` (form-data, array of files, required): The files to upload

**Features**:
- Automatically extracts headers from `metadata.csv`
- Creates `UnderlyingFeatures` from column names
- Maps features to the dataset

**Request Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/upload/dataset/1/multiple" \
     -H "Authorization: Bearer {token}" \
     -H "Content-Type: multipart/form-data" \
     -F "files=@metadata.csv" \
     -F "files=@audio1.wav" \
     -F "files=@audio2.wav"
```

**Response Example**:
```json
{
  "message": "Processed 3 files",
  "uploaded_files": [
    {
      "filename": "metadata_a1b2c3d4.csv",
      "original_filename": "metadata.csv",
      "file_size": 1024,
      "status": "success (metadata only)"
    },
    {
      "filename": "audio1_x7y8z9w0.wav",
      "original_filename": "audio1.wav",
      "file_size": 2048,
      "status": "success"
    }
  ],
  "failed_files": [],
  "storage_type": "output_evaluation",
  "metadata_processed": true,
  "features_created": ["gender", "age"],
  "dataset_id": 5
}
```

---

#### List Uploaded Datasets

**Endpoint**: `GET /api/v1/upload/dataset/{audit_id}`

Retrieve a list of all datasets uploaded by the current user for a specific audit.

**Parameters**:
- `audit_id` (path, integer, required): The audit ID to list files for

**Request Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/upload/dataset/1" \
     -H "Authorization: Bearer {token}"
```

**Response Example**:
```json
{
  "uploaded_files": [
    {
      "id": 1,
      "filename": "dataset_a1b2c3d4.csv",
      "file_size": 1024,
      "upload_time": 1640995200,
      "file_path": "storage/audits/audit_1/users/456/output_evaluation/input/dataset_a1b2c3d4.csv"
    }
  ],
  "total_files": 1,
  "audit_id": 1,
  "storage_type": "output_evaluation"
}
```

---

#### Delete Dataset File

**Endpoint**: `DELETE /api/v1/upload/dataset/{audit_id}`

Delete an uploaded dataset file for a specific audit and user.

**Parameters**:
- `audit_id` (path, integer, required): The audit ID

**Request Body**:
```json
{
  "filename": "dataset_a1b2c3d4.csv"
}
```

**Request Example**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/upload/dataset/1" \
     -H "Authorization: Bearer {token}" \
     -H "Content-Type: application/json" \
     -d '{"filename": "dataset_a1b2c3d4.csv"}'
```

**Response Example**:
```json
{
  "message": "File deleted successfully",
  "filename": "dataset_a1b2c3d4.csv",
  "audit_id": 1
}
```

**Error Responses**:
- `404 Not Found`: User not associated with audit or file not found
- `500 Internal Server Error`: Deletion failed

---

### Audit Data Upload Endpoints

#### Upload Audit Input Data

**Endpoint**: `POST /api/v1/upload/audit/{audit_id}/input`

Upload input data for an audit (used by audit instigators).

**Parameters**:
- `audit_id` (path, integer, required): The audit ID
- `file` (form-data, file, required): The input file to upload

**Storage Location**: `storage/audits/audit_{audit_id}/input/`

**Request Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/upload/audit/1/input" \
     -H "Authorization: Bearer {token}" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@requirements.pdf"
```

**Response Example**:
```json
{
  "message": "Audit input data uploaded successfully",
  "filename": "requirements_x1y2z3w4.pdf",
  "original_filename": "requirements.pdf",
  "file_size": 2048,
  "file_path": "storage/audits/audit_1/input/requirements_x1y2z3w4.pdf",
  "content_type": "application/pdf",
  "storage_type": "audit_input"
}
```

---

#### List Audit Files

**Endpoint**: `GET /api/v1/upload/audit/{audit_id}/files`

List all files for a specific audit (input files and results.csv if it exists).

**Parameters**:
- `audit_id` (path, integer, required): The audit ID

**Request Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/upload/audit/1/files" \
     -H "Authorization: Bearer {token}"
```

**Response Example**:
```json
{
  "files": [
    {
      "filename": "metadata.csv",
      "file_size": 2048,
      "upload_time": 1640995200,
      "file_path": "storage/audits/audit_1/input/metadata.csv"
    },
    {
      "filename": "results.csv",
      "file_size": 4096,
      "upload_time": 1640995300,
      "file_path": "storage/audits/audit_1/results.csv"
    }
  ],
  "total_files": 2,
  "audit_id": 1,
  "storage_type": "audit_input"
}
```

---

#### View/Download Audit File

**Endpoint**: `GET /api/v1/upload/audit/{audit_id}/view/{filename}`

View or download audit input files or results.csv.

**Parameters**:
- `audit_id` (path, integer, required): The audit ID
- `filename` (path, string, required): The filename to view (e.g., "results.csv", "metadata.csv")

**Special Handling**:
- If `filename` is "results.csv", looks in audit root: `storage/audits/audit_{audit_id}/results.csv`
- Otherwise, looks in input folder: `storage/audits/audit_{audit_id}/input/{filename}`

**Request Example**:
```bash
# View results.csv
curl -X GET "http://localhost:8000/api/v1/upload/audit/1/view/results.csv" \
     -H "Authorization: Bearer {token}" \
     --output results.csv

# View input file
curl -X GET "http://localhost:8000/api/v1/upload/audit/1/view/metadata.csv" \
     -H "Authorization: Bearer {token}" \
     --output metadata.csv
```

**Response**: File content with appropriate headers for viewing/downloading

---

## Error Handling

### Common Error Codes

| Status Code | Description | Common Causes |
|-------------|-------------|---------------|
| 400 | Bad Request | Invalid file type, missing parameters |
| 401 | Unauthorized | Missing or invalid authentication token |
| 403 | Forbidden | User not authorized to access this audit |
| 404 | Not Found | User not associated with audit, file not found |
| 500 | Internal Server Error | Database errors, file system errors |

### Error Response Format

```json
{
  "detail": "Error description here"
}
```

## Usage Examples

### Python Client Example

```python
import requests

# Upload single dataset
def upload_dataset(audit_id: int, file_path: str, token: str):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(
            f'http://localhost:8000/api/v1/upload/dataset/{audit_id}/single',
            files=files,
            headers=headers
        )
    return response.json()

# List uploaded datasets
def list_datasets(audit_id: int, token: str):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(
        f'http://localhost:8000/api/v1/upload/dataset/{audit_id}',
        headers=headers
    )
    return response.json()

# Download file
def download_file(audit_id: int, filename: str, token: str):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(
        f'http://localhost:8000/api/v1/upload/dataset/{audit_id}/view/{filename}',
        headers=headers
    )
    with open(filename, 'wb') as f:
        f.write(response.content)
```

### JavaScript Client Example

```javascript
// Upload single file
async function uploadDataset(auditId, file, token) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`/api/v1/upload/dataset/${auditId}/single`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        },
        body: formData
    });

    return await response.json();
}

// List files
async function listDatasets(auditId, token) {
    const response = await fetch(`/api/v1/upload/dataset/${auditId}`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    return await response.json();
}

// Download file
async function downloadFile(auditId, filename, token) {
    const response = await fetch(
        `/api/v1/upload/dataset/${auditId}/view/${filename}`,
        {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        }
    );

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}
```

### React Component Example

```jsx
import { useState } from 'react';

function FileUploadManager({ auditId, token }) {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);

  const uploadFile = async (file) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(
        `http://localhost:8000/api/v1/upload/dataset/${auditId}/single`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        }
      );

      const data = await response.json();
      alert(data.message);
      loadFiles(); // Refresh file list
    } catch (error) {
      alert('Upload failed: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  const loadFiles = async () => {
    const response = await fetch(
      `http://localhost:8000/api/v1/upload/dataset/${auditId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    const data = await response.json();
    setFiles(data.uploaded_files);
  };

  const downloadFile = async (filename) => {
    const response = await fetch(
      `http://localhost:8000/api/v1/upload/dataset/${auditId}/view/${filename}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
  };

  return (
    <div>
      <input
        type="file"
        onChange={(e) => uploadFile(e.target.files[0])}
        disabled={uploading}
      />
      <button onClick={loadFiles}>Refresh Files</button>

      <ul>
        {files.map((file) => (
          <li key={file.id}>
            {file.filename}
            <button onClick={() => downloadFile(file.filename)}>
              Download
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## Best Practices

### File Management

1. **File Size Limits**: Consider implementing file size limits based on your infrastructure
2. **Virus Scanning**: Implement virus scanning for uploaded files in production
3. **Backup Strategy**: Ensure uploaded files are included in your backup strategy
4. **Cleanup**: Implement cleanup procedures for old or orphaned files

### Security Considerations

1. **Authentication**: Always verify user authentication and authorization
2. **File Validation**: Validate file types and content beyond just extensions
3. **Path Traversal**: The system prevents path traversal attacks by using safe filename generation and path validation
4. **Storage Permissions**: Ensure proper file system permissions on storage directories
5. **User Isolation**: Users can only access their own uploaded files

### Performance Optimization

1. **Asynchronous Processing**: Consider async file processing for large files
2. **Progress Tracking**: Implement upload progress tracking for better UX
3. **Compression**: Consider file compression for storage efficiency
4. **CDN Integration**: Use CDN for file serving in production environments

## Database Schema

The upload system integrates with the following database tables:

- `OutputEvaluationData`: Stores file location information for user uploads
- `MappingOutputEvaluationUser`: Links users to their uploaded evaluation data
- `MappingAuditUser`: Associates users with audits
- `InputDatasetMetadata`: Stores audit input dataset locations
- `DatasetMetadata`: Main dataset information
- `UnderlyingFeatures`: Feature definitions extracted from metadata
- `MappingDatasetFeatures`: Links features to datasets

Ensure these tables exist and have proper relationships before using the upload endpoints.

## Migration from Old Structure

If you have data in the old storage structure (`storage/users/{user_id}/output_evaluation/`), run the migration script:

```bash
python scripts/migrations/datasset.py
```

This will:
- Create the new directory structure
- Migrate existing files to the new locations
- Update database records
- Create underlying features from metadata.csv
