"""Tests for Reliability Engineering: LLM retries, timeouts, error mapping, and failure recovery (Phase 10)."""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from openai import APITimeoutError, BadRequestError
import pytest
from sqlalchemy.orm import Session

from fieldops.application.field_service_workflow import run_field_service_workflow
from fieldops.core.exceptions import LLMTimeoutError
from fieldops.core.logging import redact_email, redact_phone, sanitize_message
from fieldops.llm.client import OpenAIClient
from fieldops.llm.exceptions import LLMCallError
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)

MOCK_PARSED = ParsedServiceRequest(
    service_type="HVAC",
    urgency="high",
    location="Shinjuku",
    required_skills=["HVAC"],
    preferred_time="tomorrow afternoon",
    problem_description="AC repair",
)


# ==============================================================================
# 1. LLM Reliability, Retries, Timeouts & Failure Recovery (Section 32)
# ==============================================================================


def test_llm_retry_on_transient_timeout_succeeds_on_second_attempt() -> None:
    """1. Mock provider times out on 1st attempt, succeeds on 2nd -> retry_with_backoff succeeds."""
    mock_sdk_client = MagicMock()

    # Setup side effect: 1st call timeout, 2nd call returns valid choice
    mock_choice = MagicMock()
    mock_choice.message.refusal = None
    mock_choice.message.parsed = MOCK_PARSED

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_request = MagicMock()
    timeout_err = APITimeoutError(request=mock_request)

    mock_sdk_client.beta.chat.completions.parse.side_effect = [
        timeout_err,
        mock_completion,
    ]

    openai_client = OpenAIClient(api_key="test-key", max_retries=3)
    openai_client._client = mock_sdk_client

    result = openai_client.parse_structured(
        messages=[{"role": "user", "content": "hello"}],
        response_format=ParsedServiceRequest,
    )

    assert result.service_type == "HVAC"
    assert mock_sdk_client.beta.chat.completions.parse.call_count == 2


def test_llm_continuous_timeouts_transition_workflow_to_llm_failed() -> None:
    """2. Continuous timeouts exceeding max retries -> workflow captures llm_failed state."""
    mock_request = MagicMock()
    timeout_err = APITimeoutError(request=mock_request)

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        side_effect=LLMTimeoutError("Request timed out"),
    ):
        state = run_field_service_workflow(
            message="My AC is leaking water in Shinjuku",
            customer_name="Alice",
            email="alice@example.com",
            request_id="wf-timeout-fail",
        )

    assert state["workflow_status"] == "llm_failed"
    assert state["error_code"] == "llm_timeout"
    assert state["failed_step"] == "parse_request"
    assert state["retryable"] is True
    # Verify no technician matching or scheduling occurred
    assert state["service_type"] is None
    assert state["candidate_technician_ids"] == []


def test_llm_permanent_bad_request_does_not_retry() -> None:
    """3. HTTP 400 BadRequestError is permanent: fails immediately on 1st attempt without retrying."""
    mock_sdk_client = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 400
    bad_req_err = BadRequestError("Invalid model parameter", response=mock_response, body=None)

    mock_sdk_client.beta.chat.completions.parse.side_effect = bad_req_err

    openai_client = OpenAIClient(api_key="test-key", max_retries=3)
    openai_client._client = mock_sdk_client

    with pytest.raises(LLMCallError, match="OpenAI API bad request") as exc_info:
        openai_client.parse_structured(
            messages=[{"role": "user", "content": "hello"}],
            response_format=ParsedServiceRequest,
        )

    assert exc_info.value.retryable is False
    assert mock_sdk_client.beta.chat.completions.parse.call_count == 1


def test_llm_structured_output_invalid_fails_safely_without_hallucinating() -> None:
    """4. If model output fails schema parsing (returns None), records structured_output_invalid and halts."""
    mock_sdk_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.refusal = None
    mock_choice.message.parsed = None  # Failed structured output

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_sdk_client.beta.chat.completions.parse.return_value = mock_completion

    openai_client = OpenAIClient(api_key="test-key", max_retries=3)
    openai_client._client = mock_sdk_client

    with pytest.raises(LLMCallError, match="Failed to parse structured output"):
        openai_client.parse_structured(
            messages=[{"role": "user", "content": "hello"}],
            response_format=ParsedServiceRequest,
        )

    # When fed into workflow node, must transition to llm_failed without inventing data
    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        side_effect=LLMCallError("Failed to parse structured output from model response.", retryable=False),
    ):
        state = run_field_service_workflow(
            message="Unintelligible broken prompt",
            customer_name="Alice",
            email="alice@example.com",
            request_id="wf-invalid-schema",
        )

    assert state["workflow_status"] == "llm_failed"
    assert state["error_code"] == "structured_output_invalid"
    assert state["service_type"] is None
    assert state["retryable"] is False


# ==============================================================================
# 2. HTTP Error Mapping Tests (Section 34)
# ==============================================================================


def test_http_error_mapping_validation_error_400() -> None:
    """Validation error maps to HTTP 400 Bad Request."""
    resp = client.post("/service-requests", json={
        "customer_name": "Alice",
        "email": "alice@example.com",
        "message": "   ",
    })
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"].lower()


def test_http_error_mapping_unknown_resource_404() -> None:
    """Unknown workflow thread maps to HTTP 404 Not Found."""
    resp = client.post(
        "/service-requests/non-existent-thread-xyz/approval",
        json={"decision": "approve"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_http_error_mapping_conflict_409(test_db_session: Session) -> None:
    """Duplicate approval attempt maps to HTTP 409 Conflict."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)
    test_db_session.commit()

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=MOCK_PARSED,
    ):
        create_resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "message": "AC broken in Shinjuku tomorrow afternoon",
            },
        )
    req_id = create_resp.json()["request_id"]

    # 1st approval succeeds
    resp1 = client.post(f"/service-requests/{req_id}/approval", json={"decision": "approve"})
    assert resp1.status_code == 200

    # 2nd approval maps to 409 Conflict
    resp2 = client.post(f"/service-requests/{req_id}/approval", json={"decision": "approve"})
    assert resp2.status_code == 409
    assert "not awaiting approval" in resp2.json()["detail"].lower()


def test_http_error_mapping_llm_unavailable_503() -> None:
    """Temporary LLM outage maps to HTTP 503 Service Unavailable."""
    with patch(
        "fieldops.main.run_field_service_workflow",
        side_effect=LLMTimeoutError("OpenAI API gateway timeout"),
    ):
        resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "message": "AC broken in Shinjuku",
            },
        )
    assert resp.status_code == 503
    assert "timeout" in resp.json()["detail"].lower()


# ==============================================================================
# 3. Sensitive Data Redaction & Logging Utilities (Section 22 & 35)
# ==============================================================================


def test_redact_email() -> None:
    """Customer email is properly masked in logs."""
    assert redact_email("alice@example.com") == "a***e@example.com"
    assert redact_email("bob@test.org") == "b*b@test.org"
    assert redact_email(None) == "[EMPTY]"


def test_redact_phone() -> None:
    """Customer phone number masks all but the final 4 digits."""
    assert redact_phone("090-1234-5678") == "*********" + "5678"
    assert redact_phone("1234") == "****"
    assert redact_phone(None) == "[EMPTY]"


def test_sanitize_message() -> None:
    """Customer message records length and truncated preview."""
    msg = "My air conditioner is leaking water in Shinjuku and causing water damage to the floor"
    sanitized = sanitize_message(msg, max_preview=30)
    assert sanitized["length"] == len(msg)
    assert sanitized["preview"].endswith("...")
    assert len(sanitized["preview"]) <= 33
