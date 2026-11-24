import json
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount

import litellm

project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

app = Server("universal-llm-inference")

SUPPORTED_PROVIDERS = {
    "openai": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
    "anthropic": ["claude-3-sonnet-20240229", "claude-3-haiku-20240307", "claude-3-opus-20240229"],
    "gemini": ["gemini-pro", "gemini-pro-vision"],
    "groq": ["mixtral-8x7b-32768", "llama2-70b-4096"],
}

DEFAULT_CONFIG = {"temperature": 0.7, "max_tokens": 1000, "top_p": 1.0}


def _run_litellm_inference(inputs: dict) -> dict:
    """Run inference using LiteLLM — same logic as the old LitServe server."""
    try:
        provider = inputs["model_provider"].lower()
        api_key = inputs["api_key"]
        model_name = inputs["model_name"]

        # Set env var for the provider
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "google": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
        }
        if provider in env_map:
            os.environ[env_map[provider]] = api_key

        # Model reference prefix
        prefix_map = {"gemini": "gemini/", "google": "gemini/", "groq": "groq/"}
        model_ref = prefix_map.get(provider, "") + model_name

        # Messages
        messages = []
        if inputs.get("system_prompt"):
            messages.append({"role": "system", "content": inputs["system_prompt"]})
        messages.append({"role": "user", "content": inputs["prompt"]})

        # Extra kwargs
        kwargs = {k: v for k, v in inputs.items()
                  if k not in {"prompt", "model_name", "api_key", "model_provider",
                               "system_prompt", "temperature", "max_tokens"}}

        response = litellm.completion(
            model=model_ref,
            messages=messages,
            temperature=inputs.get("temperature", DEFAULT_CONFIG["temperature"]),
            max_tokens=inputs.get("max_tokens", DEFAULT_CONFIG["max_tokens"]),
            **kwargs,
        )

        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = None

        return {
            "success": True,
            "output": response.choices[0].message.content,
            "model_name": model_name,
            "model_provider": provider,
            "error": None,
            "usage": response.usage._asdict() if response.usage else None,
            "cost": cost,
        }
    except Exception as e:
        return {
            "success": False,
            "output": None,
            "model_name": inputs.get("model_name"),
            "model_provider": inputs.get("model_provider"),
            "error": str(e),
            "usage": None,
            "cost": None,
        }


# ---------------------------------------------------------------------------
# Standardised output translation
# ---------------------------------------------------------------------------

def _standardise_output(raw_result: dict) -> dict:
    """Convert LLM output into standardised evaluation format.

    Standardised fields:
      - generated_text (str): the model's response
      - prediction_success (bool)
      - y_pred (str): alias for generated_text (evaluation pipeline uses this)
      - token_usage (dict): prompt/completion/total tokens
      - generation_cost (float)
    """
    std = {"prediction_success": False}
    if not isinstance(raw_result, dict):
        return std

    if raw_result.get("success"):
        std["prediction_success"] = True
        std["generated_text"] = raw_result.get("output", "")
        std["y_pred"] = raw_result.get("output", "")
        std["token_usage"] = raw_result.get("usage")
        std["generation_cost"] = raw_result.get("cost")
    else:
        std["error"] = raw_result.get("error")

    return std


