"""Integration layer exceptions."""


class IntegrationError(Exception):
    """Base exception for external third-party integration errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable


class TransientIntegrationError(IntegrationError):
    """Transient, recoverable failure (e.g. rate limit, network timeout, 503)."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message=message, provider=provider, retryable=True)


class PermanentIntegrationError(IntegrationError):
    """Permanent, non-recoverable failure (e.g. invalid payload, client 400, unresolvable recipient)."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message=message, provider=provider, retryable=False)


class AuthenticationIntegrationError(IntegrationError):
    """Authentication failure with third-party service (e.g. invalid API token, expired OAuth)."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message=message, provider=provider, retryable=False)
