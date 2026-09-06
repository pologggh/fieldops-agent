# FieldOps Workflow Policies (v1.0.0)

This document specifies the authoritative business decision policies governing the FieldOps Agent LangGraph workflow engine.

All high-stakes business decisions (human review gating, technician dispatch escalation, recovery and retry budgeting, compensation actions) are strictly evaluated by deterministic Python rule policies. Language models (LLMs) are restricted to semantic interpretation and text parameter extraction; they never possess autonomous authority to bypass policies, approve appointments, or route around operational safeguards.

---

## 1. Core Policy Hierarchy & Reason Codes

Every workflow decision produces a structured `DecisionResult` containing:
- `action`: One of `PROCEED`, `WAIT_FOR_APPROVAL`, `ESCALATE`, `RETRY`, `COMPENSATE`, `ASK_FOR_INFORMATION`, `STOP`.
- `reason_code`: Canonical typed reason code (`ReasonCode`).
- `reason`: Human-readable explanation suitable for operator and audit display.
- `policy_version`: Semantic version of the governing policy (e.g., `"1.0.0"`).
- `requires_human`: Boolean indicating whether human intervention is required.
- `required_role`: Role required to authorize resumption (`NONE`, `OPERATOR`, `SENIOR_OPERATOR`, `ADMIN`).
- `retryable`: Boolean indicating whether automated retry is permissible.
- `metadata`: Contextual decision parameters (urgency, slot window, SLA deadline, error details).

### Reason Code Catalog (`ReasonCode`)

| Category | Reason Code | Description | Default Action | Default Human Review Level |
|---|---|---|---|---|
| **Intake** | `VALIDATION_FAILED` | Input syntax or type validation failure | `ASK_FOR_INFORMATION` | `NONE` |
| | `MISSING_LOCATION` | Inferred request is missing service location | `ASK_FOR_INFORMATION` | `NONE` |
| | `MISSING_TIME` | Preferred time window ambiguous or unparseable | `ASK_FOR_INFORMATION` | `NONE` |
| | `CLARIFICATION_LIMIT_EXCEEDED` | Customer clarification loop exceeded budget (3) | `ESCALATE` | `OPERATOR` |
| **Dispatch** | `NO_ELIGIBLE_TECHNICIAN` | No technician matches required skills/zone | `ESCALATE` | `OPERATOR` / `SENIOR_OPERATOR` |
| | `SLA_CANNOT_BE_MET` | Earliest available slot breaches SLA deadline | `ESCALATE` | `SENIOR_OPERATOR` |
| | `HIGH_RISK_DISPATCH` | Emergency dispatch requiring operator signoff | `WAIT_FOR_APPROVAL` | `OPERATOR` / `ADMIN` |
| **HITL Review** | `EMERGENCY_TIER` | Emergency urgency tier requiring senior review | `WAIT_FOR_APPROVAL` | `SENIOR_OPERATOR` |
| | `OVERTIME_TIER` | After-hours or weekend service window | `WAIT_FOR_APPROVAL` | `OPERATOR` |
| | `SLA_RISK_TIER` | Slot within 1 hour of SLA deadline | `WAIT_FOR_APPROVAL` | `OPERATOR` |
| | `RE_RESCHEDULE_TIER` | Appointment has been rescheduled >= 2 times | `WAIT_FOR_APPROVAL` | `ADMIN` |
| | `STANDARD_AUTO_APPROVE` | Standard business hours, normal urgency | `PROCEED` | `NONE` |
| **Recovery** | `TRANSIENT_NETWORK_ERROR` | Idempotent external API or network glitch | `RETRY` | `NONE` |
| | `RATE_LIMIT_EXCEEDED` | 429 Too Many Requests with retry-after | `RETRY` | `NONE` |
| | `RETRY_BUDGET_EXHAUSTED` | Retry attempts exceeded maximum budget (3) | `ESCALATE` | `SENIOR_OPERATOR` |
| | `EXTERNAL_INTEGRATION_FAILED`| External sync failed; core business fact preserved| `COMPENSATE` | `NONE` / `OPERATOR` |
| | `CRITICAL_INVARIANT_VIOLATION`| Illegal state transition or invariant breach | `STOP` | `ADMIN` |

---

