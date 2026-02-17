
from collections.abc import Generator
from unittest.mock import patch
from faker import Faker
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, delete
from sqlalchemy import event
from uuid import uuid4
from datetime import datetime, timezone

from src.main import app
from src.database import engine, get_session 
from src.models import *
from src.core.security import get_password_hash
from src.services.user_service import create_user
from test.utils import user_authentication_headers

@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="session")
def fake():
    faker = Faker()
    Faker.seed(222)  
    return faker

@pytest.fixture(scope="session")
def normal_user_data(db, fake):
    email = fake.company_email()
    user_data = {
            "email":email,
            "full_name":fake.name(),
            "username":fake.user_name(),
            "password":fake.password(),
            "is_active":True,
            "is_superuser":False,
            "is_verified":True,
        }
    user_create = UserCreate(**user_data)
    user = create_user(session=db, user_create=user_create)
    yield user_data 
    statement = delete(User).where(User.email == email)
    db.execute(statement)
    db.commit()


@pytest.fixture(scope="session")
def normaluser_header(client, db, fake):
    email=fake.company_email()
    password=fake.password()
    user_create = UserCreate(
        email=email,
        full_name=fake.name(),
        username=fake.user_name(),
        password=password,
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    create_user(session=db, user_create=user_create)
    headers = user_authentication_headers(client=client, email=email, password=password)
    yield headers
    statement = delete(User).where(User.email == email)
    db.execute(statement)
    db.commit()


@pytest.fixture(scope="session")
def superuser_header(client, db, fake):
    email=fake.company_email()
    password=fake.password()
    user_create = UserCreate(
        email=email,
        full_name=fake.name(),
        username=fake.user_name(),
        password=password,
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    create_user(session=db, user_create=user_create)
    headers = user_authentication_headers(client=client, email=email, password=password)
    yield headers
    statement = delete(User).where(User.email == email)
    db.execute(statement)
    db.commit()

@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

@pytest.fixture
def cleanup_user(db: Session):
    emails_to_cleanup = []

    yield emails_to_cleanup  

    for email in emails_to_cleanup:
        stmt = delete(User).where(User.email == email)
        db.execute(stmt)
    db.commit()

@pytest.fixture
def cleanup_audit(db: Session):
    """Fixture to track and cleanup audit IDs after tests."""
    audit_ids_to_cleanup = []
    yield audit_ids_to_cleanup
    for audit_id in audit_ids_to_cleanup:
        stmt = delete(Audit).where(Audit.id == audit_id)
        db.execute(stmt)
    db.commit()


@pytest.fixture
def cleanup_application(db: Session):
    """Fixture to track and cleanup application IDs after tests."""
    app_ids_to_cleanup = []
    yield app_ids_to_cleanup
    for app_id in app_ids_to_cleanup:
        stmt = delete(Application).where(Application.id == app_id)
        db.execute(stmt)
    db.commit()

@pytest.fixture
def existing_user_headers(client):
    headers = user_authentication_headers(client=client,
                                          email='jane.smith@company.com',
                                          password='password123')
    return headers    

# Application Fixtures
@pytest.fixture
def test_application(db: Session, fake):
    """Creates a test application with realistic data."""
    application = Application(
        name=fake.company() + " Platform",
        description=fake.text(max_nb_chars=200),
        url=fake.url(),
        access_type=fake.random_int(min=0, max=2),  # 0=Black Box, 1=Grey Box, 2=White Box
        testing_evaluation={
            "test_coverage": fake.random.uniform(70.0, 99.0),
            "test_types": ["unit", "integration", "performance"],
            "last_tested": fake.date_this_year().isoformat(),
            "test_results": {
                "passed": fake.random_int(min=100, max=500),
                "failed": fake.random_int(min=0, max=10),
                "skipped": fake.random_int(min=0, max=5)
            }
        },
        deployment={
            "environment": fake.random_element(elements=("development", "staging", "production")),
            "deployment_date": fake.date_this_year().isoformat(),
            "version": f"{fake.random_int(min=1, max=5)}.{fake.random_int(min=0, max=9)}.{fake.random_int(min=0, max=9)}",
            "infrastructure": {
                "cloud_provider": fake.random_element(elements=("AWS", "Azure", "GCP")),
                "region": fake.random_element(elements=("us-west-1", "us-east-1", "eu-central-1")),
                "instances": fake.random_int(min=1, max=10)
            }
        },
        business_case=fake.text(max_nb_chars=150),
        legal_framework=fake.random_element(elements=(
            "SOC2 compliant", 
            "GDPR ready", 
            "ISO 27001 certified",
            "HIPAA compliant"
        ))
    )
    
    db.add(application)
    db.commit()
    db.refresh(application)
    yield application
    
    # Cleanup
    db.delete(application)
    db.commit()


# Audit Fixtures
@pytest.fixture
def test_audit(db: Session, test_application, fake):
    """Creates a test audit linked to an application."""
    audit = Audit(
        name=fake.sentence(nb_words=4),
        status=fake.random_int(min=0, max=2),  # 0=Not Started, 1=In Progress, 2=Finished
        recommendation=fake.text(max_nb_chars=200),
        application_id=test_application.id
    )
    
    db.add(audit)
    db.commit()
    db.refresh(audit)
    yield audit
    
    # Cleanup
    db.delete(audit)
    db.commit()


# Role Fixtures
@pytest.fixture
def test_roles(db: Session):
    """Creates test audit roles."""
    roles_data = [
        {"role": "admin"},
        {"role": "auditor"}, 
        {"role": "analyst"}
    ]
    
    roles = []
    for role_data in roles_data:
        role = MappingAuditRoles(**role_data)
        db.add(role)
        roles.append(role)
    
    db.commit()
    for role in roles:
        db.refresh(role)
    
    yield roles
    
    # Cleanup
    for role in roles:
        db.delete(role)
    db.commit()


# Event Fixtures
@pytest.fixture
def test_events(db: Session, fake):
    """Creates test events with realistic data."""
    events_data = []
    for _ in range(5):
        events_data.append({
            "description": fake.sentence(nb_words=4),
            "cause": fake.text(max_nb_chars=100),
            "likelihood": fake.random.uniform(0.1, 1.0),
            "magnitude": fake.random.uniform(0.1, 1.0),
            "valence": fake.random.uniform(-1.0, 1.0)
        })
    
    events = []
    for event_data in events_data:
        event = Events(**event_data)
        db.add(event)
        events.append(event)
    
    db.commit()
    for event in events:
        db.refresh(event)
    
    yield events
    
    # Cleanup
    for event in events:
        db.delete(event)
    db.commit()


# Event Category Fixtures
@pytest.fixture
def test_event_categories(db: Session, fake):
    """Creates test event categories."""
    categories_data = [
        {"event_name": "Business Performance", "description": "Revenue and growth related events"},
        {"event_name": "Customer Experience", "description": "Customer satisfaction events"},
        {"event_name": "Operational Excellence", "description": "Efficiency and operational events"}
    ]
    
    categories = []
    for category_data in categories_data:
        category = EventsCategory(**category_data)
        db.add(category)
        categories.append(category)
    
    db.commit()
    for category in categories:
        db.refresh(category)
    
    yield categories
    
    # Cleanup
    for category in categories:
        db.delete(category)
    db.commit()


# Entity Fixtures
@pytest.fixture
def entities_data(db: Session, fake):
    """Creates test entities."""
    entities_data = [
        {"name": "Active Customers", "num_individuals": fake.random_int(min=1000, max=100000)},
        {"name": "Monthly Transactions", "num_individuals": fake.random_int(min=10000, max=1000000)},
        {"name": "Product Units", "num_individuals": fake.random_int(min=100, max=50000)},
        {"name": "Employee Base", "num_individuals": fake.random_int(min=50, max=5000)}
    ]
    
    entities = []
    for entity_data in entities_data:
        entity = Entities(**entity_data)
        db.add(entity)
        entities.append(entity)
    
    db.commit()
    for entity in entities:
        db.refresh(entity)
    
    yield entities
    
    # Cleanup
    for entity in entities:
        db.delete(entity)
    db.commit()


# Metrics Fixtures
@pytest.fixture
def test_metrics(db: Session, fake):
    """Creates test metrics."""
    metrics_data = []
    for _ in range(5):
        metrics_data.append({
            "description": fake.sentence(nb_words=3),
            "reason": fake.text(max_nb_chars=100)
        })
    
    metrics = []
    for metric_data in metrics_data:
        metric = Metrics(**metric_data)
        db.add(metric)
        metrics.append(metric)
    
    db.commit()
    for metric in metrics:
        db.refresh(metric)
    
    yield metrics
    
    # Cleanup
    for metric in metrics:
        db.delete(metric)
    db.commit()


# AI/ML Fixtures
@pytest.fixture
def test_ai_models(db: Session, fake):
    """Creates test AI models."""
    models_data = [
        {
            "name": "Customer Sentiment Analyzer",
            "model_type": False,  # Predictive
            "location": "/models/sentiment_analyzer.pkl",
            "acceptable_formats": ["txt", "csv"],
            "output_context": "Sentiment scores",
            "task": "Sentiment analysis"
        },
        {
            "name": "GPT-4 Assistant",
            "model_type": True,  # Generative
            "location": None,
            "acceptable_formats": ["txt", "html"],
            "output_context": "Natural language responses",
            "task": "Text generation"
        }
    ]
    
    models = []
    for model_data in models_data:
        model = Modelmetadata(**model_data)
        db.add(model)
        models.append(model)
    
    db.commit()
    for model in models:
        db.refresh(model)
    
    yield models
    
    # Cleanup
    for model in models:
        db.delete(model)
    db.commit()


@pytest.fixture
def test_datasets(db: Session, fake):
    """Creates test datasets with metadata."""
    datasets_data = [
        {
            "purpose": "Training data for sentiment analysis",
            "copyright_agreement": True
        },
        {
            "purpose": "Customer support conversation logs",
            "copyright_agreement": False
        }
    ]
    
    datasets = []
    for dataset_data in datasets_data:
        dataset = DatasetMetadata(**dataset_data)
        db.add(dataset)
        datasets.append(dataset)
    
    db.commit()
    for dataset in datasets:
        db.refresh(dataset)
    
    yield datasets
    
    # Cleanup
    for dataset in datasets:
        db.delete(dataset)
    db.commit()


# Complete Test Environment Fixture
@pytest.fixture
def complete_test_environment(
    db: Session,
    test_user,
    test_superuser,
    test_application,
    test_audit,
    test_roles,
    test_events,
    test_event_categories,
    test_entities,
    test_metrics,
    test_ai_models,
    test_datasets
):
    """
    Provides a complete test environment with all major entities created.
    Useful for integration tests that need multiple related objects.
    """
    return {
        "db": db,
        "user": test_user,
        "superuser": test_superuser,
        "application": test_application,
        "audit": test_audit,
        "roles": test_roles,
        "events": test_events,
        "categories": test_event_categories,
        "entities": test_entities,
        "metrics": test_metrics,
        "ai_models": test_ai_models,
        "datasets": test_datasets
    }


# Mapping Fixtures for Testing Relationships
@pytest.fixture
def test_audit_user_mappings(db: Session, test_audit, test_user, test_superuser):
    """Creates audit-user mappings for testing."""
    mappings = []
    for user in [test_user, test_superuser]:
        mapping = MappingAuditUser(
            audit_id=test_audit.id,
            user_id=user.id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_user_roles_mappings(db: Session, test_user, test_superuser, test_roles):
    """Creates user-role mappings for testing."""
    mappings = [
        UserRoles(user_id=test_user.id, role_id=test_roles[1].id),  # auditor
        UserRoles(user_id=test_superuser.id, role_id=test_roles[0].id)  # admin
    ]
    
    for mapping in mappings:
        db.add(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_metrics_events_mappings(db: Session, test_metrics, test_events, test_audit_user_mappings, fake):
    """Creates metrics-events mappings for testing."""
    mappings = []
    
    # Create some sample metric values first
    metric_values = []
    for _ in range(3):
        value = MetricsValues(
            output="percentage",
            threshold=fake.random.uniform(10.0, 90.0),
            features=["test", "sample"],
            scale_points={"low": 0, "medium": 50, "high": 100}
        )
        db.add(value)
        metric_values.append(value)
    
    db.commit()
    for value in metric_values:
        db.refresh(value)
    
    # Create mappings between metrics and events
    for i in range(min(3, len(test_metrics), len(test_events))):
        mapping = MappingMetricsEvents(
            metric_id=test_metrics[i].id,
            event_id=test_events[i].id,
            user_audit_id=test_audit_user_mappings[i % len(test_audit_user_mappings)].id,
            values_id=metric_values[i].id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    for value in metric_values:
        db.delete(value)
    db.commit()


@pytest.fixture
def test_events_entities_mappings(db: Session, test_events, test_entities, test_audit_user_mappings):
    """Creates events-entities mappings for testing."""
    mappings = []
    
    for i in range(min(len(test_events), len(test_entities))):
        mapping = MappingEventsEntities(
            user_audit_id=test_audit_user_mappings[i % len(test_audit_user_mappings)].id,
            event_id=test_events[i].id,
            entity_id=test_entities[i].id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_events_category_mappings(db: Session, test_events, test_event_categories):
    """Creates events-category mappings for testing."""
    mappings = []
    
    for i, event in enumerate(test_events):
        mapping = MappingEventsCategory(
            event_id=event.id,
            category_id=test_event_categories[i % len(test_event_categories)].id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_user_events_mappings(db: Session, test_events, test_audit_user_mappings):
    """Creates user-events mappings for testing."""
    mappings = []
    
    for i, event in enumerate(test_events):
        mapping = MappingUserEvents(
            user_audit_id=test_audit_user_mappings[i % len(test_audit_user_mappings)].id,
            event_id=event.id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_audit_model_mappings(db: Session, test_audit, test_ai_models):
    """Creates audit-model mappings for testing AI/ML governance."""
    mappings = []
    
    for model in test_ai_models:
        mapping = MappingAuditModel(
            model_id=model.id,
            audit_id=test_audit.id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_audit_pipeline(db: Session):
    """Creates an audit pipeline for testing."""
    pipeline = AuditPipeline()
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    
    yield pipeline
    
    # Cleanup
    db.delete(pipeline)
    db.commit()


@pytest.fixture
def test_model_dataset_mappings(db: Session, test_audit_pipeline, test_ai_models, test_datasets):
    """Creates model-dataset-audit mappings for testing."""
    mappings = []
    
    for i, model in enumerate(test_ai_models):
        dataset = test_datasets[i % len(test_datasets)]
        mapping = MappingModelDatasetAudit(
            auditpipeline=test_audit_pipeline.id,
            model_id=model.id,
            dataset_id=dataset.id
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_event_values(db: Session, test_user, fake):
    """Creates custom event values for testing."""
    event_values = []
    
    for _ in range(3):
        value = EventValues(
            likelihood=fake.random.uniform(0.1, 1.0),
            magnitude=fake.random.uniform(0.1, 1.0),
            valence=fake.random.uniform(-1.0, 1.0),
            description=fake.text(max_nb_chars=100),
            created_by_user_id=test_user.id,
            is_default=False
        )
        db.add(value)
        event_values.append(value)
    
    # Add one default value
    default_value = EventValues(
        likelihood=0.5,
        magnitude=0.5,
        valence=0.0,
        description="Default event values template",
        created_by_user_id=test_user.id,
        is_default=True
    )
    db.add(default_value)
    event_values.append(default_value)
    
    db.commit()
    for value in event_values:
        db.refresh(value)
    
    yield event_values
    
    # Cleanup
    for value in event_values:
        db.delete(value)
    db.commit()


@pytest.fixture
def test_event_values_mappings(db: Session, test_events, test_event_values, test_audit_user_mappings):
    """Creates event-values mappings for testing custom event assessments."""
    mappings = []
    
    for i in range(min(3, len(test_events), len(test_event_values) - 1)):  # -1 to exclude default
        mapping = MappingEventValues(
            event_id=test_events[i].id,
            event_values_id=test_event_values[i].id,
            user_audit_id=test_audit_user_mappings[i % len(test_audit_user_mappings)].id,
            is_active=True
        )
        db.add(mapping)
        mappings.append(mapping)
    
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    
    yield mappings
    
    # Cleanup
    for mapping in mappings:
        db.delete(mapping)
    db.commit()


@pytest.fixture
def test_api_keys(db: Session, test_user, test_superuser, test_ai_models, fake):
    """Creates API keys for testing model access."""
    api_keys = []
    
    for i, model in enumerate(test_ai_models):
        user = test_user if i % 2 == 0 else test_superuser
        api_key = Apikeymodel(
            user_id=user.id,
            model_api_key=f"sk-test-{fake.lexify('?' * 20)}",
            costing_policy=fake.random_element(elements=("pay-per-request", "monthly-subscription", "enterprise-tier")),
            model_metadata_id=model.id
        )
        db.add(api_key)
        api_keys.append(api_key)
    
    db.commit()
    for api_key in api_keys:
        db.refresh(api_key)
    
    yield api_keys
    
    # Cleanup
    for api_key in api_keys:
        db.delete(api_key)
    db.commit()


# Complete Mappings Test Environment
@pytest.fixture
def complete_mappings_environment(
    db: Session,
    test_audit_user_mappings,
    test_user_roles_mappings,
    test_metrics_events_mappings,
    test_events_entities_mappings,
    test_events_category_mappings,
    test_user_events_mappings,
    test_audit_model_mappings,
    test_model_dataset_mappings,
    test_event_values_mappings,
    test_api_keys
):
    """
    Provides a complete test environment with all mapping relationships.
    Perfect for testing complex queries and relationship integrity.
    """
    return {
        "db": db,
        "audit_user_mappings": test_audit_user_mappings,
        "user_roles_mappings": test_user_roles_mappings,
        "metrics_events_mappings": test_metrics_events_mappings,
        "events_entities_mappings": test_events_entities_mappings,
        "events_category_mappings": test_events_category_mappings,
        "user_events_mappings": test_user_events_mappings,
        "audit_model_mappings": test_audit_model_mappings,
        "model_dataset_mappings": test_model_dataset_mappings,
        "event_values_mappings": test_event_values_mappings,
        "api_keys": test_api_keys
    }


# Mock Fixtures for External Dependencies
@pytest.fixture
def mock_email_service():
    """Mock email service to prevent actual emails during tests."""
    with patch('src.services.email_service.send_email') as mock_send:
        mock_send.return_value = {"status": "sent", "message_id": "test-123"}
        yield mock_send


@pytest.fixture
def mock_external_api():
    """Mock external API calls during tests."""
    with patch('src.services.external_api.make_request') as mock_request:
        mock_request.return_value = {"status": "success", "data": {"test": True}}
        yield mock_request
