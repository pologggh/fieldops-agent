"""Conversational Agent Engine.

Coordinates multi-turn dialogue comprehension, deterministic draft merging,
correction handling, missing fields verification, prompt injection defense,
and clarification/summary state transitions.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from fieldops.core.config import settings
from fieldops.conversation.fake_llm import parse_conversation_turn_with_fake_llm
from fieldops.conversation.prompts import CONVERSATION_AGENT_SYSTEM_PROMPT
from fieldops.llm.client import OpenAIClient
from fieldops.observability.metrics import (
    CONVERSATION_CLARIFICATIONS_TOTAL,
    CONVERSATION_FAILURES_TOTAL,
    CONVERSATION_TURNS_TOTAL,
    CONVERSATION_TURN_DURATION_SECONDS,
)
from fieldops.observability.tracing import trace_conversation_operation

logger = logging.getLogger(__name__)

# Permitted draft fields whitelist (Hard security boundary)
ALLOWED_DRAFT_FIELDS = {
    "service_type",
    "urgency",
    "location",
    "preferred_time",
    "problem_description",
    "required_skills",
}

# Strictly forbidden injection attributes
PROHIBITED_INJECTION_FIELDS = {
    "technician_id",
    "assigned_technician_id",
    "approval_status",
    "dispatch_score",
    "sla_deadline",
    "sla_target",
    "override_status",
    "status",
    "role",
    "customer_id",
    "id",
}


class StructuredTurnOutput(BaseModel):
    """Structured LLM turn extraction format."""
    draft_updates: Dict[str, Any] = Field(default_factory=dict)
    user_intent: str = "provide_info"  # provide_info, clarify, modify, emergency, prompt_injection, irrelevant
    assistant_reply: str = ""
    safety_warning: Optional[str] = None


def sanitize_and_merge_draft(
    current_draft: Dict[str, Any],
    raw_updates: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Deterministically merge updates into draft, stripping prompt injections and validating completeness.

    Rules:
    1. Only ALLOWED_DRAFT_FIELDS are accepted.
    2. Prohibited injection fields are unconditionally dropped.
    3. Explicit non-empty updates replace existing values (supporting user corrections).
    4. Unmentioned fields retain their existing values.
    5. Required fields are evaluated deterministically.
    """
    merged = dict(current_draft or {})

    for key, val in raw_updates.items():
        # Security: Strip prompt injections
        if key in PROHIBITED_INJECTION_FIELDS:
            logger.warning("Blocked attempt to inject prohibited draft attribute: %s", key)
            continue
        if key not in ALLOWED_DRAFT_FIELDS:
            logger.warning("Ignored unwhitelisted draft attribute: %s", key)
            continue

        # Merge non-empty values
        if val is not None:
            if isinstance(val, str) and val.strip():
                merged[key] = val.strip()
            elif isinstance(val, list):
                merged[key] = val
            elif isinstance(val, (int, float, bool)):
                merged[key] = val

    # Ensure defaults
    if not merged.get("service_type"):
        merged["service_type"] = "General Maintenance"
    if not merged.get("urgency"):
        merged["urgency"] = "medium"
    if not isinstance(merged.get("required_skills"), list):
        merged["required_skills"] = []

    # Deterministic missing fields verification
    missing: List[str] = []
    if not merged.get("problem_description"):
        missing.append("problem_description")
    if not merged.get("location"):
        missing.append("location")
    if not merged.get("preferred_time"):
        missing.append("preferred_time")

    merged["missing_fields"] = missing
    merged["is_complete"] = len(missing) == 0

    return merged, missing


