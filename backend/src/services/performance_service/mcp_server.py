"""
MCP Server for the performance/evaluation pipeline.

Exposes two tools:
  - evaluate_metric: Run a single metric computation
  - run_evaluation: Run the full evaluation pipeline (read data, infer, evaluate, save)
"""

import json
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

app = Server("evaluation-service")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="evaluate_metric",
            description=(
                "Compute a single evaluation metric. Supports classification, regression, "
                "fairness, ranking, calibration, generative, and keyword metrics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Name of the metric (e.g. accuracy, f1, mse, demographic_parity, bleu)",
                    },
                    "y_pred": {
                        "type": "array",
                        "description": "Predicted values",
                        "items": {},
                    },
                    "y_true": {
                        "type": "array",
                        "description": "True/actual values",
                        "items": {},
                    },
                    "sensitive_attr": {
                        "type": "array",
                        "description": "Sensitive attribute values (for fairness metrics)",
                        "items": {},
                    },
                    "y_pred_proba": {
                        "type": "array",
                        "description": "Predicted probabilities (for AUC, calibration, etc.)",
                        "items": {},
                    },
                    "ranges": {
                        "type": "object",
                        "description": "Range definitions for grouping (e.g. age ranges)",
                    },
                    "kwargs": {
                        "type": "object",
                        "description": "Additional keyword arguments for the metric function",
                    },
                },
                "required": ["metric_name"],
            },
        ),
        Tool(
            name="list_available_metrics",
            description="List all available evaluation metrics grouped by category.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "list_available_metrics":
        return _list_metrics()
    elif name == "evaluate_metric":
        return _evaluate_metric(arguments)
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


def _list_metrics():
    from src.services.performance_service.functions import METRICS_REGISTRY

    metrics = [{"name": k, "function": METRICS_REGISTRY[k].__name__} for k in sorted(METRICS_REGISTRY)]
    return [TextContent(type="text", text=json.dumps({"metrics": metrics}))]


def _evaluate_metric(arguments: dict):
    from src.services.performance_service.run_functions import evaluate_function

    metric_name = arguments.get("metric_name")
    if not metric_name:
        return [TextContent(type="text", text=json.dumps({"error": "metric_name is required"}))]

    # Build kwargs for the metric function
    kwargs = {}
    for key in ("y_pred", "y_true", "sensitive_attr", "y_pred_proba", "ranges"):
        if key in arguments:
            kwargs[key] = arguments[key]

    # Merge any extra kwargs
    if "kwargs" in arguments and isinstance(arguments["kwargs"], dict):
        kwargs.update(arguments["kwargs"])

    try:
        result = evaluate_function(metric_name, **kwargs)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


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
    print("Starting Evaluation MCP Server on port 8005")
    uvicorn.run(starlette_app, host="0.0.0.0", port=8005)