## 2. Multi-Level Human Review Matrix (`ApprovalPolicy v1.0.0`)

FieldOps implements four explicit Human-In-The-Loop review levels:
1. `NONE`: Automated flow; no human approval required.
2. `OPERATOR`: First-line operations specialist.
3. `SENIOR_OPERATOR`: Senior operations supervisor (authorizes emergencies & SLA exceptions).
4. `ADMIN`: System administrator (authorizes critical multi-reschedule actions or system invariant overrides).

### Authorization Hierarchy
Role capabilities are strictly hierarchical:
$$\text{ADMIN} \succ \text{SENIOR\_OPERATOR} \succ \text{OPERATOR} \succ \text{NONE}$$

- An `ADMIN` can approve any level (`NONE`, `OPERATOR`, `SENIOR_OPERATOR`, `ADMIN`).
- A `SENIOR_OPERATOR` can approve `OPERATOR` and `SENIOR_OPERATOR`.
- An `OPERATOR` can only approve `OPERATOR`.
- Any unauthorized resumption attempt immediately rejects with `HTTP 403 Forbidden` (`WorkflowStateError`), and does **not** consume or corrupt the underlying LangGraph checkpoint.

### Evaluation Decision Table

```
+-----------------------------------------------------------------------------------------------+
| Urgency    | Window Slot      | Reschedule Count | SLA Remaining | Review Level    | Reason Code          |
+============+==================+==================+===============+=================+======================+
| emergency  | Any              | Any              | Any           | SENIOR_OPERATOR | EMERGENCY_TIER       |
| high       | After-hours/Sun  | Any              | Any           | OPERATOR        | OVERTIME_TIER        |
| Any        | Any              | >= 2             | Any           | ADMIN           | RE_RESCHEDULE_TIER   |
| Any        | Any              | < 2              | <= 60 mins    | OPERATOR        | SLA_RISK_TIER        |
| low/medium | Weekday 08-18    | 0-1              | > 60 mins     | NONE            | STANDARD_AUTO_APPROVE|
+-----------------------------------------------------------------------------------------------+
```

---

## 3. Dispatch & Escalation Policies (`EscalationPolicy v1.0.0`)

When automated matching or scheduling encounters operational constraints, `EscalationPolicy` categorizes the incident severity, maps the required operational role, and issues explicit reason codes:

1. **No Candidate in Zone (`NO_ELIGIBLE_TECHNICIAN`)**:
   - Severity: `P1` (if `urgency == 'emergency'`) -> Assigned to `SENIOR_OPERATOR`.
   - Severity: `P2` (standard urgency) -> Assigned to `OPERATOR`.
   - Action: Workflow pauses in `no_technician_available` / `escalated`, emits structured audit log, and notifies customer that an operations specialist is manually routing a technician.

2. **No Slots Available (`NO_AVAILABLE_SLOTS`)**:
   - Triggers `needs_rescheduling` subgraph.
   - Increment `reschedule_count`.
   - If `reschedule_count >= 3`, automatically escalates to `OPERATOR` under `RESCHEDULE_LIMIT_EXCEEDED`.

3. **SLA Breach Imminent (`SLA_CANNOT_BE_MET`)**:
   - Earliest possible technician arrival breaches calculated contract SLA.
   - Assigned to `SENIOR_OPERATOR` to authorize overtime, cross-zone dispatch, or customer SLA renegotiation.

---

## 4. Recovery & Retry Policies (`RecoveryPolicy v1.0.0`)

Workflow execution failures are separated into deterministic categories:

1. **Transient Failures (Retryable)**:
   - Network dropouts, database deadlock rollbacks, external calendar HTTP 429/503.
   - Guarded by `retry_budget = 3`.
   - Exponential backoff with jitter applied via Celery or workflow retry loops.

2. **Permanent / Unrecoverable Failures (Non-Retryable)**:
   - Schema validation errors, missing customer data, model refusals, non-existent entity IDs.
   - Zero retry attempts wasted; routed directly to `needs_information` or `escalation_subgraph`.

3. **Budget Exhaustion (`RETRY_BUDGET_EXHAUSTED`)**:
   - When `retry_count >= retry_budget`, workflow halts retry loop, marks status `escalated`, records diagnostic trace, and assigns to `SENIOR_OPERATOR`.
