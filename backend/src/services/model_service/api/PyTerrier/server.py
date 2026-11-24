"""
PyTerrier RAG MCP Server — BM25 retrieval over user-provided prompt/document files.

Pipeline:
  1. pyterrier_index  — builds a BM25 index from .txt files at a given S3 prefix
                        (one index per prefix, persisted to /data/indexes/)
  2. pyterrier_rag    — takes a query, retrieves top-K docs from the index,
                        then calls the LLM MCP registered in Modelmetadata to
                        generate a grounded answer from the retrieved context.
  3. translate_io     — standard evaluation pipeline I/O translation.

Index persistence:
  Indexes are stored at /data/indexes/<index_id>/ inside the container.
  index_id is the MD5 of the S3 prefix so the same corpus always maps to the
  same index directory and avoids re-indexing on every call.

LLM generation:
  The server calls the Universal LLM MCP (http://universal-llm-inference:8003)
  using the same MCPClientManager pattern used by the main backend.  The caller
  must pass model_provider, model_name, and api_key in the request so no keys
  are stored in the container.

Port: 8006
"""

import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import boto3
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount, Route

project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVICE_NAME = "pyterrier-rag"
TOOL_NAME = "pyterrier_rag"
PORT = 8006

# Where indexes are persisted inside the container (mounted volume in compose)
INDEX_BASE = Path(os.environ.get("PYTERRIER_INDEX_DIR", "/data/indexes"))

# Universal LLM MCP endpoint — can be overridden via env for testing
LLM_MCP_URL = os.environ.get("LLM_MCP_URL", "http://universal-llm-inference:8003")

# Default retrieval depth
DEFAULT_TOP_K = 5

app = Server(SERVICE_NAME)

# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", ""),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", ""),
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    )


def _download_prefix_to_dir(s3_prefix: str, local_dir: Path, s3_bucket: str | None = None) -> list[dict]:
    """
    Download all .txt files under s3_prefix into local_dir.
    Returns a list of dicts: [{docno, text, file_name}, ...]
    """
    bucket = s3_bucket or os.environ.get("S3_BUCKET_NAME", "workbench")
    s3 = _get_s3_client()

    paginator = s3.get_paginator("list_objects_v2")
    docs = []

    for page in paginator.paginate(Bucket=bucket, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".txt"):
                continue

            local_path = local_dir / Path(key).name
            s3.download_file(bucket, key, str(local_path))

            text = local_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                # docno must be alphanumeric for PyTerrier
                safe_name = Path(key).stem.replace("-", "_").replace(".", "_")
                docs.append({
                    "docno": safe_name,
                    "text": text,
                    "file_name": Path(key).name,
                    "s3_key": key,
                })

    return docs


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def _index_id(s3_prefix: str, s3_bucket: str | None = None) -> str:
    """Stable directory name for a given (bucket, prefix) pair."""
    key = f"{s3_bucket or ''}::{s3_prefix}"
    return hashlib.md5(key.encode()).hexdigest()


def _index_path(s3_prefix: str, s3_bucket: str | None = None) -> Path:
    return INDEX_BASE / _index_id(s3_prefix, s3_bucket)


def _index_exists(s3_prefix: str, s3_bucket: str | None = None) -> bool:
    idx = _index_path(s3_prefix, s3_bucket)
    return (idx / "data.properties").exists()


def _build_index(s3_prefix: str, force: bool = False, s3_bucket: str | None = None) -> dict:
    """
    Download docs from S3 and build a BM25 index.
    Returns metadata about the index.
    """
    import pyterrier as pt

    if not pt.started():
        pt.init()

    idx_path = _index_path(s3_prefix, s3_bucket)

    if _index_exists(s3_prefix, s3_bucket) and not force:
        return {
            "index_path": str(idx_path),
            "rebuilt": False,
            "doc_count": None,  # unknown without loading
        }

    idx_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        docs = _download_prefix_to_dir(s3_prefix, Path(tmp), s3_bucket)

    if not docs:
        raise ValueError(f"No .txt files found under S3 prefix: {s3_prefix!r}")

    import pandas as pd
    df = pd.DataFrame(docs)[["docno", "text"]]

    indexer = pt.IterDictIndexer(str(idx_path), overwrite=True)
    indexer.index(df.to_dict(orient="records"))

    return {
        "index_path": str(idx_path),
        "rebuilt": True,
        "doc_count": len(docs),
        "s3_prefix": s3_prefix,
        "s3_bucket": s3_bucket,
    }


def _load_retriever(s3_prefix: str, top_k: int, s3_bucket: str | None = None):
    """Return a BM25 retriever for the index at s3_prefix."""
    import pyterrier as pt

    if not pt.started():
        pt.init()

    idx_path = _index_path(s3_prefix, s3_bucket)
    index = pt.IndexFactory.of(str(idx_path))
    return pt.BatchRetrieve(index, wmodel="BM25", num_results=top_k, metadata=["docno", "text"])


