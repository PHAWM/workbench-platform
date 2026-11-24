import asyncio
import json
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

app = Server("annif-subject-indexing")

AVAILABLE_PROJECTS = {
    "yso-en": {"name": "YSO English (2025.2.Kant)", "language": "en", "backend": "nn_ensemble"},
    "ykl-en": {"name": "PLC English", "language": "en", "backend": "ensemble"},
}

_predictor = None


def _get_predictor():
    global _predictor
    if _predictor is None:
        from src.services.model_service.models.ANNIF.annif_predictor import AnnifPredictor
        _predictor = AnnifPredictor(
            base_url="https://ai.finto.fi/v1",
            available_projects=AVAILABLE_PROJECTS,
        )
    return _predictor


# ---------------------------------------------------------------------------
# Standardised output translation
# ---------------------------------------------------------------------------

def _standardise_output(raw_result: dict) -> dict:
    """Convert ANNIF's raw output into the standardised evaluation format.

    Standardised fields:
      - predicted_subjects (str): semicolon-separated predicted labels
      - top_subjects (str): top 3 labels
      - subject_count (int)
      - y_pred (str): predicted_subjects (for keyword_accuracy metric)
      - prediction_success (bool)
    """
    std = {"prediction_success": False}

    if not isinstance(raw_result, dict):
        return std

    # The predictor returns {"success": True, "results": [...], "project_id": ...}
    if raw_result.get("success") and "results" in raw_result:
        results = raw_result["results"]
        labels = [item.get("label", "") for item in results if "label" in item]

        std["predicted_subjects"] = "; ".join(labels)
        std["top_subjects"] = "; ".join(labels[:3])
        std["subject_count"] = raw_result.get("count", len(results))
        std["project_id"] = raw_result.get("project_id", "unknown")
        std["prediction_success"] = True

        # y_pred for the evaluation pipeline (keyword_accuracy uses this)
        std["y_pred"] = std["predicted_subjects"]

        # Per-subject scores for detailed analysis
        std["subject_scores"] = [
            {"label": item.get("label"), "score": item.get("score")}
            for item in results
        ]
    elif "error" in raw_result:
        std["error"] = raw_result["error"]

    return std


def _translate_input(raw_input: dict) -> dict:
    """Translate generic evaluation input into ANNIF-specific format.

    Accepts file_info-style dict from the evaluation pipeline and returns
    what predict_subjects expects, including HTML extraction.
    """
    text = ""
    # Extract text from various possible fields
    data = raw_input.get("data", raw_input)
    if isinstance(data, dict):
        for field in ("text", "content", "prompt"):
            if field in data and data[field]:
                text = str(data[field])
                break
        if not text:
            text = str(data)
    elif isinstance(data, str):
        text = data

    # HTML extraction
    text_stripped = text.strip()
    if text_stripped.startswith("<") and ("html" in text_stripped.lower() or "<body" in text_stripped.lower()):
        try:
            from src.services.model_service.models.ANNIF.annif_predictor import AnnifPredictor
            text = AnnifPredictor.extract_text_from_html(text)
        except Exception:
            pass

    return {
        "text": text,
        "project_id": raw_input.get("project_id", data.get("project_id", "yso-en") if isinstance(data, dict) else "yso-en"),
        "limit": raw_input.get("limit", 15),
        "threshold": raw_input.get("threshold", 0.0),
    }


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="predict_subjects",
            description=(
                "Predict subjects/topics for text documents using ANNIF. "
                "Returns standardised evaluation-ready output with y_pred (predicted_subjects), subject_count."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to classify (single request)"},
                    "documents": {
                        "type": "array",
                        "description": "Array of text strings for batch prediction",
                        "items": {"type": "string"},
                    },
                    "project_id": {
                        "type": "string",
                        "enum": list(AVAILABLE_PROJECTS.keys()),
                        "description": "ANNIF project to use. Defaults to yso-en.",
                    },
                    "limit": {"type": "integer", "description": "Max number of subjects to return (default 10)"},
                    "threshold": {"type": "number", "description": "Minimum score threshold (default 0.0)"},
                },
            },
        ),
        Tool(
            name="translate_io",
            description=(
                "Translate raw evaluation-pipeline input into ANNIF format, and/or "
                "translate raw ANNIF output into standardised evaluation format."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["input", "output", "both"],
                        "description": "'input' to translate eval input → ANNIF input, "
                                       "'output' to translate ANNIF output → standardised, "
                                       "'both' for full round-trip.",
                    },
                    "raw_input": {
                        "type": "object",
                        "description": "The raw input from the evaluation pipeline.",
                    },
                    "raw_output": {
                        "type": "object",
                        "description": "The raw ANNIF output to translate (for direction='output').",
                    },
                },
                "required": ["direction"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "predict_subjects":
        return await _handle_predict(arguments)
    elif name == "translate_io":
        return _handle_translate(arguments)
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def _handle_predict(arguments: dict):
    try:
        predictor = _get_predictor()
        project_id = arguments.get("project_id", "yso-en")
        limit = arguments.get("limit", 10)
        threshold = arguments.get("threshold", 0.0)

        documents = arguments.get("documents")
        text = arguments.get("text", "")

        if documents is not None:
            raw_result = await asyncio.to_thread(
                predictor.predict_batch, documents, project_id, limit, threshold
            )
            # Batch: standardise each item
            if isinstance(raw_result, list):
                standardised = [_standardise_output(r) for r in raw_result]
            else:
                standardised = _standardise_output(raw_result)
            return [TextContent(type="text", text=json.dumps({
                "raw_output": raw_result,
                "standardised": standardised,
            }, default=str))]
        else:
            raw_result = await asyncio.to_thread(
                predictor.predict, text, project_id, limit, threshold
            )
            standardised = _standardise_output(raw_result)
            return [TextContent(type="text", text=json.dumps({
                "raw_output": raw_result,
                **standardised,
            }, default=str))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"prediction_success": False, "error": str(e)}))]


def _handle_translate(arguments: dict):
    direction = arguments.get("direction", "both")
    result = {}

    if direction in ("input", "both"):
        raw_input = arguments.get("raw_input", {})
        result["translated_input"] = _translate_input(raw_input)

    if direction in ("output", "both"):
        raw_output = arguments.get("raw_output", {})
        result["translated_output"] = _standardise_output(raw_output)

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
    print("Starting ANNIF Subject Indexing MCP Server on port 8004")
    uvicorn.run(starlette_app, port=8004)
