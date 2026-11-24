"""
Integration tests for S3StorageManager and get_storage_manager() factory.

Uses moto to mock AWS S3 — no real network calls are made.
Run with:  pytest test/test_storage/test_s3_storage.py -v
"""

import io
import os
import json
import pytest
import pandas as pd

# moto must be imported before boto3 to intercept calls
boto3 = pytest.importorskip("boto3", reason="boto3 not installed")
moto = pytest.importorskip("moto", reason="moto not installed")

from moto import mock_s3
from src.services.utility_service.s3_storage_service import S3StorageManager, get_storage_manager
from src.services.utility_service.storage_service import (
    StorageManager,
    save_output_data,
    discover_input_data_with_metadata,
    InputFileMetadataManager,
    _local_path_to_s3_key,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BUCKET = "test-workbench"
ENDPOINT = "http://localhost:9999"  # moto intercepts regardless of endpoint


@pytest.fixture
def s3_manager():
    """S3StorageManager wired to a moto-mocked bucket."""
    with mock_s3():
        mgr = S3StorageManager(
            endpoint_url=ENDPOINT,
            access_key="test",
            secret_key="test",
            bucket_name=BUCKET,
            region="us-east-1",
        )
        yield mgr


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "text": ["hello world", "foo bar", "baz qux"],
        "true_value": [0, 1, 0],
    })


# ---------------------------------------------------------------------------
# get_storage_manager() factory
# ---------------------------------------------------------------------------

