"""LLM module for natural language processing and structured output extraction."""

from fieldops.llm.client import OpenAIClient
from fieldops.llm.exceptions import (
    EmptyMessageError,
    LLMCallError,
    LLMConfigurationError,
    ServiceRequestParseError,
)
from fieldops.llm.parser import parse_service_request
from fieldops.llm.schemas import (
    AnalyzeServiceRequestResponse,
    ParsedServiceRequest,
    ParseRequestInput,
    ServiceRequestApprovalInput,
    ServiceRequestApprovalResponse,
    ServiceRequestCreateInput,
    ServiceRequestCreateResponse,
)

__all__ = [
    "OpenAIClient",
    "ParsedServiceRequest",
    "ParseRequestInput",
    "AnalyzeServiceRequestResponse",
    "ServiceRequestCreateInput",
    "ServiceRequestCreateResponse",
    "ServiceRequestApprovalInput",
    "ServiceRequestApprovalResponse",
    "parse_service_request",
    "ServiceRequestParseError",
    "EmptyMessageError",
    "LLMConfigurationError",
    "LLMCallError",
]
