from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fieldops.llm import (
    EmptyMessageError,
    LLMCallError,
    LLMConfigurationError,
    ParsedServiceRequest,
    parse_service_request,
)
from fieldops.llm.client import OpenAIClient
from fieldops.main import app

client = TestClient(app)


def test_parsed_service_request_schema_validation() -> None:
    """Test ParsedServiceRequest validation with complete and minimal valid payloads."""
    # Complete payload
    full_data = {
        "service_type": "HVAC",
        "urgency": "high",
        "location": "Shinjuku",
        "required_skills": ["HVAC"],
        "preferred_time": "this afternoon",
        "problem_description": "AC stopped working with burning smell",
    }
    parsed = ParsedServiceRequest.model_validate(full_data)
    assert parsed.service_type == "HVAC"
    assert parsed.urgency == "high"
    assert parsed.location == "Shinjuku"
    assert parsed.required_skills == ["HVAC"]
    assert parsed.preferred_time == "this afternoon"
    assert parsed.problem_description == "AC stopped working with burning smell"

    # Minimal payload with nullables
    min_data = {
        "service_type": "Other",
        "urgency": "low",
        "location": None,
        "required_skills": [],
        "preferred_time": None,
        "problem_description": "General question",
    }
    parsed_min = ParsedServiceRequest.model_validate(min_data)
    assert parsed_min.location is None
    assert parsed_min.required_skills == []
    assert parsed_min.preferred_time is None

    # Missing required field raises ValidationError
    with pytest.raises(ValidationError):
        ParsedServiceRequest.model_validate({"service_type": "HVAC"})


def test_empty_message_handling() -> None:
    """Test that empty or whitespace-only messages raise EmptyMessageError."""
    with pytest.raises(EmptyMessageError, match="cannot be empty"):
        parse_service_request("")

    with pytest.raises(EmptyMessageError, match="cannot be empty"):
        parse_service_request("   \n\t  ")


def test_parser_with_mock_client_success() -> None:
    """Test parser delegates properly to client and returns structured output."""
    mock_client = MagicMock(spec=OpenAIClient)
    expected_result = ParsedServiceRequest(
        service_type="Plumbing",
        urgency="high",
        location="Yokohama",
        required_skills=["Plumbing"],
        preferred_time="tomorrow morning",
        problem_description="Water pipe leaking under the sink",
    )
    mock_client.parse_structured.return_value = expected_result

    raw_message = "Water pipe is leaking under the sink in Yokohama. Need someone tomorrow morning."
    result = parse_service_request(raw_message, client=mock_client)

    assert result == expected_result
    mock_client.parse_structured.assert_called_once()
    call_args = mock_client.parse_structured.call_args[1]
    messages = call_args["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == raw_message
    assert call_args["response_format"] == ParsedServiceRequest


def test_parser_with_mock_client_llm_call_error() -> None:
    """Test parser raises LLMCallError when client call fails."""
    mock_client = MagicMock(spec=OpenAIClient)
    mock_client.parse_structured.side_effect = LLMCallError("Rate limit exceeded")

    with pytest.raises(LLMCallError, match="Rate limit exceeded"):
        parse_service_request("Help with my heating", client=mock_client)


def test_parser_missing_api_key_error() -> None:
    """Test that unconfigured client raises LLMConfigurationError."""
    unconfigured_client = OpenAIClient(api_key=None)
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY is not configured"):
        parse_service_request("AC is broken", client=unconfigured_client)


def test_api_parse_service_request_success() -> None:
    """Test POST /parse-service-request endpoint with successful parse."""
    mock_parsed = ParsedServiceRequest(
        service_type="HVAC",
        urgency="high",
        location="Shinjuku",
        required_skills=["HVAC"],
        preferred_time="this afternoon",
        problem_description="AC stopped working with burning smell",
    )

    with patch("fieldops.main.parse_service_request", return_value=mock_parsed):
        response = client.post(
            "/parse-service-request",
            json={
                "message": "My AC stopped working and there is a burning smell. I'm in Shinjuku and need someone this afternoon."
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["service_type"] == "HVAC"
    assert data["urgency"] == "high"
    assert data["location"] == "Shinjuku"
    assert data["required_skills"] == ["HVAC"]
    assert data["preferred_time"] == "this afternoon"
    assert data["problem_description"] == "AC stopped working with burning smell"


def test_api_parse_service_request_empty_message() -> None:
    """Test POST /parse-service-request with empty input returns 400."""
    response = client.post("/parse-service-request", json={"message": "   "})
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]


def test_api_parse_service_request_missing_api_key() -> None:
    """Test POST /parse-service-request returns 503 when API key is not set."""
    with patch(
        "fieldops.main.parse_service_request",
        side_effect=LLMConfigurationError("OPENAI_API_KEY is not configured"),
    ):
        response = client.post(
            "/parse-service-request",
            json={"message": "Need electrician for sparking outlet"},
        )
    assert response.status_code == 503
    assert "OPENAI_API_KEY is not configured" in response.json()["detail"]


def test_api_parse_service_request_llm_call_failure() -> None:
    """Test POST /parse-service-request returns 502 when upstream LLM fails."""
    with patch(
        "fieldops.main.parse_service_request",
        side_effect=LLMCallError("Upstream API error"),
    ):
        response = client.post(
            "/parse-service-request",
            json={"message": "Help with plumbing leak"},
        )
    assert response.status_code == 502
    assert "Upstream API error" in response.json()["detail"]