# ---------------------------------------------------------------------------
# LLM generation via Universal MCP
# ---------------------------------------------------------------------------

async def _call_llm_mcp(
    prompt: str,
    model_provider: str,
    model_name: str,
    api_key: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> dict:
    """Call the Universal LLM MCP and return its raw response dict."""
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client

    sse_url = LLM_MCP_URL.rstrip("/") + "/sse"
    arguments = {
        "prompt": prompt,
        "model_provider": model_provider,
        "model_name": model_name,
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_prompt:
        arguments["system_prompt"] = system_prompt

    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("llm_inference", arguments=arguments)

    if result and result.content:
        raw = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"prediction_success": False, "error": "LLM MCP returned non-JSON", "raw": raw}

    return {"prediction_success": False, "error": "Empty response from LLM MCP"}


# ---------------------------------------------------------------------------
# Core RAG logic
# ---------------------------------------------------------------------------

def _build_rag_prompt(query: str, retrieved_docs: list[dict], system_prompt: Optional[str]) -> tuple[str, str]:
    """
    Build the final prompt string from query + retrieved context.
    Returns (user_prompt, system_prompt).
    """
    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        context_parts.append(f"[Document {i}] (file: {doc.get('file_name', doc['docno'])})\n{doc['text']}")

    context_block = "\n\n".join(context_parts)

    user_prompt = (
        f"Use the following documents to answer the question.\n\n"
        f"{context_block}\n\n"
        f"Question: {query}"
    )

    final_system = system_prompt or (
        "You are a helpful assistant. Answer only based on the provided documents. "
        "If the answer is not in the documents, say so."
    )

    return user_prompt, final_system


def _run_rag(arguments: dict) -> list:
    """
    Full RAG pipeline:
      1. Ensure index exists (build if needed)
      2. BM25 retrieval
      3. Async LLM generation
    """
    query = arguments.get("query", "").strip()
    s3_prefix = arguments.get("s3_prefix", "").strip()
    s3_bucket = arguments.get("s3_bucket")
    model_provider = arguments.get("model_provider", "openai")
    model_name = arguments.get("model_name", "")
    api_key = arguments.get("api_key", "")
    top_k = int(arguments.get("top_k", DEFAULT_TOP_K))
    system_prompt = arguments.get("system_prompt")
    temperature = float(arguments.get("temperature", 0.7))
    max_tokens = int(arguments.get("max_tokens", 1024))
    force_reindex = bool(arguments.get("force_reindex", False))

    if not query:
        return [TextContent(type="text", text=json.dumps({"prediction_success": False, "error": "query is required"}))]
    if not s3_prefix:
        return [TextContent(type="text", text=json.dumps({"prediction_success": False, "error": "s3_prefix is required"}))]
    if not model_name:
        return [TextContent(type="text", text=json.dumps({"prediction_success": False, "error": "model_name is required"}))]
    if not api_key:
        return [TextContent(type="text", text=json.dumps({"prediction_success": False, "error": "api_key is required"}))]

    try:
        # 1. Index
        if not _index_exists(s3_prefix, s3_bucket) or force_reindex:
            _build_index(s3_prefix, force=force_reindex, s3_bucket=s3_bucket)

        # 2. Retrieve
        import pandas as pd
        retriever = _load_retriever(s3_prefix, top_k, s3_bucket)
        results_df = retriever.search(query)

        if results_df.empty:
            retrieved = []
        else:
            retrieved = results_df[["docno", "text", "score"]].to_dict(orient="records")

        # 3. Generate
        user_prompt, sys_prompt = _build_rag_prompt(query, retrieved, system_prompt)

        llm_response = asyncio.run(
            _call_llm_mcp(
                prompt=user_prompt,
                model_provider=model_provider,
                model_name=model_name,
                api_key=api_key,
                system_prompt=sys_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

        generated_text = llm_response.get("generated_text") or llm_response.get("y_pred", "")
        prediction_success = llm_response.get("prediction_success", False)

        output = {
            "prediction_success": prediction_success,
            "y_pred": generated_text,
            "generated_text": generated_text,
            "query": query,
            "retrieved_docs": retrieved,
            "retrieved_count": len(retrieved),
            "s3_prefix": s3_prefix,
            "model_name": model_name,
            "model_provider": model_provider,
            "token_usage": llm_response.get("token_usage"),
            "generation_cost": llm_response.get("generation_cost"),
        }

    except Exception as e:
        output = {"prediction_success": False, "error": str(e), "query": query}

    return [TextContent(type="text", text=json.dumps(output, default=str))]


def _run_index(arguments: dict) -> list:
    """Build or rebuild a BM25 index for an S3 prefix."""
    s3_prefix = arguments.get("s3_prefix", "").strip()
    s3_bucket = arguments.get("s3_bucket")
    force = bool(arguments.get("force_reindex", False))

    if not s3_prefix:
        return [TextContent(type="text", text=json.dumps({"success": False, "error": "s3_prefix is required"}))]

    try:
        result = _build_index(s3_prefix, force=force, s3_bucket=s3_bucket)
        result["success"] = True
        result["index_id"] = _index_id(s3_prefix, s3_bucket)
    except Exception as e:
        result = {"success": False, "error": str(e), "s3_prefix": s3_prefix}

    return [TextContent(type="text", text=json.dumps(result, default=str))]


# ---------------------------------------------------------------------------
# Standardised output / input translation
# ---------------------------------------------------------------------------

def _standardise_output(raw_result: dict) -> dict:
    return {
        "prediction_success": raw_result.get("prediction_success", False),
        "y_pred": raw_result.get("generated_text") or raw_result.get("y_pred", ""),
        "generated_text": raw_result.get("generated_text", ""),
        "retrieved_docs": raw_result.get("retrieved_docs", []),
        "retrieved_count": raw_result.get("retrieved_count", 0),
    }


def _translate_input(raw_input: dict) -> dict:
    """
    Convert an evaluation-pipeline file_info dict into pyterrier_rag arguments.
    The pipeline passes text content as raw_input["data"]["text"] or similar.
    """
    data = raw_input.get("data", raw_input)
    query = ""
    if isinstance(data, dict):
        for field in ("query", "prompt", "text", "content", "message"):
            if data.get(field):
                query = str(data[field])
                break
    elif isinstance(data, str):
        query = data

    return {
        "query": query,
        "s3_prefix": raw_input.get("s3_prefix", ""),
        "model_provider": raw_input.get("model_provider", "openai"),
        "model_name": raw_input.get("model_name", ""),
        "api_key": raw_input.get("api_key", ""),
        "top_k": raw_input.get("top_k", DEFAULT_TOP_K),
    }


# ---------------------------------------------------------------------------
# MCP tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name=TOOL_NAME,
            description=(
                "RAG pipeline using PyTerrier BM25 retrieval + LLM generation. "
                "Retrieves relevant documents from an S3 prefix, then generates a "
                "grounded answer via the Universal LLM MCP. "
                "Returns y_pred (generated answer) and retrieved_docs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or prompt to answer from the document corpus.",
                    },
                    "s3_prefix": {
                        "type": "string",
                        "description": (
                            "S3 key prefix pointing to the .txt corpus to retrieve from. "
                            "e.g. 'storage/audits/audit_2/input/' or 'storage/users/{user_id}/output_evaluation/audit_1/input/'"
                        ),
                    },
                    "s3_bucket": {
                        "type": "string",
                        "description": "S3 bucket override (multi-tenant). Defaults to S3_BUCKET_NAME env var.",
                    },
                    "model_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "gemini", "groq"],
                        "description": "LLM provider for generation. Passed through to Universal LLM MCP.",
                    },
                    "model_name": {
                        "type": "string",
                        "description": "Model identifier, e.g. gpt-4, claude-3-sonnet-20240229.",
                    },
                    "api_key": {
                        "type": "string",
                        "description": "API key for the chosen provider.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": f"Number of documents to retrieve. Default {DEFAULT_TOP_K}.",
                        "default": DEFAULT_TOP_K,
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional system prompt for the LLM. Defaults to a grounded-answer instruction.",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "LLM temperature. Default 0.7.",
                        "default": 0.7,
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Max tokens for LLM generation. Default 1024.",
                        "default": 1024,
                    },
                    "force_reindex": {
                        "type": "boolean",
                        "description": "If true, rebuild the index even if one already exists for this prefix.",
                        "default": False,
                    },
                },
                "required": ["query", "s3_prefix", "model_name", "api_key"],
            },
        ),
        Tool(
            name="pyterrier_index",
            description=(
                "Build or rebuild a BM25 index from .txt files at an S3 prefix. "
                "Call this once per corpus before running pyterrier_rag, or when "
                "the corpus changes. The index is persisted to disk so pyterrier_rag "
                "can skip re-indexing on subsequent calls."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "s3_prefix": {
                        "type": "string",
                        "description": "S3 key prefix containing the .txt files to index.",
                    },
                    "s3_bucket": {
                        "type": "string",
                        "description": "S3 bucket override (multi-tenant). Defaults to S3_BUCKET_NAME env var.",
                    },
                    "force_reindex": {
                        "type": "boolean",
                        "description": "Rebuild even if an index already exists. Default false.",
                        "default": False,
                    },
                },
                "required": ["s3_prefix"],
            },
        ),
        Tool(
            name="translate_io",
            description=(
                "Translate between the evaluation pipeline's generic format and "
                "this service's specific I/O. direction='input' prepares pyterrier_rag "
                "arguments from a file_info dict; direction='output' standardises results."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["input", "output", "both"]},
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
        return _run_rag(arguments)
    elif name == "pyterrier_index":
        return _run_index(arguments)
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


# ---------------------------------------------------------------------------
# SSE transport
# ---------------------------------------------------------------------------

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
    INDEX_BASE.mkdir(parents=True, exist_ok=True)
    print(f"Starting {SERVICE_NAME} MCP Server on port {PORT}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=PORT)
