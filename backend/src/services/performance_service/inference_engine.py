"""Model inference engine — input preparation, API calls, output transformation."""
import asyncio
import json
import os
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Input preparation
# ---------------------------------------------------------------------------

def prepare_model_input_sam(file_info: Dict[str, Any], model_metadata) -> Dict[str, Any]:
    """Prepare input for SAM — emits s3_key for S3 backends, container path otherwise."""
    file_path = file_info['file_path']

    # S3 keys are relative paths without a leading slash and don't reference local storage.
    # When running with S3StorageManager, file_info['file_path'] is already the S3 key.
    is_s3_key = (
        not os.path.isabs(file_path)
        and 'storage/' not in file_path
        and not file_path.startswith('.')
    )
    if is_s3_key:
        return {"s3_key": file_path, "model_type": "all"}

    path = Path(file_path)
    if str(path).startswith('storage/'):
        file_path = '/app/' + str(path)
    elif not os.path.isabs(file_path):
        abs_path = os.path.abspath(file_path)
        if 'storage/' in abs_path:
            storage_part = abs_path.split('storage/', 1)[1]
            file_path = '/app/storage/' + storage_part
        else:
            file_path = abs_path
    else:
        if 'storage/' in file_path:
            storage_part = file_path.split('storage/', 1)[1]
            file_path = '/app/storage/' + storage_part

    return {"file_location": file_path, "model_type": "all"}


def prepare_model_input(file_info: Dict[str, Any], model_metadata) -> Dict[str, Any]:
    """Prepare input for any model based on file type and model metadata."""
    import pandas as pd
    is_generative = bool(model_metadata.model_type)

    if not is_generative:
        is_attachment = (
            (model_metadata.task and 'attachment' in model_metadata.task.lower()) or
            (model_metadata.output_context and 'attachment' in model_metadata.output_context.lower())
        )
        if is_attachment:
            if file_info['file_type'] == 'audio':
                audit_id = file_info['metadata'].get('audit_id',
                           file_info['metadata'].get('extracted_id', 'unknown'))
                return {
                    "file_location": {"audit_id": audit_id, "file_name": file_info['file_name']},
                    "model_type": "mc2",
                }
            else:
                input_data = file_info['data'] or {}
                return {
                    "file_location": {
                        "audit_id": input_data.get('audit_id', file_info['metadata'].get('audit_id', 'unknown')),
                        "file_name": input_data.get('file_name', file_info['file_name']),
                    },
                    "model_type": input_data.get('model_type', 'all'),
                }

        # Generic predictive model (e.g. Annif)
        if file_info['file_type'] == 'text' and file_info['data']:
            input_data = file_info['data']
            if isinstance(input_data, dict):
                text_content = None
                for field in ['text', 'content', 'prompt']:
                    if field in input_data:
                        text_content = input_data[field]
                        break
                if text_content:
                    if model_metadata.name and 'annif' in model_metadata.name.lower():
                        text_str = str(text_content).strip()
                        if text_str.startswith('<') and ('html' in text_str.lower() or '<body' in text_str.lower()):
                            from src.services.model_service.models.ANNIF.annif_predictor import AnnifPredictor
                            text_content = AnnifPredictor.extract_text_from_html(text_content)
                    return {
                        "text": text_content,
                        "project_id": input_data.get('project_id', 'yso-en'),
                        "limit": 15,
                        "threshold": input_data.get('threshold', 0.0),
                    }
                return {"text": str(input_data), "project_id": "yso-en", "limit": 15, "threshold": 0.0}
            return {"text": str(input_data), "project_id": "yso-en", "limit": 15, "threshold": 0.0}
        return file_info['data'] or {'file_path': file_info['file_path']}

    # Generative model
    if file_info['data']:
        input_data = file_info['data']
        if isinstance(input_data, dict):
            for field in ['prompt', 'text', 'content', 'message', 'query']:
                if field in input_data:
                    return {"prompt": input_data[field]}
            import pandas as pd
            prompt_parts = [f"{k}: {v}" for k, v in input_data.items() if pd.notna(v)]
            return {"prompt": " | ".join(prompt_parts)}
        return {"prompt": str(input_data)}
    return {"prompt": f"Process file: {file_info['file_name']}"}


