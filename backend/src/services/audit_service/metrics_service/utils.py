"""Metric utility and helper functions"""
from typing import List, Dict, Optional
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def get_user_audit_ids(session: Session, user_id: int) -> List[int]:
    """Get all audit IDs associated with the current user"""
    statement = select(MappingAuditUser.id).where(MappingAuditUser.user_id == user_id)
    audit_ids = session.exec(statement).all()
    return audit_ids


def create_metric_value_details(
    session: Session,
    metric_value_id: int,
    underlying_features: List[dict] = None,
    target_features: List[dict] = None,
    scale_points: dict = None
):
    """Create associated underlying_features, target_features and scale points for a metric value"""
    if underlying_features:
        for feature_data in underlying_features:
            feature_mapping = MetricsUnderlyingFeatures(
                metric_values_id=metric_value_id,
                feature_id=feature_data.feature_id,
                ranges=feature_data.ranges
            )
            session.add(feature_mapping)

    if target_features:
        for feature_data in target_features:
            target_mapping = MetricsTargetFeatures(
                metric_values_id=metric_value_id,
                target_feature_id=feature_data.feature_id
            )
            session.add(target_mapping)

    if scale_points:
        scale_point_mapping = MetricsScalePoints(
            metric_values_id=metric_value_id,
            scale_points=scale_points
        )
        session.add(scale_point_mapping)

    session.commit()


def get_metric_value_details(session: Session, metric_value_id: int):
    """Get associated underlying_features, target_features and scale points for a metric value"""
    # Get underlying_features
    underlying_features_statement = select(MetricsUnderlyingFeatures).where(
        MetricsUnderlyingFeatures.metric_values_id == metric_value_id
    )
    underlying_features = session.exec(underlying_features_statement).all()

    # Get target_features
    target_features_statement = select(MetricsTargetFeatures).where(
        MetricsTargetFeatures.metric_values_id == metric_value_id
    )
    target_features = session.exec(target_features_statement).all()

    # Get scale points
    scale_points_statement = select(MetricsScalePoints).where(
        MetricsScalePoints.metric_values_id == metric_value_id
    )
    scale_points = session.exec(scale_points_statement).first()

    return underlying_features, target_features, scale_points


def get_effective_threshold(
    session: Session,
    user_audit_id: int,
    metric_id: int,
    event_id: int,
    values_id: int
) -> tuple[str, bool]:
    """
    Get the effective threshold and whether it's customised.

    Always checks for user's custom threshold first. If a custom threshold exists
    in UserMetricThresholds, it takes precedence over the base MetricsValues threshold.

    If the base threshold is "Not Set" (case-insensitive), the custom threshold
    will be used instead if available.

    Returns:
        tuple: (effective_threshold, is_customised)
    """
    # Get base threshold from MetricsValues
    base_value = session.get(MetricsValues, values_id)
    if not base_value:
        return None, False

    # Always check for user's custom threshold first
    custom_threshold = session.exec(
        select(UserMetricThresholds).where(
            UserMetricThresholds.user_audit_id == user_audit_id,
            UserMetricThresholds.metric_id == metric_id,
            UserMetricThresholds.event_id == event_id,
            UserMetricThresholds.values_id == values_id
        )
    ).first()

    if custom_threshold:
        return custom_threshold.custom_threshold, True

    # If base threshold is "Not Set", check if there's ANY custom threshold for this metric/event/values
    # This handles cases where the base was created with "Not Set" but a user has customised it
    if base_value.threshold and base_value.threshold.lower() == "not set":
        any_custom_threshold = session.exec(
            select(UserMetricThresholds).where(
                UserMetricThresholds.metric_id == metric_id,
                UserMetricThresholds.event_id == event_id,
                UserMetricThresholds.values_id == values_id
            )
        ).first()

        if any_custom_threshold:
            return any_custom_threshold.custom_threshold, True

    # No customisation, return base threshold
    return base_value.threshold, False


