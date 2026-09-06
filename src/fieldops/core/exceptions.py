"""Core exceptions hierarchy for FieldOps Agent.

Classifies errors into:
- User input validation errors (400, non-retryable)
- Resource not found errors (404, non-retryable)
- Business/idempotency conflicts (409, non-retryable)
- Transient infrastructure/LLM errors (503, retryable)
- Internal database/workflow errors (500, non-retryable)
"""

from typing import Any


class FieldOpsError(Exception):
    """Base exception for all FieldOps Agent domain and infrastructure errors."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code

    def __str__(self) -> str:
        return self.message


class ValidationError(FieldOpsError):
    """Raised when client/user input fails business or schema validation (HTTP 400)."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 400,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class ResourceNotFoundError(FieldOpsError):
    """Raised when a requested resource, entity, or workflow thread is not found (HTTP 404)."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 404,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class ConflictError(FieldOpsError):
    """Raised for business conflicts such as appointment scheduling overlaps or invalid state transitions (HTTP 409)."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class DuplicateRequestError(FieldOpsError):
    """Raised when an idempotency key matches an existing record with different payload or when concurrent request is in flight (HTTP 409)."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class LLMServiceError(FieldOpsError):
    """Raised when an LLM provider error occurs (e.g. rate limit, provider 5xx, or refusal)."""

    def __init__(
        self,
        message: str,
        retryable: bool = True,
        status_code: int = 503,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class LLMTimeoutError(LLMServiceError):
    """Raised when an LLM API call exceeds the configured timeout threshold."""

    def __init__(
        self,
        message: str = "LLM service request timed out.",
        retryable: bool = True,
        status_code: int = 503,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class DatabaseOperationError(FieldOpsError):
    """Raised on unexpected or transient database operational failures."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class WorkflowStateError(FieldOpsError):
    """Raised on invalid workflow state transitions or unrecoverable workflow node failures."""

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class WorkflowInvariantError(WorkflowStateError):
    """Raised when an internal workflow invariant or state transition rule is violated."""

    def __init__(
        self,
        message: str = "Workflow state invariant violation detected.",
        retryable: bool = False,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class InvalidStateTransitionError(ConflictError):
    """Raised when an entity is requested to transition along an illegal path."""

    def __init__(
        self,
        message: str = "Invalid entity state transition requested.",
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class RequestNotCancellableError(ConflictError):
    """Raised when attempting to cancel a service request or appointment that cannot be cancelled."""

    def __init__(
        self,
        message: str = "This request cannot be cancelled in its current state.",
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class AppointmentNotReschedulableError(ConflictError):
    """Raised when attempting to reschedule an appointment in an invalid state."""

    def __init__(
        self,
        message: str = "This appointment cannot be rescheduled in its current state.",
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class AppointmentAlreadyCompletedError(ConflictError):
    """Raised when attempting an operation on an already completed appointment."""

    def __init__(
        self,
        message: str = "Appointment has already been completed.",
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class AppointmentAlreadyCancelledError(ConflictError):
    """Raised when attempting an operation on an already cancelled appointment."""

    def __init__(
        self,
        message: str = "Appointment has already been cancelled.",
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)


class ReassignmentNoCandidateError(ConflictError):
    """Raised when reassigning a technician fails due to no eligible candidate."""

    def __init__(
        self,
        message: str = "No eligible replacement technician found for reassignment.",
        retryable: bool = False,
        status_code: int = 409,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, retryable=retryable, status_code=status_code, **kwargs)

