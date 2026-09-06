"""Email integration contract and data transfer objects."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, ConfigDict


class EmailSendResult(BaseModel):
    """Normalized result returned by email provider."""

    model_config = ConfigDict(frozen=True)

    provider_message_id: str
    status: str
    provider: str = "fake_email"


class EmailClient(ABC):
    """Abstract boundary protocol for email providers."""

    @abstractmethod
    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> EmailSendResult:
        """Send an email, ensuring provider-side tracking."""
        pass
