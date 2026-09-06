"""Lightweight LangGraph workflow for Customer Conversational Intake.

Distinct and isolated from the main FieldOps operations workflow.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict
from langgraph.graph import END, START, StateGraph

from fieldops.conversation.agent_engine import process_turn


class ConversationGraphState(TypedDict):
    conversation_id: int
    customer_id: int
    current_message: str
    history: List[Dict[str, str]]
    draft: Dict[str, Any]
    missing_fields: List[str]
    conversation_status: str
    assistant_action: str
    assistant_message: str
    safety_warning: Optional[str]


def process_message_node(state: ConversationGraphState) -> Dict[str, Any]:
    """Execute conversational turn processing."""
    updated_draft, next_status, reply, action, warning = process_turn(
        current_draft=state.get("draft", {}),
        messages=state.get("history", []),
        new_message=state["current_message"],
        conversation_id=state.get("conversation_id"),
    )
    return {
        "draft": updated_draft,
        "missing_fields": updated_draft.get("missing_fields", []),
        "conversation_status": next_status,
        "assistant_action": action,
        "assistant_message": reply,
        "safety_warning": warning,
    }


def route_after_processing(state: ConversationGraphState) -> Literal["ask_clarification", "present_summary"]:
    """Conditional edge evaluating whether clarification or summary is needed."""
    if state.get("missing_fields"):
        return "ask_clarification"
    return "present_summary"


def ask_clarification_node(state: ConversationGraphState) -> Dict[str, Any]:
    """Sets active clarification status."""
    return {"conversation_status": "active", "assistant_action": "ask_clarification"}


def present_summary_node(state: ConversationGraphState) -> Dict[str, Any]:
    """Sets awaiting confirmation status."""
    return {"conversation_status": "awaiting_confirmation", "assistant_action": "present_summary"}


def build_conversation_graph():
    """Construct the isolated conversational LangGraph pipeline."""
    graph = StateGraph(ConversationGraphState)

    graph.add_node("process_message", process_message_node)
    graph.add_node("ask_clarification", ask_clarification_node)
    graph.add_node("present_summary", present_summary_node)

    graph.add_edge(START, "process_message")
    graph.add_conditional_edges(
        "process_message",
        route_after_processing,
        {
            "ask_clarification": "ask_clarification",
            "present_summary": "present_summary",
        },
    )
    graph.add_edge("ask_clarification", END)
    graph.add_edge("present_summary", END)

    return graph.compile()


conversation_graph = build_conversation_graph()
