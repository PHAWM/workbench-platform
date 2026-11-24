"""
Tests for MCPClientManager and run_model_inference MCP path.

All MCP network calls are mocked — no real MCP servers required.
Run with:  pytest test/test_mcp/test_mcp_client.py -v
"""

import asyncio
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.utility_service.mcp_client import MCPClientManager


# ---------------------------------------------------------------------------
# Helpers to build fake MCP result objects
# ---------------------------------------------------------------------------

def _make_tool_result(payload: Dict[str, Any]):
    """Build a fake mcp CallToolResult with one TextContent item."""
    content_item = MagicMock()
    content_item.text = json.dumps(payload)
    result = MagicMock()
    result.content = [content_item]
    return result


def _make_empty_result():
    result = MagicMock()
    result.content = []
    return result


def _make_tool_list(names):
    tools = []
    for name in names:
        t = MagicMock()
        t.name = name
        t.description = f"Tool {name}"
        t.inputSchema = {}
        tools.append(t)
    tool_list = MagicMock()
    tool_list.tools = tools
    return tool_list


# ---------------------------------------------------------------------------
# _parse_result
# ---------------------------------------------------------------------------

class TestParseResult:
    def test_parses_json_text_content(self):
        payload = {"y_pred": "secure", "prediction_success": True, "confidence": 0.9}
        result = _make_tool_result(payload)
        parsed = MCPClientManager._parse_result(result)
        assert parsed == payload

    def test_empty_content_returns_error(self):
        result = _make_empty_result()
        parsed = MCPClientManager._parse_result(result)
        assert parsed["success"] is False
        assert "Empty response" in parsed["error"]

    def test_non_json_text_returned_as_output(self):
        content_item = MagicMock()
        content_item.text = "plain text response"
        result = MagicMock()
        result.content = [content_item]
        parsed = MCPClientManager._parse_result(result)
        assert parsed["success"] is True
        assert parsed["output"] == "plain text response"


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------

class TestCallTool:
    @pytest.mark.asyncio
    async def test_call_tool_returns_parsed_result(self):
        expected = {"y_pred": "insecure", "prediction_success": True, "confidence": 0.75}
        fake_result = _make_tool_result(expected)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=fake_result)

        with patch("src.services.utility_service.mcp_client.sse_client") as mock_sse, \
             patch("src.services.utility_service.mcp_client.ClientSession") as mock_cls:

            # sse_client is used as async context manager yielding (read, write)
            mock_sse.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_sse.return_value.__aexit__ = AsyncMock(return_value=False)

            # ClientSession is used as async context manager yielding the session
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = MCPClientManager()
            result = await client.call_tool(
                server_url="http://sam-api:8002",
                tool_name="predict_attachment",
                arguments={"s3_key": "audits/audit_1/input/file.wav"},
            )

        assert result == expected
        mock_session.call_tool.assert_awaited_once_with(
            "predict_attachment", {"s3_key": "audits/audit_1/input/file.wav"}
        )

    @pytest.mark.asyncio
    async def test_call_tool_uses_sse_endpoint(self):
        fake_result = _make_tool_result({"success": True})

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=fake_result)

        captured_url = {}

        def capture_sse(url):
            captured_url["url"] = url
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        with patch("src.services.utility_service.mcp_client.sse_client", side_effect=capture_sse), \
             patch("src.services.utility_service.mcp_client.ClientSession") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = MCPClientManager()
            await client.call_tool("http://sam-api:8002", "predict_attachment", {})

        assert captured_url["url"] == "http://sam-api:8002/sse"


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

class TestListTools:
    @pytest.mark.asyncio
    async def test_list_tools_returns_tool_list(self):
        fake_tools = _make_tool_list(["predict_attachment", "translate_io"])

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=fake_tools)

        with patch("src.services.utility_service.mcp_client.sse_client") as mock_sse, \
             patch("src.services.utility_service.mcp_client.ClientSession") as mock_cls:
            mock_sse.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_sse.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = MCPClientManager()
            tools = await client.list_tools("http://sam-api:8002")

        assert len(tools) == 2
        assert tools[0].name == "predict_attachment"
        assert tools[1].name == "translate_io"


# ---------------------------------------------------------------------------
# run_model_inference — MCP path (sync bridge)
# ---------------------------------------------------------------------------

