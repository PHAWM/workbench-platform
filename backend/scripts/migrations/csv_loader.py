"""
CSV-based data loader for v4 migrations.

This migration creates a minimal setup with only two test accounts:
- test-audit-instigator@company.com (audit instigator)
- test-auditor@company.com (auditor)

Data is loaded from CSV files in the storage/seed_data/ directory.
"""
from sqlmodel import Session, select
from uuid import uuid4
from pathlib import Path
import csv
import datetime
import secrets
from typing import Optional, Dict, Any, List

from src.core.security import get_password_hash
from src.models import *


# ============================================================================
# Configuration
# ============================================================================

SEED_DATA_DIR = Path("storage/seed_data")
DEFAULT_PASSWORD = "password123"

# Audit-Event mapping: defines which events belong to which audit
# Events are matched by name prefix
AUDIT_EVENT_MAPPING = {
    "SAM Audit": ["Prediction Correctness", "Gender Fairness"],
    "Annif Audit": ["Subject Correctness", "Value of subject keywords"],
    "Test Audit - Annif Text Classification": ["Subject Correctness", "Value of subject keywords"],
}

def get_events_for_audit(audit_name: str, events_map: Dict[str, int]) -> Dict[str, int]:
    """Get events that belong to a specific audit.

    Returns filtered events_map containing only events for this audit.
    If audit not in mapping, returns empty dict.
    """
    allowed_event_names = AUDIT_EVENT_MAPPING.get(audit_name, [])
    return {
        name: event_id
        for name, event_id in events_map.items()
        if name in allowed_event_names
    }

# Test accounts configuration
TEST_ACCOUNTS = [
    {
        "email": "test-audit-instigator@company.com",
        "full_name": "Test Audit Instigator",
        "username": "test_audit_instigator",
        "gender": "Not Set",
        "ethnicity": "Not Set",
        "country": "Not Set",
        "organisation": "Test Company",
        "is_active": True,
        "is_superuser": False,
        "role": "audit_instigator"
    },
    {
        "email": "test-auditor@company.com",
        "full_name": "Test Auditor",
        "username": "test_auditor",
        "gender": "Not Set",
        "ethnicity": "Not Set",
        "country": "Not Set",
        "organisation": "Test Company",
        "is_active": True,
        "is_superuser": False,
        "role": "auditor"
    }
]


# ============================================================================
# CSV Reading Utilities
# ============================================================================

