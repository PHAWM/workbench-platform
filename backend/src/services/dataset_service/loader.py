"""
Dataset loader service for importing datasets from external sources
(HuggingFace, PyTorch) into the workbench storage and database.
"""

import io
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from sqlmodel import Session, select

from src.services.utility_service.s3_storage_service import get_storage_manager, S3StorageManager
from src.models import (
    DatasetMetadata,
    InputDatasetMetadata,
    OutputDatasetMetadata,
    UnderlyingFeatures,
    MappingDatasetFeatures,
    TargetFeatures,
    MappingModelTargetFeatures,
)


class DatasetLoaderService:
    """
    Loads datasets from various sources and materializes them into the
    workbench storage directory so the existing evaluation pipeline can
    consume them without changes.

    Supported sources:
        - huggingface: Uses the `datasets` library (datasets.load_dataset)
        - pytorch:     Uses torchvision / torchaudio / torchtext datasets
        - file:        A remote URL pointing to a CSV / JSON / Parquet file
    """

    def __init__(self, storage_base_path: str = "storage"):
        self.storage_base_path = Path(storage_base_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_dataset(
        self,
        session: Session,
        source_type: str,
        dataset_name: str,
        split: str = "test",
        subset: Optional[str] = None,
        max_samples: Optional[int] = None,
        label_column: Optional[str] = None,
        text_column: Optional[str] = None,
        purpose: str = "benchmark",
        audit_id: Optional[int] = None,
        target_features: Optional[List[str]] = None,
        underlying_feature_columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Import a dataset from an external source into the workbench.

        1. Downloads / loads the dataset
        2. Converts to a DataFrame
        3. Saves as CSV in storage/datasets/<dataset_name>/
        4. Creates DatasetMetadata + InputDatasetMetadata records

        Returns:
            Dict with dataset_id, input_metadata_id, location, row_count,
            columns, and source info.
        """

        # Step 1 — load into a DataFrame
        if source_type == "huggingface":
            df, source_info = self._load_huggingface(
                dataset_name, split, subset, max_samples
            )
        elif source_type == "pytorch":
            df, source_info = self._load_pytorch(
                dataset_name, split, max_samples
            )
        elif source_type == "file":
            df, source_info = self._load_file(dataset_name, max_samples)
        else:
            raise ValueError(
                f"Unsupported source type: '{source_type}'. "
                "Use 'huggingface', 'pytorch', or 'file'."
            )

        # Step 2 — normalise column names
        df = self._normalise_columns(df, label_column, text_column)

        # Step 3 — save to storage
        safe_name = dataset_name.replace("/", "_").replace("\\", "_")
        if subset:
            safe_name = f"{safe_name}_{subset}"
        safe_name = f"{safe_name}_{split}"

        sm = get_storage_manager()

        if isinstance(sm, S3StorageManager):
            dataset_dir = f"datasets/{safe_name}"
            csv_key = f"{dataset_dir}/data.csv"
            buf = io.BytesIO()
            df.to_csv(buf, index=False)
            sm.write_file(csv_key, buf.getvalue(), content_type="text/csv")

            if "true_value" in df.columns:
                meta_cols = [c for c in df.columns if c != "text"]
                if meta_cols:
                    meta_buf = io.BytesIO()
                    df[meta_cols].to_csv(meta_buf, index=False)
                    sm.write_file(f"{dataset_dir}/metadata.csv", meta_buf.getvalue(), content_type="text/csv")
        else:
            dataset_dir_path = self.storage_base_path / "datasets" / safe_name
            dataset_dir_path.mkdir(parents=True, exist_ok=True)
            df.to_csv(dataset_dir_path / "data.csv", index=False)
            if "true_value" in df.columns:
                meta_cols = [c for c in df.columns if c != "text"]
                if meta_cols:
                    df[meta_cols].to_csv(dataset_dir_path / "metadata.csv", index=False)
            dataset_dir = str(dataset_dir_path)

        # Step 4 — build headers & datatypes dicts from the DataFrame
        headers = {col: col for col in df.columns}
        datatypes = {col: str(df[col].dtype) for col in df.columns}

        # Step 5 — persist to database
        dataset_meta = DatasetMetadata(
            purpose=purpose,
            copyright_agreement=None,
        )
        session.add(dataset_meta)
        session.flush()

        input_meta = InputDatasetMetadata(
            dataset_metadata_id=dataset_meta.id,
            headers=headers,
            benchmark_dataset=True,
            datatypes=datatypes,
            location=str(dataset_dir),
            source=source_info,
        )
        session.add(input_meta)
        session.flush()

        # Create an empty output metadata pointing at the output subdirectory
        output_dir = f"{dataset_dir}/output" if isinstance(sm, S3StorageManager) else str(Path(dataset_dir) / "output")
        if not isinstance(sm, S3StorageManager):
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        output_meta = OutputDatasetMetadata(
            dataset_metadata_id=dataset_meta.id,
            headers={},
            benchmark_dataset=True,
            datatypes={},
            location=output_dir,
            source=source_info,
        )
        session.add(output_meta)
        session.flush()

        # Step 6 — create UnderlyingFeatures + MappingDatasetFeatures
        # Same logic as the admin panel's create_complete_dataset
        EXCLUDED_FIELDS = {
            "id", "true_value", "y_pred", "y_actual",
            "file", "output", "subjects",
        }

        # If caller specified which columns are features, use those;
        # otherwise register all non-system columns.
        if underlying_feature_columns:
            feature_col_names = [
                c for c in underlying_feature_columns if c in df.columns
            ]
        else:
            feature_col_names = [
                c for c in df.columns if c not in EXCLUDED_FIELDS
            ]

        created_features = []
        for col_name in feature_col_names:
            existing_feat = session.exec(
                select(UnderlyingFeatures)
                .where(UnderlyingFeatures.feature_name == col_name)
            ).first()
            if not existing_feat:
                existing_feat = UnderlyingFeatures(feature_name=col_name)
                session.add(existing_feat)
                session.flush()
            existing_mapping = session.exec(
                select(MappingDatasetFeatures).where(
                    MappingDatasetFeatures.dataset_metadata_id == dataset_meta.id,
                    MappingDatasetFeatures.underlying_feature_id == existing_feat.id,
                )
            ).first()
            if not existing_mapping:
                session.add(MappingDatasetFeatures(
                    dataset_metadata_id=dataset_meta.id,
                    underlying_feature_id=existing_feat.id,
                ))
            created_features.append(col_name)

        # Step 7 — create TargetFeatures + MappingModelTargetFeatures
        created_targets = []
        if target_features:
            for target_name in target_features:
                existing_target = session.exec(
                    select(TargetFeatures)
                    .where(TargetFeatures.target_feature == target_name)
                ).first()
                if not existing_target:
                    existing_target = TargetFeatures(
                        target_feature=target_name, function_name=None
                    )
                    session.add(existing_target)
                    session.flush()
                existing_mapping = session.exec(
                    select(MappingModelTargetFeatures).where(
                        MappingModelTargetFeatures.dataset_metadata_id == dataset_meta.id,
                        MappingModelTargetFeatures.target_feature_id == existing_target.id,
                    )
                ).first()
                if not existing_mapping:
                    session.add(MappingModelTargetFeatures(
                        dataset_metadata_id=dataset_meta.id,
                        target_feature_id=existing_target.id,
                    ))
                created_targets.append(target_name)

        session.commit()

        return {
            "dataset_id": dataset_meta.id,
            "input_metadata_id": input_meta.id,
            "output_metadata_id": output_meta.id,
            "location": str(dataset_dir),
            "row_count": len(df),
            "columns": list(df.columns),
            "underlying_features": created_features,
            "target_features": created_targets,
            "source": source_info,
        }

    # ------------------------------------------------------------------
    # Source loaders
    # ------------------------------------------------------------------

    def _load_huggingface(
        self,
        dataset_name: str,
        split: str,
        subset: Optional[str],
        max_samples: Optional[int],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Load a dataset from HuggingFace Hub."""
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError(
                "The 'datasets' package is required for HuggingFace imports. "
                "Install it with: pip install datasets"
            )

        kwargs: Dict[str, Any] = {"path": dataset_name, "split": split}
        if subset:
            kwargs["name"] = subset

        ds = load_dataset(**kwargs)

        if max_samples and len(ds) > max_samples:
            ds = ds.select(range(max_samples))

        df = ds.to_pandas()

        source_info = {
            "type": "huggingface",
            "name": dataset_name,
            "split": split,
            "subset": subset,
            "total_rows_available": len(ds),
            "rows_imported": len(df),
        }
        return df, source_info

    def _load_pytorch(
        self,
        dataset_name: str,
        split: str,
        max_samples: Optional[int],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Load a torchvision / torchaudio / torchtext dataset.

        Supports common datasets like CIFAR10, MNIST, FashionMNIST, etc.
        For image datasets the raw pixel data is not stored — only the label
        and an index are kept, since the evaluation pipeline works with
        structured predictions, not raw images.
        """
        try:
            import torchvision
        except ImportError:
            raise ImportError(
                "The 'torchvision' package is required for PyTorch dataset imports. "
                "Install it with: pip install torchvision"
            )

        is_train = split.lower() == "train"
        dataset_name_lower = dataset_name.lower()

        # Map common names to torchvision classes
        pytorch_datasets = {
            "cifar10": torchvision.datasets.CIFAR10,
            "cifar100": torchvision.datasets.CIFAR100,
            "mnist": torchvision.datasets.MNIST,
            "fashionmnist": torchvision.datasets.FashionMNIST,
            "fashion_mnist": torchvision.datasets.FashionMNIST,
        }

        dataset_cls = pytorch_datasets.get(dataset_name_lower)
        if dataset_cls is None:
            available = ", ".join(pytorch_datasets.keys())
            raise ValueError(
                f"PyTorch dataset '{dataset_name}' not recognised. "
                f"Available: {available}"
            )

        # PyTorch datasets always download to local cache (not stored in S3)
        cache_dir = Path(self.storage_base_path) / "cache" / "pytorch"
        cache_dir.mkdir(parents=True, exist_ok=True)

        ds = dataset_cls(root=str(cache_dir), train=is_train, download=True)

        # Build a DataFrame from (index, label) pairs
        records = []
        targets = ds.targets if hasattr(ds, "targets") else [y for _, y in ds]
        class_names = ds.classes if hasattr(ds, "classes") else None

        limit = max_samples if max_samples else len(targets)
        for i in range(min(limit, len(targets))):
            label = targets[i]
            if hasattr(label, "item"):
                label = label.item()
            record = {"id": i, "true_value": label}
            if class_names:
                record["true_value_label"] = class_names[label]
            records.append(record)

        df = pd.DataFrame(records)

        source_info = {
            "type": "pytorch",
            "name": dataset_name,
            "split": split,
            "total_rows_available": len(targets),
            "rows_imported": len(df),
        }
        return df, source_info

    def _load_file(
        self,
        url: str,
        max_samples: Optional[int],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Load a dataset from a remote CSV, JSON, or Parquet URL."""
        url_lower = url.lower()

        if url_lower.endswith(".parquet"):
            df = pd.read_parquet(url)
        elif url_lower.endswith(".json") or url_lower.endswith(".jsonl"):
            df = pd.read_json(url, lines=url_lower.endswith(".jsonl"))
        else:
            # Default to CSV
            df = pd.read_csv(url)

        if max_samples and len(df) > max_samples:
            df = df.head(max_samples)

        source_info = {
            "type": "file",
            "url": url,
            "rows_imported": len(df),
        }
        return df, source_info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_columns(
        df: pd.DataFrame,
        label_column: Optional[str] = None,
        text_column: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Rename user-specified or common columns so the evaluation pipeline
        can find them:
            - label / target → true_value
            - sentence / input / question / prompt → text
            - Add an 'id' column if missing
        """
        df = df.copy()

        # Rename label column
        if label_column and label_column in df.columns:
            df = df.rename(columns={label_column: "true_value"})
        elif "true_value" not in df.columns:
            for candidate in ["label", "target", "labels", "targets", "class"]:
                if candidate in df.columns:
                    df = df.rename(columns={candidate: "true_value"})
                    break

        # Rename text column
        if text_column and text_column in df.columns:
            df = df.rename(columns={text_column: "text"})
        elif "text" not in df.columns:
            for candidate in ["sentence", "input", "question", "prompt", "content"]:
                if candidate in df.columns:
                    df = df.rename(columns={candidate: "text"})
                    break

        # Ensure there is an id column
        if "id" not in df.columns:
            df.insert(0, "id", range(len(df)))

        return df
