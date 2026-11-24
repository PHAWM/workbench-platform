"""
MCP Server Template — copy this directory to create a new model service.

Every model MCP server exposes two tools:
  1. Your prediction tool (e.g. custom_predict) — runs inference
  2. translate_io — translates between the evaluation pipeline's generic
     format and your model's specific I/O, so the pipeline stays model-agnostic.

Steps:
  1. Copy this directory and rename it (e.g., YourModel/)
  2. Update SERVICE_NAME, PORT, and TOOL_NAME below
  3. Load your model in _get_model()
  4. Implement _standardise_output() to convert your model's raw output
     into the standardised format (y_pred, prediction_success, etc.)
  5. Implement _translate_input() to convert evaluation pipeline input
     into your model's expected format
  6. Add your model to docker-compose.yml:

     your-model-api:
       build:
         context: ../../../../
         dockerfile: src/services/model_service/api/YourModel/Dockerfile
       container_name: your-model
       environment:
         - PYTHONPATH=/app
         - S3_ENDPOINT_URL=${S3_ENDPOINT_URL}
         - S3_ACCESS_KEY=${S3_ACCESS_KEY}
         - S3_SECRET_KEY=${S3_SECRET_KEY}
         - S3_BUCKET_NAME=${S3_BUCKET_NAME}
       restart: unless-stopped
       networks:
         - backend-network

  7. Register in Modelmetadata with location: "http://your-model-api:{PORT}"
     and mcp_tool_name: "{TOOL_NAME}"
"""

import json
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount

project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# -- Configuration --
SERVICE_NAME = "custom-model"
TOOL_NAME = "custom_predict"  # Must match mcp_tool_name in Modelmetadata
PORT = 8010  # SAM=8002, Universal=8003, ANNIF=8004, Eval=8005

app = Server(SERVICE_NAME)

_model = None


def _get_model():
    """Load your model here. This runs once on first tool call."""
    global _model
    if _model is None:
        _model = None  # TODO: Load your model
    return _model


def _get_s3_client():
    """Helper to create an S3 client if your model needs file access."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", ""),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", ""),
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    )


# ---------------------------------------------------------------------------
# TODO: Implement these two functions for your model
# ---------------------------------------------------------------------------

def _standardise_output(raw_result: dict) -> dict:
    """Convert your model's raw output into the standardised evaluation format.

    Must return at minimum:
      - prediction_success (bool)
      - y_pred: the primary prediction value

    Optional standardised fields:
      - y_pred_proba (float): probability of positive class
      - confidence (float)
      - generated_text (str): for generative models
    """
    return {
        "prediction_success": raw_result.get("success", False),
        "y_pred": raw_result.get("output"),
    }


def _translate_input(raw_input: dict) -> dict:
    """Translate generic evaluation input into your model's expected format.

    raw_input is the file_info-style dict from the evaluation pipeline.
    Return what your prediction tool expects as arguments.
    """
    return {"input_data": raw_input.get("data", raw_input)}


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name=TOOL_NAME,
            description="Your model's description here. Returns standardised evaluation-ready output.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_data": {
                        "type": "string",
                        "description": "The input to your model",
                    },
                    "s3_key": {
                        "type": "string",
                        "description": "Optional S3 key if your model needs file input",
                    },
                },
                "required": ["input_data"],
            },
        ),
        Tool(
            name="translate_io",
            description=(
                "Translate between the evaluation pipeline's generic format and "
                "this model's specific I/O. Use direction='input' to prepare model input, "
                "'output' to standardise model output, 'both' for both."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["input", "output", "both"],
                    },
                    "raw_input": {"type": "object"},
                    "raw_output": {"type": "object"},
                },
                "required": ["direction"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == TOOL_NAME:
        return _handle_predict(arguments)
    elif name == "translate_io":
        return _handle_translate(arguments)
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


def _handle_predict(arguments: dict):
    try:
        model = _get_model()

        # TODO: Replace with your model inference
        raw_result = {"success": True, "output": None}

        standardised = _standardise_output(raw_result)
        return [TextContent(type="text", text=json.dumps({
            "raw_output": raw_result, **standardised
        }, default=str))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({
            "prediction_success": False, "error": str(e)
        }))]


def _handle_translate(arguments: dict):
    direction = arguments.get("direction", "both")
    result = {}
    if direction in ("input", "both"):
        result["translated_input"] = _translate_input(arguments.get("raw_input", {}))
    if direction in ("output", "both"):
        result["translated_output"] = _standardise_output(arguments.get("raw_output", {}))
    return [TextContent(type="text", text=json.dumps(result, default=str))]


# --- SSE Transport ---
sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting {SERVICE_NAME} MCP Server on port {PORT}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=PORT)