class TestRunModelInferenceMCPPath:
    def _make_model(self, location, mcp_tool_name, model_type=False, name="SAM"):
        m = MagicMock()
        m.location = location
        m.mcp_tool_name = mcp_tool_name
        m.model_type = model_type
        m.name = name
        return m

    def test_mcp_path_called_when_tool_name_set(self):
        from src.services.performance_service.run_functions import run_model_inference

        model = self._make_model("http://sam-api:8002", "predict_attachment")
        mcp_response = {"y_pred": "secure", "prediction_success": True, "confidence": 0.88}

        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync",
                   return_value=mcp_response) as mock_mcp:
            result = run_model_inference(model, {"s3_key": "audits/audit_1/input/file.wav"})

        mock_mcp.assert_called_once_with(
            "http://sam-api:8002",
            "predict_attachment",
            {"s3_key": "audits/audit_1/input/file.wav"},
        )
        assert result == mcp_response

    def test_mcp_injects_api_key_for_llm_model(self):
        from src.services.performance_service.run_functions import run_model_inference

        model = self._make_model("http://universal-llm-api:8003", "llm_inference",
                                 model_type=True, name="gpt-4")
        mcp_response = {"y_pred": "generated text", "prediction_success": True}

        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync",
                   return_value=mcp_response) as mock_mcp:
            run_model_inference(model, {"prompt": "hello"}, api_key="sk-abc123")

        _, _, call_args = mock_mcp.call_args[0]
        assert call_args["api_key"] == "sk-abc123"
        assert call_args["model_provider"] == "openai"

    def test_mcp_path_not_used_when_no_tool_name(self):
        from src.services.performance_service.run_functions import run_model_inference

        model = self._make_model("http://legacy-api:8099", None)

        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync") as mock_mcp, \
             patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            mock_post.return_value.json.return_value = {"result": "ok"}
            run_model_inference(model, {"text": "hello"})

        mock_mcp.assert_not_called()

    def test_legacy_with_api_key_path(self):
        from src.services.performance_service.run_functions import run_model_inference

        model = self._make_model("with_api_key", None, model_type=True, name="gpt-4-model")
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            mock_post.return_value.json.return_value = {"generated_text": "hello"}
            mock_post.return_value.raise_for_status = MagicMock()
            result = run_model_inference(model, {"prompt": "hello"}, api_key="sk-test")

        call_url = mock_post.call_args[0][0]
        assert "universal-llm-api" in call_url
        call_json = mock_post.call_args[1]["json"]
        assert call_json["api_key"] == "sk-test"
        assert call_json["model_provider"] == "openai"

    def test_mcp_error_returned_as_dict(self):
        from src.services.performance_service.run_functions import run_model_inference

        model = self._make_model("http://sam-api:8002", "predict_attachment")
        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync",
                   return_value={"error": "connection refused", "success": False}):
            result = run_model_inference(model, {})

        assert result["success"] is False
        assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# run_batch_model_inference — MCP path
# ---------------------------------------------------------------------------

class TestRunBatchModelInferenceMCPPath:
    def _make_model(self, location, mcp_tool_name, model_type=False, name="SAM"):
        m = MagicMock()
        m.location = location
        m.mcp_tool_name = mcp_tool_name
        m.model_type = model_type
        m.name = name
        return m

    def test_batch_mcp_path_called(self):
        from src.services.performance_service.run_functions import run_batch_model_inference

        model = self._make_model("http://annif-api:8004", "predict_subjects")
        inputs = [{"text": f"doc {i}"} for i in range(5)]
        batch_result = {"results": [{"y_pred": f"label_{i}"} for i in range(5)]}

        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync",
                   return_value=batch_result) as mock_mcp:
            results = run_batch_model_inference(model, inputs, batch_size=10)

        mock_mcp.assert_called_once()
        call_args = mock_mcp.call_args[0]
        assert call_args[0] == "http://annif-api:8004"
        assert call_args[1] == "predict_subjects"
        assert len(results) == 5

    def test_batch_mcp_chunks_correctly(self):
        from src.services.performance_service.run_functions import run_batch_model_inference

        model = self._make_model("http://annif-api:8004", "predict_subjects")
        inputs = [{"text": f"doc {i}"} for i in range(7)]

        call_count = 0
        def fake_mcp(url, tool, payload):
            nonlocal call_count
            call_count += 1
            items = payload.get("batch_items", [])
            return {"results": [{"y_pred": "label"} for _ in items]}

        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync",
                   side_effect=fake_mcp):
            results = run_batch_model_inference(model, inputs, batch_size=3)

        # 7 items / batch_size 3 → 3 calls (3+3+1)
        assert call_count == 3
        assert len(results) == 7

    def test_batch_mcp_handles_list_result(self):
        from src.services.performance_service.run_functions import run_batch_model_inference

        model = self._make_model("http://sam-api:8002", "predict_attachment")
        inputs = [{"s3_key": f"file_{i}.wav"} for i in range(3)]
        # Server returns a plain list
        list_result = [{"y_pred": "secure"}, {"y_pred": "insecure"}, {"y_pred": "secure"}]

        with patch("src.services.performance_service.run_functions._run_mcp_tool_sync",
                   return_value=list_result):
            results = run_batch_model_inference(model, inputs, batch_size=10)

        assert len(results) == 3
        assert results[1]["y_pred"] == "insecure"

    def test_batch_falls_back_to_legacy_when_no_tool_name(self):
        from src.services.performance_service.run_functions import run_batch_model_inference

        model = self._make_model("http://legacy:8099", None)
        inputs = [{"text": "a"}, {"text": "b"}]

        with patch("src.services.performance_service.run_functions.run_model_inference",
                   return_value={"result": "ok"}) as mock_single:
            results = run_batch_model_inference(model, inputs)

        assert mock_single.call_count == 2
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Scaffold route — model metadata mcp_tool_name field
# ---------------------------------------------------------------------------

class TestModelMetadataMcpToolName:
    """Verify that the mcp_tool_name field is stored and retrieved correctly."""

    def test_mcp_tool_name_on_modelmetadata(self, db):
        from src.models import Modelmetadata

        model = Modelmetadata(
            name="Test MCP Model",
            model_type=False,
            location="http://test-model:8010",
            mcp_tool_name="test_predict",
            acceptable_formats=["csv"],
            output_context="classification",
            task="binary classification",
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        assert model.mcp_tool_name == "test_predict"
        assert model.location == "http://test-model:8010"

        db.delete(model)
        db.commit()