def process_turn(
    current_draft: Dict[str, Any],
    messages: List[Dict[str, str]],
    new_message: str,
    conversation_id: Optional[int] = None,
) -> Tuple[Dict[str, Any], str, str, str, Optional[str]]:
    """Process a single conversational turn.

    Args:
        current_draft: Existing draft snapshot.
        messages: Previous dialogue turns (role and content).
        new_message: New customer message content.
        conversation_id: Optional conversation ID for telemetry.

    Returns:
        tuple of (updated_draft, next_status, assistant_message, assistant_action, safety_warning)
    """
    start_time = time.perf_counter()

    with trace_conversation_operation("process_turn", conversation_id=conversation_id):
        # 1. Parse turn using LLM or Fake LLM
        turn_output: StructuredTurnOutput
        try:
            if settings.LOAD_TEST_MODE or settings.LLM_PROVIDER == "fake":
                with trace_conversation_operation("parse", conversation_id=conversation_id, action="fake_parse"):
                    fake_res = parse_conversation_turn_with_fake_llm(
                        current_draft=current_draft,
                        new_message=new_message,
                        history=messages[-10:],
                    )
                    turn_output = StructuredTurnOutput(
                        draft_updates=fake_res.draft_updates,
                        user_intent=fake_res.user_intent,
                        assistant_reply=fake_res.assistant_reply,
                        safety_warning=fake_res.safety_warning,
                    )
            else:
                with trace_conversation_operation("parse", conversation_id=conversation_id, action="llm_parse"):
                    llm_client = OpenAIClient()
                    # Construct windowed history (last 10 messages)
                    history_context = "\n".join(
                        f"{m.get('role', 'user')}: {m.get('content', '')}"
                        for m in messages[-10:]
                    )
                    draft_context = (
                        f"Current Draft: Problem='{current_draft.get('problem_description', '')}', "
                        f"Location='{current_draft.get('location', '')}', "
                        f"Time='{current_draft.get('preferred_time', '')}', "
                        f"Trade='{current_draft.get('service_type', '')}'"
                    )
                    system_content = f"{CONVERSATION_AGENT_SYSTEM_PROMPT}\n\n{draft_context}"

                    api_messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": f"Recent Conversation:\n{history_context}\n\nLatest Customer Message: {new_message}"},
                    ]

                    turn_output = llm_client.parse_structured(
                        messages=api_messages,
                        response_format=StructuredTurnOutput,
                    )

        except Exception as exc:
            logger.warning("Conversational parser error, falling back to deterministic fake parser: %s", exc)
            CONVERSATION_FAILURES_TOTAL.labels(error_type=type(exc).__name__).inc()
            fake_res = parse_conversation_turn_with_fake_llm(
                current_draft=current_draft,
                new_message=new_message,
                history=messages[-10:],
            )
            turn_output = StructuredTurnOutput(
                draft_updates=fake_res.draft_updates,
                user_intent=fake_res.user_intent,
                assistant_reply=fake_res.assistant_reply,
                safety_warning=fake_res.safety_warning,
            )

        # 2. Deterministic Validation & Merge
        with trace_conversation_operation("validate", conversation_id=conversation_id):
            updated_draft, missing = sanitize_and_merge_draft(
                current_draft=current_draft,
                raw_updates=turn_output.draft_updates,
            )

            if turn_output.safety_warning:
                updated_draft["safety_warning"] = turn_output.safety_warning

        # 3. Determine next action & status
        if updated_draft["is_complete"]:
            next_status = "awaiting_confirmation"
            assistant_action = "present_summary"
            CONVERSATION_TURNS_TOTAL.labels(result="summary").inc()
        else:
            next_status = "active"
            assistant_action = "ask_clarification"
            for m in missing:
                CONVERSATION_CLARIFICATIONS_TOTAL.labels(missing_field=m).inc()
            CONVERSATION_TURNS_TOTAL.labels(result="clarification").inc()

        duration = time.perf_counter() - start_time
        CONVERSATION_TURN_DURATION_SECONDS.observe(duration)

        return (
            updated_draft,
            next_status,
            turn_output.assistant_reply,
            assistant_action,
            turn_output.safety_warning,
        )
