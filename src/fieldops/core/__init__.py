"""Core configuration and exceptions package."""

from fieldops.core.config import settings
from fieldops.core.exceptions import (
    ConflictError,
    DatabaseOperationError,
    DuplicateRequestError,
    FieldOpsError,
    LLMServiceError,
    LLMTimeoutError,
    ResourceNotFoundError,
    ValidationError,
    WorkflowStateError,
)

__all__ = [
    "settings",
    "FieldOpsError",
    "ValidationError",
    "ResourceNotFoundError",
    "ConflictError",
    "DuplicateRequestError",
    "LLMServiceError",
    "LLMTimeoutError",
    "DatabaseOperationError",
    "WorkflowStateError",
]
