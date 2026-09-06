from fieldops.core.config import settings
from fieldops.llm.client import OpenAIClient
from fieldops.llm.exceptions import EmptyMessageError
from fieldops.llm.fake_llm import parse_with_fake_llm
from fieldops.llm.schemas import ParsedServiceRequest

PARSER_SYSTEM_PROMPT = """You are a field service operations intake assistant.
Your task is to analyze natural language customer requests and extract structured information strictly according to the specified schema.

Follow these strict rules:
1. Extract information SOLELY from the customer's text. Do NOT hallucinate or assume unstated details.
2. If location or preferred_time is not explicitly mentioned, return null. Never guess or invent a location.
3. If technical skills cannot be reasonably inferred, return an empty list [].
4. service_type should be classified accurately (e.g. 'HVAC', 'Plumbing', 'Electrical', 'Networking', 'Appliance Repair', 'Other').
5. urgency is a semantic interpretation ('low', 'medium', 'high', 'emergency') based on reported severity (e.g., active burning smell or flooding implies 'high' or 'emergency'). Note: this is a linguistic assessment, not a final business safety rule.
6. preferred_time must preserve the customer's expressed phrasing (e.g. 'this afternoon', 'tomorrow morning'). Do not convert to dates.
7. problem_description must be a concise, objective summary of the issue.
8. Strictly interpret only. Do NOT schedule appointments, assign technicians, or perform any business operations."""


def parse_service_request(
    message: str,
    client: OpenAIClient | None = None,
) -> ParsedServiceRequest:
    """Parse an incoming raw customer service request message into structured format.

    Args:
        message: Raw customer request text.
        client: Optional OpenAIClient instance (defaults to standard client).

    Returns:
        Validated ParsedServiceRequest instance.

    Raises:
        EmptyMessageError: If the message is empty or contains only whitespace.
        LLMConfigurationError: If the LLM client is missing API credentials.
        LLMCallError: If the LLM API call fails or the model returns an invalid response.
    """
    cleaned_message = message.strip() if message else ""
    if not cleaned_message:
        raise EmptyMessageError("Customer service request message cannot be empty.")

    if client is None and (settings.LOAD_TEST_MODE or settings.LLM_PROVIDER == "fake"):
        return parse_with_fake_llm(cleaned_message)

    llm_client = client or OpenAIClient()

    messages = [
        {"role": "system", "content": PARSER_SYSTEM_PROMPT},
        {"role": "user", "content": cleaned_message},
    ]

    return llm_client.parse_structured(
        messages=messages,
        response_format=ParsedServiceRequest,
    )
