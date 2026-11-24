import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

# Ensure project root is on the path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

app = Server("sam-attachment-monitor")

# Model loaded at startup
_predictor = None


def _get_predictor():
    global _predictor
    if _predictor is None:
        from src.services.model_service.models.SAM import AttachmentPredictor
        _predictor = AttachmentPredictor()
        _predictor.load_models()
    return _predictor


def _get_s3_client():
    """Create an S3 client from environment variables."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", ""),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", ""),
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    )


# ---------------------------------------------------------------------------
# Standardised output translation
# ---------------------------------------------------------------------------

def _standardise_output(raw_result: dict, model_type: str) -> dict:
    """Convert SAM's nested model outputs into the standardised evaluation format.

    Standardised fields:
      - y_pred (int): 1=Secure, 0=Insecure  (primary prediction)
      - y_pred_proba (float): probability of the positive class
      - confidence (float): max(secure_prob, insecure_prob)
      - prediction_success (bool)
      - model_details (dict): per-sub-model breakdown
    """
    std = {"prediction_success": False, "model_details": {}}

    # raw_result is the predictor output — could be a dict keyed by model name
    # when model_type == "all", or a single model output otherwise.
    if not isinstance(raw_result, dict):
        return std

    # Collect successful sub-model outputs
    model_outputs = []
    mc2_output = None

    for key in ("audio", "text", "mc1", "mc2"):
        sub = raw_result.get(key)
        if isinstance(sub, dict) and sub.get("success"):
            model_outputs.append(sub)
            std["model_details"][key] = {
                "prediction": sub.get("prediction"),
                "confidence": sub.get("confidence"),
                "secure_probability": sub.get("secure_probability"),
                "insecure_probability": sub.get("insecure_probability"),
            }
            if key == "mc2":
                mc2_output = sub

    # If only a single-model result (not keyed by audio/text/mc1/mc2)
    if not model_outputs and raw_result.get("success"):
        model_outputs = [raw_result]
        mc2_output = raw_result  # treat single model as primary

    if not model_outputs:
        return std

    std["prediction_success"] = True

    # --- Primary prediction (MC2 preferred, else majority vote) ---
    primary = mc2_output if mc2_output else None

    if primary:
        pred = primary.get("prediction")
        if isinstance(pred, str):
            std["y_pred"] = 1 if pred.lower() == "secure" else 0
        elif isinstance(pred, (int, float)):
            std["y_pred"] = int(pred)
        std["y_pred_proba"] = primary.get("secure_probability")
        std["confidence"] = primary.get("confidence")
    else:
        # Majority vote
        numeric_preds = []
        for m in model_outputs:
            p = m.get("prediction")
            if isinstance(p, str):
                numeric_preds.append(1 if p.lower() == "secure" else 0)
            elif isinstance(p, (int, float)):
                numeric_preds.append(int(p))
        if numeric_preds:
            std["y_pred"] = Counter(numeric_preds).most_common(1)[0][0]

        # Average probabilities
        sec_probs = [m["secure_probability"] for m in model_outputs if m.get("secure_probability") is not None]
        if sec_probs:
            std["y_pred_proba"] = sum(sec_probs) / len(sec_probs)
            insec_probs = [m["insecure_probability"] for m in model_outputs if m.get("insecure_probability") is not None]
            if insec_probs:
                std["confidence"] = max(std["y_pred_proba"], sum(insec_probs) / len(insec_probs))

    return std


# ---------------------------------------------------------------------------
# I/O translation tool
# ---------------------------------------------------------------------------

def _translate_input(raw_input: dict) -> dict:
    """Translate generic evaluation input into SAM-specific format.

    Accepts the evaluation pipeline's file_info-style dict and returns
    exactly what predict_attachment expects, handling path conversions.
    """
    # S3 key takes priority
    s3_key = raw_input.get("s3_key")
    if s3_key:
        return {"s3_key": s3_key, "model_type": raw_input.get("model_type", "all")}

    # Local file path — handle Docker container path translation
    file_path = raw_input.get("file_path", raw_input.get("file_location", ""))
    if file_path:
        path_str = str(file_path)
        # Convert host storage path to container path
        if "storage/" in path_str and not path_str.startswith("/app/"):
            storage_part = path_str.split("storage/", 1)[1]
            path_str = "/app/storage/" + storage_part
        return {"file_location": path_str, "model_type": raw_input.get("model_type", "all")}

    return raw_input


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="predict_attachment",
            description=(
                "Predict attachment style from an audio file. "
                "Returns standardised evaluation-ready output with y_pred, y_pred_proba, confidence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "s3_key": {
                        "type": "string",
                        "description": "S3 key of the audio file to analyse",
                    },
                    "s3_bucket": {
                        "type": "string",
                        "description": "S3 bucket override (multi-tenant). Defaults to S3_BUCKET_NAME env var.",
                    },
                    "model_type": {
                        "type": "string",
                        "enum": ["audio", "text", "mc1", "mc2", "all"],
                        "description": "Which SAM model to run. Defaults to 'all'.",
                    },
                    "file_location": {
                        "type": "string",
                        "description": "Direct file path (legacy local mode). Use s3_key for S3.",
                    },
                },
            },
        ),
        Tool(
            name="translate_io",
            description=(
                "Translate raw evaluation-pipeline input into SAM format, and/or "
                "translate raw SAM output into standardised evaluation format. "
                "Use this to avoid model-specific logic in the evaluation pipeline."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["input", "output", "both"],
                        "description": "'input' to translate eval input → SAM input, "
                                       "'output' to translate SAM output → standardised, "
                                       "'both' to do a full round-trip (run prediction too).",
                    },
                    "raw_input": {
                        "type": "object",
                        "description": "The raw input from the evaluation pipeline (file_info style).",
                    },
                    "raw_output": {
                        "type": "object",
                        "description": "The raw SAM output to translate (for direction='output').",
                    },
                    "model_type": {
                        "type": "string",
                        "enum": ["audio", "text", "mc1", "mc2", "all"],
                    },
                },
                "required": ["direction"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    print(f"[SAM MCP] call_tool invoked: name={name!r} arguments={arguments!r}", flush=True)
    if name == "predict_attachment":
        return await _handle_predict(arguments)
    elif name == "translate_io":
        return _handle_translate(arguments)
    else:
        print(f"[SAM MCP] Unknown tool: {name}", flush=True)
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def _handle_predict(arguments: dict):
    model_type = arguments.get("model_type", "all")
    s3_key = arguments.get("s3_key")
    s3_bucket = arguments.get("s3_bucket")
    file_location = arguments.get("file_location")
    print(f"[SAM MCP] _handle_predict: s3_key={s3_key} s3_bucket={s3_bucket} file_location={file_location} model_type={model_type}", flush=True)

    try:
        predictor = _get_predictor()

        # Determine file path
        if s3_key:
            s3 = _get_s3_client()
            bucket = s3_bucket or os.environ.get("S3_BUCKET_NAME", "workbench")
            print(f"[SAM MCP] Downloading from bucket={bucket!r} key={s3_key!r} endpoint={os.environ.get('S3_ENDPOINT_URL')!r}", flush=True)
            suffix = "." + s3_key.rsplit(".", 1)[-1] if "." in s3_key else ".wav"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                s3.download_fileobj(bucket, s3_key, tmp)
            except Exception as dl_err:
                print(f"[SAM MCP] download_fileobj FAILED: {dl_err!r}", flush=True)
                # Try a list to confirm visibility
                try:
                    listing = s3.list_objects_v2(Bucket=bucket, Prefix=s3_key, MaxKeys=3)
                    print(f"[SAM MCP] list with prefix returned: {[o['Key'] for o in listing.get('Contents', [])]}", flush=True)
                except Exception as ls_err:
                    print(f"[SAM MCP] list FAILED too: {ls_err!r}", flush=True)
                raise
            tmp.close()
            audio_file_path = tmp.name
            cleanup = True
        elif file_location:
            audio_file_path = file_location
            cleanup = False
        else:
            return [TextContent(type="text", text=json.dumps({
                "success": False, "error": "Either s3_key or file_location is required"
            }))]

        # Run prediction
        if model_type == "all" or not model_type:
            raw_result = predictor.predict_all_models(audio_file_path)
        else:
            raw_result = predictor.predict_single_model(audio_file_path, model_type)

        if cleanup:
            os.unlink(audio_file_path)

        # Return both raw and standardised output
        standardised = _standardise_output(raw_result, model_type)
        return [TextContent(type="text", text=json.dumps({
            "raw_output": raw_result,
            **standardised,
        }, default=str))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({
            "prediction_success": False, "error": str(e)
        }))]


def _handle_translate(arguments: dict):
    direction = arguments.get("direction", "both")
    result = {}

    if direction in ("input", "both"):
        raw_input = arguments.get("raw_input", {})
        result["translated_input"] = _translate_input(raw_input)

    if direction in ("output", "both"):
        raw_output = arguments.get("raw_output", {})
        model_type = arguments.get("model_type", "all")
        result["translated_output"] = _standardise_output(raw_output, model_type)

    return [TextContent(type="text", text=json.dumps(result, default=str))]


# --- SSE Transport ---
sse = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())
    return Response()


starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)


if __name__ == "__main__":
    import uvicorn
    print("Starting SAM Attachment Monitor MCP Server on port 8002")
    uvicorn.run(starlette_app, host="0.0.0.0", port=8002)
