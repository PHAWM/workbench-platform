"""Output evaluation service functions"""
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlmodel import Session, select, and_
import traceback

from src.models import *
from .utils import convert_numpy_to_json_serializable
from src.services.performance_service.run_functions import run_output_evaluation, run_output_classification


def clear_output_evaluation_results_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Clear cached output evaluation results to force re-running inference.

    This service function handles the entire business logic for clearing output evaluation results,
    including:
    - User audit access verification
    - MappingOutcomeEvaluationValues deletion
    - Response construction with deletion count

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user clearing the results
        session: Database session

    Returns:
        Dictionary with message and deleted_count

    Raises:
        HTTPException: If user has no access to the audit
    """
    user_audit = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_audit:
        raise HTTPException(status_code=404, detail="User not associated with this audit")

    # Delete all outcome evaluation values for this user/audit
    deleted_count = 0
    outcome_mappings = session.exec(
        select(MappingOutcomeEvaluationValues)
        .where(
            MappingOutcomeEvaluationValues.user_audit_id == user_audit.id,
            MappingOutcomeEvaluationValues.audit_id == audit_id
        )
    ).all()

    for mapping in outcome_mappings:
        session.delete(mapping)
        deleted_count += 1

    session.commit()

    return {
        "message": "Output evaluation results cleared",
        "deleted_count": deleted_count
    }

async def generate_output_evaluation_results_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> 'OutputEvaluationResponse':
    """
    Generate output evaluation results by running inference on uploaded data.

    This service function handles the entire business logic for generating output evaluations,
    including:
    - User audit access verification
    - Model metadata retrieval with optional API key
    - User uploaded data location retrieval
    - Complex pipeline query with multiple joins
    - Pipeline grouping by metric to avoid duplicate evaluations
    - Output evaluation execution via run_output_evaluation
    - Result creation/update in MappingOutcomeEvaluationValues
    - File information and metadata extraction
    - Response construction

    OPTIMIZATION: Groups pipelines by metric to run each evaluation once instead of per-pipeline.

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user generating the results
        session: Database session

    Returns:
        OutputEvaluationResponse with audit_criteria list

    Raises:
        HTTPException: If user has no access, model not found, or evaluation fails
    """
    try:
        # Get user audit mapping first
        user_audit = session.exec(
            select(MappingAuditUser)
            .where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user_id
            )
        ).first()

        if not user_audit:
            raise HTTPException(status_code=404, detail="User not associated with this audit")

        # Get the audit instigator's user_audit_id
        # MappingAuditPipelineEvents, MappingMetricsEvents, MappingEventsAuditStatus are created by the instigator
        audit_instigator = session.exec(
            select(MappingAuditUser)
            .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
            .where(
                MappingAuditUser.audit_id == audit_id,
                AuditRoles.role == 'audit_instigator'
            )
        ).first()

        # Fallback to current user if no instigator found
        instigator_user_audit_id = audit_instigator.id if audit_instigator else user_audit.id

        print(f"Debug: audit_id={audit_id}, user_audit.id={user_audit.id}, instigator_user_audit_id={instigator_user_audit_id}")

        # Get model from audit mapping (API key is optional)
        model_data = session.exec(
            select(Modelmetadata)
            .join(MappingAuditModel, MappingAuditModel.model_id == Modelmetadata.id)
            .where(MappingAuditModel.audit_id == audit_id)
        ).first()

        if not model_data:
            raise HTTPException(status_code=404, detail="Model not found for this audit")

        model = model_data

        # Try to get API key for current user (optional for output evaluation)
        api_key_data = session.exec(
            select(Apikeymodel.model_api_key)
            .where(
                Apikeymodel.model_metadata_id == model.id,
                Apikeymodel.user_id == current_user_id
            )
        ).first()

        api_key = api_key_data if api_key_data else None

        # Get user's uploaded data location (just need one since all files are in same directory)
        user_output_eval = session.exec(
            select(OutputEvaluationData)
            .join(MappingOutputEvaluationUser, OutputEvaluationData.id == MappingOutputEvaluationUser.output_eval_id)
            .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
            .limit(1)
        ).first()

        if not user_output_eval:
            raise HTTPException(status_code=404, detail="No uploaded evaluation data found for this user")

        # Get pipelines with proper audit and user filters
        pipelines = session.exec(
            select(
                MappingAuditPipelineEvents,
                TargetFeatures,
                MappingOutcomeEvaluationValues,
                MetricsValues,
                MappingEventsAuditStatus.id,
                UserMetricThresholds.custom_threshold,
                OutputEvaluationData.id
            )
            .join(Events, MappingAuditPipelineEvents.event_id == Events.id)
            .join(Metrics, MappingAuditPipelineEvents.metric_id == Metrics.id)
            .join(MappingOutputEvaluationUser, MappingOutputEvaluationUser.user_audit_id == user_audit.id)
            .join(OutputEvaluationData, OutputEvaluationData.id == MappingOutputEvaluationUser.output_eval_id)
            .outerjoin(MappingOutcomeEvaluationValues, and_(
                MappingAuditPipelineEvents.metric_id == MappingOutcomeEvaluationValues.metric_id,
                MappingAuditPipelineEvents.event_id == MappingOutcomeEvaluationValues.event_id,
                MappingOutcomeEvaluationValues.user_audit_id == user_audit.id,
                MappingOutcomeEvaluationValues.data_id == OutputEvaluationData.id,
                MappingOutcomeEvaluationValues.audit_id == audit_id
            ))
            .join(MappingEventsAuditStatus, and_(
                MappingAuditPipelineEvents.metric_id == MappingEventsAuditStatus.metric_id,
                MappingAuditPipelineEvents.event_id == MappingEventsAuditStatus.event_id,
                MappingEventsAuditStatus.user_audit_id == instigator_user_audit_id
            ))
            .join(MappingMetricsEvents, and_(
                MappingAuditPipelineEvents.metric_id == MappingMetricsEvents.metric_id,
                MappingAuditPipelineEvents.event_id == MappingMetricsEvents.event_id,
                MappingMetricsEvents.user_audit_id == instigator_user_audit_id
            ))
            .join(MetricsValues, MappingMetricsEvents.values_id == MetricsValues.id)
            .join(MappingAuditPipelineAudit, MappingAuditPipelineEvents.audit_pipeline == MappingAuditPipelineAudit.audit_pipeline)
            .join(MappingAuditUser, MappingAuditPipelineEvents.user_audit_id == MappingAuditUser.id)
            .outerjoin(UserMetricThresholds, and_(
                UserMetricThresholds.user_audit_id == MappingAuditUser.id,
                UserMetricThresholds.metric_id == MappingAuditPipelineEvents.metric_id,
                UserMetricThresholds.event_id == MappingAuditPipelineEvents.event_id,
                UserMetricThresholds.values_id == MetricsValues.id
            ))
            .join(MetricsTargetFeatures, MetricsValues.id == MetricsTargetFeatures.metric_values_id)
            .join(TargetFeatures, MetricsTargetFeatures.target_feature_id == TargetFeatures.id)
            .where(
                MappingAuditPipelineAudit.audit_id == audit_id,
                MappingAuditPipelineEvents.user_audit_id == instigator_user_audit_id
            )
        )

        pipeline_list = list(pipelines)

        print(f"📋 Found {len(pipeline_list)} pipeline items")
        for idx, (pipeline, target_features, outcome_values, metric_values, audit_criteria_id, custom_threshold, data_id) in enumerate(pipeline_list):
            print(f"  Pipeline {idx + 1}: metric_id={pipeline.metric_id}, event_id={pipeline.event_id}, outcome_values={'EXISTS' if outcome_values else 'None'}, data_id={data_id}")

        results = []

        metrics_to_evaluate = {}
        for pipeline, target_features, outcome_values, metric_values, audit_criteria_id, custom_threshold, data_id in pipeline_list:
            metric_key = target_features.function_name

            if metric_key not in metrics_to_evaluate:
                metrics_to_evaluate[metric_key] = {
                    'function_name': target_features.function_name,
                    'pipelines': []
                }

            metrics_to_evaluate[metric_key]['pipelines'].append({
                'pipeline': pipeline,
                'target_features': target_features,
                'outcome_values': outcome_values,
                'metric_values': metric_values,
                'audit_criteria_id': audit_criteria_id,
                'custom_threshold': custom_threshold,
                'data_id': data_id
            })

        # Run evaluation once per unique metric
        print(f"\nProcessing {len(metrics_to_evaluate)} unique metrics: {list(metrics_to_evaluate.keys())}")

        evaluation_results = {}
        for metric_name, metric_info in metrics_to_evaluate.items():
            print(f"\nProcessing metric: {metric_name}")

            # Check if any outcome already has output (and no errors)
            existing_output = None
            for item in metric_info['pipelines']:
                if (item['outcome_values'] and
                    item['outcome_values'].output and
                    item['outcome_values'].output != {} and
                    "error" not in item['outcome_values'].output):
                    existing_output = item['outcome_values'].output
                    print(f"Found existing output for {metric_name}")
                    break

            if existing_output:
                evaluation_results[metric_name] = existing_output
            else:
                print(f"🔄 No existing output, running evaluation for {metric_name}")
                # Run evaluation once for this metric
                output_data = run_output_evaluation(
                    session=session,
                    model_metadata=model,
                    input_dataset_metadata=user_output_eval,
                    metric_name=metric_name,
                    user_id=current_user_id,
                    storage_base_path="storage",
                    api_key=api_key
                )
                print(output_data)
                print(f"📦 Received output_data: {output_data.get('success', False)}")
                evaluation_results[metric_name] = output_data.get("evaluation_result", {})

        # Now create results for each pipeline using the shared evaluation results
        print(f"\n📝 Creating/updating records for {len(metrics_to_evaluate)} metrics")
        for metric_name, metric_info in metrics_to_evaluate.items():
            eval_output = evaluation_results[metric_name]
            print(f"\n🔧 Processing metric: {metric_name} with {len(metric_info['pipelines'])} pipelines")

            for item in metric_info['pipelines']:
                pipeline = item['pipeline']
                target_features = item['target_features']
                outcome_values = item['outcome_values']
                metric_values = item['metric_values']
                audit_criteria_id = item['audit_criteria_id']
                custom_threshold = item['custom_threshold']
                data_id = item['data_id']

                # Determine the effective threshold (custom if exists, otherwise default)
                # If base threshold is "Not Set" (case-insensitive), check for any custom threshold
                base_threshold = metric_values.threshold
                if custom_threshold is not None:
                    effective_threshold = custom_threshold
                elif base_threshold and base_threshold.lower() == "not set":
                    # Look for any custom threshold for this metric/event/values combination
                    any_custom = session.exec(
                        select(UserMetricThresholds.custom_threshold).where(
                            UserMetricThresholds.metric_id == pipeline.metric_id,
                            UserMetricThresholds.event_id == pipeline.event_id,
                            UserMetricThresholds.values_id == metric_values.id
                        )
                    ).first()
                    effective_threshold = any_custom if any_custom else base_threshold
                else:
                    effective_threshold = base_threshold

                # Create or update outcome_values in the combined MappingOutcomeEvaluationValues table
                if outcome_values is None:
                    # No record exists - create new mapping with output data
                    print(f"Creating new MappingOutcomeEvaluationValues for metric_id={pipeline.metric_id}, event_id={pipeline.event_id}, data_id={data_id}")
                    outcome_values = MappingOutcomeEvaluationValues(
                        metric_id=pipeline.metric_id,
                        event_id=pipeline.event_id,
                        audit_id=audit_id,
                        user_audit_id=user_audit.id,  # Use current user's user_audit_id, not pipeline's
                        data_id=data_id,
                        output=convert_numpy_to_json_serializable(eval_output),
                        meet_requirement=0,
                        notes=""
                    )
                    session.add(outcome_values)
                    session.flush()
                    print(f"Created MappingOutcomeEvaluationValues with id={outcome_values.id}")
                elif not outcome_values.output or outcome_values.output == {}:
                    # Record exists but no output - update with output data
                    print(f"Updating existing MappingOutcomeEvaluationValues id={outcome_values.id} with output")
                    outcome_values.output = convert_numpy_to_json_serializable(eval_output)
                    session.add(outcome_values)
                    session.flush()
                    print(f"Updated MappingOutcomeEvaluationValues id={outcome_values.id}")
                else:
                    # Record exists with output - skip (already generated)
                    print(f"⏭️  Skipping MappingOutcomeEvaluationValues id={outcome_values.id} - output already exists")

                print(outcome_values)

                # Extract file information from output for sorting/display
                file_name = None
                file_index = None
                metadata = None

                if outcome_values.output:
                    # Try to get classification data
                    classification = outcome_values.output.get('classification', {})
                    if classification:
                        file_name = classification.get('file_name')
                        metadata = {
                            'gender': classification.get('gender'),
                            'age': classification.get('age'),
                            'id': classification.get('id'),
                        }
                        # Remove None values
                        metadata = {k: v for k, v in metadata.items() if v is not None}

                    file_index = outcome_values.output.get('file_index')

                results.append(OutputEvaluationItem(
                    audit_criteria_id=audit_criteria_id,
                    output=outcome_values.output,
                    target_features=target_features.target_feature,
                    threshold=effective_threshold,
                    requirements=outcome_values.meet_requirement,
                    notes=outcome_values.notes if outcome_values.notes else None,
                    data_id=outcome_values.data_id,
                    file_name=file_name,
                    file_index=file_index,
                    metadata=metadata if metadata else None
                ))

        session.commit()

        return OutputEvaluationResponse(
            audit_criteria=results
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        error_trace = traceback.format_exc()
        print(f"Error in generate_output_evaluation_results_comprehensive: {str(e)}")
        print(f"Traceback:\n{error_trace}")

        # Rollback database changes
        session.rollback()

        # Return 500 error with details
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while generating output evaluation: {str(e)}"
        )

async def classify_output_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> 'OutputClassificationResponse':
    """
    Generate output classification for an audit using run_output_classification.

    This service function handles the entire business logic for output classification,
    including:
    - User audit access verification
    - Model metadata retrieval with optional API key
    - User uploaded data location retrieval
    - Running classification via run_output_classification
    - Creating MappingOutcomeEvaluationValues records for ALL event/metric combinations
    - Matching classifications to files by name
    - Response construction

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting classification
        session: Database session

    Returns:
        OutputClassificationResponse with classification results

    Raises:
        HTTPException: If user has no access, model not found, or classification fails
    """
    from pathlib import Path

    try:
        # Get user audit mapping
        user_audit = session.exec(
            select(MappingAuditUser)
            .where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user_id
            )
        ).first()

        if not user_audit:
            raise HTTPException(
                status_code=404,
                detail="User not associated with this audit"
            )

        # Get the audit instigator's user_audit_id
        audit_instigator = session.exec(
            select(MappingAuditUser)
            .join(AuditRoles, AuditRoles.id == MappingAuditUser.roles_id)
            .where(
                MappingAuditUser.audit_id == audit_id,
                AuditRoles.role == 'audit_instigator'
            )
        ).first()

        # Fallback to current user if no instigator found
        instigator_user_audit_id = audit_instigator.id if audit_instigator else user_audit.id

        print(f"[classify_output] Found user_audit: id={user_audit.id}, instigator_user_audit_id={instigator_user_audit_id}")

        # Get model metadata with optional API key
        model_query = (
            select(Modelmetadata, Apikeymodel.model_api_key)
            .join(MappingAuditModel, MappingAuditModel.model_id == Modelmetadata.id)
            .outerjoin(Apikeymodel, Apikeymodel.model_metadata_id == Modelmetadata.id)
            .where(MappingAuditModel.audit_id == audit_id)
        )
        model_result = session.exec(model_query).first()

        if not model_result:
            raise HTTPException(
                status_code=404,
                detail=f"No model found for audit {audit_id}"
            )

        model, api_key = model_result
        print(f"[classify_output] Found model: id={model.id}, name={model.name}")

        # Get user's uploaded data (need the OutputEvaluationData object, not just location string)
        user_output_eval = session.exec(
            select(OutputEvaluationData)
            .join(MappingOutputEvaluationUser, OutputEvaluationData.id == MappingOutputEvaluationUser.output_eval_id)
            .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
            .limit(1)
        ).first()

        if not user_output_eval:
            raise HTTPException(status_code=404, detail="No uploaded evaluation data found for this user")

        print(f"[classify_output] User data location: {user_output_eval.location}")

        # Get ALL uploaded files for this user
        all_user_files = session.exec(
            select(MappingOutputEvaluationUser, OutputEvaluationData)
            .join(OutputEvaluationData)
            .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
        ).all()

        all_uploaded_data_ids = {eval_data.id for _, eval_data in all_user_files}
        print(f"[classify_output] Total uploaded files: {len(all_uploaded_data_ids)}")

        # Check if there are already existing MappingOutcomeEvaluationValues with output
        existing_outcomes = session.exec(
            select(MappingOutcomeEvaluationValues)
            .where(
                MappingOutcomeEvaluationValues.audit_id == audit_id,
                MappingOutcomeEvaluationValues.user_audit_id == user_audit.id
            )
        ).all()

        # Track which data_ids already have valid output (not empty and no error)
        # Also track meet_requirement per data_id to pick the best value
        processed_data_ids = set()
        existing_classification = []
        data_id_to_classification = {}  # data_id -> (output, notes, meet_requirement)

        for outcome in existing_outcomes:
            if outcome.output and outcome.output != {} and "error" not in outcome.output:
                processed_data_ids.add(outcome.data_id)

                # Track the best meet_requirement for each data_id
                # Prefer non-zero values over zero
                if outcome.data_id not in data_id_to_classification:
                    data_id_to_classification[outcome.data_id] = {
                        'output': outcome.output,
                        'notes': outcome.notes if outcome.notes else "",
                        'meet_requirement': outcome.meet_requirement
                    }
                else:
                    # If current is 0 but new one is not, use the new one
                    current_req = data_id_to_classification[outcome.data_id]['meet_requirement']
                    if current_req == 0 and outcome.meet_requirement != 0:
                        data_id_to_classification[outcome.data_id]['meet_requirement'] = outcome.meet_requirement
                    # Also update notes if current is empty but new one has notes
                    if not data_id_to_classification[outcome.data_id]['notes'] and outcome.notes:
                        data_id_to_classification[outcome.data_id]['notes'] = outcome.notes

        # Build existing_classification from the tracked data
        for data_id, data in data_id_to_classification.items():
            enriched_output = dict(data['output'])
            enriched_output['notes'] = data['notes']
            enriched_output['requirements'] = data['meet_requirement']
            enriched_output['data_id'] = data_id
            existing_classification.append(enriched_output)

        # Find new files that haven't been processed yet
        new_data_ids = all_uploaded_data_ids - processed_data_ids
        print(f"[classify_output] Already processed: {len(processed_data_ids)} files, New files to process: {len(new_data_ids)}")

        # If no new files to process, return cached results
        if not new_data_ids and existing_classification:
            print(f"[classify_output] No new files, returning {len(existing_classification)} cached classification outputs")
            return OutputClassificationResponse(
                success=True,
                model_id=model.id,
                model_name=model.name,
                total_entries_processed=len(existing_classification),
                classifications=existing_classification
            )

        # There are new files to process - run classification
        print(f"[classify_output] Running classification for new files...")
        classification_result = run_output_classification(
            session=session,
            model_metadata=model,
            input_dataset_metadata=user_output_eval,
            user_id=current_user_id,
            storage_base_path="storage",
            api_key=api_key
        )
        print(f"[classify_output] Classification completed")
        print(f"   classification_result type: {type(classification_result)}")

        # Track newly processed classifications to combine with existing ones
        new_classifications = []

        # Store classification results in MappingOutcomeEvaluationValues
        # For EACH uploaded file, we create a record for EVERY event/metric combination
        if "classifications" in classification_result:
            print(f"[classify_output] Storing classification results in database...")

            # Get all event-metric pairs for this audit (using instigator's user_audit_id)
            event_metric_pairs = session.exec(
                select(
                    MappingEventsAuditStatus.event_id,
                    MappingEventsAuditStatus.metric_id
                )
                .where(
                    MappingEventsAuditStatus.audit_id == audit_id,
                    MappingEventsAuditStatus.user_audit_id == user_audit.id
                )
            ).all()

            print(f"[classify_output] Found {len(event_metric_pairs)} event-metric pairs")

            # Get all OutputEvaluationData records for this user and audit
            user_file_mappings = session.exec(
                select(MappingOutputEvaluationUser, OutputEvaluationData)
                .join(OutputEvaluationData)
                .where(MappingOutputEvaluationUser.user_audit_id == user_audit.id)
            ).all()

            print(f"[classify_output] Found {len(user_file_mappings)} user files")

            # Create a dict of filename -> OutputEvaluationData.id
            # Also track which files are new (not yet processed)
            filename_to_data_id = {}
            filename_to_is_new = {}
            for mapping, eval_data in user_file_mappings:
                file_path = Path(eval_data.location)
                filename_to_data_id[file_path.name] = eval_data.id
                filename_to_is_new[file_path.name] = eval_data.id in new_data_ids
                print(f"  Mapped file: {file_path.name} -> data_id={eval_data.id}, is_new={eval_data.id in new_data_ids}")

            # For each classification output, match to data_id and create records (only for new files)
            for classification_output in classification_result.get("classifications", []):
                file_name = classification_output.get("file_name")
                print(f"\nProcessing classification for file: {file_name}")

                # Match file_name to data_id
                data_id = filename_to_data_id.get(file_name)
                if not data_id:
                    print(f"Warning: No data_id found for file {file_name}, skipping")
                    continue

                # Skip files that have already been processed (not new)
                is_new_file = filename_to_is_new.get(file_name, False)
                if not is_new_file:
                    print(f"  Skipping already processed file: {file_name}")
                    continue

                # Get the OutputEvaluationData record
                data_record = session.get(OutputEvaluationData, data_id)
                if not data_record:
                    print(f"Warning: OutputEvaluationData not found for data_id={data_id}")
                    continue

                print(f"  Matched to data_id={data_id} (new file)")

                # Default meet_requirement to 0 (Not Evaluated) - user can update via batch endpoint
                default_requirement = 0

                # Enrich output with notes, requirements, and data_id for new files
                enriched_output = dict(classification_output)
                enriched_output['notes'] = ""
                enriched_output['requirements'] = default_requirement
                enriched_output['data_id'] = data_id
                new_classifications.append(enriched_output)

                # Create output for this specific file (individual classification)
                individual_output = classification_output

                # For EACH event-metric pair, create or update MappingOutcomeEvaluationValues
                for event_id, metric_id in event_metric_pairs:
                    # Check if record already exists for this specific combination
                    existing_outcome = session.exec(
                        select(MappingOutcomeEvaluationValues)
                        .where(
                            MappingOutcomeEvaluationValues.data_id == data_record.id,
                            MappingOutcomeEvaluationValues.audit_id == audit_id,
                            MappingOutcomeEvaluationValues.user_audit_id == user_audit.id,
                            MappingOutcomeEvaluationValues.event_id == event_id,
                            MappingOutcomeEvaluationValues.metric_id == metric_id
                        )
                    ).first()

                    if existing_outcome is None:
                        # Create new record with individual output
                        print(f"  Creating MappingOutcomeEvaluationValues for data_id={data_record.id}, event_id={event_id}, metric_id={metric_id}")
                        new_outcome = MappingOutcomeEvaluationValues(
                            metric_id=metric_id,
                            event_id=event_id,
                            audit_id=audit_id,
                            user_audit_id=user_audit.id,
                            data_id=data_record.id,
                            output=convert_numpy_to_json_serializable(individual_output),
                            meet_requirement=default_requirement,
                            notes=""
                        )
                        session.add(new_outcome)

                    elif not existing_outcome.output or existing_outcome.output == {}:
                        # Update existing record with individual output - preserve existing meet_requirement
                        print(f"  Updating MappingOutcomeEvaluationValues id={existing_outcome.id} for event_id={event_id}, metric_id={metric_id}")
                        existing_outcome.output = convert_numpy_to_json_serializable(individual_output)
                        # Don't overwrite meet_requirement - keep existing value from database
                        session.add(existing_outcome)
                    else:
                        print(f"  ⏭️  Skipping MappingOutcomeEvaluationValues id={existing_outcome.id} - already has output")

            print(classification_result)
            # Commit all changes
            session.commit()
            print(f"[classify_output] Committed all records to database")

        # Combine existing classifications with newly processed ones
        all_classifications = existing_classification + new_classifications
        print(f"[classify_output] Total classifications: {len(all_classifications)} (existing: {len(existing_classification)}, new: {len(new_classifications)})")

        # Build the combined result
        combined_result = {
            "success": True,
            "model_id": model.id,
            "model_name": model.name,
            "total_entries_processed": len(all_classifications),
            "classifications": all_classifications
        }

        # Ensure result is JSON serializable before returning
        try:
            serialized_result = convert_numpy_to_json_serializable(combined_result)
            print(f"Successfully serialized classification_result")
            return OutputClassificationResponse(**serialized_result)
        except Exception as serialize_error:
            print(f"Error serializing classification_result: {serialize_error}")
            print(f"   combined_result type: {type(combined_result)}")
            print(f"   combined_result keys: {combined_result.keys() if isinstance(combined_result, dict) else 'N/A'}")
            raise

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        error_trace = traceback.format_exc()
        print(f"Error in classify_output: {str(e)}")
        print(f"Traceback:\n{error_trace}")

        # Rollback database changes
        try:
            session.rollback()
        except Exception as rollback_error:
            print(f"Error during rollback: {rollback_error}")

        # Return 500 error with details
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while generating output classification: {str(e)}"
        )

async def get_output_results_comprehensive(
    audit_id: int,
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Retrieve generated output classification results for an audit.

    This service function handles the entire business logic for retrieving output results,
    including:
    - User audit access verification
    - MappingOutcomeEvaluationValues retrieval
    - Results formatting
    - Response construction

    Args:
        audit_id: The ID of the audit
        current_user_id: The ID of the user requesting the results
        session: Database session

    Returns:
        Dictionary with audit_id, total_results, results list, and optional message

    Raises:
        HTTPException: If user has no access or retrieval fails
    """
    try:
        # Get user audit mapping
        user_audit = session.exec(
            select(MappingAuditUser)
            .where(
                MappingAuditUser.audit_id == audit_id,
                MappingAuditUser.user_id == current_user_id
            )
        ).first()

        if not user_audit:
            raise HTTPException(status_code=404, detail="User not associated with this audit")

        # Query for outcome evaluation values
        query = select(MappingOutcomeEvaluationValues).where(
            MappingOutcomeEvaluationValues.audit_id == audit_id,
            MappingOutcomeEvaluationValues.user_audit_id == user_audit.id
        )

        # Execute query
        results = session.exec(query).all()

        if not results:
            return {
                "audit_id": audit_id,
                "total_results": 0,
                "results": [],
                "message": "No generated output results found for this audit"
            }

        # Format results - return all fields from outcome_values
        formatted_results = []
        for outcome_values in results:
            formatted_results.append({
                "id": outcome_values.id,
                "metric_id": outcome_values.metric_id,
                "event_id": outcome_values.event_id,
                "audit_id": outcome_values.audit_id,
                "user_audit_id": outcome_values.user_audit_id,
                "data_id": outcome_values.data_id,
                "output": outcome_values.output,
                "meet_requirement": outcome_values.meet_requirement,
                "notes": outcome_values.notes
            })

        return {
            "audit_id": audit_id,
            "total_results": len(formatted_results),
            "results": formatted_results
        }

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in get_output_results: {str(e)}")
        print(f"Traceback:\n{error_trace}")

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while retrieving output results: {str(e)}"
        )

