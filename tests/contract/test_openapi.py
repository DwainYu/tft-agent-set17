"""OpenAPI contract tests using Schemathesis (placeholder).

These tests will fuzz the API against its OpenAPI schema to verify that
all endpoints conform to the declared contract.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


@pytest.mark.skip(reason="OpenAPI schema not yet generated")
class TestOpenAPIContract:
    """Verify API endpoints conform to the OpenAPI specification.

    Once the OpenAPI schema is generated (e.g. from FastAPI's /openapi.json),
    these tests should:
    - Load the schema from openapi.yaml or the running app
    - Use schemathesis to generate random valid inputs
    - Assert that all responses match the declared response schemas
    - Assert that error responses use the correct status codes
    """

    def test_ask_endpoint_contract(self):
        """POST /ask should conform to OpenAPI schema."""
        raise NotImplementedError

    def test_health_endpoint_contract(self):
        """GET /health should conform to OpenAPI schema."""
        raise NotImplementedError

    def test_auth_register_contract(self):
        """POST /auth/register should conform to OpenAPI schema."""
        raise NotImplementedError

    def test_auth_login_contract(self):
        """POST /auth/login should conform to OpenAPI schema."""
        raise NotImplementedError

    def test_conversations_list_contract(self):
        """GET /conversations should conform to OpenAPI schema."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Schemathesis property-based testing (active once schema is available)
# ---------------------------------------------------------------------------
# Uncomment and configure once openapi.yaml exists:
#
# import schemathesis
#
# schema = schemathesis.from_path("openapi.yaml")
#
# @schema.parametrize()
# @pytest.mark.contract
# def test_api_fuzz(case):
#     """Fuzz every endpoint with random valid inputs."""
#     response = case.call_asgi(app=app)
#     case.validate_response(response)
