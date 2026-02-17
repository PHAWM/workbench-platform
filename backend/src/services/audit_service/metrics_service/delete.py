"""Metric deletion service functions"""
from typing import Any, Dict
from fastapi import HTTPException
from sqlmodel import Session, select

from src.models import *


def delete_metric(metric_id: int, session: Session) -> Dict[str, Any]:
    """Delete a metric and its dependent records"""
    statement = select(Metrics).where(Metrics.id == metric_id)
    db_metric = session.exec(statement).first()

    if not db_metric:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Set metric_id to null in dependent records
    qual_metrics = session.exec(select(QualitativeMetrics).where(QualitativeMetrics.metric_id == metric_id)).all()
    quant_metrics = session.exec(select(QuantitativeMetrics).where(QuantitativeMetrics.metric_id == metric_id)).all()
    metric_mappings = session.exec(select(MappingUserMetrics).where(MappingUserMetrics.metric_id == metric_id)).all()

    session.delete(qual_metrics)
    session.delete(quant_metrics)
    session.delete(metric_mappings)
    session.delete(db_metric)
    session.commit()

    total_affected = len(qual_metrics) + len(quant_metrics) + len(metric_mappings)
    if total_affected > 0:
        return {"message": f"Metric deleted successfully. {total_affected} dependent records had their metric_id set to null."}
    return {"message": "Metric deleted successfully"}


def delete_qualitative_metric(qual_id: int, session: Session) -> Dict[str, str]:
    """Delete a qualitative metric"""
    statement = select(QualitativeMetrics).where(QualitativeMetrics.id == qual_id)
    db_qual_metric = session.exec(statement).first()

    if not db_qual_metric:
        raise HTTPException(status_code=404, detail="Qualitative metric not found")

    session.delete(db_qual_metric)
    session.commit()
    return {"message": "Qualitative metric deleted successfully"}


def delete_quantitative_metric(quant_id: int, session: Session) -> Dict[str, str]:
    """Delete a quantitative metric"""
    statement = select(QuantitativeMetrics).where(QuantitativeMetrics.id == quant_id)
    db_quant_metric = session.exec(statement).first()

    if not db_quant_metric:
        raise HTTPException(status_code=404, detail="Quantitative metric not found")

    session.delete(db_quant_metric)
    session.commit()
    return {"message": "Quantitative metric deleted successfully"}


def reset_threshold_to_default_comprehensive(
    metric_id: int,
    event_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Reset a customised threshold back to default (delete custom threshold).

    This service function handles:
    - User audit access verification
    - Metric-event mapping retrieval
    - Custom threshold lookup and deletion
    - Default threshold retrieval
    - Response construction

    Args:
        metric_id: The ID of the metric
        event_id: The ID of the event
        current_user_id: The ID of the user resetting the threshold
        session: Database session

    Returns:
        Dictionary with message, metric_id, event_id, default_threshold, and was_custom

    Raises:
        HTTPException: If user has no access, mapping not found, or no custom threshold exists
    """
    # Get user_audit_id for the current user
    user_audit_mapping = session.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit_mapping:
        raise HTTPException(status_code=403, detail="User audit mapping not found")

    # Get the metric-event mapping to find values_id
    mapping = session.exec(
        select(MappingMetricsEvents).where(
            MappingMetricsEvents.event_id == event_id,
            MappingMetricsEvents.metric_id == metric_id
        )
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="Metric-event mapping not found")

    # Find and delete custom threshold
    custom_threshold = session.exec(
        select(UserMetricThresholds).where(
            UserMetricThresholds.user_audit_id == user_audit_mapping.id,
            UserMetricThresholds.metric_id == metric_id,
            UserMetricThresholds.event_id == event_id,
            UserMetricThresholds.values_id == mapping.values_id
        )
    ).first()

    if not custom_threshold:
        raise HTTPException(status_code=404, detail="No custom threshold found to reset")

    session.delete(custom_threshold)
    session.commit()

    # Get the default threshold to return
    base_value = session.get(MetricsValues, mapping.values_id)

    return {
        "message": "Custom threshold reset to default",
        "metric_id": metric_id,
        "event_id": event_id,
        "default_threshold": base_value.threshold if base_value else None,
        "was_custom": True
    }
