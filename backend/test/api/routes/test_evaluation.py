import pytest
from fastapi.testclient import TestClient
from sqlmodel import select
from src.models import (
    MappingAuditUser,
    MappingEventsAuditStatus,
    MappingAuditOutcomeUser,
)
from src.core.enums import RECOMMENDATION_TEXT_MAP, STATUS_TEXT_MAP
from src.core.config import settings

def test_get_status_summary(client: TestClient, db, existing_user_headers):
    # Prepare data: get a valid audit and user mapping
    audit_id = 1  # Use a valid audit ID present in test DB

    # Get a user audit mapping for current user
    user_audit = db.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id
        )
    ).first()

    if not user_audit:
        pytest.skip("No user audit mapping found for test")

    response = client.get(f"{settings.API_V1_STR}/evaluation/status/{audit_id}/summary",
                          headers=existing_user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "audit_criteria" in data
    assert "recommendation" in data

def test_submit_audit(client: TestClient, db, existing_user_headers):
    audit_id = 1  # Use valid audit id

    submission_data = {
        "recommendation": 3,
        "notes": "Recommended for approval"
    }
    response = client.put(f"{settings.API_V1_STR}/evaluation/status/{audit_id}/submit",
                          json=submission_data, headers=existing_user_headers)
    assert response.status_code == 200
    assert "successfully submitted" in response.json()["message"].lower()

def test_update_status(client: TestClient, db, existing_user_headers):
    audit_id = 1

    # Get an existing MappingEventsAuditStatus record for this audit
    # First get the user to find their user_audit_id
    from src.models import User, MappingAuditUser, MappingEventsAuditStatus
    user = db.exec(select(User).where(User.email == 'jane.smith@company.com')).first()
    if not user:
        pytest.skip("Test user jane.smith@company.com not found")

    user_audit = db.exec(
        select(MappingAuditUser).where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == user.id
        )
    ).first()

    if not user_audit:
        pytest.skip("No user audit mapping found for test")

    # Get an existing audit status record
    audit_status = db.exec(
        select(MappingEventsAuditStatus).where(
            MappingEventsAuditStatus.audit_id == audit_id,
            MappingEventsAuditStatus.user_audit_id == user_audit.id
        )
    ).first()

    if not audit_status:
        pytest.skip("No audit status record found for test")

    event_id = audit_status.event_id
    metric_id = audit_status.metric_id

    update_data = {
        "event_id": event_id,
        "metric_id": metric_id,
        "recommendation": 2,
        "notes": "Needs improvement"
    }
    response = client.put(f"{settings.API_V1_STR}/evaluation/status/{audit_id}",
                          json=update_data, headers=existing_user_headers)
    assert response.status_code == 200
    result = response.json()
    assert "Audit Status has been updated" in result.get("message", "")
'''
def test_update_status_batch(client: TestClient, db, existing_user_headers):
    audit_id = 1
    batch_data = [
        {
            "event_id": 4,
            "metric_id": 6,
            "user_audit_id": 1,
            "recommendation": 3,
            "notes": "Batch update 1"
        },
        {
            "event_id": 2,
            "metric_id": 2,
            "user_audit_id": 1,
            "recommendation": 1,
            "notes": "Batch update 2"
        }
    ]
    response = client.put(f"{settings.API_V1_STR}/evaluation/status/{audit_id}/batch",
                          json=batch_data, headers=existing_user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "updated_status" in data
    assert "not_updated_status" in data 
'''    
def test_get_results_summary(client: TestClient, db, existing_user_headers):
    audit_id = 1
    response = client.get(f"{settings.API_V1_STR}/evaluation/results/{audit_id}/summary",
                          headers=existing_user_headers)
    assert response.status_code == 200
    data = response.json()
    assert "audit_criteria" in data
    assert "total_criteria" in data

