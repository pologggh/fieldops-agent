"""LLM cost calculation module based on model token pricing."""

import logging

logger = logging.getLogger(__name__)

# Standard reference pricing per 1,000,000 tokens (in USD).
# Note: Pricing must be maintained in sync with upstream provider revisions.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {
        "input_per_million": 0.150,
        "output_per_million": 0.600,
    },
    "gpt-4o": {
        "input_per_million": 2.500,
        "output_per_million": 10.000,
    },
    "gpt-4-turbo": {
        "input_per_million": 10.000,
        "output_per_million": 30.000,
    },
    "gpt-3.5-turbo": {
        "input_per_million": 0.500,
        "output_per_million": 1.500,
    },
}


def calculate_llm_cost(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    """Calculate estimated cost in USD based on input and output tokens.

    Returns:
        float: Estimated cost rounded to 8 decimal places.
        None: If model pricing is not configured or token counts are unavailable.
    """
    if prompt_tokens is None or completion_tokens is None:
        return None

    # Normalize model string (strip vendor prefixes if any)
    clean_model = model.lower().split("/")[-1].strip()

    pricing = MODEL_PRICING.get(clean_model)
    if not pricing:
        logger.debug("No pricing configuration found for model '%s'", clean_model)
        return None

    input_cost = (prompt_tokens / 1_000_000.0) * pricing["input_per_million"]
    output_cost = (completion_tokens / 1_000_000.0) * pricing["output_per_million"]
    total_cost = round(input_cost + output_cost, 8)
    return total_cost
