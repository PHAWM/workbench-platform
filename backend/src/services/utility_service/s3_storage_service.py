import io
import json
import uuid
import fnmatch
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import boto3
import pandas as pd
from botocore.exceptions import ClientError


class S3StorageManager:
    """S3-compatible storage manager (works with RustFS, MinIO, AWS S3).

    Drop-in replacement for StorageManager — same interface, backed by S3.
    Path mapping: local `storage/audits/audit_5/input/` becomes S3 key `audits/audit_5/input/`.
    """

    def __init__(self, endpoint_url: str, access_key: str, secret_key: str,
                 bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Create the bucket if it doesn't exist. Ignore 403 (bucket exists, access restricted)."""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("403", "Forbidden"):
                # Bucket exists but we lack HeadBucket permission — that's fine
                return
            # Any other error (404 / NoSuchBucket) — try to create
            try:
                self.s3.create_bucket(Bucket=self.bucket_name)
            except ClientError as ce:
                create_code = ce.response["Error"]["Code"]
                if create_code not in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
                    raise

    # ------------------------------------------------------------------
    # Path helpers (return S3 key prefixes instead of Path objects)
    # ------------------------------------------------------------------

    def get_user_output_path(self, user_id: str, audit_id: str = None) -> str:
        if audit_id:
            return f"audits/audit_{audit_id}/users/{user_id}/output_evaluation/input/"
        return f"users/{user_id}/output_evaluation/input/"

    def get_user_output_evaluation_path(self, user_id: str, audit_id: str) -> str:
        return f"audits/audit_{audit_id}/users/{user_id}/output_evaluation/output/"

    def get_audit_input_path(self, audit_id: str) -> str:
        return f"audits/audit_{audit_id}/input/"

    def get_audit_results_path(self, audit_id: str) -> str:
        return f"audits/audit_{audit_id}/results.csv"

    def generate_output_filename(self, dataset_name: str, file_extension: str = "csv") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_hash = str(uuid.uuid4())[:8]
        return f"{dataset_name}_{timestamp}_{unique_hash}.{file_extension}"

    # ------------------------------------------------------------------
    # Core S3 operations
    # ------------------------------------------------------------------

    def read_file(self, key: str) -> bytes:
        """Read raw bytes from S3."""
        response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()

    def write_file(self, key: str, data: bytes, content_type: str = "application/octet-stream"):
        """Write raw bytes to S3."""
        self.s3.put_object(Bucket=self.bucket_name, Key=key, Body=data, ContentType=content_type)

    def delete_file(self, key: str):
        """Delete an object from S3."""
        self.s3.delete_object(Bucket=self.bucket_name, Key=key)

    def read_csv(self, key: str, **kwargs) -> pd.DataFrame:
        """Read a CSV from S3 into a DataFrame."""
        raw = self.read_file(key)
        return pd.read_csv(io.BytesIO(raw), **kwargs)

    def write_csv(self, key: str, df: pd.DataFrame, index: bool = False):
        """Write a DataFrame as CSV to S3."""
        buf = io.BytesIO()
        df.to_csv(buf, index=index)
        buf.seek(0)
        self.write_file(key, buf.read(), content_type="text/csv")

    def read_json(self, key: str) -> Any:
        """Read a JSON file from S3."""
        raw = self.read_file(key)
        return json.loads(raw.decode("utf-8"))

    def write_json(self, key: str, data: Any):
        """Write JSON data to S3."""
        self.write_file(key, json.dumps(data, indent=2, default=str).encode("utf-8"),
                        content_type="application/json")

    def read_excel(self, key: str, **kwargs) -> pd.DataFrame:
        """Read an Excel file from S3 into a DataFrame."""
        raw = self.read_file(key)
        return pd.read_excel(io.BytesIO(raw), **kwargs)

    def write_parquet(self, key: str, df: pd.DataFrame, index: bool = False):
        """Write a DataFrame as Parquet to S3."""
        buf = io.BytesIO()
        df.to_parquet(buf, index=index)
        buf.seek(0)
        self.write_file(key, buf.read(), content_type="application/octet-stream")

    def file_exists(self, key: str) -> bool:
        """Check if a key exists in the bucket."""
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False

    def delete_file(self, key: str):
        """Delete a key from the bucket."""
        self.s3.delete_object(Bucket=self.bucket_name, Key=key)

    def list_files(self, prefix: str, file_patterns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """List files under a prefix, optionally filtered by glob patterns."""
        if file_patterns is None:
            file_patterns = ["*.csv", "*.json", "*.xlsx", "*.txt", "*.wav",
                             "*.mp3", "*.pdf", "*.docx", "*.html"]

        all_keys: List[Dict[str, Any]] = []
        paginator = self.s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                file_name = key.rsplit("/", 1)[-1] if "/" in key else key
                if not file_name:
                    continue
                # Apply pattern filter
                if any(fnmatch.fnmatch(file_name, p) for p in file_patterns):
                    all_keys.append({
                        "key": key,
                        "file_name": file_name,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                    })

        return all_keys

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for reading a file."""
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=expiration,
        )

    def upload_local_file(self, local_path: str, key: str):
        """Upload a local file to S3."""
        self.s3.upload_file(local_path, self.bucket_name, key)

    def download_to_temp(self, key: str, suffix: str = "") -> str:
        """Download an S3 object to a temporary file and return the path.

        Caller is responsible for cleaning up the temp file.
        """
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        self.s3.download_fileobj(self.bucket_name, key, tmp)
        tmp.close()
        return tmp.name

    # ------------------------------------------------------------------
    # Compatibility layer — mirrors StorageManager.discover_files_in_path
    # ------------------------------------------------------------------

    def discover_files_in_path(self, prefix: str, file_patterns: List[str] = None) -> List[Dict[str, Any]]:
        """Discover files under an S3 prefix, returning metadata compatible with StorageManager."""
        raw_files = self.list_files(prefix, file_patterns)
        discovered = []
        for f in raw_files:
            file_info = {
                "file_path": f["key"],  # S3 key instead of local path
                "file_name": f["file_name"],
                "file_extension": "." + f["file_name"].rsplit(".", 1)[-1].lower() if "." in f["file_name"] else "",
                "file_size": f["size"],
                "created_time": f["last_modified"],
                "file_type": self._determine_file_type(f["file_name"]),
                "data": None,
                "metadata": {},
            }
            # Extract hash/ID from filename if present
            stem = f["file_name"].rsplit(".", 1)[0] if "." in f["file_name"] else f["file_name"]
            parts = stem.split("_")
            if len(parts) > 1:
                file_info["metadata"]["extracted_id"] = parts[-1]
                file_info["metadata"]["base_name"] = "_".join(parts[:-1])
            discovered.append(file_info)
        return discovered

    @staticmethod
    def _determine_file_type(file_name: str) -> str:
        ext = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""
        type_mapping = {
            ".csv": "structured_data", ".json": "structured_data",
            ".xlsx": "structured_data", ".xls": "structured_data",
            ".txt": "text", ".html": "text", ".htm": "text",
            ".xml": "text", ".md": "text",
            ".wav": "audio", ".mp3": "audio", ".mp4": "audio",
            ".m4a": "audio", ".flac": "audio",
            ".pdf": "document", ".docx": "document", ".doc": "document",
        }
        return type_mapping.get(ext, "unknown")


_storage_manager_cache: dict = {}


def _tenant_bucket_name(base: str, tenant_id: str) -> str:
    """Return a valid S3 bucket name for a tenant.

    S3 bucket names must be lowercase, 3-63 chars, and contain only
    letters, numbers, and hyphens (no underscores).
    """
    safe = tenant_id.lower().replace("_", "-")
    return f"{base}-{safe}"


def get_storage_manager(tenant_id: str | None = None):
    """Factory: returns S3StorageManager or local StorageManager based on config.

    When tenant_id is provided and STORAGE_BACKEND is s3, uses a per-tenant bucket
    named ``{S3_BUCKET_NAME}-{tenant_id}`` (e.g. ``workbench-phawm-sam``).
    Results are cached per tenant_id so the bucket check only happens once per tenant.
    """
    global _storage_manager_cache

    cache_key = tenant_id or "__default__"
    if cache_key in _storage_manager_cache:
        return _storage_manager_cache[cache_key]

    from src.core.config import settings

    if settings.STORAGE_BACKEND == "s3":
        if tenant_id:
            bucket_name = _tenant_bucket_name(settings.S3_BUCKET_NAME, tenant_id)
        else:
            bucket_name = settings.S3_BUCKET_NAME
        instance = S3StorageManager(
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            bucket_name=bucket_name,
            region=settings.S3_REGION,
        )
    else:
        from src.services.utility_service.storage_service import StorageManager
        instance = StorageManager()

    _storage_manager_cache[cache_key] = instance
    return instance
