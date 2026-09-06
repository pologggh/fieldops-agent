"""Deterministic Fake LLM parser for Customer Conversational Agent.

Used for unit tests, evaluation runs, and offline development when LLM_PROVIDER=fake.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FakeConversationTurnOutput(BaseModel):
    draft_updates: Dict[str, Any] = Field(default_factory=dict)
    user_intent: str = "provide_info"  # provide_info, clarify, modify, emergency, prompt_injection, irrelevant
    assistant_reply: str = ""
    safety_warning: Optional[str] = None


def parse_conversation_turn_with_fake_llm(
    current_draft: Dict[str, Any],
    new_message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> FakeConversationTurnOutput:
    """Fast, deterministic turn parser and response generator for fake LLM mode."""
    text = new_message.strip()
    lower = text.lower()
    updates: Dict[str, Any] = {}
    warning: Optional[str] = None

    # 1. Prompt Injection Detection
    if any(k in lower for k in ("ignore instructions", "ignore your rules", "technician_id", "mark approved", "set approval", "bypass dispatch", "assign ken")):
        return FakeConversationTurnOutput(
            draft_updates={},
            user_intent="prompt_injection",
            assistant_reply=(
                "I understand your request, but technician assignments and approvals are managed "
                "strictly by our automated dispatch engine and operations team once your request is submitted. "
                "I can only help collect your service details."
            ),
            safety_warning=None,
        )

    # 2. Irrelevant / Greeting
    if lower in ("hello", "hi", "hey", "good morning", "good evening"):
        return FakeConversationTurnOutput(
            draft_updates={},
            user_intent="greeting",
            assistant_reply="Hello! What maintenance or repair issue are you experiencing today?",
        )

    if any(k in lower for k in ("tell me a joke", "who are you", "what is the weather", "write a poem", "who won")):
        return FakeConversationTurnOutput(
            draft_updates={},
            user_intent="irrelevant",
            assistant_reply="I am the FieldOps intake assistant. I can only help you log and schedule property maintenance requests. What issue are you experiencing?",
        )

    # 3. Emergency / Safety Detection
    if any(k in lower for k in ("smoke", "spark", "burning", "fire", "gas smell", "flooding", "burst pipe")):
        updates["urgency"] = "emergency"
        warning = "Please keep a safe distance from active hazards and contact emergency services if there is immediate danger."

    # 4. Service Type Classification
    if any(k in lower for k in ("ac", "air condition", "heat", "cooling", "furnace", "thermostat", "hvac")):
        updates["service_type"] = "HVAC"
        updates["required_skills"] = ["HVAC"]
    elif any(k in lower for k in ("leak", "pipe", "water", "sink", "drain", "toilet", "plumb")):
        updates["service_type"] = "Plumbing"
        updates["required_skills"] = ["Plumbing"]
    elif any(k in lower for k in ("electric", "wire", "power", "outlet", "breaker", "spark")):
        updates["service_type"] = "Electrical"
        updates["required_skills"] = ["Electrical"]
    elif any(k in lower for k in ("network", "wifi", "router", "internet", "ethernet")):
        updates["service_type"] = "Networking"
        updates["required_skills"] = ["Networking"]
    elif any(k in lower for k in ("refrigerator", "fridge", "dishwasher", "washer", "dryer", "oven", "stove", "appliance")):
        updates["service_type"] = "Appliance Repair"
        updates["required_skills"] = ["Appliance Repair"]
    elif any(k in lower for k in ("paint", "lawn", "roof", "clean", "window", "door")):
        updates["service_type"] = "General Maintenance"
        updates["required_skills"] = []

    # 5. Location Extraction (with Correction support)
    districts = ["shinjuku", "shibuya", "tokyo", "yokohama", "minato", "roppongi", "chiyoda", "shinagawa", "ginza", "ikebukuro", "ueno", "meguro", "metro core", "bay area", "zone east", "zone north"]

    # Check for explicit correction phrases: "in X, not Y", "changed to X", "X instead of Y", "X not Y"
    corr_match = re.search(r"(?:in|to|is|address is|property is)\s+([A-Za-z0-9\s\-]+?)(?:,\s*not\b|\s+not\b|\s+instead\b)", text, re.IGNORECASE)
    if corr_match:
        cand = corr_match.group(1).strip().lower()
        for d in districts:
            if d in cand:
                updates["location"] = d.title()
                break

    if not updates.get("location"):
        # Check if any district is explicitly negated: e.g. "not Shinjuku", "not in Shinjuku", "instead of Shinjuku"
        negated_matches = re.findall(r"(?:not\s+(?:in\s+)?|instead\s+of\s+)([a-z0-9\s\-]+)", lower)
        negated_str = " ".join(negated_matches)

        found_districts = []
        for d in districts:
            if d in lower:
                if d in negated_str and ("not " + d in lower or "instead of " + d in lower):
                    continue
                pos = lower.rfind(d)
                found_districts.append((pos, d))

        if found_districts:
            found_districts.sort(key=lambda x: x[0], reverse=True)
            updates["location"] = found_districts[0][1].title()

    # Generic location match: explicit markers like "location is", "address is", "property is", "located at", "located in"
    if not updates.get("location"):
        loc_match = re.search(r"(?:location is|address is|property is|located at|located in)\s+([A-Za-z0-9\s,\.\-#]+?)(?:\.|\band\b|\btomorrow\b|\btoday\b|\bat\b|$)", text, re.IGNORECASE)
        if loc_match:
            candidate = loc_match.group(1).strip()
            verbs = {"is", "are", "was", "were", "has", "have", "not", "urgent", "problem", "vibrating", "leaking"}
            if len(candidate) > 2 and not any(v in candidate.lower().split() for v in verbs):
                updates["location"] = candidate

    # 6. Preferred Time Window Extraction
    time_keywords = [
        "tomorrow afternoon", "tomorrow morning", "tomorrow evening", "tomorrow 2pm", "tomorrow 10am",
        "tomorrow", "today", "this afternoon", "this morning", "friday afternoon", "friday morning",
        "friday", "monday", "next week", "asap", "immediate", "urgent"
    ]
    for tk in time_keywords:
        if tk in lower:
            updates["preferred_time"] = tk.title() if len(tk) <= 10 else tk.capitalize()
            break

    # 7. Problem Description Extraction
    is_correction = any(k in lower for k in ("actually", "wait", "change", "correct", "instead", "not in", ", not"))
    # If the user is just stating a location or time, don't overwrite existing problem description
    is_pure_location = bool(updates.get("location") and (len(text.split()) <= 4 or is_correction) and not any(k in lower for k in ("broken", "leak", "fail", "stop", "smoke", "overflow", "damage")))
    is_pure_time = bool(updates.get("preferred_time") and (len(text.split()) <= 4 or is_correction) and not any(k in lower for k in ("broken", "leak", "fail", "stop", "smoke", "overflow", "damage")))
    
    if not is_pure_location and not is_pure_time:
        # User provided actual symptom/problem
        if current_draft.get("problem_description"):
            # Check if this is an addition
            if text not in current_draft["problem_description"]:
                updates["problem_description"] = f"{current_draft['problem_description']}. {text}".strip()
        else:
            updates["problem_description"] = text

    # Compute merged state preview to formulate natural assistant reply
    merged_desc = updates.get("problem_description") or current_draft.get("problem_description")
    merged_loc = updates.get("location") or current_draft.get("location")
    merged_time = updates.get("preferred_time") or current_draft.get("preferred_time")
    merged_type = updates.get("service_type") or current_draft.get("service_type") or "General Maintenance"

    # Clarification logic
    if not merged_desc:
        assistant_reply = "Could you please describe what issue or malfunction you are experiencing?"
    elif not merged_loc:
        assistant_reply = "Thank you for the description. Which district, address, or building is the property located in?"
    elif not merged_time:
        assistant_reply = f"Got it, located in {merged_loc}. What date and time window would you prefer a technician to visit?"
    else:
        # All required fields present -> Present summary
        assistant_reply = (
            f"I have summarized your service request:\n"
            f"- Trade: {merged_type}\n"
            f"- Issue: {merged_desc}\n"
            f"- Location: {merged_loc}\n"
            f"- Preferred Visit: {merged_time}\n\n"
            f"Please review the details above. When you are ready, click 'Confirm & Submit' to send this request to our dispatch team."
        )

    if warning:
        assistant_reply = f"{warning}\n\n{assistant_reply}"

    return FakeConversationTurnOutput(
        draft_updates=updates,
        user_intent="provide_info",
        assistant_reply=assistant_reply,
        safety_warning=warning,
    )
