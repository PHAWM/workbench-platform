import sys
import os
import pandas as pd
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add project root to Python path (from tests directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlmodel import SQLModel, Session, create_engine
try:
    from src.database import create_db_and_tables, SQL_CONNECTION_STRING
    from src.models import *
    from src.services.performance_service.run_functions import run_evaluation
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root or tests directory")
    sys.exit(1)

def setup_test_data():
    """Create test data files in storage directory structure"""

    # Create storage directory structure in tests directory
    test_dir = Path(__file__).parent
    storage_base = test_dir / "test_storage"
    audit_id = "1"  # Use simple ID, storage manager will add "audit_" prefix
    audit_input_path = storage_base / "audits" / f"audit_{audit_id}" / "input"
    audit_output_path = storage_base / "audits" / f"audit_{audit_id}" / "output"
    
    # Create directories
    audit_input_path.mkdir(parents=True, exist_ok=True)
    audit_output_path.mkdir(parents=True, exist_ok=True)

    # Create sample results.csv at audit root (as per storage service structure)
    # Results go to: storage/audits/audit_{audit_id}/results.csv
    audit_root = storage_base / "audits" / f"audit_{audit_id}"
    results_data = {
        'id': [1, 2, 3, 4, 5],
        'output': [
            '{"prediction": 1, "confidence": 0.85}',
            '{"prediction": 0, "confidence": 0.72}',
            '{"prediction": 1, "confidence": 0.91}',
            '{"prediction": 0, "confidence": 0.68}',
            '{"prediction": 1, "confidence": 0.79}'
        ],
        'file_name': ['conv_001.txt', 'conv_002.txt', 'conv_003.txt', 'conv_004.txt', 'conv_005.txt']
    }
    results_df = pd.DataFrame(results_data)
    results_df.to_csv(audit_root / "results.csv", index=False)

    # Create sample metadata.csv in INPUT directory (for metadata enrichment)
    metadata_data = {
        'id': [1, 2, 3, 4, 5],
        'gender': ['Male', 'Female', 'Male', 'Female', 'Male'],
        'age': [25, 34, 45, 28, 52],
        'true_value': [1, 0, 1, 1, 0],
        'file_name': ['conv_001.txt', 'conv_002.txt', 'conv_003.txt', 'conv_004.txt', 'conv_005.txt']
    }
    metadata_df = pd.DataFrame(metadata_data)
    metadata_df.to_csv(audit_input_path / "metadata.csv", index=False)
    
    # Also create some input files for fallback testing
    input_files_data = [
        {'text': 'Customer complaint about billing', 'id': 1},
        {'text': 'Request for product information', 'id': 2},
        {'text': 'Technical support question', 'id': 3},
        {'text': 'Praise for customer service', 'id': 4},
        {'text': 'Return request', 'id': 5}
    ]
    
    for i, data in enumerate(input_files_data, 1):
        with open(audit_input_path / f"conv_{i:03d}.txt", 'w') as f:
            f.write(data['text'])
    
    # Create input metadata.csv
    input_metadata_df = pd.DataFrame(metadata_data)
    input_metadata_df.to_csv(audit_input_path / "metadata.csv", index=False)
    
    return audit_id, str(audit_input_path), str(audit_output_path), str(storage_base)

def create_mock_objects():
    """Create mock objects similar to your database models"""
    
    # Mock MappingAuditPipelineEvents
    pipeline_event = Mock()
    pipeline_event.id = 2
    pipeline_event.event_id = 2
    pipeline_event.audit_pipeline = 1
    pipeline_event.metric_id = 1
    pipeline_event.user_audit_id = 2
    
    # Mock TargetFeatures
    target_features = Mock()
    target_features.target_feature = 'accuracy'
    target_features.id = 1
    target_features.function_name = 'confusion_matrix'
    
    # Mock DatasetMetadata
    dataset_metadata = Mock()
    dataset_metadata.id = 2
    dataset_metadata.copyright_agreement = False
    dataset_metadata.purpose = 'Customer support conversation logs for training'
    
    # Mock Modelmetadata
    model_metadata = Mock()
    model_metadata.name = 'GPT-4 Customer Support'
    model_metadata.location = 'https://api.openai.com/v1/chat/completions'
    model_metadata.output_context = 'Natural language responses'
    model_metadata.acceptable_formats = ['txt', 'html']
    model_metadata.id = 2
    model_metadata.model_type = True  # Generative AI
    model_metadata.task = 'Customer support automation'
    
    # Mock MetricsValues
    metrics_values = Mock()
    metrics_values.output = {}
    metrics_values.id = 1
    metrics_values.threshold = 0.85
    
    # API key
    api_key = 'sk-proj-abcdef1234567890abcdef1234567890'
    
    return pipeline_event, target_features, dataset_metadata, model_metadata, metrics_values, api_key

def create_mock_dataset_metadata_objects(input_path, output_path):
    """Create mock InputDatasetMetadata and OutputDatasetMetadata objects"""

    # Mock InputDatasetMetadata
    input_dataset_metadata = Mock()
    input_dataset_metadata.location = f"audit:1/input"  # Use simple ID matching setup_test_data
    input_dataset_metadata.datatypes = {
        'id': 'int',
        'text': 'str',
        'gender': 'str',
        'age': 'int',
        'true_value': 'int'
    }

    # Mock OutputDatasetMetadata
    output_dataset_metadata = Mock()
    output_dataset_metadata.location = f"audit:1/output"  # Use simple ID matching setup_test_data
    output_dataset_metadata.headers = {}
    output_dataset_metadata.datatypes = {}

    return input_dataset_metadata, output_dataset_metadata

@pytest.fixture
def test_storage_setup():
    """Pytest fixture to set up and tear down test storage"""
    audit_id, input_path, output_path, storage_base = setup_test_data()
    yield audit_id, input_path, output_path, storage_base
    
    # Cleanup after test
    import shutil
    if Path(storage_base).exists():
        shutil.rmtree(storage_base)

def test_run_evaluation_with_existing_results(test_storage_setup):
    """Test run_evaluation function with existing results.csv and metadata.csv"""
    
    audit_id, input_path, output_path, storage_base = test_storage_setup
    
    print("Creating mock objects...")
    pipeline_event, target_features, dataset_metadata, model_metadata, metrics_values, api_key = create_mock_objects()
    
    # Create dataset metadata objects
    input_dataset_metadata, output_dataset_metadata = create_mock_dataset_metadata_objects(input_path, output_path)
    
    # Mock session
    mock_session = Mock()
    
    print("Testing run_evaluation with existing results...")
    
    try:
        # Test the function
        result = run_evaluation(
            session=mock_session,
            model_metadata=model_metadata,
            input_dataset_metadata=input_dataset_metadata,
            output_dataset_metadata=output_dataset_metadata,
            metric_name=target_features.function_name,
            user_id="test_user_123",
            storage_base_path=storage_base,
            api_key=api_key
        )
        
        print("\n" + "="*50)
        print("TEST RESULTS")
        print("="*50)
        print(f"Success: {result['success']}")
        print(f"Model Name: {result['model_name']}")
        print(f"Model Type: {result['model_type']}")
        print(f"Total Entries: {result['total_entries_processed']}")
        print(f"Used Existing Results: {result.get('used_existing_results', False)}")
        print(f"Results Source: {result.get('results_source', 'unknown')}")
        print(f"Metadata Merged: {result.get('metadata_merged', False)}")
        print(f"Output Location: {result['output_location']}")
        print(f"Metric Name: {result['metric_name']}")
        print(f"Output Columns: {result['output_columns']}")
        
        if result['evaluation_result']:
            print(f"\nEvaluation Result:")
            print(result['evaluation_result'])
        
        assert result['success'] == True
        assert result['used_existing_results'] == True
        assert 'y_pred' in result['output_columns']
        assert 'y_true' in result['output_columns']
        assert 'label_gender' in result['output_columns']
        
        return result
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Test failed with error: {e}")

def test_run_evaluation_without_existing_results():
    """Test run_evaluation function without existing results (fallback to inference)"""

    print("\n" + "="*50)
    print("TESTING WITHOUT EXISTING RESULTS")
    print("="*50)

    # Create fresh test data without results files
    test_dir = Path(__file__).parent
    storage_base = test_dir / "test_storage_inference"
    audit_id = "2"  # Use simple ID, storage manager will add "audit_" prefix
    audit_input_path = storage_base / "audits" / f"audit_{audit_id}" / "input"
    audit_output_path = storage_base / "audits" / f"audit_{audit_id}" / "output"
    
    # Create directories
    audit_input_path.mkdir(parents=True, exist_ok=True)
    audit_output_path.mkdir(parents=True, exist_ok=True)
    
    # Create only input files (no results.csv or metadata.csv in output)
    input_files_data = [
        {'text': 'Customer complaint about billing', 'id': 1},
        {'text': 'Request for product information', 'id': 2},
        {'text': 'Technical support question', 'id': 3}
    ]
    
    for i, data in enumerate(input_files_data, 1):
        with open(audit_input_path / f"conv_{i:03d}.txt", 'w') as f:
            f.write(data['text'])
    
    # Create input metadata.csv
    metadata_data = {
        'id': [1, 2, 3],
        'gender': ['Male', 'Female', 'Male'],
        'age': [25, 34, 45],
        'true_value': [1, 0, 1],
        'file_name': ['conv_001.txt', 'conv_002.txt', 'conv_003.txt']
    }
    metadata_df = pd.DataFrame(metadata_data)
    metadata_df.to_csv(audit_input_path / "metadata.csv", index=False)
    
    try:
        # Create mock objects
        pipeline_event, target_features, dataset_metadata, model_metadata, metrics_values, api_key = create_mock_objects()
        
        # Modify model to use a mock location instead of real API
        model_metadata.location = "http://localhost:8000/mock_inference"
        
        # Create dataset metadata objects
        input_dataset_metadata = Mock()
        input_dataset_metadata.location = f"audit:2/input"  # audit_id is "2"
        input_dataset_metadata.datatypes = {'id': 'int', 'text': 'str'}

        output_dataset_metadata = Mock()
        output_dataset_metadata.location = f"audit:2/output"  # audit_id is "2"
        output_dataset_metadata.headers = {}
        output_dataset_metadata.datatypes = {}
        
        # Mock session
        mock_session = Mock()
        
        print("Testing run_evaluation without existing results (inference mode)...")
        
        # This will likely fail due to the mock API endpoint, but we can see the flow
        result = run_evaluation(
            session=mock_session,
            model_metadata=model_metadata,
            input_dataset_metadata=input_dataset_metadata,
            output_dataset_metadata=output_dataset_metadata,
            metric_name=target_features.function_name,
            user_id="test_user_123",
            storage_base_path=str(storage_base),
            api_key=api_key
        )
        
        print(f"Inference test result: {result}")
        
        # Clean up
        import shutil
        if storage_base.exists():
            shutil.rmtree(storage_base)
        
    except Exception as e:
        print(f"Expected error in inference mode (mock API): {e}")
        # Clean up even if test fails
        import shutil
        if storage_base.exists():
            shutil.rmtree(storage_base)

def test_pipeline_tuple_format(test_storage_setup):
    """Test with the exact tuple format you provided"""
    
    print("\n" + "="*50)
    print("TESTING WITH PIPELINE TUPLE FORMAT")
    print("="*50)
    
    audit_id, input_path, output_path, storage_base = test_storage_setup
    
    # Create objects matching your format
    pipeline_event, target_features, dataset_metadata, model_metadata, metrics_values, api_key = create_mock_objects()
    
    # Create the tuple as you provided
    pipeline_tuple = (
        pipeline_event,  # MappingAuditPipelineEvents
        target_features,  # TargetFeatures  
        dataset_metadata,  # DatasetMetadata
        model_metadata,  # Modelmetadata
        metrics_values,  # MetricsValues
        api_key  # API key string
    )
    
    print("Pipeline tuple created:")
    print(f"  Pipeline Event: ID={pipeline_tuple[0].id}")
    print(f"  Target Features: {pipeline_tuple[1].target_feature} ({pipeline_tuple[1].function_name})")
    print(f"  Dataset: {pipeline_tuple[2].purpose}")
    print(f"  Model: {pipeline_tuple[3].name}")
    print(f"  Metrics Values: threshold={pipeline_tuple[4].threshold}")
    print(f"  API Key: {pipeline_tuple[5][:20]}...")
    
    # Extract components for run_evaluation
    _, target_feat, dataset_meta, model_meta, metrics_val, api_key = pipeline_tuple
    
    # Create dataset metadata objects
    input_dataset_metadata, output_dataset_metadata = create_mock_dataset_metadata_objects(input_path, output_path)
    
    # Mock session
    mock_session = Mock()
    
    print("\nRunning evaluation with pipeline tuple data...")
    
    result = run_evaluation(
        session=mock_session,
        model_metadata=model_meta,
        input_dataset_metadata=input_dataset_metadata,
        output_dataset_metadata=output_dataset_metadata,
        metric_name=target_feat.function_name,
        user_id="test_user_123",
        storage_base_path=storage_base,
        api_key=api_key
    )
    
    print(f"Pipeline tuple test successful: {result['success']}")
    
    assert result['success'] == True
    assert result['metric_name'] == 'confusion_matrix'
    assert result['model_name'] == 'GPT-4 Customer Support'
    
    return result

if __name__ == "__main__":
    print("Starting run_evaluation test script...")
    print("="*50)
    
    # Manual test execution (when not using pytest)
    try:
        # Setup test data
        audit_id, input_path, output_path, storage_base = setup_test_data()
        
        # Test 1: With existing results
        class MockTestSetup:
            def __init__(self, data):
                self.data = data
            def __iter__(self):
                return iter(self.data)
        
        mock_setup = MockTestSetup((audit_id, input_path, output_path, storage_base))
        result1 = test_run_evaluation_with_existing_results(mock_setup)
        
        # Test 2: Without existing results (inference mode)
        test_run_evaluation_without_existing_results()
        
        # Test 3: Pipeline tuple format
        result3 = test_pipeline_tuple_format(mock_setup)
        
        print("\n" + "="*50)
        print("ALL TESTS COMPLETED")
        print("="*50)
        
        if result1 and result1['success']:
            print("✅ Test 1 (existing results): PASSED")
        else:
            print("❌ Test 1 (existing results): FAILED")
        
        if result3 and result3['success']:
            print("✅ Test 3 (pipeline tuple): PASSED") 
        else:
            print("❌ Test 3 (pipeline tuple): FAILED")
        
        print(f"\nTest files created in {storage_base}/audits/audit_1/")
        print("You can examine the generated results and debug any issues.")
        
        # Cleanup
        import shutil
        if Path(storage_base).exists():
            shutil.rmtree(storage_base)
            print("Test storage cleaned up.")
            
    except Exception as e:
        print(f"Test execution failed: {e}")
        import traceback
        traceback.print_exc()