def update_outcome_evaluation_batch_comprehensive(
    audit_id: int,
    batch_updated_data: List['AuditStatusUpdate'],
    current_user_id: str,
    session: Session
) -> Dict[str, Any]:
    """
    Batch update outcome evaluation values (meet_requirement status and notes).

    This service function handles the entire business logic for batch outcome updates,
    including:
    - User audit access verification
    - Multiple outcome evaluation values retrieval
    - Batch meet_requirement and notes updates
    - Response construction with success/failure lists

    Args:
        audit_id: The ID of the audit
        batch_updated_data: List of status updates with event_id, metric_id, data_id, meet_requirement, notes
        current_user_id: The ID of the user updating the outcomes
        session: Database session

    Returns:
        Dictionary with message, updated_outcomes list, not_updated_outcomes list, totals

    Raises:
        HTTPException: If user has no access or batch update fails
    """
    user_metric_check = session.exec(
        select(MappingAuditUser)
        .where(
            MappingAuditUser.audit_id == audit_id,
            MappingAuditUser.user_id == current_user_id
        )
    ).first()

    if not user_metric_check:
        raise HTTPException(status_code=401, detail="Access denied")

    print(user_metric_check)
    try:
        updated_outcomes = []
        not_updated_outcomes = []

        for updated_data in batch_updated_data:
            # Build query - if data_id is provided, use it for precise matching
            query = select(MappingOutcomeEvaluationValues).where(
                MappingOutcomeEvaluationValues.event_id == updated_data.event_id,
                MappingOutcomeEvaluationValues.metric_id == updated_data.metric_id,
                MappingOutcomeEvaluationValues.user_audit_id == user_metric_check.id,
                MappingOutcomeEvaluationValues.audit_id == audit_id
            )

            # If data_id is specified, filter by it
            if updated_data.data_id is not None:
                query = query.where(MappingOutcomeEvaluationValues.data_id == updated_data.data_id)

            outcome_mapping = session.exec(query).first()

            print(f"Updating: event_id={updated_data.event_id}, metric_id={updated_data.metric_id}, data_id={updated_data.data_id}")
            if not outcome_mapping:
                # Record doesn't exist - need to run generate first
                not_updated_outcomes.append({
                    "event_id": updated_data.event_id,
                    "metric_id": updated_data.metric_id,
                    "data_id": updated_data.data_id,
                    "reason": "No output generated yet. Please run generate/output first."
                })
            else:
                outcome_updated = False

                # Update output
                if updated_data.output is not None:
                    outcome_mapping.output = updated_data.output
                    outcome_updated = True

                # Update meet_requirement
                if updated_data.meet_requirement is not None:
                    outcome_mapping.meet_requirement = updated_data.meet_requirement
                    outcome_updated = True

                if updated_data.notes is not None:
                    outcome_mapping.notes = updated_data.notes
                    outcome_updated = True

                if outcome_updated:
                    session.add(outcome_mapping)
                    updated_outcomes.append({
                        "event_id": updated_data.event_id,
                        "metric_id": updated_data.metric_id,
                        "data_id": updated_data.data_id,
                        "output": outcome_mapping.output,
                        "meet_requirement": outcome_mapping.meet_requirement,
                        "notes": outcome_mapping.notes
                    })

        # Commit all changes at once
        session.commit()

        return {
            "message": "Outcome evaluation status has been updated",
            "updated_outcomes": updated_outcomes,
            "not_updated_outcomes": not_updated_outcomes,
            "total_updated": len(updated_outcomes),
            "total_not_updated": len(not_updated_outcomes)
        }

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Error in batch operation: {str(e)}")
