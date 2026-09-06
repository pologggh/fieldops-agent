# ADR 0006: Policy-Driven Workflow Decisions over LLM Autonomy

## Status
Accepted

## Context
In field service management, high-consequence decisions include:
- Dispatching technicians to hazardous emergency repairs.
- Committing to contractual SLA response times.
- Approving overtime compensation for weekend and night visits.
- Escalating blocked tickets to human supervisors.

Allowing language models to make these operational decisions via free-form prompt engineering invites non-determinism, security bypasses (prompt injection), policy drift, and unexplainable outcomes.

## Decision Drivers
1. **Separation of Semantic Parsing from Business Policy**: The LLM's ideal competency is natural language understanding (extracting unstructured customer complaints into typed intent). Business governance belongs in auditable, deterministic code.
2. **Versioned Policy Governance**: Enterprise operations require policy versions (`v1.0.0`) pinned to service requests to track regulatory compliance and contractual obligations.
3. **Role-Based Authorization Hierarchies**: Human approval gates must enforce strict security boundaries (`ADMIN` > `SENIOR_OPERATOR` > `OPERATOR` > `NONE`) that cannot be circumvented.
4. **Structured Decision Explainability**: Frontline operators and customers need transparent, human-readable reason codes (`ReasonCode`) rather than opaque model explanations.

## Decision
We established a strict architectural separation: **LLMs perform semantic extraction; deterministic Python policies govern all operational decisions**.

1. **Policy Hierarchy (`src/fieldops/agent/decisions/policies.py`)**:
   - `ApprovalPolicy (v1.0.0)`: Deterministically maps emergency tiers, overtime windows, SLA proximity, and prior reschedule counts to required human review levels (`NONE`, `OPERATOR`, `SENIOR_OPERATOR`, `ADMIN`).
   - `EscalationPolicy (v1.0.0)`: Classifies matching failures and SLA breaches into operational severity tiers (`P1`, `P2`) and assigns them to operator queues.
   - `RecoveryPolicy (v1.0.0)`: Differentiates transient retries from permanent failures and manages retry budgeting (`MAX_RETRY_BUDGET = 3`).

2. **Standardized Decision DTO (`DecisionResult`)**:
   Every decision node outputs an immutable `DecisionResult` containing:
   - `action`: `PROCEED`, `WAIT_FOR_APPROVAL`, `ESCALATE`, `RETRY`, `COMPENSATE`, `ASK_FOR_INFORMATION`, `STOP`.
   - `reason_code`: Canonical typed reason code (e.g. `ReasonCode.EMERGENCY_TIER`, `ReasonCode.NO_ELIGIBLE_TECHNICIAN`).
   - `reason`: Operator-facing natural explanation.
   - `policy_version`: Semantic version of the governing policy.
   - `requires_human`: Boolean review flag.
   - `required_role`: Role authorized to approve resumption.

3. **Checkpointed Resumption Protection**:
   - Resuming an interrupted workflow (`POST /service-requests/{id}/approval`) enforces `user.role` authorization prior to consuming the LangGraph checkpoint.
   - Unauthorized attempts reject with `HTTP 403 Forbidden` (`WorkflowStateError`), preserving the checkpoint intact for the designated role.

## Consequences
### Positive:
- **Zero Hallucinated Approvals**: LLMs cannot autonomously approve emergencies or bypass operational constraints.
- **Auditable Governance**: 100% of dispatch and escalation decisions are attributed to specific policy versions and reason codes in database audit logs.
- **Explainability API**: Real-time state inspection (`GET /internal/workflows/{request_id}`) returns full decision history and active policies.
- **Safe Security Boundaries**: Operator role checks are enforced in the application service layer before invoking graph resumption.

### Negative / Trade-offs:
- Adding new approval criteria requires code changes in policy classes rather than simple prompt adjustments. (This ensures intentional change management and test verification).