class TestGetStorageManagerFactory:
    def test_returns_local_manager_by_default(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        # Reload settings so env var is picked up
        from src.core.config import settings
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
        mgr = get_storage_manager()
        assert isinstance(mgr, StorageManager)

    def test_returns_s3_manager_when_configured(self, monkeypatch):
        from src.core.config import settings
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
        monkeypatch.setattr(settings, "S3_ENDPOINT_URL", ENDPOINT)
        monkeypatch.setattr(settings, "S3_ACCESS_KEY", "test")
        monkeypatch.setattr(settings, "S3_SECRET_KEY", "test")
        monkeypatch.setattr(settings, "S3_BUCKET_NAME", BUCKET)
        monkeypatch.setattr(settings, "S3_REGION", "us-east-1")

        with mock_s3():
            mgr = get_storage_manager()
        assert isinstance(mgr, S3StorageManager)


# ---------------------------------------------------------------------------
# Core S3 read/write operations
# ---------------------------------------------------------------------------

class TestS3CoreOperations:
    def test_write_and_read_csv(self, s3_manager, sample_df):
        key = "audits/audit_1/input/data.csv"
        s3_manager.write_csv(key, sample_df)
        result = s3_manager.read_csv(key)
        assert list(result.columns) == list(sample_df.columns)
        assert len(result) == len(sample_df)

    def test_write_and_read_json(self, s3_manager):
        key = "audits/audit_1/config.json"
        payload = {"model": "sam", "version": "2.0"}
        s3_manager.write_json(key, payload)
        result = s3_manager.read_json(key)
        assert result == payload

    def test_write_and_read_raw_bytes(self, s3_manager):
        key = "audits/audit_1/input/audio.wav"
        data = b"\x00\x01\x02\x03"
        s3_manager.write_file(key, data)
        result = s3_manager.read_file(key)
        assert result == data

    def test_write_and_read_parquet(self, s3_manager, sample_df):
        key = "audits/audit_1/output/results.parquet"
        s3_manager.write_parquet(key, sample_df)
        raw = s3_manager.read_file(key)
        result = pd.read_parquet(io.BytesIO(raw))
        assert len(result) == len(sample_df)

    def test_file_exists_true(self, s3_manager):
        key = "audits/audit_2/input/test.csv"
        s3_manager.write_file(key, b"col\nval")
        assert s3_manager.file_exists(key) is True

    def test_file_exists_false(self, s3_manager):
        assert s3_manager.file_exists("nonexistent/key.csv") is False

    def test_delete_file(self, s3_manager):
        key = "tmp/delete_me.csv"
        s3_manager.write_file(key, b"data")
        assert s3_manager.file_exists(key) is True
        s3_manager.delete_file(key)
        assert s3_manager.file_exists(key) is False

    def test_list_files_with_pattern(self, s3_manager, sample_df):
        s3_manager.write_csv("audits/audit_3/input/a.csv", sample_df)
        s3_manager.write_csv("audits/audit_3/input/b.csv", sample_df)
        s3_manager.write_file("audits/audit_3/input/audio.wav", b"\x00")

        files = s3_manager.list_files("audits/audit_3/input/", ["*.csv"])
        names = {f["file_name"] for f in files}
        assert "a.csv" in names
        assert "b.csv" in names
        assert "audio.wav" not in names

    def test_list_files_all_patterns(self, s3_manager, sample_df):
        s3_manager.write_csv("audits/audit_4/input/data.csv", sample_df)
        s3_manager.write_file("audits/audit_4/input/clip.wav", b"\x00")
        files = s3_manager.list_files("audits/audit_4/input/")
        names = {f["file_name"] for f in files}
        assert "data.csv" in names
        assert "clip.wav" in names

    def test_generate_presigned_url(self, s3_manager):
        key = "audits/audit_5/input/file.wav"
        s3_manager.write_file(key, b"\x00")
        url = s3_manager.generate_presigned_url(key, expiration=60)
        assert "file.wav" in url

    def test_upload_local_file(self, s3_manager, tmp_path):
        local = tmp_path / "upload.csv"
        local.write_text("col\nval")
        key = "audits/audit_6/input/upload.csv"
        s3_manager.upload_local_file(str(local), key)
        assert s3_manager.file_exists(key) is True

    def test_download_to_temp(self, s3_manager, tmp_path):
        key = "audits/audit_7/input/audio.wav"
        s3_manager.write_file(key, b"\x52\x49\x46\x46")
        tmp = s3_manager.download_to_temp(key, suffix=".wav")
        try:
            assert os.path.exists(tmp)
            with open(tmp, "rb") as f:
                assert f.read() == b"\x52\x49\x46\x46"
        finally:
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestS3PathHelpers:
    def test_get_audit_input_path(self, s3_manager):
        assert s3_manager.get_audit_input_path("5") == "audits/audit_5/input/"

    def test_get_audit_results_path(self, s3_manager):
        assert s3_manager.get_audit_results_path("5") == "audits/audit_5/results.csv"

    def test_get_user_output_path_with_audit(self, s3_manager):
        path = s3_manager.get_user_output_path("user-123", "5")
        assert "audit_5" in path
        assert "user-123" in path

    def test_get_user_output_path_without_audit(self, s3_manager):
        path = s3_manager.get_user_output_path("user-123")
        assert "user-123" in path

    def test_generate_output_filename(self, s3_manager):
        name = s3_manager.generate_output_filename("results", "csv")
        assert name.startswith("results_")
        assert name.endswith(".csv")


# ---------------------------------------------------------------------------
# discover_files_in_path (compatibility layer)
# ---------------------------------------------------------------------------

class TestDiscoverFilesInPath:
    def test_discovers_csv_files(self, s3_manager, sample_df):
        s3_manager.write_csv("audits/audit_8/input/rows.csv", sample_df)
        s3_manager.write_file("audits/audit_8/input/clip.wav", b"\x00")

        files = s3_manager.discover_files_in_path("audits/audit_8/input/", ["*.csv"])
        assert len(files) == 1
        assert files[0]["file_name"] == "rows.csv"
        assert files[0]["file_type"] == "structured_data"
        assert "file_path" in files[0]
        assert "metadata" in files[0]

    def test_skips_empty_prefix_entries(self, s3_manager):
        # Upload a real file so the prefix exists
        s3_manager.write_file("audits/audit_9/input/data.csv", b"col\nval")
        files = s3_manager.discover_files_in_path("audits/audit_9/input/")
        # Should contain at least the real file
        assert any(f["file_name"] == "data.csv" for f in files)

    def test_returns_empty_for_missing_prefix(self, s3_manager):
        files = s3_manager.discover_files_in_path("audits/audit_999/input/")
        assert files == []


# ---------------------------------------------------------------------------
# save_output_data — S3 branch
# ---------------------------------------------------------------------------

class TestSaveOutputDataS3:
    def test_saves_csv_to_s3(self, s3_manager, sample_df):
        location = "storage/audits/audit_10/output"
        key = save_output_data(sample_df, location, s3_manager)
        assert key.endswith(".csv")
        result = s3_manager.read_csv(key)
        assert len(result) == len(sample_df)

    def test_saves_to_explicit_csv_key(self, s3_manager, sample_df):
        location = "audits/audit_11/output/results.csv"
        key = save_output_data(sample_df, location, s3_manager)
        assert key.endswith(".csv")
        result = s3_manager.read_csv(key)
        assert len(result) == len(sample_df)

    def test_large_df_uses_parquet(self, s3_manager):
        big_df = pd.DataFrame({"x": range(10001)})
        location = "audits/audit_12/output"
        key = save_output_data(big_df, location, s3_manager)
        assert key.endswith(".parquet")
        assert s3_manager.file_exists(key)


# ---------------------------------------------------------------------------
# _local_path_to_s3_key helper
# ---------------------------------------------------------------------------

class TestLocalPathToS3Key:
    def test_strips_storage_prefix(self):
        assert _local_path_to_s3_key("storage/audits/audit_5/input/") == "audits/audit_5/input/"

    def test_audit_colon_format(self):
        assert _local_path_to_s3_key("audit:5/input") == "audits/audit_5/input/"

    def test_user_colon_format(self):
        key = _local_path_to_s3_key("user:user-abc/5/output")
        assert "audit_5" in key
        assert "user-abc" in key

    def test_bare_key_passthrough(self):
        assert _local_path_to_s3_key("audits/audit_5/input/") == "audits/audit_5/input/"


# ---------------------------------------------------------------------------
# discover_input_data_with_metadata — S3 branch
# ---------------------------------------------------------------------------

class TestDiscoverInputDataWithMetadataS3:
    def test_reads_csv_rows_from_s3(self, s3_manager, sample_df):
        s3_manager.write_csv("audits/audit_13/input/data.csv", sample_df)
        metadata_manager = InputFileMetadataManager()

        entries = discover_input_data_with_metadata(
            location="storage/audits/audit_13/input/",
            datatypes_info={},
            storage_manager=s3_manager,
            metadata_manager=metadata_manager,
        )
        assert len(entries) == len(sample_df)
        assert entries[0]["data"]["text"] == "hello world"

    def test_skips_metadata_csv(self, s3_manager, sample_df):
        s3_manager.write_csv("audits/audit_14/input/data.csv", sample_df)
        # metadata.csv should be skipped
        meta_df = pd.DataFrame({"file_name": ["data.csv"], "gender": ["F"]})
        s3_manager.write_csv("audits/audit_14/input/metadata.csv", meta_df)
        metadata_manager = InputFileMetadataManager()

        entries = discover_input_data_with_metadata(
            location="storage/audits/audit_14/input/",
            datatypes_info={},
            storage_manager=s3_manager,
            metadata_manager=metadata_manager,
        )
        # Only rows from data.csv — not metadata.csv
        assert len(entries) == len(sample_df)

    def test_reads_text_file_from_s3(self, s3_manager):
        content = "This is a test document for ANNIF."
        s3_manager.write_file("audits/audit_15/input/doc.txt",
                               content.encode("utf-8"))
        metadata_manager = InputFileMetadataManager()

        entries = discover_input_data_with_metadata(
            location="storage/audits/audit_15/input/",
            datatypes_info={},
            storage_manager=s3_manager,
            metadata_manager=metadata_manager,
        )
        assert len(entries) == 1
        assert entries[0]["data"]["text"] == content
