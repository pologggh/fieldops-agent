# ADR 0005: Modular LangGraph Subgraphs over Autonomous Multi-Agent Frameworks

## Status
Accepted

## Context
As FieldOps Agent scaled through Phase 28, the core service request lifecycle grew increasingly multifaceted: semantic parsing, customer clarification turns, geo-spatial technician matching, schedule conflict resolution, multi-tiered human-in-the-loop approvals, transactional database commits, and external calendar synchronization.

A common temptation in the GenAI industry is to adopt autonomous Multi-Agent frameworks (e.g. AutoGen, CrewAI, multi-agent conversational swarms) where independent LLM-powered agents "converse" with one another to negotiate dispatch schedules and resolve errors.

We evaluated whether to introduce Multi-Agent swarms or to structure the system using modular LangGraph subgraphs within a single coherent state machine.

## Decision Drivers
1. **Determinism & Predictability**: Field operations involve physical technicians, customer homes, SLA contracts, and financial commitments. Non-deterministic inter-agent conversational negotiations introduce catastrophic unpredictability, hallucinations, and unprovable termination guarantees.
2. **State Serializability & Crash Recovery**: Checkpointed workflows must survive worker crashes and pause for hours or days awaiting operator approval. A single unified, typed state schema (`FieldServiceState`) ensures 100% JSON-serializable persistence in SQLite/PostgreSQL checkpoints.
3. **Execution Latency & Cost**: Autonomous agent swarms generate cascading LLM calls, ballooning token costs and introducing 10-30 second latency per decision. Subgraphs execute deterministic Python code in microseconds, invoking LLMs only for semantic parsing.
4. **Debuggability & Operational Observability**: Regulators and enterprise operators require exact causal attribution for every dispatch decision. Subgraphs maintain explicit reason codes, policy versioning, and finite step counters.

## Decision
We decided to adopt **modular LangGraph Subgraphs** integrated into a parent workflow graph, explicitly rejecting Multi-Agent autonomous architectures:

1. **Dedicated Subgraph Boundaries**:
   - `intake_subgraph`: Semantic extraction, schema validation, clarification loop bounding, and atomic customer/request creation.
   - `dispatch_subgraph`: Geo-spatial candidate matching, technician availability verification, and dispatch policy evaluation.
   - `approval_subgraph`: Multi-level review evaluation assigning human review level based on urgency, overtime, and SLA proximity.
   - `appointment_subgraph`: Atomic database persistence, Outbox event generation, and external sync dispatch.
   - `reschedule_subgraph`: Bounded rescheduling cycles with auto-escalation upon exceeding limit.
   - `escalation_subgraph`: Severity classification, operational queue attribution, and audit logging.

2. **Single Shared State Schema (`FieldServiceState`)**:
   - All subgraphs read and mutate a unified, typed schema.
   - State additions (`last_decision`, `human_review_level`, `step_count`, `clarification_count`, `reschedule_count`) are backward-compatible.

3. **Deterministic Python Guards over Agent Autonomy**:
   - Edge routing is executed by pure Python router functions (`route_after_intake`, `route_after_dispatch`, `route_after_human_review`).
   - Finite State Machine transition guards (`VALID_WORKFLOW_TRANSITIONS`) reject illegal transitions at runtime.

## Consequences
### Positive:
- **Hermetic, Fast Unit Testing**: Subgraphs compile into isolated `CompiledStateGraph` instances that can be invoked and verified in unit tests in milliseconds without LLM mocks or network calls.
- **Zero Token Cost for Routing**: All subgraph transitions and routing decisions execute via pure Python logic.
- **Audit Compliance**: Every routing transition is recorded with structured reason codes and policy versions.
- **Bounded Execution**: Loop counters (`step_count <= 25`) provide mathematical guarantees against infinite loops.

### Negative / Trade-offs:
- Subgraphs require explicit typing and deliberate contract management.
- Dynamic business logic variations require updating deterministic policy rules rather than modifying natural language prompts. (This trade-off is strongly favorable for mission-critical enterprise SaaS).