def read_csv(filename: str) -> List[Dict[str, Any]]:
    """Read a CSV file and return list of dictionaries."""
    filepath = SEED_DATA_DIR / filename
    if not filepath.exists():
        print(f"   ⚠️  CSV file not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def parse_bool(value: str) -> bool:
    """Parse a string to boolean."""
    return value.lower() in ('true', '1', 'yes', 'y')


def parse_int(value: str, default: int = 0) -> int:
    """Parse a string to integer with default."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_float(value: str, default: float = 0.0) -> float:
    """Parse a string to float with default."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ============================================================================
# User Management
# ============================================================================

def add_test_users(session: Session) -> Dict[str, Any]:
    """Create the two test user accounts.

    Returns:
        Dict mapping email to user object
    """
    print("\n📦 Creating test users...")
    users_map = {}

    for user_data in TEST_ACCOUNTS:
        email = user_data["email"].lower()

        # Check if user exists
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            print(f"   ✓ User already exists: {email}")
            users_map[email] = existing
            continue

        # Create new user
        user = User(
            id=uuid4(),
            email=email,
            full_name=user_data["full_name"],
            username=user_data["username"],
            gender=user_data.get("gender", "Not Set"),
            ethnicity=user_data.get("ethnicity", "Not Set"),
            country=user_data.get("country", "Not Set"),
            organisation=user_data.get("organisation", "Test Company"),
            is_active=user_data.get("is_active", True),
            is_superuser=user_data.get("is_superuser", False),
            hashed_password=get_password_hash(DEFAULT_PASSWORD),
            is_verified=True
        )
        session.add(user)
        users_map[email] = user
        print(f"   ✅ Created user: {email}")

    session.commit()
    return users_map


def add_user_invitations(session: Session, users_map: Dict[str, User]) -> Dict[str, str]:
    """Create invitation tokens for test users.

    Returns:
        Dict mapping email to invitation token
    """
    print("\n📦 Creating user invitations...")
    tokens_map = {}

    for email, user in users_map.items():
        # Check if invitation exists
        existing = session.exec(
            select(UserInvitation).where(
                UserInvitation.user_id == user.id,
                UserInvitation.invitation_used == False
            )
        ).first()

        if existing:
            tokens_map[email] = existing.invitation_token
            print(f"   ✓ Invitation exists for: {email}")
            continue

        # Create invitation
        token = secrets.token_urlsafe(64)
        invitation = UserInvitation(
            user_id=user.id,
            invitation_token=token,
            invitation_used=False,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        )
        session.add(invitation)
        tokens_map[email] = token
        print(f"   ✅ Created invitation for: {email}")

    session.commit()
    return tokens_map


# ============================================================================
# Roles
# ============================================================================

def add_audit_roles(session: Session) -> Dict[str, int]:
    """Create audit roles.

    Returns:
        Dict mapping role name to role id
    """
    print("\n📦 Creating audit roles...")
    roles = ["audit_instigator", "auditor"]
    roles_map = {}

    for role_name in roles:
        existing = session.exec(select(AuditRoles).where(AuditRoles.role == role_name)).first()
        if existing:
            roles_map[role_name] = existing.id
            print(f"   ✓ Role exists: {role_name}")
            continue

        role = AuditRoles(role=role_name)
        session.add(role)
        session.flush()
        roles_map[role_name] = role.id
        print(f"   ✅ Created role: {role_name}")

    session.commit()
    return roles_map


# ============================================================================
# CSV-based Data Loading
# ============================================================================

def load_applications_from_csv(session: Session) -> Dict[str, int]:
    """Load applications with full V3 data including testing_evaluation, deployment, business_case, legal_framework.

    Returns:
        Dict mapping application name to id
    """
    print("\n📦 Loading applications...")
    apps_map = {}

    # Full V3 application data with all JSON fields
    applications = [
        {
            "name": "SAM",
            "description": "The School Attachment Monitor (SAM) is an AI application that predicts whether a child shows signs of secure or insecure attachment, based on recordings of their speech. 'Attachment' is a psychological term that refers to the early emotional bond developed between an infant and their primary caregiver, which plays a key role in shaping a person's future relationships and overall emotional well-being. Even though insecure attachment is not a pathology, research shows it is often linked to emotional difficulties in adulthood, which might affect a person's quality of life and contribute to mental or physical health issues. SAM was developed as a screening tool for the early detection of insecure attachment in children, supporting timely expert intervention when needed. Users simply upload audio recordings of a child's speech, and the application predicts how likely it is that that the child has a secure or insecure attachment style.",
            "url": "https://www.gla.ac.uk/schools/healthwellbeing/staff/helenminnis/",
            "access_type": 1,  # Grey Box
            "organisation": "University of Glasgow",
            "testing_evaluation": {
                "testing_details": "It has been tested before, internally.",
                "audit_instigator_details": "Helen Minnis (School of Health and Wellbeing, University of Glasgow) https://www.gla.ac.uk/schools/healthwellbeing/staff/helenminnis/, Alessandro Vinciarelli (School of Computing Science – University of Glasgow) https://www.gla.ac.uk/schools/computing/staff/alessandrovinciarelli/ ,Areej Buker (Imam Abdulrahman bin Faisal University Saudi Arabia) https://www.researchgate.net/profile/Areej-Buker ",
                "model_details": "SAM uses an AI model which considers both semantic and acoustic information of the input data. In other words, it takes into account both what the child says (words and expressions used) and how they say it (sound characteristics of their voice). The model has been trained to tell the difference between examples of 'Secure' and 'Insecure' attachment, based on a large number of recordings that were labelled by attachment experts. Each time a new recording is processed by SAM, the AI algorithm extracts the relevant information (both the language used and the voice characteristics) from it and compares it to what it has learned from the training examples. If the recording is more similar to the 'Secure' examples, it is classified as 'Secure', if it is closer to the 'Insecure' examples, it is classified as 'Insecure'.",
                "dataset_details": "The SAM dataset includes 512 audio recordings of children taking part in an attachment assessment. Each child is labelled as either 'secure' or 'insecure' based on their responses. A total of 104 children, aged between 5 and 9 years, took part in the study (57 girls and 47 boys). The distribution of attachment types in the dataset reflects what is typically seen in the general population: 59 children were labelled as 'secure' and 45 as 'insecure'. The attachment assessment used is called the Manchester Child Attachment Story Task (MCAST). In this task, children are asked to respond to five short, imaginary stories involving mild stressful situations, revealing how they might cope with real-life emotional challenges. All the recordings were processed by the AI application using standard .wav audio files. The results are also organised by gender and age group, so we can see how different groups compare.",
            },
            "deployment": {
                "environment": "SAM can be used in schools by educators, in psychology practices by mental health specialists or even at home by parents.",
                "version": "This is a research prototype and has not yet been deployed.",
            },
            "business_case": "The motivation behind SAM's development lies in the implications of Attachment Theory, which posits that early bonds between infants and their caregivers influence the relationships they will form later in life and their overall well-being. More specifically, children have been found to develop an Internal Working Model (IWM) of how interactions take place in life, which can be positive or negative depending on their caregivers' behaviour. Consistent and responsive caregivers lead to a positive IWM, which helps the development of secure attachment, while inconsistent or unresponsive caregivers lead to a negative IWM, resulting in insecure attachment. Children with insecure attachment tend to face more emotional difficulties in adulthood, which might lead to a lower life quality and potentially result in physical or mental health problems. To address these issues, SAM was developed as a screening tool for the early detection of insecure attachment in children, indicating when experts' intervention might be needed.",
            "legal_framework": "This is not considered a medical device because it doesn't provide medical advice. It follows GDPR rules to protect users' privacy. https://gdpr-info.eu/"
        },
        {
            "name": "Annif",
            "description": "Annif is an open source toolkit for automated subject indexing. It integrates several machine learning and AI based algorithms for text classification. Annif automates subject indexing and classification independently of indexing vocabulary, it uses multiple text classification algorithms to produce subject indexes. By being independent of a specific indexing vocabulary or indexing algorithm, it is more adaptable and more likely to suggest a wider range of subjects/keywords. Subject indexing is an incredibly labour intensive process and Annif is one of many tools created from the 1960s onwards that attempts to automate the process. Annif uses extant metadata to build metadata for newly input text files. While Annif provides precision, recall and F1 scores in its evaluation model it does not provide a way to critically audit the model from a participant standpoint.",
            "url": "http://annif.org",
            "access_type": 1,  # Grey Box
            "organisation": "Curatorial Advisor David Livingstone Museum",
            "testing_evaluation": {
                "testing_details": "It has been tested before, internally.",
                "audit_instigator_details": "Kate Simpson (Curatorial Advisor David Livingstone Museum) kathryn.simpson@dltrust.uk. Sandra Lowson (Director David Livingstone Museum) sandra.lowson@dltrust.uk",
                "model_details": "YSO English (2025.7.Laotse), refers to a specific Annif project configuration that uses the English version of the YSO (General Finnish Ontology) vocabulary for automated subject indexing",
                "dataset_details": "The subject index or keywords are generated by the model creating mathematical representations of the text to allow analysis, comparison and pattern recognition in the text data, vector representations. The backend, TFIDF, of Annif calculates a vector representation of each subject within a test corpora. When a new text document is inputted into Annif, the model suggests subjects based on the vector similarity of the words in the text to the test corpora about that subject. The documents in this auditing example consists of the text of the three digitised Missionary Travels manuscript books (MS. 42428 ; MS. 42429; MS. 42428) which together were the source for David Livingstone's book Missionary Travels (published in 1857). The manuscript books are held by the National Library of Scotland and available online through LivingstoneOnline.org and Adam Matthew Digital.",
            },
            "deployment": {
                "environment": "Annif is an automated subject indexing tool that can be used with multiple controlled subject vocabularies. Annif can be trained on documents already indexed and then suggest institution specific subject vocabularies for new documents ingested.",
                "version": "Deployed. Used by the EU, Getty Conservation Institute, The National Library of Poland, German National Library, Yle (Finish Broadcasting Company).",
            },
            "business_case": "Case study - Missionary Travels (1857) original manuscript. No subject keywords are currently applied to this and other manuscripts in the NLS, the application of subject keywords can show users what is in the text. By being able to identify what is in texts users can access information they might not be aware of. Current structures always place engagement through the lens of the author, collector or creator; by enabling subject keyword engagement it widens access and allows users to establish what subjects are covered in a manuscript. Compare with limited subject keyword for published text https://search.worldcat.org/title/848572 and ebook https://catalog.hathitrust.org/Record/102124189. This example would allow audit instigators to see whether it is of value to run current digitised texts through annif and update catalogue entries as appropriate. The Audit Instigator acknowledges that due to the age and nature of some texts, the Auditor may encounter offensive terminology. The presence of offensive terminology within the workbench is not an endorsement of the language or content found when an audit is run. The terms may occur because they exist within records, subject keyword lists, or texts and have evidential value. The Audit Instigator acknowledges the impact, hurt and significant affect such language or imagery can have on the Auditor.",
            "legal_framework": "Copyright and Licensing Images © National Library of Scotland. Creative Commons Share-alike 2.5 UK: Scotland (https://creativecommons.org/licenses/by-nc-sa/2.5/scotland/). As relevant, Dr. Neil Imray Livingstone Wilson. Creative Commons Attribution-NonCommercial 3.0 Unported (https://creativecommons.org/licenses/by-nc/3.0/). Texts © Livingstone, David, 1813-1873. 'Missionary Travels and Researches in South Africa (Parts I, II & III), January-October 1857.' Livingstone Online."
        }
    ]

    for app_data in applications:
        name = app_data["name"]
        existing = session.exec(select(Application).where(Application.name == name)).first()
        if existing:
            apps_map[name] = existing.id
            print(f"   ✓ Application exists: {name}")
            continue

        app = Application(**app_data)
        session.add(app)
        session.flush()
        apps_map[name] = app.id
        print(f"   ✅ Created application: {name}")

    session.commit()
    return apps_map


def load_models_from_csv(session: Session) -> Dict[str, int]:
    """Load model metadata from CSV.

    CSV format: name,model_type,location,acceptable_formats,output_context,task

    Returns:
        Dict mapping model name to id
    """
    print("\n📦 Loading models from CSV...")
    data = read_csv("models.csv")
    models_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default models")
        # Create SAM and Annif models as defaults
        default_models = [
            {
                "name": "SAM",
                "model_type": False,
                "location": "http://sam-api:8002",
                "acceptable_formats": ["wav", "mp3"],
                "output_context": "Prediction.",
                "task": "Classifies Secure and Insecure attachments."
            },
            {
                "name": "Annif",
                "model_type": False,
                "location": "http://annif-api:8004",
                "acceptable_formats": ["txt", "html"],
                "output_context": "Theme ranking of content",
                "task": "Text Analysis"
            }
        ]
        for model_data in default_models:
            existing = session.exec(select(Modelmetadata).where(Modelmetadata.name == model_data["name"])).first()
            if not existing:
                model = Modelmetadata(**model_data)
                session.add(model)
                session.flush()
                models_map[model_data["name"]] = model.id
            else:
                models_map[model_data["name"]] = existing.id
        session.commit()
        return models_map

    for row in data:
        name = row.get("name", "").strip()
        if not name:
            continue

        existing = session.exec(select(Modelmetadata).where(Modelmetadata.name == name)).first()
        if existing:
            models_map[name] = existing.id
            print(f"   ✓ Model exists: {name}")
            continue

        # Parse acceptable_formats from comma-separated string
        formats_str = row.get("acceptable_formats", "")
        acceptable_formats = [f.strip() for f in formats_str.split(",") if f.strip()] if formats_str else None

        model = Modelmetadata(
            name=name,
            model_type=parse_int(row.get("model_type", "0")) == 1,  # 0=Predictive, 1=Generative
            location=row.get("location", ""),
            acceptable_formats=acceptable_formats,
            output_context=row.get("output_context", ""),
            task=row.get("task", "")
        )
        session.add(model)
        session.flush()
        models_map[name] = model.id
        print(f"   ✅ Created model: {name}")

    session.commit()
    return models_map


def add_api_keys(session: Session, models_map: Dict[str, int], users_map: Dict[str, User]):
    """Add API keys for SAM and Annif models.

    This is REQUIRED for the evaluation service query to work.
    The query joins on Apikeymodel, so models without API keys won't appear.
    """
    print("\n📦 Creating API keys for models...")

    try:
        # Get user IDs
        instigator = users_map.get("test-audit-instigator@company.com")
        auditor = users_map.get("test-auditor@company.com")

        if not instigator or not auditor:
            print("   ⚠️  Users not found, skipping API keys")
            return

        sam_model_id = models_map.get("SAM")
        annif_model_id = models_map.get("Annif")

        api_keys = []

        # SAM model keys for both users
        if sam_model_id:
            api_keys.extend([
                {
                    "user_id": instigator.id,
                    "model_api_key": "sk-proj-sam-instigator-key",
                    "costing_policy": "pay-per-request",
                    "model_metadata_id": sam_model_id
                },
                {
                    "user_id": auditor.id,
                    "model_api_key": "sk-proj-sam-auditor-key",
                    "costing_policy": "pay-per-request",
                    "model_metadata_id": sam_model_id
                },
            ])

        # Annif model keys for both users
        if annif_model_id:
            api_keys.extend([
                {
                    "user_id": instigator.id,
                    "model_api_key": "annif-api-key-instigator",
                    "costing_policy": "pay-per-request",
                    "model_metadata_id": annif_model_id
                },
                {
                    "user_id": auditor.id,
                    "model_api_key": "annif-api-key-auditor",
                    "costing_policy": "pay-per-request",
                    "model_metadata_id": annif_model_id
                },
            ])

        for api_key_data in api_keys:
            existing = session.exec(
                select(Apikeymodel).where(
                    Apikeymodel.user_id == api_key_data["user_id"],
                    Apikeymodel.model_metadata_id == api_key_data["model_metadata_id"]
                )
            ).first()

            if not existing:
                api_key = Apikeymodel(**api_key_data)
                session.add(api_key)
                print(f"   ✅ Created API key for model {api_key_data['model_metadata_id']}")

        session.commit()
        print(f"   ✅ Created {len(api_keys)} API keys for SAM & Annif models")

    except Exception as e:
        session.rollback()
        print(f"   ❌ Failed to add API keys: {e}")
        raise


def ensure_directory_exists(directory_path: str) -> None:
    """Create directory if it doesn't exist"""
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def load_datasets_from_csv(session: Session) -> Dict[str, int]:
    """Load dataset metadata with Input/Output datasets from CSV or defaults.

    Creates:
    - DatasetMetadata (main dataset info)
    - InputDatasetMetadata (input data location and schema)
    - OutputDatasetMetadata (output data location and schema)
    - Directory structure for storage

    Returns:
        Dict mapping dataset name to id
    """
    print("\n📦 Loading datasets from CSV...")
    datasets_map = {}

    # Create directory structure for all audit storage locations
    print("   📁 Creating directory structure for audits...")
    audit_locations = [
        ("storage/audits/audit_1/input", "storage/audits/audit_1/output"),
        ("storage/audits/audit_2/input", "storage/audits/audit_2/output"),
        ("storage/audits/audit_3/input", "storage/audits/audit_3/output")
    ]

    for input_loc, output_loc in audit_locations:
        ensure_directory_exists(input_loc)
        ensure_directory_exists(output_loc)

    # Dataset definitions with full metadata
    datasets_config = [
        {
            "purpose": "The SAM dataset includes 512 audio recordings of children taking part in an attachment assessment. Each child is labelled as either 'secure' or 'insecure' based on their responses.",
            "copyright_agreement": True,
            "input": {
                "headers": {
                    "id": "integer",
                    "gender": "string",
                    "age": "integer",
                    "file": "string",
                    "true_value": "string"
                },
                "benchmark_dataset": False,
                "datatypes": {
                    "id": {"type": "int", "range": "N/A"},
                    "gender": {"type": "varchar(20)", "range": ["male", "female"]},
                    "age": {"type": "int", "range": ["P1", "P2", "P3", "P4"]},
                    "file": {"type": "varchar(100)", "range": "N/A"},
                    "true_value": {"type": "varchar(100)", "range": "N/A"},
                },
                "location": "storage/audits/audit_1/input"
            },
            "output": {
                "headers": {"id": "integer", "output": "string"},
                "benchmark_dataset": False,
                "datatypes": {
                    "id": {"type": "int", "range": "N/A"},
                    "output": {"type": "varchar(100)", "range": "N/A"}
                },
                "location": "storage/audits/audit_1/output"
            }
        },
        {
            "purpose": "Model Ingestion Data - Generative Theme ranking Model - Annif (Test Audit)",
            "copyright_agreement": True,
            "input": {
                "headers": {"id": "integer", "text": "string", "subject": "string", "true_value": "string"},
                "benchmark_dataset": False,
                "datatypes": {
                    "id": {"type": "int", "range": "N/A"},
                    "text": {"type": "text", "range": "N/A"},
                    "subject": {"type": "text", "range": "N/A"},
                    "true_value": {"type": "varchar(100)", "range": "N/A"},
                },
                "location": "storage/audits/audit_2/input"
            },
            "output": {
                "headers": {"id": "integer", "output": "string", "subjects": "string"},
                "benchmark_dataset": False,
                "datatypes": {
                    "id": {"type": "int", "range": "N/A"},
                    "output": {"type": "text", "range": "N/A"},
                    "subjects": {"type": "text", "range": "N/A"}
                },
                "location": "storage/audits/audit_2/output"
            }
        },
        {
            "purpose": "For this auditing workbench evaluation, the vocabularies or subjects will be taken from Annif called 'YSO NN ensemble English'.",
            "copyright_agreement": True,
            "input": {
                "headers": {"id": "integer", "text": "string", "subject": "string", "true_value": "string"},
                "benchmark_dataset": False,
                "datatypes": {
                    "id": {"type": "int", "range": "N/A"},
                    "text": {"type": "text", "range": "N/A"},
                    "subject": {"type": "varchar(100)", "range": "N/A"},
                    "true_value": {"type": "varchar(100)", "range": "N/A"},
                },
                "location": "storage/audits/audit_3/input"
            },
            "output": {
                "headers": {"id": "integer", "output": "string", "subjects": "string"},
                "benchmark_dataset": False,
                "datatypes": {
                    "id": {"type": "int", "range": "N/A"},
                    "output": {"type": "text", "range": "N/A"},
                    "subjects": {"type": "text", "range": "N/A"}
                },
                "location": "storage/audits/audit_3/output"
            }
        }
    ]

    for idx, ds_config in enumerate(datasets_config):
        # Create DatasetMetadata
        existing = session.exec(
            select(DatasetMetadata).where(DatasetMetadata.purpose == ds_config["purpose"])
        ).first()

        if existing:
            dataset_id = existing.id
            datasets_map[f"dataset_{idx+1}"] = dataset_id
            print(f"   ✓ Dataset exists: dataset_{idx+1}")
        else:
            dataset = DatasetMetadata(
                purpose=ds_config["purpose"],
                copyright_agreement=ds_config["copyright_agreement"]
            )
            session.add(dataset)
            session.flush()
            dataset_id = dataset.id
            datasets_map[f"dataset_{idx+1}"] = dataset_id
            print(f"   ✅ Created dataset: dataset_{idx+1}")

        # Create InputDatasetMetadata
        input_config = ds_config["input"]
        existing_input = session.exec(
            select(InputDatasetMetadata).where(InputDatasetMetadata.location == input_config["location"])
        ).first()

        if not existing_input:
            input_ds = InputDatasetMetadata(
                dataset_metadata_id=dataset_id,
                headers=input_config["headers"],
                benchmark_dataset=input_config["benchmark_dataset"],
                datatypes=input_config["datatypes"],
                location=input_config["location"]
            )
            session.add(input_ds)
            print(f"   ✅ Created input dataset metadata for dataset_{idx+1}")

        # Create OutputDatasetMetadata
        output_config = ds_config["output"]
        existing_output = session.exec(
            select(OutputDatasetMetadata).where(OutputDatasetMetadata.location == output_config["location"])
        ).first()

        if not existing_output:
            output_ds = OutputDatasetMetadata(
                dataset_metadata_id=dataset_id,
                headers=output_config["headers"],
                benchmark_dataset=output_config["benchmark_dataset"],
                datatypes=output_config["datatypes"],
                location=output_config["location"]
            )
            session.add(output_ds)
            print(f"   ✅ Created output dataset metadata for dataset_{idx+1}")

    session.commit()
    print("   ✅ Created all dataset metadata with Input/Output locations")
    return datasets_map


def load_events_from_csv(session: Session) -> Dict[str, int]:
    """Load events from CSV.

    CSV format: event_name,event_description,cause,reason,likelihood,magnitude,valence

    Returns:
        Dict mapping event name to id
    """
    print("\n📦 Loading events from CSV...")
    data = read_csv("events.csv")
    events_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default events")
        default_events = [
            {
                "name": "Prediction Correctness",
                "description": "How well does SAM predict secure or insecure attachment.",
                "cause": "Lack of diversity in data. Lack of balance in the dataset. Poor modelling.",
                "reason": "Because incorrect results could have a negative impact on children and their families.",
                "likelihood": 0.0,
                "magnitude": 0.0,
                "valence": 0.0
            },
            {
                "name": "Gender Fairness",
                "description": "Does SAM perform equally well for boys and girls?",
                "cause": "Lack of diversity in data. Lack of balance in the dataset. Poor modelling.",
                "reason": "Because gender biased predictions can exacerbate gender stereotypes.",
                "likelihood": 0.5,
                "magnitude": 0.75,
                "valence": -1.0
            },
            {
                "name": "Subject Correctness",
                "description": "How well does Annif predict appropriate subject keywords.",
                "cause": "Lack of diversity in data. Lack of balance in the dataset. Poor modelling.",
                "reason": "Because incorrect results could have a negative impact on findability.",
                "likelihood": 0.0,
                "magnitude": 0.0,
                "valence": 0.0
            },
            {
                "name": "Value of subject keywords",
                "description": "The value or perceived worth of the subject keywords raised.",
                "cause": "Lack of diversity in vocabulary. Lack of balance in the dataset. Poor modelling.",
                "reason": "Because biased subject keywords can exacerbate outdated knowledge structures.",
                "likelihood": 0.0,
                "magnitude": 0.0,
                "valence": 0.0
            }
        ]
        for event_data in default_events:
            existing = session.exec(select(Events).where(Events.name == event_data["name"])).first()
            if not existing:
                event = Events(**event_data)
                session.add(event)
                session.flush()
                events_map[event_data["name"]] = event.id
            else:
                events_map[event_data["name"]] = existing.id
        session.commit()
        return events_map

    for row in data:
        name = row.get("event_name", "").strip()
        if not name:
            continue

        existing = session.exec(select(Events).where(Events.name == name)).first()
        if existing:
            events_map[name] = existing.id
            print(f"   ✓ Event exists: {name}")
            continue

        event = Events(
            name=name,
            description=row.get("event_description", ""),
            cause=row.get("cause", ""),
            reason=row.get("reason", ""),
            likelihood=parse_float(row.get("likelihood", "0.0")),
            magnitude=parse_float(row.get("magnitude", "0.0")),
            valence=parse_float(row.get("valence", "0.0"))
        )
        session.add(event)
        session.flush()
        events_map[name] = event.id
        print(f"   ✅ Created event: {name}")

    session.commit()
    return events_map


def load_metrics_from_csv(session: Session) -> Dict[str, int]:
    """Load metrics from CSV.

    CSV format: metric_name,metric_description,reason

    Returns:
        Dict mapping metric name to id
    """
    print("\n📦 Loading metrics from CSV...")
    data = read_csv("metrics.csv")
    metrics_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default metrics")
        default_metrics = [
            {"name": "Accuracy", "description": "The proportion of correct over the total number of predictions.", "reason": "Because it is an established performance metric"},
            {"name": "Recall", "description": "The proportion of individuals with Insecure Attachment that SAM correctly predicted as Insecure.", "reason": "Because it is an established performance metric"},
            {"name": "Accuracy Parity", "description": "The difference in the Accuracy between groups.", "reason": "Because it is an established fairness metric"},
            {"name": "ANNIF Accuracy", "description": "The proportion of correct keywords over the total number of predictions.", "reason": "Because it is an established performance metric"},
            {"name": "Keyword Salience", "description": "How valuable are the subject keywords suggested to the topic catalogue or collection", "reason": "Because it is an established fairness metric"},
        ]
        for metric_data in default_metrics:
            existing = session.exec(select(Metrics).where(Metrics.name == metric_data["name"])).first()
            if not existing:
                metric = Metrics(**metric_data)
                session.add(metric)
                session.flush()
                metrics_map[metric_data["name"]] = metric.id
            else:
                metrics_map[metric_data["name"]] = existing.id
        session.commit()
        return metrics_map

    for row in data:
        name = row.get("metric_name", "").strip()
        if not name:
            continue

        existing = session.exec(select(Metrics).where(Metrics.name == name)).first()
        if existing:
            metrics_map[name] = existing.id
            print(f"   ✓ Metric exists: {name}")
            continue

        metric = Metrics(
            name=name,
            description=row.get("metric_description", ""),
            reason=row.get("reason", "")
        )
        session.add(metric)
        session.flush()
        metrics_map[name] = metric.id
        print(f"   ✅ Created metric: {name}")

    session.commit()

    # Create QuantitativeMetrics with proper formulas
    print("   📦 Creating quantitative metric types...")
    quantitative_formulas = {
        "Accuracy": "(Number of individuals who were correctly predicted to be Secure + Number of individuals who were correctly predicted to be Insecure) / Total number of predictions",
        "Recall": "Number of individuals who were correctly predicted with Insecure Attachment / Number of Individuals who actually have Insecure Attachment",
        "Accuracy Parity": "|Accuracy for boys – Accuracy for girls|",
        "ANNIF Accuracy": "Number of subject keywords that were correctly assigned / Total number of keywords that were output",
    }
    for metric_name, metric_id in metrics_map.items():
        if metric_name in quantitative_formulas:
            existing_quant = session.exec(
                select(QuantitativeMetrics).where(QuantitativeMetrics.metric_id == metric_id)
            ).first()
            if not existing_quant:
                quant_metric = QuantitativeMetrics(
                    metric_id=metric_id,
                    formula=quantitative_formulas[metric_name]
                )
                session.add(quant_metric)
    session.commit()
    print("   ✅ Created quantitative metric types")

    # Create QualitativeMetrics with proper definitions (only for Keyword Salience)
    print("   📦 Creating qualitative metric types...")
    qualitative_definitions = {
        "Keyword Salience": "Assessment of how valuable the subject keywords are to the topic, catalogue or collection",
    }
    for metric_name, metric_id in metrics_map.items():
        if metric_name in qualitative_definitions:
            existing_qual = session.exec(
                select(QualitativeMetrics).where(QualitativeMetrics.metric_id == metric_id)
            ).first()
            if not existing_qual:
                qual_metric = QualitativeMetrics(
                    metric_id=metric_id,
                    definition=qualitative_definitions[metric_name]
                )
                session.add(qual_metric)
    session.commit()
    print("   ✅ Created qualitative metric types")

    return metrics_map


def load_entities_from_csv(session: Session) -> Dict[str, int]:
    """Load entities from CSV.

    CSV format: entity_name,entity_description

    Returns:
        Dict mapping entity name to id
    """
    print("\n📦 Loading entities from CSV...")
    data = read_csv("entities.csv")
    entities_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default entities")
        default_entities = [
            {"name": "Patients", "num_individuals": 0},
            {"name": "GPs", "num_individuals": 0},
            {"name": "Family Members", "num_individuals": 0},
            {"name": "Non-English Speakers", "num_individuals": 0},
            {"name": "People with no IT equipment", "num_individuals": 0},
            {"name": "Ethnic Groups", "num_individuals": 0},
            {"name": "Communities", "num_individuals": 0},
            {"name": "Subject Vocabulary Lists", "num_individuals": 0},
            {"name": "Catalogue Users", "num_individuals": 0},
        ]
        for entity_data in default_entities:
            existing = session.exec(select(Entities).where(Entities.name == entity_data["name"])).first()
            if not existing:
                entity = Entities(**entity_data)
                session.add(entity)
                session.flush()
                entities_map[entity_data["name"]] = entity.id
            else:
                entities_map[entity_data["name"]] = existing.id
        session.commit()
        return entities_map

    for row in data:
        name = row.get("entity_name", "").strip()
        if not name:
            continue

        existing = session.exec(select(Entities).where(Entities.name == name)).first()
        if existing:
            entities_map[name] = existing.id
            print(f"   ✓ Entity exists: {name}")
            continue

        entity = Entities(
            name=name,
            num_individuals=parse_int(row.get("num_individuals", "0"))
        )
        session.add(entity)
        session.flush()
        entities_map[name] = entity.id
        print(f"   ✅ Created entity: {name}")

    session.commit()
    return entities_map


def load_underlying_features(session: Session) -> Dict[str, int]:
    """Load underlying features for SAM and other audits.

    Returns:
        Dict mapping feature name to id
    """
    print("\n📦 Loading underlying features...")
    features_map = {}

    features = [
        {"feature_name": "gender"},  # For SAM: boys/girls
        {"feature_name": "age"}
    ]

    for feature_data in features:
        existing = session.exec(
            select(UnderlyingFeatures).where(
                UnderlyingFeatures.feature_name == feature_data["feature_name"]
            )
        ).first()

        if existing:
            features_map[feature_data["feature_name"]] = existing.id
            print(f"   ✓ Feature exists: {feature_data['feature_name']}")
        else:
            feature = UnderlyingFeatures(**feature_data)
            session.add(feature)
            session.flush()
            features_map[feature_data["feature_name"]] = feature.id
            print(f"   ✅ Created feature: {feature_data['feature_name']}")

    session.commit()
    return features_map


def add_underlying_features_and_mappings(session: Session):
    """Create UnderlyingFeatures from dataset headers and map them to datasets.

    This is ESSENTIAL for the system to work properly.
    """
    print("\n🔧 Creating underlying features from dataset headers...")

    # System fields to exclude from underlying features
    EXCLUDED_FIELDS = {'id', 'true_value', 'y_pred', 'y_actual', 'file', 'output', 'subjects'}

    # Get all input datasets
    input_datasets = session.exec(select(InputDatasetMetadata)).all()

    # Extract unique feature names from all input datasets
    all_features = set()
    for input_ds in input_datasets:
        if input_ds.headers:
            # Filter out excluded fields
            dataset_features = {k for k in input_ds.headers.keys() if k not in EXCLUDED_FIELDS}
            all_features.update(dataset_features)

    # Create UnderlyingFeatures for each unique feature
    feature_map = {}
    for feature_name in all_features:
        # Check if feature already exists
        existing_feature = session.exec(
            select(UnderlyingFeatures).where(UnderlyingFeatures.feature_name == feature_name)
        ).first()

        if existing_feature:
            feature_map[feature_name] = existing_feature
            print(f"   ✓ Feature '{feature_name}' already exists (id: {existing_feature.id})")
        else:
            new_feature = UnderlyingFeatures(feature_name=feature_name)
            session.add(new_feature)
            session.flush()
            feature_map[feature_name] = new_feature
            print(f"   + Created feature '{feature_name}' (id: {new_feature.id})")

    session.commit()

    # Map features to datasets using MappingDatasetFeatures
    print("   🗺️  Mapping features to datasets...")

    datasets = session.exec(select(DatasetMetadata)).all()

    for dataset in datasets:
        # Get all headers from input datasets for this dataset
        dataset_features = set()

        # Get input headers
        input_ds = session.exec(
            select(InputDatasetMetadata).where(
                InputDatasetMetadata.dataset_metadata_id == dataset.id
            )
        ).first()

        if input_ds and input_ds.headers:
            # Filter out excluded fields
            filtered_features = {k for k in input_ds.headers.keys() if k not in EXCLUDED_FIELDS}
            dataset_features.update(filtered_features)

        # Create mappings
        for feature_name in dataset_features:
            feature = feature_map.get(feature_name)
            if not feature:
                print(f"   Warning: Feature '{feature_name}' not found in feature_map")
                continue

            # Check if mapping already exists
            existing_mapping = session.exec(
                select(MappingDatasetFeatures).where(
                    MappingDatasetFeatures.dataset_metadata_id == dataset.id,
                    MappingDatasetFeatures.underlying_feature_id == feature.id
                )
            ).first()

            if not existing_mapping:
                mapping = MappingDatasetFeatures(
                    dataset_metadata_id=dataset.id,
                    underlying_feature_id=feature.id
                )
                session.add(mapping)
                print(f"   → Mapped '{feature_name}' to dataset {dataset.id}")

    session.commit()
    print("   ✅ Features created and mapped to datasets successfully!")


def load_categories_from_csv(session: Session) -> Dict[str, int]:
    """Load event categories from CSV.

    CSV format: category_name,category_description

    Returns:
        Dict mapping category name to id
    """
    print("\n📦 Loading categories from CSV...")
    data = read_csv("categories.csv")
    categories_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default categories")
        default_categories = [
            {"event_name": "Performance", "description": "Performance-related evaluation criteria"},
            {"event_name": "Fairness", "description": "Fairness and bias evaluation criteria"},
            {"event_name": "Accuracy", "description": "Accuracy-related criteria"},
            {"event_name": "Subject Analysis", "description": "Subject and keyword analysis criteria"},
        ]
        for cat_data in default_categories:
            existing = session.exec(select(EventsCategory).where(EventsCategory.event_name == cat_data["event_name"])).first()
            if not existing:
                category = EventsCategory(**cat_data)
                session.add(category)
                session.flush()
                categories_map[cat_data["event_name"]] = category.id
            else:
                categories_map[cat_data["event_name"]] = existing.id
        session.commit()
        return categories_map

    for row in data:
        name = row.get("category_name", "").strip()
        if not name:
            continue

        existing = session.exec(select(EventsCategory).where(EventsCategory.event_name == name)).first()
        if existing:
            categories_map[name] = existing.id
            print(f"   ✓ Category exists: {name}")
            continue

        category = EventsCategory(
            event_name=name,
            description=row.get("category_description", "")
        )
        session.add(category)
        session.flush()
        categories_map[name] = category.id
        print(f"   ✅ Created category: {name}")

    session.commit()
    return categories_map


def load_target_features_from_csv(session: Session) -> Dict[str, int]:
    """Load target features from CSV.

    CSV format: target_feature,function_name

    Returns:
        Dict mapping target feature to id
    """
    print("\n📦 Loading target features from CSV...")
    data = read_csv("target_features.csv")
    features_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default target features")
        default_features = [
            {"target_feature": "Accuracy", "function_name": "accuracy"},
            {"target_feature": "Recall", "function_name": "recall"}
        ]
        for feature_data in default_features:
            existing = session.exec(select(TargetFeatures).where(TargetFeatures.target_feature == feature_data["target_feature"])).first()
            if not existing:
                feature = TargetFeatures(**feature_data)
                session.add(feature)
                session.flush()
                features_map[feature_data["target_feature"]] = feature.id
            else:
                features_map[feature_data["target_feature"]] = existing.id
        session.commit()
        return features_map

    for row in data:
        name = row.get("target_feature", "").strip()
        if not name:
            continue

        existing = session.exec(select(TargetFeatures).where(TargetFeatures.target_feature == name)).first()
        if existing:
            features_map[name] = existing.id
            print(f"   ✓ Target feature exists: {name}")
            continue

        feature = TargetFeatures(
            target_feature=name,
            function_name=row.get("function_name", name.lower())
        )
        session.add(feature)
        session.flush()
        features_map[name] = feature.id
        print(f"   ✅ Created target feature: {name}")

    session.commit()
    return features_map


# ============================================================================
# Audits and Mappings
# ============================================================================

def load_audits_from_csv(
    session: Session,
    apps_map: Dict[str, int]
) -> Dict[str, int]:
    """Load audits from CSV.

    CSV format: name,description,application

    Returns:
        Dict mapping audit name to id
    """
    print("\n📦 Loading audits from CSV...")
    data = read_csv("audits.csv")
    audits_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default audit")
        app_id = list(apps_map.values())[0] if apps_map else None
        existing = session.exec(select(Audit).where(Audit.name == "Test Audit")).first()
        if not existing:
            audit = Audit(
                name="Test Audit",
                description="Default test audit",
                application="Test Application"
            )
            session.add(audit)
            session.flush()
            audits_map["Test Audit"] = audit.id

            # Create audit-application mapping
            if app_id:
                mapping = MappingAuditApplication(
                    audit_id=audit.id,
                    application_id=app_id
                )
                session.add(mapping)
        else:
            audits_map["Test Audit"] = existing.id
        session.commit()
        return audits_map

    for row in data:
        name = row.get("name", "").strip()
        if not name:
            continue

        existing = session.exec(select(Audit).where(Audit.name == name)).first()
        if existing:
            audits_map[name] = existing.id
            print(f"   ✓ Audit exists: {name}")
            continue

        app_name = row.get("application", "")
        audit = Audit(
            name=name,
            description=row.get("description", ""),
            application=app_name
        )
        session.add(audit)
        session.flush()
        audits_map[name] = audit.id
        print(f"   ✅ Created audit: {name}")

        # Create audit-application mapping
        if app_name in apps_map:
            existing_mapping = session.exec(
                select(MappingAuditApplication).where(
                    MappingAuditApplication.audit_id == audit.id,
                    MappingAuditApplication.application_id == apps_map[app_name]
                )
            ).first()
            if not existing_mapping:
                mapping = MappingAuditApplication(
                    audit_id=audit.id,
                    application_id=apps_map[app_name]
                )
                session.add(mapping)

    session.commit()
    return audits_map


def create_audit_user_mappings(
    session: Session,
    users_map: Dict[str, User],
    roles_map: Dict[str, int],
    audits_map: Dict[str, int]
) -> Dict[str, int]:
    """Create mappings between users and audits with roles.

    Returns:
        Dict mapping (user_email, audit_name) to user_audit_id
    """
    print("\n📦 Creating audit-user mappings...")
    user_audit_map = {}

    # Get role assignments from test accounts config
    for account in TEST_ACCOUNTS:
        email = account["email"].lower()
        role = account["role"]

        user = users_map.get(email)
        role_id = roles_map.get(role)

        if not user or not role_id:
            continue

        # Map user to all audits
        for audit_name, audit_id in audits_map.items():
            key = (email, audit_name)

            existing = session.exec(
                select(MappingAuditUser).where(
                    MappingAuditUser.audit_id == audit_id,
                    MappingAuditUser.user_id == user.id,
                    MappingAuditUser.roles_id == role_id
                )
            ).first()

            if existing:
                user_audit_map[key] = existing.id
                print(f"   ✓ Mapping exists: {email} -> {audit_name} ({role})")
                continue

            mapping = MappingAuditUser(
                audit_id=audit_id,
                user_id=user.id,
                roles_id=role_id
            )
            session.add(mapping)
            session.flush()
            user_audit_map[key] = mapping.id
            print(f"   ✅ Created mapping: {email} -> {audit_name} ({role})")

            # Create audit outcome for this user
            existing_outcome = session.exec(
                select(MappingAuditOutcomeUser).where(
                    MappingAuditOutcomeUser.audit_id == audit_id,
                    MappingAuditOutcomeUser.user_audit_id == mapping.id
                )
            ).first()

            if not existing_outcome:
                outcome = MappingAuditOutcomeUser(
                    audit_id=audit_id,
                    user_audit_id=mapping.id,
                    status=0,
                    recommendation=0,
                    notes=""
                )
                session.add(outcome)

    session.commit()
    return user_audit_map


def create_audit_model_mappings(
    session: Session,
    audits_map: Dict[str, int],
    models_map: Dict[str, int]
):
    """Create audit-model mappings from CSV or defaults."""
    print("\n📦 Creating audit-model mappings...")
    data = read_csv("audit_models.csv")

    if not data:
        # Default: map all audits to first model
        model_id = list(models_map.values())[0] if models_map else None
        if model_id:
            for audit_name, audit_id in audits_map.items():
                existing = session.exec(
                    select(MappingAuditModel).where(
                        MappingAuditModel.audit_id == audit_id
                    )
                ).first()
                if not existing:
                    mapping = MappingAuditModel(
                        audit_id=audit_id,
                        model_id=model_id
                    )
                    session.add(mapping)
                    print(f"   ✅ Mapped audit '{audit_name}' to model")
        session.commit()
        return

    # CSV format: audit_name,model_name
    for row in data:
        audit_name = row.get("audit_name", "").strip()
        model_name = row.get("model_name", "").strip()

        audit_id = audits_map.get(audit_name)
        model_id = models_map.get(model_name)

        if not audit_id or not model_id:
            continue

        existing = session.exec(
            select(MappingAuditModel).where(
                MappingAuditModel.audit_id == audit_id,
                MappingAuditModel.model_id == model_id
            )
        ).first()

        if not existing:
            mapping = MappingAuditModel(
                audit_id=audit_id,
                model_id=model_id
            )
            session.add(mapping)
            print(f"   ✅ Mapped audit '{audit_name}' to model '{model_name}'")

    session.commit()


def create_event_metric_mappings(
    session: Session,
    events_map: Dict[str, int],
    metrics_map: Dict[str, int],
    user_audit_map: Dict[tuple, int],
    audits_map: Dict[str, int]
):
    """Create event-metric mappings with thresholds for audit instigator.

    Creates SPECIFIC event-metric pairs with correct thresholds:
    - SAM: Prediction Correctness -> Accuracy (70%), Recall (60%)
           Gender Fairness -> Accuracy Parity (5%)
    - ANNIF: Subject Correctness -> ANNIF Accuracy (80%)
             Value of subject keywords -> Keyword Salience (Of Worth)
    """
    print("\n📦 Creating event-metric mappings...")
    data = read_csv("event_metrics.csv")

    instigator_email = "test-audit-instigator@company.com"

    # Define specific event-metric mappings with thresholds
    sam_mappings = [
        ("Prediction Correctness", "Accuracy", "70"),
        ("Prediction Correctness", "Recall", "60"),
        ("Gender Fairness", "Accuracy Parity", "5"),
    ]
    annif_mappings = [
        ("Subject Correctness", "ANNIF Accuracy", "80"),
        ("Value of subject keywords", "Keyword Salience", "Of Worth"),
    ]

    if not data:
        print("   ⚠️  No CSV found, creating default mappings")
        # Create default mappings for audit instigator only
        for audit_name, audit_id in audits_map.items():
            key = (instigator_email, audit_name)
            user_audit_id = user_audit_map.get(key)
            if not user_audit_id:
                continue

            # Determine which mappings to create
            if "SAM" in audit_name:
                mappings_to_create = sam_mappings
            else:
                mappings_to_create = annif_mappings

            for event_name, metric_name, threshold in mappings_to_create:
                event_id = events_map.get(event_name)
                metric_id = metrics_map.get(metric_name)

                if not event_id or not metric_id:
                    continue

                # Check existence
                existing = session.exec(
                    select(MappingMetricsEvents).where(
                        MappingMetricsEvents.metric_id == metric_id,
                        MappingMetricsEvents.event_id == event_id,
                        MappingMetricsEvents.user_audit_id == user_audit_id
                    )
                ).first()

                if existing:
                    continue

                # Create metric value
                metric_value = MetricsValues(
                    output={},
                    threshold=threshold
                )
                session.add(metric_value)
                session.flush()

                # Create mapping
                mapping = MappingMetricsEvents(
                    metric_id=metric_id,
                    event_id=event_id,
                    user_audit_id=user_audit_id,
                    values_id=metric_value.id
                )
                session.add(mapping)
                print(f"   ✅ Created: {event_name} -> {metric_name} (threshold: {threshold})")

        session.commit()
        return

    # CSV format: audit_name,event_name,metric_name,threshold
    for row in data:
        audit_name = row.get("audit_name", "").strip()
        event_name = row.get("event_name", "").strip()
        metric_name = row.get("metric_name", "").strip()
        threshold = row.get("threshold", "70")

        key = (instigator_email, audit_name)
        user_audit_id = user_audit_map.get(key)
        event_id = events_map.get(event_name)
        metric_id = metrics_map.get(metric_name)

        if not all([user_audit_id, event_id, metric_id]):
            continue

        existing = session.exec(
            select(MappingMetricsEvents).where(
                MappingMetricsEvents.metric_id == metric_id,
                MappingMetricsEvents.event_id == event_id,
                MappingMetricsEvents.user_audit_id == user_audit_id
            )
        ).first()

        if existing:
            print(f"   ✓ Mapping exists: {event_name} -> {metric_name}")
            continue

        # Create metric value
        metric_value = MetricsValues(
            output={},
            threshold=threshold
        )
        session.add(metric_value)
        session.flush()

        # Create mapping
        mapping = MappingMetricsEvents(
            metric_id=metric_id,
            event_id=event_id,
            user_audit_id=user_audit_id,
            values_id=metric_value.id
        )
        session.add(mapping)
        print(f"   ✅ Created mapping: {event_name} -> {metric_name} (threshold: {threshold})")

    session.commit()


def create_events_audit_status(
    session: Session,
    events_map: Dict[str, int],
    metrics_map: Dict[str, int],
    audits_map: Dict[str, int],
    user_audit_map: Dict[tuple, int]
):
    """Create events audit status mappings for audit instigator ONLY.

    This matches the old migration behavior where MappingEventsAuditStatus
    is only created for the audit instigator, not the auditor.

    Creates one MappingEventsAuditStatus per (event, metric) pair that matches
    MappingAuditPipelineEvents, so the evaluation service join works correctly.
    """
    print("\n📦 Creating events audit status...")

    instigator_email = "test-audit-instigator@company.com"

    # Define specific event-metric mappings (must match create_audit_pipelines)
    # SAM: Prediction Correctness -> Accuracy, Recall; Gender Fairness -> Accuracy Parity
    # ANNIF: Subject Correctness -> ANNIF Accuracy; Value of subject keywords -> Keyword Salience
    sam_event_metrics = [
        ("Prediction Correctness", "Accuracy"),
        ("Prediction Correctness", "Recall"),
        ("Gender Fairness", "Accuracy Parity"),
    ]
    annif_event_metrics = [
        ("Subject Correctness", "ANNIF Accuracy"),
        ("Value of subject keywords", "Keyword Salience"),
    ]

    for audit_name, audit_id in audits_map.items():
        key = (instigator_email, audit_name)
        user_audit_id = user_audit_map.get(key)
        if not user_audit_id:
            continue

        # Determine which event-metric pairs to use
        if "SAM" in audit_name:
            event_metric_pairs = sam_event_metrics
        else:
            event_metric_pairs = annif_event_metrics

        # Create status mappings for each event-metric pair
        for event_name, metric_name in event_metric_pairs:
            event_id = events_map.get(event_name)
            metric_id = metrics_map.get(metric_name)

            if not event_id or not metric_id:
                continue

            existing = session.exec(
                select(MappingEventsAuditStatus).where(
                    MappingEventsAuditStatus.event_id == event_id,
                    MappingEventsAuditStatus.audit_id == audit_id,
                    MappingEventsAuditStatus.metric_id == metric_id,
                    MappingEventsAuditStatus.user_audit_id == user_audit_id
                )
            ).first()

            if existing:
                continue

            mapping = MappingEventsAuditStatus(
                event_id=event_id,
                audit_id=audit_id,
                metric_id=metric_id,
                user_audit_id=user_audit_id,
                recommendation=0,
                notes=""
            )
            session.add(mapping)

    session.commit()
    print("   ✅ Created events audit status mappings (audit instigator only)")


def create_audit_pipelines(
    session: Session,
    audits_map: Dict[str, int],
    models_map: Dict[str, int],
    datasets_map: Dict[str, int],
    events_map: Dict[str, int],
    metrics_map: Dict[str, int],
    user_audit_map: Dict[tuple, int]
):
    """Create audit pipelines and related mappings.

    Creates:
    - AuditPipeline records
    - MappingAuditPipelineAudit (links pipeline to audit)
    - MappingModelDatasetAudit (correct model/dataset per audit)
    - MappingAuditPipelineEvents (event-metric pairs for BOTH users)
    """
    print("\n📦 Creating audit pipelines...")

    instigator_email = "test-audit-instigator@company.com"
    auditor_email = "test-auditor@company.com"

    # Define audit-specific model/dataset mappings
    # SAM Audit -> SAM model (id 1), dataset 1
    # Annif audits -> Annif model (id 2), datasets 2 and 3
    sam_model_id = models_map.get("SAM")
    annif_model_id = models_map.get("Annif")

    # Define specific event-metric mappings for each audit type
    # SAM: Prediction Correctness -> Accuracy, Recall; Gender Fairness -> Accuracy Parity
    # ANNIF: Subject Correctness -> ANNIF Accuracy; Value of subject keywords -> Keyword Salience
    sam_event_metrics = [
        ("Prediction Correctness", "Accuracy"),
        ("Prediction Correctness", "Recall"),
        ("Gender Fairness", "Accuracy Parity"),
    ]
    annif_event_metrics = [
        ("Subject Correctness", "ANNIF Accuracy"),
        ("Value of subject keywords", "Keyword Salience"),
    ]

    audit_idx = 0
    for audit_name, audit_id in audits_map.items():
        # Check if pipeline exists
        existing = session.exec(select(AuditPipeline).where(AuditPipeline.id == audit_id)).first()
        if not existing:
            pipeline = AuditPipeline(id=audit_id)
            session.add(pipeline)
            session.flush()
            print(f"   ✅ Created pipeline for audit: {audit_name}")

        # Create MappingAuditPipelineAudit
        existing_mapping = session.exec(
            select(MappingAuditPipelineAudit).where(
                MappingAuditPipelineAudit.audit_pipeline == audit_id,
                MappingAuditPipelineAudit.audit_id == audit_id
            )
        ).first()
        if not existing_mapping:
            mapping = MappingAuditPipelineAudit(
                audit_pipeline=audit_id,
                audit_id=audit_id
            )
            session.add(mapping)

        # Create MappingModelDatasetAudit with correct model/dataset per audit
        if "SAM" in audit_name:
            model_id = sam_model_id
            dataset_id = datasets_map.get("dataset_1")  # SAM dataset
        else:
            model_id = annif_model_id
            # Annif Test -> dataset_2, Annif Audit -> dataset_3
            if "Test" in audit_name:
                dataset_id = datasets_map.get("dataset_2")
            else:
                dataset_id = datasets_map.get("dataset_3")

        if model_id and dataset_id:
            existing_mda = session.exec(
                select(MappingModelDatasetAudit).where(
                    MappingModelDatasetAudit.auditpipeline == audit_id
                )
            ).first()
            if not existing_mda:
                mda = MappingModelDatasetAudit(
                    auditpipeline=audit_id,
                    model_id=model_id,
                    dataset_id=dataset_id
                )
                session.add(mda)
                print(f"   ✅ Mapped audit {audit_name} to model {model_id}, dataset {dataset_id}")

        # Determine which event-metric pairs to create
        # if "SAM" in audit_name:
        #     event_metric_pairs = sam_event_metrics
        # else:
        #     event_metric_pairs = annif_event_metrics

        # # Create MappingAuditPipelineEvents for BOTH users (instigator and auditor)
        # # This is required for the evaluation service to find pipelines
        # for email in [instigator_email, auditor_email]:
        #     key = (email, audit_name)
        #     user_audit_id = user_audit_map.get(key)
        #     if not user_audit_id:
        #         continue

        #     for event_name, metric_name in event_metric_pairs:
        #         event_id = events_map.get(event_name)
        #         metric_id = metrics_map.get(metric_name)

        #         if not event_id or not metric_id:
        #             continue

        #         existing_ape = session.exec(
        #             select(MappingAuditPipelineEvents).where(
        #                 MappingAuditPipelineEvents.audit_pipeline == audit_id,
        #                 MappingAuditPipelineEvents.event_id == event_id,
        #                 MappingAuditPipelineEvents.metric_id == metric_id,
        #                 MappingAuditPipelineEvents.user_audit_id == user_audit_id
        #             )
        #         ).first()

        #         if not existing_ape:
        #             ape = MappingAuditPipelineEvents(
        #                 audit_pipeline=audit_id,
        #                 user_audit_id=user_audit_id,
        #                 event_id=event_id,
        #                 metric_id=metric_id
        #             )
        #             session.add(ape)

        # audit_idx += 1

    session.commit()
    print("   ✅ Created audit pipelines and mappings (including MappingAuditPipelineEvents)")


def create_user_events_mappings(
    session: Session,
    events_map: Dict[str, int],
    user_audit_map: Dict[tuple, int],
    audits_map: Dict[str, int]
):
    """Create MappingUserEvents for audit instigator only.

    Auditors see events through the audit instigator's mappings
    (via AuditRoles.id == 1 check in get_accessible_event_ids).

    Only creates mappings for events that belong to the specific audit
    based on AUDIT_EVENT_MAPPING configuration.
    """
    print("\n📦 Creating user-events mappings...")

    instigator_email = "test-audit-instigator@company.com"

    for audit_name, audit_id in audits_map.items():
        key = (instigator_email, audit_name)
        user_audit_id = user_audit_map.get(key)
        if not user_audit_id:
            continue

        # Get only events that belong to this audit
        audit_events = get_events_for_audit(audit_name, events_map)

        for event_name, event_id in audit_events.items():
            existing = session.exec(
                select(MappingUserEvents).where(
                    MappingUserEvents.event_id == event_id,
                    MappingUserEvents.user_audit_id == user_audit_id
                )
            ).first()

            if existing:
                continue

            mapping = MappingUserEvents(
                event_id=event_id,
                user_audit_id=user_audit_id
            )
            session.add(mapping)

    session.commit()
    print("   ✅ Created user-events mappings for audit instigator")


def create_event_types(
    session: Session,
    events_map: Dict[str, int],
    user_audit_map: Dict[tuple, int],
    audits_map: Dict[str, int]
):
    """Create EventType records for events created by audit instigator.

    This marks events as NOT user-defined (is_user_defined=False) since they
    were created by the audit instigator, not by the current auditor user.
    The created_by_user_id is set to the audit instigator's user_audit_id.
    """
    print("\n📦 Creating event types...")

    instigator_email = "test-audit-instigator@company.com"

    for audit_name, audit_id in audits_map.items():
        key = (instigator_email, audit_name)
        user_audit_id = user_audit_map.get(key)
        if not user_audit_id:
            continue

        # Get only events that belong to this audit
        audit_events = get_events_for_audit(audit_name, events_map)

        for event_name, event_id in audit_events.items():
            existing = session.exec(
                select(EventType).where(EventType.event_id == event_id)
            ).first()

            if existing:
                continue

            event_type = EventType(
                event_id=event_id,
                is_user_defined=False,  # Created by audit instigator, not user
                created_by_user_id=user_audit_id,  # Audit instigator's user_audit_id
                is_template=False,
                category=None
            )
            session.add(event_type)

    session.commit()
    print("   ✅ Created event types for audit instigator events")


def add_metrics_underlying_features(session: Session, metrics_map: Dict[str, int]):
    """Add metric underlying features for SAM Accuracy Parity metric.

    This function needs to run AFTER mappings create MetricValues.
    Links Accuracy Parity metric values to gender underlying feature.
    """
    print("\n📦 Creating metrics underlying features...")

    try:
        # Get SAM Accuracy Parity metric
        accuracy_parity_id = metrics_map.get("Accuracy Parity")
        if not accuracy_parity_id:
            print("   ⚠️  Accuracy Parity metric not found, skipping")
            return

        # Find MetricValues linked to Accuracy Parity metric through MappingMetricsEvents
        accuracy_parity_values = session.exec(
            select(MetricsValues)
            .join(MappingMetricsEvents, MappingMetricsEvents.values_id == MetricsValues.id)
            .where(MappingMetricsEvents.metric_id == accuracy_parity_id)
        ).all()

        if not accuracy_parity_values:
            print("   ⚠️  No MetricValues found for Accuracy Parity, skipping")
            return

        # Query for gender feature by NAME
        gender_feature = session.exec(
            select(UnderlyingFeatures).where(UnderlyingFeatures.feature_name == "gender")
        ).first()

        if not gender_feature:
            print("   ⚠️  Gender feature not found, skipping")
            return

        # Link each Accuracy Parity MetricValue to gender feature
        for metric_value in accuracy_parity_values:
            existing_gender = session.exec(
                select(MetricsUnderlyingFeatures).where(
                    MetricsUnderlyingFeatures.metric_values_id == metric_value.id,
                    MetricsUnderlyingFeatures.feature_id == gender_feature.id
                )
            ).first()

            if not existing_gender:
                gender_mapping = MetricsUnderlyingFeatures(
                    metric_values_id=metric_value.id,
                    feature_id=gender_feature.id,
                    ranges=["male", "female"]
                )
                session.add(gender_mapping)

        session.commit()
        print(f"   ✅ Created underlying features for {len(accuracy_parity_values)} Accuracy Parity metric values")

    except Exception as e:
        session.rollback()
        print(f"   ❌ Failed to add metric underlying features: {e}")
        raise


def add_metrics_scalepoints(session: Session, metrics_map: Dict[str, int]):
    """Add scale points for ANNIF Keyword Salience metric.

    Keyword Salience is qualitative and needs scale points.
    """
    print("\n📦 Creating metrics scale points...")

    try:
        keyword_salience_id = metrics_map.get("Keyword Salience")
        if not keyword_salience_id:
            print("   ⚠️  Keyword Salience metric not found, skipping")
            return

        # Find MetricValues linked to Keyword Salience metric
        keyword_salience_values = session.exec(
            select(MetricsValues)
            .join(MappingMetricsEvents, MappingMetricsEvents.values_id == MetricsValues.id)
            .where(MappingMetricsEvents.metric_id == keyword_salience_id)
        ).all()

        if not keyword_salience_values:
            print("   ⚠️  No MetricValues found for Keyword Salience, skipping")
            return

        # Scale points for Keyword Salience qualitative assessment
        scale_points_data = {
            "Harmful": -1.0,
            "Not Valuable": -0.5,
            "Unable to Answer": 0.0,
            "Of Worth": 0.5,
            "Valuable": 1.0
        }

        total_added = 0
        for metric_value in keyword_salience_values:
            existing = session.exec(
                select(MetricsScalePoints).where(
                    MetricsScalePoints.metric_values_id == metric_value.id
                )
            ).first()

            if not existing:
                scale_point = MetricsScalePoints(
                    metric_values_id=metric_value.id,
                    scale_points=scale_points_data
                )
                session.add(scale_point)
                total_added += 1

        session.commit()
        print(f"   ✅ Created {total_added} scale points for Keyword Salience metric")

    except Exception as e:
        session.rollback()
        print(f"   ❌ Failed to add scale points: {e}")
        raise


def add_metrics_target_features(session: Session, metrics_map: Dict[str, int]):
    """Add target features mapping for SAM and ANNIF metrics.

    Mappings:
    - SAM Accuracy -> Accuracy target feature
    - SAM Recall -> Recall target feature
    - SAM Accuracy Parity -> Accuracy target feature
    - ANNIF Accuracy -> Keyword Accuracy target feature
    """
    print("\n📦 Creating metrics target features...")

    try:
        target_features = session.exec(select(TargetFeatures)).all()
        if not target_features:
            print("   ⚠️  No target features found, skipping")
            return

        # Find target features by name
        accuracy_target = next((tf for tf in target_features if tf.target_feature == "Accuracy"), None)
        recall_target = next((tf for tf in target_features if tf.target_feature == "Recall"), None)
        keyword_accuracy_target = next((tf for tf in target_features if tf.target_feature == "Keyword Accuracy"), None)

        # Mapping configuration: (metric_name, target_feature)
        metric_target_mappings = [
            ("Accuracy", accuracy_target),
            ("Recall", recall_target or accuracy_target),
            ("Accuracy Parity", accuracy_target),
            ("ANNIF Accuracy", keyword_accuracy_target or accuracy_target),
        ]

        total_mapped = 0
        for metric_name, target_feature in metric_target_mappings:
            if not target_feature:
                continue

            metric_id = metrics_map.get(metric_name)
            if not metric_id:
                continue

            # Find MetricValues linked to this metric
            metric_values = session.exec(
                select(MetricsValues)
                .join(MappingMetricsEvents, MappingMetricsEvents.values_id == MetricsValues.id)
                .where(MappingMetricsEvents.metric_id == metric_id)
            ).all()

            for metric_value in metric_values:
                existing = session.exec(
                    select(MetricsTargetFeatures).where(
                        MetricsTargetFeatures.metric_values_id == metric_value.id
                    )
                ).first()

                if not existing:
                    mapping = MetricsTargetFeatures(
                        metric_values_id=metric_value.id,
                        target_feature_id=target_feature.id,
                    )
                    session.add(mapping)
                    total_mapped += 1

        session.commit()
        print(f"   ✅ Created {total_mapped} target feature mappings")

    except Exception as e:
        session.rollback()
        print(f"   ❌ Failed to add metric target features: {e}")
        raise


# ============================================================================
# Taxonomy Functions
# ============================================================================

def load_taxonomy_groups_from_csv(session: Session) -> Dict[str, int]:
    """Load taxonomy groups from CSV.

    CSV format: taxonomy_name,taxonomy_description,reason

    Returns:
        Dict mapping taxonomy name to id
    """
    print("\n📦 Loading taxonomy groups from CSV...")
    data = read_csv("taxonomy_groups.csv")
    taxonomy_map = {}

    if not data:
        print("   ⚠️  No CSV found, creating default taxonomy groups")
        default_taxonomies = [
            {"event_name": "Discrimination Hate Speech and Exclusion", "description": "", "reason": "Laura Weidinger 2022"},
            {"event_name": "Information Hazards", "description": "", "reason": "Laura Weidinger 2022"},
            {"event_name": "Misinformation Harms", "description": "", "reason": "Laura Weidinger 2022"},
            {"event_name": "Malicious Uses", "description": "", "reason": "Laura Weidinger 2022"},
            {"event_name": "Human-Computer Interaction Harms", "description": "", "reason": "Laura Weidinger 2022"},
            {"event_name": "Environmental and Socioeconomic harms", "description": "", "reason": "Laura Weidinger 2022"},
        ]
        for taxonomy_data in default_taxonomies:
            existing = session.exec(select(TaxonomyGroups).where(TaxonomyGroups.event_name == taxonomy_data["event_name"])).first()
            if not existing:
                taxonomy = TaxonomyGroups(**taxonomy_data)
                session.add(taxonomy)
                session.flush()
                taxonomy_map[taxonomy_data["event_name"]] = taxonomy.id
            else:
                taxonomy_map[taxonomy_data["event_name"]] = existing.id
        session.commit()
        return taxonomy_map

    for row in data:
        name = row.get("taxonomy_name", "").strip()
        if not name:
            continue

        existing = session.exec(select(TaxonomyGroups).where(TaxonomyGroups.event_name == name)).first()
        if existing:
            taxonomy_map[name] = existing.id
            print(f"   ✓ Taxonomy exists: {name}")
            continue

        taxonomy = TaxonomyGroups(
            event_name=name,
            description=row.get("taxonomy_description", ""),
            reason=row.get("reason", "")
        )
        session.add(taxonomy)
        session.flush()
        taxonomy_map[name] = taxonomy.id
        print(f"   ✅ Created taxonomy: {name}")

    session.commit()
    return taxonomy_map


def load_taxonomy_mappings_from_csv(session: Session):
    """Load taxonomy-category mappings from CSV.

    CSV format: taxonomy_id,category_id
    """
    print("\n📦 Loading taxonomy mappings from CSV...")
    data = read_csv("taxonomy_mappings.csv")

    if not data:
        print("   ⚠️  No CSV found, skipping taxonomy mappings")
        return

    for row in data:
        taxonomy_id = parse_int(row.get("taxonomy_id", "0"))
        category_id = parse_int(row.get("category_id", "0"))

        if not taxonomy_id or not category_id:
            continue

        existing = session.exec(
            select(MappingTaxonomyCategory).where(
                MappingTaxonomyCategory.taxonomy_id == taxonomy_id,
                MappingTaxonomyCategory.category_id == category_id
            )
        ).first()

        if not existing:
            mapping = MappingTaxonomyCategory(
                taxonomy_id=taxonomy_id,
                category_id=category_id
            )
            session.add(mapping)

    session.commit()
    print("   ✅ Created taxonomy-category mappings")


# ============================================================================
# Additional Mapping Functions
# ============================================================================

def create_event_entity_mappings(
    session: Session,
    events_map: Dict[str, int],
    entities_map: Dict[str, int],
    audits_map: Dict[str, int],
    user_audit_map: Dict[tuple, int]
):
    """Create event-entity mappings from audit instigator.

    Entity Assignment:
    - SAM Audit: First 5 entities (Patients, GPs, Family Members, Non-English Speakers, People with no IT equipment)
    - ANNIF Audits: Next 4 entities (Ethnic Groups, Communities, Subject Vocabulary Lists, Catalogue Users)
    """
    print("\n📦 Creating event-entity mappings...")

    instigator_email = "test-audit-instigator@company.com"

    # Define audit-specific entity assignments
    sam_entities = ["Patients", "GPs", "Family Members", "Non-English Speakers", "People with no IT equipment"]
    annif_entities = ["Ethnic Groups", "Communities", "Subject Vocabulary Lists", "Catalogue Users"]

    for audit_name, audit_id in audits_map.items():
        key = (instigator_email, audit_name)
        user_audit_id = user_audit_map.get(key)
        if not user_audit_id:
            continue

        # Get events for this audit
        audit_events = get_events_for_audit(audit_name, events_map)

        # Determine which entities to use
        if "SAM" in audit_name:
            audit_entities = sam_entities
        else:
            audit_entities = annif_entities

        for event_name, event_id in audit_events.items():
            for entity_name in audit_entities:
                entity_id = entities_map.get(entity_name)
                if not entity_id:
                    continue

                existing = session.exec(
                    select(MappingEventsEntities).where(
                        MappingEventsEntities.audit_id == audit_id,
                        MappingEventsEntities.event_id == event_id,
                        MappingEventsEntities.entity_id == entity_id
                    )
                ).first()

                if not existing:
                    mapping = MappingEventsEntities(
                        audit_id=audit_id,
                        user_audit_id=user_audit_id,
                        event_id=event_id,
                        entity_id=entity_id
                    )
                    session.add(mapping)

    session.commit()
    print("   ✅ Created event-entity mappings")


def create_event_category_mappings(
    session: Session,
    events_map: Dict[str, int],
    categories_map: Dict[str, int]
):
    """Create event-category mappings."""
    print("\n📦 Creating event-category mappings...")

    events_list = list(events_map.keys())
    categories_list = list(categories_map.values())

    if not categories_list:
        print("   ⚠️  No categories found, skipping")
        return

    for i, (event_name, event_id) in enumerate(events_map.items()):
        # Assign each event to a category (cycling through categories)
        category_id = categories_list[i % len(categories_list)]

        existing = session.exec(
            select(MappingEventsCategory).where(
                MappingEventsCategory.event_id == event_id
            )
        ).first()

        if not existing:
            mapping = MappingEventsCategory(
                event_id=event_id,
                category_id=category_id
            )
            session.add(mapping)

    session.commit()
    print("   ✅ Created event-category mappings")


def create_user_metrics_mappings(
    session: Session,
    metrics_map: Dict[str, int],
    audits_map: Dict[str, int],
    user_audit_map: Dict[tuple, int]
):
    """Create user-metrics mappings for audit instigator.

    SAM metrics (Accuracy, Recall, Accuracy Parity) for SAM Audit
    ANNIF metrics (ANNIF Accuracy, Keyword Salience) for ANNIF Audits
    """
    print("\n📦 Creating user-metrics mappings...")

    instigator_email = "test-audit-instigator@company.com"

    # Define audit-specific metrics
    sam_metrics = ["Accuracy", "Recall", "Accuracy Parity"]
    annif_metrics = ["ANNIF Accuracy", "Keyword Salience"]

    for audit_name, audit_id in audits_map.items():
        key = (instigator_email, audit_name)
        user_audit_id = user_audit_map.get(key)
        if not user_audit_id:
            continue

        # Determine which metrics to use
        if "SAM" in audit_name:
            audit_metrics = sam_metrics
        else:
            audit_metrics = annif_metrics

        for metric_name in audit_metrics:
            metric_id = metrics_map.get(metric_name)
            if not metric_id:
                continue

            existing = session.exec(
                select(MappingUserMetrics).where(
                    MappingUserMetrics.user_audit_id == user_audit_id,
                    MappingUserMetrics.metric_id == metric_id
                )
            ).first()

            if not existing:
                mapping = MappingUserMetrics(
                    user_audit_id=user_audit_id,
                    metric_id=metric_id
                )
                session.add(mapping)

    session.commit()
    print("   ✅ Created user-metrics mappings")


# ============================================================================
# Main Migration Function
# ============================================================================

def run_csv_migration(session: Session):
    """Run the complete CSV-based migration.

    This creates a minimal setup with two test accounts and loads
    all other data from CSV files.
    """
    print("\n" + "=" * 60)
    print("🚀 Starting CSV-based v4 Migration")
    print("=" * 60)

    # Ensure seed data directory exists
    SEED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Create roles first
    roles_map = add_audit_roles(session)

    # 2. Create test users
    users_map = add_test_users(session)

    # 3. Load base data from CSV
    apps_map = load_applications_from_csv(session)
    models_map = load_models_from_csv(session)

    # 3.5 Create API keys for models (REQUIRED for evaluation service)
    add_api_keys(session, models_map, users_map)

    datasets_map = load_datasets_from_csv(session)  # Creates DatasetMetadata, InputDatasetMetadata, OutputDatasetMetadata
    events_map = load_events_from_csv(session)
    metrics_map = load_metrics_from_csv(session)
    entities_map = load_entities_from_csv(session)
    underlying_features_map = load_underlying_features(session)
    categories_map = load_categories_from_csv(session)
    features_map = load_target_features_from_csv(session)
    taxonomy_map = load_taxonomy_groups_from_csv(session)
    load_taxonomy_mappings_from_csv(session)

    # 4. Create underlying features from dataset headers and map them
    add_underlying_features_and_mappings(session)

    # 5. Load audits
    audits_map = load_audits_from_csv(session, apps_map)

    # 6. Create user-audit mappings
    user_audit_map = create_audit_user_mappings(session, users_map, roles_map, audits_map)

    # 7. Create audit-model mappings
    create_audit_model_mappings(session, audits_map, models_map)

    # 8. Create user-events mappings (required for event visibility)
    create_user_events_mappings(session, events_map, user_audit_map, audits_map)

    # 9. Create event types (marks events as created by audit instigator)
    create_event_types(session, events_map, user_audit_map, audits_map)

    # 10. Create event-metric mappings
    create_event_metric_mappings(session, events_map, metrics_map, user_audit_map, audits_map)

    # 11. Create audit pipelines
    create_audit_pipelines(session, audits_map, models_map, datasets_map, events_map, metrics_map, user_audit_map)

    # 11.5 Create events audit status (REQUIRED for evaluation service)
    # create_events_audit_status(session, events_map, metrics_map, audits_map, user_audit_map)

    # 12. Create event-entity mappings
    create_event_entity_mappings(session, events_map, entities_map, audits_map, user_audit_map)

    # 13. Create event-category mappings
    create_event_category_mappings(session, events_map, categories_map)

    # 14. Create user-metrics mappings
    create_user_metrics_mappings(session, metrics_map, audits_map, user_audit_map)

    # 15. Create metrics underlying features (for Accuracy Parity -> gender)
    add_metrics_underlying_features(session, metrics_map)

    # 16. Create metrics scale points (for Keyword Salience)
    add_metrics_scalepoints(session, metrics_map)

    # 17. Create metrics target features
    add_metrics_target_features(session, metrics_map)

    print("\n" + "=" * 60)
    print("✅ CSV-based v4 Migration Complete!")
    print("=" * 60)

    # Print summary
    print("\n📊 Summary:")
    print(f"   - Users created: {len(users_map)}")
    print(f"   - Applications: {len(apps_map)}")
    print(f"   - Models: {len(models_map)}")
    print(f"   - Datasets: {len(datasets_map)}")
    print(f"   - Events: {len(events_map)}")
    print(f"   - Metrics: {len(metrics_map)}")
    print(f"   - Entities: {len(entities_map)}")
    print(f"   - Categories: {len(categories_map)}")
    print(f"   - Target Features: {len(features_map)}")
    print(f"   - Taxonomy Groups: {len(taxonomy_map)}")
    print(f"   - Audits: {len(audits_map)}")

    return {
        "users": users_map,
        "roles": roles_map,
        "applications": apps_map,
        "models": models_map,
        "datasets": datasets_map,
        "events": events_map,
        "metrics": metrics_map,
        "entities": entities_map,
        "categories": categories_map,
        "target_features": features_map,
        "taxonomy_groups": taxonomy_map,
        "audits": audits_map,
        "user_audit_map": user_audit_map,
    }