# ---------------------------------------------------------------------------
# Output transformation
# ---------------------------------------------------------------------------

def transform_model_output_sam(raw_output: Any, model_metadata, file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Transform SAM model output — handles multi-model predictions."""
    from collections import Counter

    result = {
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
    }
    result.update(file_info.get('metadata', {}))

    if 'true_value' in result:
        true_val = result['true_value']
        if isinstance(true_val, str):
            v = true_val.lower().strip()
            if v in ['secure', 'safe', 'positive', '1', 'true', 'yes']:
                result['y_true'] = 1
            elif v in ['insecure', 'unsafe', 'negative', '0', 'false', 'no']:
                result['y_true'] = 0
        elif isinstance(true_val, (int, float)):
            result['y_true'] = int(true_val)

    model_outputs = []
    mc2_output = None

    if isinstance(raw_output, dict) and 'output' in raw_output:
        output_dict = raw_output['output']
        if 'mc2' in output_dict and isinstance(output_dict['mc2'], dict):
            mc2_output = output_dict['mc2']
            if mc2_output.get('success', False):
                model_outputs.append(mc2_output)
        for model_key in ['audio', 'text', 'mc1']:
            if model_key in output_dict and isinstance(output_dict[model_key], dict):
                m = output_dict[model_key]
                if m.get('success', False):
                    model_outputs.append(m)
    elif isinstance(raw_output, list):
        model_outputs = raw_output
    elif isinstance(raw_output, dict):
        model_outputs = [raw_output]

    if mc2_output and mc2_output.get('success', False):
        mc2_pred = mc2_output.get('prediction')
        if mc2_pred is not None:
            if isinstance(mc2_pred, str):
                result['y_pred'] = 1 if mc2_pred.lower() == 'secure' else 0
            else:
                result['y_pred'] = mc2_pred
        for field in ('secure_probability', 'insecure_probability', 'confidence'):
            if mc2_output.get(field) is not None:
                result[field] = mc2_output[field]
    elif model_outputs:
        predictions = [m.get('prediction') for m in model_outputs if 'prediction' in m]
        if predictions:
            numeric = []
            for p in predictions:
                if isinstance(p, str):
                    numeric.append(1 if p.lower() == 'secure' else 0)
                else:
                    numeric.append(p)
            if numeric:
                result['y_pred'] = Counter(numeric).most_common(1)[0][0]

        secure_probs = [m.get('secure_probability') for m in model_outputs if m.get('secure_probability') is not None]
        insecure_probs = [m.get('insecure_probability') for m in model_outputs if m.get('insecure_probability') is not None]
        if secure_probs:
            result['secure_probability'] = sum(secure_probs) / len(secure_probs)
        if insecure_probs:
            result['insecure_probability'] = sum(insecure_probs) / len(insecure_probs)
        if 'secure_probability' in result and 'insecure_probability' in result:
            result['confidence'] = max(result['secure_probability'], result['insecure_probability'])

    for m in model_outputs:
        model_type = m.get('model_type', 'unknown')
        clean = model_type.lower().replace(' ', '_').replace('model', '').replace('multimodal', 'mm').strip('_')
        result[f'{clean}_prediction'] = m.get('prediction')
        result[f'{clean}_confidence'] = m.get('confidence')
        result[f'{clean}_secure_prob'] = m.get('secure_probability')
        result[f'{clean}_insecure_prob'] = m.get('insecure_probability')

    return result


def transform_model_output_annif(raw_output: Any, model_metadata, file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Annif model output — extract labels and scores."""
    result = {
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
    }
    result.update(file_info.get('metadata', {}))

    if isinstance(raw_output, dict):
        # Flat MCP shape: {"predicted_subjects": "...", "y_pred": "...", ...}
        if 'predicted_subjects' in raw_output:
            for field in ('predicted_subjects', 'top_subjects', 'subject_count', 'project_id',
                          'y_pred', 'prediction_success', 'error'):
                if field in raw_output:
                    result[field] = raw_output[field]
        # Legacy HTTP shape: {"output": {"success": True, "results": [...]}}
        elif 'output' in raw_output:
            output_data = raw_output['output']
            if output_data.get('success') and 'results' in output_data:
                results = output_data['results']
                labels = [item.get('label', '') for item in results if 'label' in item]
                result['predicted_subjects'] = '; '.join(labels)
                result['top_subjects'] = '; '.join(labels[:3])
                result['project_id'] = output_data.get('project_id', 'unknown')
                result['subject_count'] = output_data.get('count', len(results))
                result['prediction_success'] = True
            else:
                result['predicted_subjects'] = ''
                result['top_subjects'] = ''
                result['error'] = output_data.get('error', 'Unknown error')
                result['prediction_success'] = False
        else:
            result['predicted_subjects'] = ''
            result['top_subjects'] = ''
            result['prediction_success'] = False

    return result


def transform_model_output(raw_output: Any, model_metadata, file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Transform raw model output based on model metadata."""
    if 'annif' in model_metadata.name.lower():
        return transform_model_output_annif(raw_output, model_metadata, file_info)

    result = {
        'file_path': file_info['file_path'],
        'file_name': file_info['file_name'],
        'file_type': file_info['file_type'],
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
        'model_task': model_metadata.task,
        'output_context': model_metadata.output_context,
    }
    result.update(file_info['metadata'])

    if file_info['data']:
        if isinstance(file_info['data'], dict):
            result.update({f"input_{k}": v for k, v in file_info['data'].items()})
        else:
            result['input_data'] = file_info['data']

    is_generative = bool(model_metadata.model_type)

    if not is_generative:
        if isinstance(raw_output, dict) and 'output' in raw_output:
            output_data = raw_output['output']
            if isinstance(output_data, dict):
                field_map = {
                    'prediction': 'y_pred',
                    'secure_probability': 'y_pred_proba',
                    'insecure_probability': 'y_pred_proba_insecure',
                    'confidence': 'confidence',
                    'model_type': 'model_subtype_used',
                    'success': 'prediction_success',
                }
                for src, dst in field_map.items():
                    if src in output_data:
                        result[dst] = output_data[src]
        elif isinstance(raw_output, (int, float, str, bool)):
            result['y_pred'] = raw_output
    else:
        if isinstance(raw_output, dict):
            field_map = {
                'output': 'generated_text',
                'success': 'generation_success',
                'usage': 'token_usage',
                'cost': 'generation_cost',
                'error': 'generation_error',
            }
            for src, dst in field_map.items():
                if src in raw_output:
                    result[dst] = raw_output[src]
        else:
            result['generated_text'] = str(raw_output)

    return result


# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------

def is_mcp_model(model_metadata) -> bool:
    return bool(getattr(model_metadata, 'mcp_tool_name', None))


def merge_mcp_output(raw_output: Dict[str, Any], model_metadata, file_info: Dict[str, Any]) -> Dict[str, Any]:
    """Merge standardised MCP output with file metadata into a flat result row."""
    result = {
        'file_path': file_info.get('file_path', ''),
        'file_name': file_info.get('file_name', ''),
        'file_type': file_info.get('file_type', ''),
        'model_id': model_metadata.id,
        'model_name': model_metadata.name,
        'model_task': model_metadata.task,
        'output_context': model_metadata.output_context,
    }
    result.update(file_info.get('metadata', {}))
    if isinstance(raw_output, dict):
        EXCLUDE = {'raw_output', 'raw_model_output', 'subject_scores'}
        for k, v in raw_output.items():
            if k not in EXCLUDE:
                result[k] = v
    else:
        result['y_pred'] = raw_output
    return result


def run_mcp_tool_sync(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Bridge: call an async MCP tool from synchronous code."""
    import concurrent.futures
    from src.services.utility_service.mcp_client import MCPClientManager

    client = MCPClientManager()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, client.call_tool(server_url, tool_name, arguments))
                return future.result(timeout=120)
        return loop.run_until_complete(client.call_tool(server_url, tool_name, arguments))
    except Exception as e:
        return {"error": str(e), "success": False}


# ---------------------------------------------------------------------------
# Inference entry points
# ---------------------------------------------------------------------------

def _resolve_provider(model_name_lower: str) -> str:
    if 'gpt' in model_name_lower or 'openai' in model_name_lower:
        return 'openai'
    if 'claude' in model_name_lower or 'anthropic' in model_name_lower:
        return 'anthropic'
    if 'gemini' in model_name_lower or 'google' in model_name_lower:
        return 'gemini'
    return 'openai'


def run_model_inference(model_metadata, input_data: Dict[str, Any], api_key: Optional[str] = None, tenant_id: Optional[str] = None) -> Any:
    """Run inference via MCP (preferred) or legacy HTTP fallback."""
    model_location = model_metadata.location
    mcp_tool_name = getattr(model_metadata, 'mcp_tool_name', None)

    if mcp_tool_name and model_location and model_location.startswith(('http://', 'https://')):
        if api_key:
            input_data["model_provider"] = _resolve_provider(model_metadata.name.lower())
            input_data["api_key"] = api_key
        if tenant_id:
            from src.services.utility_service.s3_storage_service import _tenant_bucket_name
            from src.core.config import settings
            input_data["s3_bucket"] = _tenant_bucket_name(settings.S3_BUCKET_NAME, tenant_id)
        print(f"Calling MCP tool '{mcp_tool_name}' at {model_location}")
        return run_mcp_tool_sync(model_location, mcp_tool_name, input_data)

    if model_location and model_location.lower() == "with_api_key":
        if not bool(model_metadata.model_type):
            raise ValueError("run_inference is only supported for Generative AI models")
        if not api_key:
            raise ValueError("API key required for run_inference")
        input_data["model_provider"] = _resolve_provider(model_metadata.name.lower())
        input_data["api_key"] = api_key
        try:
            response = requests.post("http://universal-llm-api:8003/predict", json=input_data, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "success": False}

    if model_location and not model_location.startswith(('http://', 'https://')):
        model_location = f"http://{model_location}"

    try:
        is_annif = 'annif' in model_metadata.name.lower() or (model_location and 'annif' in model_location.lower())
        if is_annif:
            json_data = {
                'text': input_data.get('text', ''),
                'project_id': input_data.get('project_id', 'yso-en'),
                'limit': 15,
                'threshold': input_data.get('threshold', 0.0),
            }
            response = requests.post(f"{model_location}/predict", json=json_data, timeout=60)
        else:
            response = requests.post(f"{model_location}/predict", json=input_data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {"error": str(e), "success": False}


def run_batch_model_inference(
    model_metadata,
    batch_inputs: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    batch_size: int = 20,
    tenant_id: Optional[str] = None,
) -> List[Any]:
    """Run inference on a batch of inputs."""
    model_location = model_metadata.location
    mcp_tool_name = getattr(model_metadata, 'mcp_tool_name', None)
    results: List[Any] = []
    if tenant_id:
        from src.services.utility_service.s3_storage_service import _tenant_bucket_name
        from src.core.config import settings
        s3_bucket = _tenant_bucket_name(settings.S3_BUCKET_NAME, tenant_id)
    else:
        s3_bucket = None

    if mcp_tool_name and model_location and model_location.startswith(('http://', 'https://')):
        provider = _resolve_provider(model_metadata.name.lower()) if api_key else None
        for i in range(0, len(batch_inputs), batch_size):
            chunk = batch_inputs[i: i + batch_size]
            if api_key:
                payload = {"batch_requests": [
                    {**inp, "api_key": api_key, "model_provider": provider, "model_name": model_metadata.name}
                    for inp in chunk
                ]}
            else:
                payload = {"batch_items": chunk}
            if s3_bucket:
                payload["s3_bucket"] = s3_bucket
            batch_result = run_mcp_tool_sync(model_location, mcp_tool_name, payload)
            if isinstance(batch_result, list):
                results.extend(batch_result)
            elif batch_result.get("batch_results"):
                results.extend(batch_result["batch_results"])
            elif batch_result.get("results"):
                results.extend(batch_result["results"])
            else:
                results.append(batch_result)
        return results

    if model_location and model_location.lower() == "with_api_key":
        if not bool(model_metadata.model_type):
            raise ValueError("Batch inference with API key is only supported for Generative AI models")
        if not api_key:
            raise ValueError("API key required for batch inference")
        provider = _resolve_provider(model_metadata.name.lower())
        for i in range(0, len(batch_inputs), batch_size):
            chunk = batch_inputs[i: i + batch_size]
            batch_requests = [
                {**inp, "api_key": api_key, "model_provider": provider, "model_name": model_metadata.name}
                for inp in chunk
            ]
            try:
                response = requests.post(
                    "http://universal-llm-api:8003/predict",
                    json={"batch_requests": batch_requests},
                    timeout=300,
                )
                response.raise_for_status()
                batch_result = response.json()
                if batch_result.get("batch_results"):
                    results.extend(batch_result["batch_results"])
                else:
                    results.append(batch_result)
            except requests.exceptions.RequestException as e:
                results.extend([{"error": str(e), "success": False}] * len(chunk))
    else:
        for idx, inp in enumerate(batch_inputs):
            if idx % 50 == 0 and idx > 0:
                print(f"  Processed {idx}/{len(batch_inputs)} entries...")
            results.append(run_model_inference(model_metadata, inp, api_key, tenant_id))

    return results


# ---------------------------------------------------------------------------
# Inference loop (shared by run_output_classification and run_output_evaluation)
# ---------------------------------------------------------------------------

def run_inference_loop(
    discovered_entries: List[Dict[str, Any]],
    model_metadata,
    output_csv_path: Path,
    api_key: Optional[str] = None,
    tenant_id: Optional[str] = None,
):
    """
    Run per-file inference, returning (output_df, api_connection_failed).
    Falls back to output_csv_path if the API fails mid-loop.
    """
    import pandas as pd

    model_name = model_metadata.name
    is_sam = "sam" in model_name.lower() or "attachment" in model_name.lower() or "sentiment" in model_name.lower()
    output_rows = []
    api_connection_failed = False

    for idx, file_info in enumerate(discovered_entries):
        print(f"Processing entry {idx + 1}/{len(discovered_entries)} - {file_info['file_name']}")
        try:
            model_input = prepare_model_input_sam(file_info, model_metadata) if is_sam else prepare_model_input(file_info, model_metadata)
            raw_output = run_model_inference(model_metadata, model_input, api_key, tenant_id)

            if isinstance(raw_output, dict) and raw_output.get('error') and not raw_output.get('success', True):
                api_connection_failed = True
                print(f"API connection failed: {raw_output.get('error')}")
                break

            if is_mcp_model(model_metadata):
                transformed = merge_mcp_output(raw_output, model_metadata, file_info)
            elif is_sam:
                transformed = transform_model_output_sam(raw_output, model_metadata, file_info)
            else:
                transformed = transform_model_output(raw_output, model_metadata, file_info)
            output_rows.append(transformed)

        except Exception as e:
            print(f"Error processing entry {idx + 1}: {e}")
            if any(term in str(e) for term in ("Connection", "timeout", "refused")):
                api_connection_failed = True
                break
            err = {
                'file_path': file_info['file_path'],
                'file_name': file_info['file_name'],
                'model_id': model_metadata.id,
                'model_name': model_metadata.name,
                'processing_error': str(e),
                'prediction_success': False,
            }
            err.update(file_info.get('metadata', {}))
            output_rows.append(err)

    if api_connection_failed:
        print("API connection failed, checking for output.csv fallback...")
        if output_csv_path.exists():
            try:
                return pd.read_csv(output_csv_path), False
            except Exception as e:
                print(f"Error loading output.csv: {e}")
                return None, True
        return None, True

    return pd.DataFrame(output_rows), False
