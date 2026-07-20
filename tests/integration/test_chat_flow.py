"""Integration tests for the /ask SSE chat flow and /health endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestHealthEndpoint:
    """Verify /health returns 200 with expected payload."""

    async def test_health_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestAskSSEStreaming:
    """Verify POST /ask returns a valid SSE stream."""

    async def test_ask_returns_sse_events(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/ask",
            json={"question": "盖伦最强出装推荐"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # Parse SSE events from the response body
        body = resp.text
        assert "data:" in body or "event:" in body

    async def test_ask_sse_contains_stages(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/ask",
            json={"question": "金克丝配什么装备好"},
        )
        assert resp.status_code == 200

        body = resp.text
        # The SSE stream should mention at least the understanding and result stages
        assert "understanding" in body
        assert "result" in body

    async def test_ask_with_direction_parameter(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/ask",
            json={"question": "盖伦", "direction": "推荐装备"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        body = resp.text
        assert "推荐装备" in body

    async def test_ask_with_invalid_direction_rejected(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/ask",
            json={"question": "盖伦", "direction": "invalid_direction"},
        )
        # Pydantic Literal validation should reject this
        assert resp.status_code == 422

    async def test_ask_empty_question_rejected(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/ask",
            json={"question": ""},
        )
        assert resp.status_code == 422

    async def test_ask_result_contains_json_data(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/ask",
            json={"question": "搜索暴风大剑"},
        )
        assert resp.status_code == 200
        body = resp.text

        # Find the "result" stage event and verify it has data
        lines = body.strip().split("\n")
        result_found = False
        for line in lines:
            if "result" in line and "data:" in line:
                result_found = True
                break
        # The result event should be present (even if results are empty)
        assert result_found, "Expected a 'result' SSE event in the stream"