def _translate_input(raw_input: dict) -> dict:
    """Translate generic evaluation input into LLM-specific format.

    Accepts file_info-style dict and extracts the prompt.
    """
    data = raw_input.get("data", raw_input)
    prompt = ""

    if isinstance(data, dict):
        for field in ("prompt", "text", "content", "message", "query"):
            if field in data and data[field]:
                prompt = str(data[field])
                break
        if not prompt:
            # Create prompt from all data fields
            import pandas as pd
            parts = [f"{k}: {v}" for k, v in data.items() if not (hasattr(pd, 'isna') and pd.isna(v))]
            prompt = " | ".join(parts)
    elif isinstance(data, str):
        prompt = data

    return {
        "prompt": prompt,
        "model_name": raw_input.get("model_name", ""),
        "api_key": raw_input.get("api_key", ""),
        "model_provider": raw_input.get("model_provider", "openai"),
    }


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="llm_inference",
            description=(
                "Run LLM inference via any major provider (OpenAI, Anthropic, Gemini, Groq). "
                "Returns standardised evaluation-ready output with y_pred (generated_text)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The input prompt/message"},
                    "model_name": {"type": "string", "description": "Model identifier (e.g. gpt-4, claude-3-sonnet-20240229)"},
                    "api_key": {"type": "string", "description": "API key for the model provider"},
                    "model_provider": {"type": "string", "enum": ["openai", "anthropic", "gemini", "groq"], "description": "Provider name. Defaults to openai."},
                    "system_prompt": {"type": "string", "description": "Optional system prompt"},
                    "temperature": {"type": "number", "description": "Temperature for generation (default 0.7)"},
                    "max_tokens": {"type": "integer", "description": "Maximum tokens to generate (default 1000)"},
                    "batch_requests": {
                        "type": "array",
                        "description": "Array of request objects for batch inference",
                        "items": {"type": "object"},
                    },
                },
            },
        ),
        Tool(
            name="translate_io",
            description=(
                "Translate raw evaluation-pipeline input into LLM format, and/or "
                "translate raw LLM output into standardised evaluation format."
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
    if name == "llm_inference":
        return _handle_inference(arguments)
    elif name == "translate_io":
        return _handle_translate(arguments)
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


def _handle_translate(arguments: dict):
    direction = arguments.get("direction", "both")
    result = {}
    if direction in ("input", "both"):
        result["translated_input"] = _translate_input(arguments.get("raw_input", {}))
    if direction in ("output", "both"):
        result["translated_output"] = _standardise_output(arguments.get("raw_output", {}))
    return [TextContent(type="text", text=json.dumps(result, default=str))]


def _handle_inference(arguments: dict):
    try:
        # Batch mode
        if "batch_requests" in arguments:
            results = []
            total_cost = 0.0
            total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            for i, req in enumerate(arguments["batch_requests"]):
                req.setdefault("model_provider", "openai")
                req.setdefault("temperature", DEFAULT_CONFIG["temperature"])
                req.setdefault("max_tokens", DEFAULT_CONFIG["max_tokens"])
                result = _run_litellm_inference(req)
                results.append(result)
                if result.get("cost"):
                    total_cost += result["cost"]
                if result.get("usage"):
                    for k in total_tokens:
                        total_tokens[k] += result["usage"].get(k, 0)

            output = {
                "is_batch": True,
                "batch_results": results,
                "total_requests": len(arguments["batch_requests"]),
                "successful_requests": sum(1 for r in results if r.get("success")),
                "failed_requests": sum(1 for r in results if not r.get("success")),
                "total_cost": total_cost if total_cost > 0 else None,
                "total_usage": total_tokens if total_tokens["total_tokens"] > 0 else None,
            }
            return [TextContent(type="text", text=json.dumps(output, default=str))]

        # Single request
        for field in ("prompt", "model_name", "api_key"):
            if not arguments.get(field):
                return [TextContent(type="text", text=json.dumps({
                    "success": False, "error": f"{field} is required"
                }))]

        arguments.setdefault("model_provider", "openai")
        arguments.setdefault("temperature", DEFAULT_CONFIG["temperature"])
        arguments.setdefault("max_tokens", DEFAULT_CONFIG["max_tokens"])

        raw = _run_litellm_inference(arguments)
        standardised = _standardise_output(raw)
        return [TextContent(type="text", text=json.dumps({
            "raw_output": raw, **standardised
        }, default=str))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"prediction_success": False, "error": str(e)}))]


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
    print("Starting Universal LLM Inference MCP Server on port 8003")
    uvicorn.run(starlette_app, host="0.0.0.0", port=8003)