def get_dataset_for_audit(session: Session, audit_id: int) -> int | None:
    """Get the dataset_id associated with an audit via audit pipeline"""
    # Get the audit pipeline for this audit
    audit_pipeline_mapping = session.exec(
        select(MappingAuditPipelineAudit).where(
            MappingAuditPipelineAudit.audit_id == audit_id
        )
    ).first()

    if not audit_pipeline_mapping:
        return None

    # Get the dataset from the model-dataset-audit mapping
    dataset_mapping = session.exec(
        select(MappingModelDatasetAudit).where(
            MappingModelDatasetAudit.auditpipeline == audit_pipeline_mapping.audit_pipeline
        )
    ).first()

    return dataset_mapping.dataset_id if dataset_mapping else None


def validate_feature_ids(
    session: Session,
    underlying_features: List[Dict] = None,
    target_features: List[Dict] = None,
    dataset_id: int = None,
    user_audit_id: int = None
):
    """
    Validate that all feature_ids exist and belong to either the dataset or are user-specific features.
    If dataset_id is provided, also validates features and marks which ones are user-specific.
    Returns a dict with validation results and feature categorization.
    """
    result = {
        "valid": True,
        "dataset_features": [],
        "user_features": [],
        "invalid_features": []
    }

    # Validate underlying_features
    if underlying_features:
        feature_ids = [f.feature_id for f in underlying_features if f.feature_id]
        if feature_ids:
            existing_underlying_features = session.exec(
                select(UnderlyingFeatures.id).where(UnderlyingFeatures.id.in_(feature_ids))
            ).all()

            if len(existing_underlying_features) != len(set(feature_ids)):
                missing_ids = set(feature_ids) - set(existing_underlying_features)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid underlying feature_ids: {list(missing_ids)}"
                )

            # If dataset_id provided, categorize features
            if dataset_id:
                # Get dataset features
                dataset_feature_mappings = session.exec(
                    select(MappingDatasetFeatures.underlying_feature_id).where(
                        MappingDatasetFeatures.dataset_metadata_id == dataset_id,
                        MappingDatasetFeatures.underlying_feature_id.in_(feature_ids)
                    )
                ).all()

                result["dataset_features"] = list(dataset_feature_mappings)

                # Check for user-specific features
                non_dataset_features = set(feature_ids) - set(dataset_feature_mappings)

                if non_dataset_features and user_audit_id:
                    # Check if these are valid user-specific features
                    user_feature_mappings = session.exec(
                        select(MappingUserAuditFeatures.underlying_feature_id).where(
                            MappingUserAuditFeatures.user_audit_id == user_audit_id,
                            MappingUserAuditFeatures.underlying_feature_id.in_(list(non_dataset_features))
                        )
                    ).all()

                    result["user_features"] = list(user_feature_mappings)

                    # Features that are neither in dataset nor user-specific
                    invalid_features = non_dataset_features - set(user_feature_mappings)
                    if invalid_features:
                        result["invalid_features"] = list(invalid_features)
                        result["valid"] = False
                elif non_dataset_features:
                    # No user_audit_id provided, so can't validate user features
                    result["invalid_features"] = list(non_dataset_features)
                    result["valid"] = False

    # Validate target_features
    result["dataset_target_features"] = []
    result["user_target_features"] = []
    result["invalid_target_features"] = []

    if target_features:
        target_feature_ids = [f.feature_id for f in target_features if f.feature_id]
        if target_feature_ids:
            existing_target_features = session.exec(
                select(TargetFeatures.id).where(TargetFeatures.id.in_(target_feature_ids))
            ).all()

            if len(existing_target_features) != len(set(target_feature_ids)):
                missing_ids = set(target_feature_ids) - set(existing_target_features)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid target feature_ids: {list(missing_ids)}"
                )

            # If dataset_id provided, categorize target features
            if dataset_id:
                # Get dataset target features
                dataset_target_mappings = session.exec(
                    select(MappingModelTargetFeatures.target_feature_id).where(
                        MappingModelTargetFeatures.dataset_metadata_id == dataset_id,
                        MappingModelTargetFeatures.target_feature_id.in_(target_feature_ids)
                    )
                ).all()

                result["dataset_target_features"] = list(dataset_target_mappings)

                # Check for user-specific target features
                non_dataset_targets = set(target_feature_ids) - set(dataset_target_mappings)

                if non_dataset_targets and user_audit_id:
                    # Check if these are valid user-specific target features
                    user_target_mappings = session.exec(
                        select(MappingUserAuditTargetFeatures.target_feature_id).where(
                            MappingUserAuditTargetFeatures.user_audit_id == user_audit_id,
                            MappingUserAuditTargetFeatures.target_feature_id.in_(list(non_dataset_targets))
                        )
                    ).all()

                    result["user_target_features"] = list(user_target_mappings)

                    # Target features that are neither in dataset nor user-specific
                    invalid_targets = non_dataset_targets - set(user_target_mappings)
                    if invalid_targets:
                        result["invalid_target_features"] = list(invalid_targets)
                        result["valid"] = False

    return result


