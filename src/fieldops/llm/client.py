"""Lightweight wrapper around OpenAI SDK with Structured Outputs support, timeout, and retry."""

from typing import Any, TypeVar

from openai import (
    APITimeoutError,
    BadRequestError,
    OpenAI,
    OpenAIError,
)
from pydantic import BaseModel

from fieldops.core.config import settings
from fieldops.core.exceptions import LLMTimeoutError
from fieldops.llm.exceptions import LLMCallError, LLMConfigurationError
from fieldops.llm.retry import retry_with_backoff
from fieldops.observability.llm_cost import calculate_llm_cost
from fieldops.observability.metrics import (
    LLM_ESTIMATED_COST_TOTAL,
    LLM_FAILURES_TOTAL,
    LLM_INPUT_TOKENS_TOTAL,
    LLM_OUTPUT_TOKENS_TOTAL,
    LLM_REQUESTS_TOTAL,
)
from fieldops.observability.tracing import trace_llm_call

T = TypeVar("T", bound=BaseModel)



class OpenAIClient:
    """Lightweight wrapper around OpenAI SDK with Structured Outputs support."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL or "gpt-4o-mini"
        self.base_url = base_url
        self.timeout = timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self._client: OpenAI | None = None

        if self.api_key:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,  # Retries handled at application level with backoff & logging
            )

    @property
    def client(self) -> OpenAI:
        """Return the initialized OpenAI SDK client or raise configuration error."""
        if self._client is None:
            if not self.api_key:
                raise LLMConfigurationError(
                    "OPENAI_API_KEY is not configured. Please set it in .env or system environment."
                )
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,
            )
        return self._client

    def parse_structured(
        self,
        messages: list[dict[str, str]],
        response_format: type[T],
        model: str | None = None,
    ) -> T:
        """Invoke OpenAI beta chat completions parse to return a validated Pydantic model with retry."""
        client = self.client
        target_model = model or self.model

        def _call() -> T:
            with trace_llm_call(model=target_model) as trace_meta:
                try:
                    completion = client.beta.chat.completions.parse(
                        model=target_model,
                        messages=messages,  # type: ignore[arg-type]
                        response_format=response_format,
                    )
                except APITimeoutError as e:
                    LLM_REQUESTS_TOTAL.labels(model=target_model, status="failure").inc()
                    LLM_FAILURES_TOTAL.labels(model=target_model, error_type="APITimeoutError").inc()
                    raise LLMTimeoutError(f"OpenAI API call timed out: {e}") from e
                except BadRequestError as e:
                    LLM_REQUESTS_TOTAL.labels(model=target_model, status="failure").inc()
                    LLM_FAILURES_TOTAL.labels(model=target_model, error_type="BadRequestError").inc()
                    # 400 Bad Request is permanent client error, not retryable
                    raise LLMCallError(f"OpenAI API bad request (400): {e}", retryable=False) from e
                except OpenAIError as e:
                    LLM_REQUESTS_TOTAL.labels(model=target_model, status="failure").inc()
                    LLM_FAILURES_TOTAL.labels(model=target_model, error_type=type(e).__name__).inc()
                    raise LLMCallError(f"OpenAI API call failed: {e}", retryable=True) from e
                except Exception as e:
                    LLM_REQUESTS_TOTAL.labels(model=target_model, status="failure").inc()
                    LLM_FAILURES_TOTAL.labels(model=target_model, error_type=type(e).__name__).inc()
                    raise LLMCallError(f"Unexpected error during LLM invocation: {e}", retryable=False) from e

                # Extract usage and record metrics
                usage = getattr(completion, "usage", None)
                raw_prompt = getattr(usage, "prompt_tokens", 0) if usage else 0
                prompt_tokens = raw_prompt if isinstance(raw_prompt, (int, float)) else 0

                raw_completion = getattr(usage, "completion_tokens", 0) if usage else 0
                completion_tokens = raw_completion if isinstance(raw_completion, (int, float)) else 0

                raw_total = getattr(usage, "total_tokens", prompt_tokens + completion_tokens) if usage else 0
                total_tokens = raw_total if isinstance(raw_total, (int, float)) else (prompt_tokens + completion_tokens)

                raw_cost = calculate_llm_cost(target_model, int(prompt_tokens), int(completion_tokens))
                cost = raw_cost if isinstance(raw_cost, (int, float)) else 0.0

                trace_meta["input_tokens"] = prompt_tokens
                trace_meta["output_tokens"] = completion_tokens
                trace_meta["total_tokens"] = total_tokens
                trace_meta["estimated_cost"] = cost

                LLM_REQUESTS_TOTAL.labels(model=target_model, status="success").inc()
                if prompt_tokens > 0:
                    LLM_INPUT_TOKENS_TOTAL.labels(model=target_model).inc(prompt_tokens)
                if completion_tokens > 0:
                    LLM_OUTPUT_TOKENS_TOTAL.labels(model=target_model).inc(completion_tokens)
                if cost > 0:
                    LLM_ESTIMATED_COST_TOTAL.labels(model=target_model).inc(cost)

                choice = completion.choices[0]
                if choice.message.refusal:
                    # Refusal is non-retryable semantic decision by model
                    raise LLMCallError(f"Model refused request: {choice.message.refusal}", retryable=False)

                parsed: T | None = choice.message.parsed
                if parsed is None:
                    # Structured output invalid
                    raise LLMCallError("Failed to parse structured output from model response.", retryable=False)

                return parsed

        base_delay = 0.01 if settings.APP_ENV == "testing" else 0.5
        return retry_with_backoff(
            _call,
            max_attempts=self.max_retries,
            base_delay=base_delay,
            operation_name="OpenAIClient.parse_structured",
        )
