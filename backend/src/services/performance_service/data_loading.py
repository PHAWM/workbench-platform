"""CSV / DataFrame loading, merging, and output.csv validation."""
import pandas as pd
from pathlib import Path
from typing import List, Optional, Tuple


def read_csv_flexible(path) -> pd.DataFrame:
    """Read a CSV trying comma, 'comma-space', and tab separators."""
    path = Path(path)
    try:
        df = pd.read_csv(path)
        if len(df.columns) == 1:
            col = df.columns[0]
            if ', ' in col:
                df = pd.read_csv(path, sep=', ')
            elif '\t' in col:
                df = pd.read_csv(path, sep='\t')
    except Exception:
        try:
            df = pd.read_csv(path, sep=', ')
        except Exception:
            df = pd.read_csv(path, sep='\t')
    df.columns = df.columns.str.strip()
    return df


def aggregate_multi_run_results(df: pd.DataFrame) -> pd.DataFrame:
    """If results.csv has multiple runs per participant, aggregate to one row each."""
    if 'child_id' not in df.columns or 'run' not in df.columns:
        return df

    unique_participants = df['child_id'].nunique()
    if len(df) <= unique_participants:
        return df

    num_runs = len(df) // unique_participants
    print(f"Detected {num_runs} runs × {unique_participants} participants — aggregating...")

    if 'output' in df.columns:
        agg = df.groupby('child_id', as_index=False).agg(
            {'output': lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]}
        )
        agg['id'] = agg['child_id']
        print(f"Aggregated {len(df)} → {len(agg)} rows")
        return agg

    return df


def aggregate_multi_run_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse multi-run metadata to one row per participant."""
    if 'id' not in df.columns or 'child_id' not in df.columns:
        return df

    unique_ids = df['id'].nunique()
    if len(df) <= unique_ids:
        return df

    agg_dict = {}
    for col in ['gender', 'age', 'file']:
        if col in df.columns:
            agg_dict[col] = 'first'
    if 'true_value' in df.columns:
        agg_dict['true_value'] = lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]

    agg = df.groupby('child_id', as_index=False).agg(agg_dict)
    agg['id'] = agg['child_id']
    return agg


def load_and_merge_results(results_path: Path, metadata_path: Optional[Path]) -> pd.DataFrame:
    """
    Load results.csv and optionally merge with metadata.csv.
    Handles multi-run aggregation automatically.
    """
    results_df = read_csv_flexible(results_path)
    print(f"Loaded results.csv with {len(results_df)} rows")
    results_df = aggregate_multi_run_results(results_df)

    if metadata_path and metadata_path.exists():
        print(f"Found metadata.csv at: {metadata_path}")
        metadata_df = read_csv_flexible(metadata_path)
        metadata_df = aggregate_multi_run_metadata(metadata_df)

        if 'id' in results_df.columns and 'id' in metadata_df.columns:
            combined = pd.merge(results_df, metadata_df, on='id', how='left')
            print(f"Merged on 'id': {len(combined)} rows")
        elif len(results_df) == len(metadata_df):
            combined = pd.concat([results_df, metadata_df], axis=1)
            print("Merged by index position")
        else:
            print("Cannot merge: no common 'id' column and row counts differ")
            combined = results_df
    else:
        combined = results_df

    return combined


def validate_output_csv(
    output_csv_path: Path,
    input_file_names: set,
) -> Optional[pd.DataFrame]:
    """
    Load existing output.csv and validate it covers all input files.
    Returns the DataFrame if valid, None if missing or incomplete.
    """
    if not output_csv_path.exists():
        return None

    try:
        df = pd.read_csv(output_csv_path)
        print(f"Loaded existing output.csv with {len(df)} rows")

        if 'file_name' not in df.columns:
            print("output.csv missing 'file_name' column — will re-run inference")
            return None

        missing = input_file_names - set(df['file_name'].dropna().unique())
        if missing:
            print(f"output.csv missing {len(missing)} input file(s) — will re-run inference")
            return None

        print(f"output.csv is complete ({len(input_file_names)} files)")
        return df

    except Exception as e:
        print(f"Error loading output.csv: {e}")
        return None


def register_metadata_manager(input_location: str, storage_base_path: str):
    """Build an InputFileMetadataManager with metadata.csv registered if present."""
    from src.services.utility_service.storage_service import InputFileMetadataManager

    metadata_manager = InputFileMetadataManager(storage_base_path)
    metadata_csv_path = Path(input_location) / "metadata.csv"

    if metadata_csv_path.exists():
        print(f"Found metadata.csv at: {metadata_csv_path}")
        try:
            meta_df = pd.read_csv(metadata_csv_path)
            available_columns = [c for c in meta_df.columns if c != 'file_name']
        except Exception as e:
            print(f"Could not read metadata.csv: {e}")
            available_columns = ['id', 'gender', 'age', 'true_value', 'expected_subjects', 'notes']

        metadata_manager.add_metadata_file(
            str(metadata_csv_path),
            'csv',
            'file_name',
            available_columns,
        )

    return metadata_manager
