"""LLM parsing and client exceptions integrated with core exception hierarchy."""

from typing import Any

from fieldops.core.exceptions import (
    FieldOpsError,
    LLMServiceError,
    ValidationError,
)


class ServiceRequestParseError(FieldOpsError):
    """Base exception for service request parsing failures."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class EmptyMessageError(ValidationError, ServiceRequestParseError):
    """Raised when the input customer message is empty or whitespace only (HTTP 400)."""

    def __init__(
        self,
        message: str = "Customer service request message cannot be empty.",
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, retryable=False, status_code=400, **kwargs)


class LLMConfigurationError(LLMServiceError, ServiceRequestParseError):
    """Raised when the LLM client is missing required configuration (HTTP 503)."""

    def __init__(
        self,
        message: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, retryable=False, status_code=503, **kwargs)


class LLMCallError(LLMServiceError, ServiceRequestParseError):
    """Raised when an error occurs during the LLM API call or response processing (HTTP 502/503)."""

    def __init__(
        self,
        message: str,
        retryable: bool = True,
        status_code: int = 502,
        **kwargs: Any,
    ) -> None:
        super().__init__(message=message, retryable=retryable, status_code=status_code, **kwargs)