def validate_target_feature_ids(session: Session, target_features: List[Dict]):
    """Validate that all target feature_ids exist"""
    target_feature_ids = [f.feature_id for f in target_features if hasattr(f, 'feature_id')]

    if target_feature_ids:
        existing_target_features = session.exec(
            select(TargetFeatures.id).where(TargetFeatures.id.in_(target_feature_ids))
        ).all()

        if len(existing_target_features) != len(set(target_feature_ids)):
            missing_ids = set(target_feature_ids) - set(existing_target_features)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target feature_ids: {list(missing_ids)}"
            )


def ensure_user_audit_feature_mappings(
    session: Session,
    user_audit_id: int,
    dataset_id: int,
    underlying_features: List = None,
    target_features: List = None
):
    """
    Ensure that features not in the dataset are linked to the user-audit mapping tables.

    This function checks which features are NOT in the dataset and creates
    MappingUserAuditFeatures / MappingUserAuditTargetFeatures entries for them
    if they don't already exist.

    Args:
        session: Database session
        user_audit_id: The user-audit mapping ID
        dataset_id: The dataset ID to check features against
        underlying_features: List of underlying feature objects with feature_id
        target_features: List of target feature objects with feature_id
    """
    # Handle underlying features
    if underlying_features:
        feature_ids = [f.feature_id for f in underlying_features if hasattr(f, 'feature_id') and f.feature_id]

        if feature_ids and dataset_id:
            # Get features that are in the dataset
            dataset_feature_ids = session.exec(
                select(MappingDatasetFeatures.underlying_feature_id).where(
                    MappingDatasetFeatures.dataset_metadata_id == dataset_id,
                    MappingDatasetFeatures.underlying_feature_id.in_(feature_ids)
                )
            ).all()

            # Features not in dataset need user-audit mapping
            non_dataset_features = set(feature_ids) - set(dataset_feature_ids)

            for feature_id in non_dataset_features:
                # Check if mapping already exists
                existing_mapping = session.exec(
                    select(MappingUserAuditFeatures).where(
                        MappingUserAuditFeatures.user_audit_id == user_audit_id,
                        MappingUserAuditFeatures.underlying_feature_id == feature_id
                    )
                ).first()

                if not existing_mapping:
                    # Create the mapping
                    user_feature_mapping = MappingUserAuditFeatures(
                        user_audit_id=user_audit_id,
                        underlying_feature_id=feature_id
                    )
                    session.add(user_feature_mapping)

            session.commit()

    # Handle target features
    if target_features:
        target_feature_ids = [f.feature_id for f in target_features if hasattr(f, 'feature_id') and f.feature_id]

        if target_feature_ids and dataset_id:
            # Get target features that are in the dataset
            dataset_target_ids = session.exec(
                select(MappingModelTargetFeatures.target_feature_id).where(
                    MappingModelTargetFeatures.dataset_metadata_id == dataset_id,
                    MappingModelTargetFeatures.target_feature_id.in_(target_feature_ids)
                )
            ).all()

            # Target features not in dataset need user-audit mapping
            non_dataset_targets = set(target_feature_ids) - set(dataset_target_ids)

            for target_id in non_dataset_targets:
                # Check if mapping already exists
                existing_mapping = session.exec(
                    select(MappingUserAuditTargetFeatures).where(
                        MappingUserAuditTargetFeatures.user_audit_id == user_audit_id,
                        MappingUserAuditTargetFeatures.target_feature_id == target_id
                    )
                ).first()

                if not existing_mapping:
                    # Create the mapping
                    user_target_mapping = MappingUserAuditTargetFeatures(
                        user_audit_id=user_audit_id,
                        target_feature_id=target_id
                    )
                    session.add(user_target_mapping)

            session.commit()
