# FieldOps Agentic Workflow v2 Architecture

This document describes the Phase 28 upgrade of the FieldOps Agent workflow engine: **Policy-Driven + Dynamic Routing + Recoverable + Explainable Agentic Workflow**.

---

## 1. High-Level Main Graph Architecture

The workflow orchestrates business subgraphs and human intervention gates using a single, unified `FieldServiceState` schema.

```mermaid
graph TD
    START([START]) --> IntakeSG[Intake Subgraph]

    IntakeSG --> RouteIntake{route_after_intake}
    RouteIntake -- "needs_information<br/>(clarification_count < 3)" --> END([END: Wait for Customer])
    RouteIntake -- "escalated<br/>(clarification >= 3)" --> EscalationSG[Escalation Subgraph]
    RouteIntake -- "service_request_created" --> DispatchSG[Dispatch Subgraph]

    DispatchSG --> RouteDispatch{route_after_dispatch}
    RouteDispatch -- "schedule_options_ready" --> BuildProposal[Build Appointment Proposal]
    RouteDispatch -- "no_technician_available /<br/>no_available_slots / escalated" --> EscalationSG

    BuildProposal --> CheckApproval{ApprovalPolicy Evaluation}
    CheckApproval -- "human_review_required = true<br/>(OPERATOR / SENIOR / ADMIN)" --> HumanReview[Human Review Gate<br/><i>Interrupt / Checkpoint</i>]
    CheckApproval -- "human_review_required = false<br/>(NONE)" --> ApptSG[Appointment Subgraph]

    HumanReview --> ResumeReview{Operator Decision}
    ResumeReview -- "Approved" --> ApptSG
    ResumeReview -- "Rejected" --> HandleRejection[Handle Rejection Node]

    HandleRejection --> EscalationSG

    ApptSG --> RouteAppt{route_after_appointment}
    RouteAppt -- "appointment_created" --> END([END: Completed])
    RouteAppt -- "needs_rescheduling" --> ReschedSG[Reschedule Subgraph]
    RouteAppt -- "failed" --> EscalationSG

    ReschedSG --> RouteResched{route_after_reschedule}
    RouteResched -- "ready_for_scheduling<br/>(reschedule_count < 3)" --> DispatchSG
    RouteResched -- "escalated<br/>(reschedule_count >= 3)" --> EscalationSG

    EscalationSG --> END([END: Escalated to Ops Queue])
```

---

## 2. Subgraph Specifications

### 2.1 Intake Subgraph (`intake_subgraph`)
Handles customer message extraction, semantic parsing, deterministic validation, loop bounding, and atomic database persistence.

```mermaid
graph LR
    subgraph Intake Subgraph
        I_START([START]) --> Parse[Parse Request<br/><i>LLM Semantic Extraction</i>]
        Parse --> Validate[Validate Request<br/><i>Python Schema Rules</i>]
        Validate --> Decision[Intake Decision<br/><i>Loop Bound Check</i>]
        Decision -- "Valid" --> Persist[Persist Service Request<br/><i>Single Atomic Transaction</i>]
        Decision -- "Missing Fields" --> I_END([END: needs_information])
        Persist --> I_END2([END: service_request_created])
    end
```

### 2.2 Dispatch Subgraph (`dispatch_subgraph`)
Evaluates geographical technician availability, required skill match, and schedule slot availability with deterministic policies.

```mermaid
graph LR
    subgraph Dispatch Subgraph
        D_START([START]) --> Match[Match Technicians<br/><i>Zone & Skills Filter</i>]
        Match -- "Matched" --> Schedule[Check Schedule<br/><i>Technician Working Hours</i>]
        Match -- "No Candidates" --> DispatchDec[Dispatch Decision<br/><i>Escalation Policy</i>]
        Schedule --> DispatchDec
        DispatchDec --> D_END([END])
    end
```

### 2.3 Approval Subgraph & HITL Review Gate
Evaluates urgency tiers, overtime, SLA risks, and prior reschedules to determine required human reviewer role.

```mermaid
graph TD
    subgraph Approval Evaluation
        A_IN([Appointment Options]) --> EvalTier{Evaluate ApprovalPolicy}
        EvalTier -- "Urgency == emergency" --> TierSenior[ReviewLevel: SENIOR_OPERATOR<br/>Reason: EMERGENCY_TIER]
        EvalTier -- "Weekend / After-hours" --> TierOvertime[ReviewLevel: OPERATOR<br/>Reason: OVERTIME_TIER]
        EvalTier -- "SLA Margin <= 60m" --> TierSLA[ReviewLevel: OPERATOR<br/>Reason: SLA_RISK_TIER]
        EvalTier -- "Reschedules >= 2" --> TierAdmin[ReviewLevel: ADMIN<br/>Reason: RE_RESCHEDULE_TIER]
        EvalTier -- "Standard Business Hours" --> TierAuto[ReviewLevel: NONE<br/>Auto-Approve]
    end
```

### 2.4 Appointment Subgraph (`appointment_subgraph`)
Ensures Core Business Fact priority: transactional database commit occurs first, staging Outbox events for asynchronous external sync.

```mermaid
graph LR
    subgraph Appointment Subgraph
        AP_START([START]) --> Finalize[Finalize Appointment<br/><i>DB Commit + Outbox Event</i>]
        Finalize --> TriggerOutbox[Trigger Outbox Worker<br/><i>Celery Async Job</i>]
        TriggerOutbox --> AP_END([END: appointment_created])
    end
```

### 2.5 Reschedule Subgraph (`reschedule_subgraph`)
Bounds rescheduling cycles to prevent infinite looping when schedule conflicts occur.

```mermaid
graph LR
    subgraph Reschedule Subgraph
        R_START([START]) --> IncCounter[Increment reschedule_count]
        IncCounter --> CheckLimit{reschedule_count >= 3?}
        CheckLimit -- "Yes" --> EscalateOps[Set Reason: RESCHEDULE_LIMIT_EXCEEDED<br/>Route to Escalation]
        CheckLimit -- "No" --> ClearOldSlots[Reset Staged Proposal<br/>Route to ready_for_scheduling]
        EscalateOps --> R_END([END])
        ClearOldSlots --> R_END
    end
```

### 2.6 Escalation Subgraph (`escalation_subgraph`)
Classifies failure reasons, records structured audit trail, and attributes operational ticket to correct role queue.

```mermaid
graph LR
    subgraph Escalation Subgraph
        E_START([START]) --> Classify[Classify Severity & Role<br/><i>P1: Senior Operator / P2: Operator</i>]
        Classify --> AuditLog[Write AuditLog<br/><i>workflow.escalated</i>]
        AuditLog --> Alert[Emit Operational Alert<br/><i>Event Bus</i>]
        Alert --> E_END([END: escalated])
    end
```

---

## 3. Failure Classification & Recovery Flow

```mermaid
graph TD
    FailNode[Workflow Node Error / Failure] --> ClassifyFail{Failure Type}

    ClassifyFail -- "Transient (Network / Deadlock / 429)" --> CheckBudget{retry_count < retry_budget?}
    CheckBudget -- "Yes (Budget Available)" --> IncRetry[retry_count += 1<br/>Exponential Backoff] --> RetryNode[Retry Node Execution]
    CheckBudget -- "No (Budget Exhausted)" --> EscalateBudget[Reason: RETRY_BUDGET_EXHAUSTED<br/>Escalate to Senior Operator]

    ClassifyFail -- "Permanent (Invalid Input / Schema Error)" --> NoRetry[Zero Retries Wasted] --> RouteInfo[Route to needs_information or Escalation]

    ClassifyFail -- "External Integration (Google Calendar 5xx)" --> Compensate[Compensation Engine<br/>1. Mark IntegrationRecord failed<br/>2. Preserve DB Appointment<br/>3. Enqueue Reconciliation]

    ClassifyFail -- "State Guard / Invariant Breach" --> InvariantStop[WorkflowInvariantError<br/>Immediate Workflow Halt & Admin Alert]
```

---

## 4. Multi-Level Human Review Authorization Matrix

Resumption of an interrupted workflow (`POST /service-requests/{id}/approval`) verifies the actor's role against the required review level:

```mermaid
graph LR
    Actor[Authenticated User] --> CheckLevel{Actor Role vs Required Review Level}
    CheckLevel -- "ADMIN approving any level" --> Authorized[Authorized: Workflow Resumes]
    CheckLevel -- "SENIOR_OPERATOR approving OPERATOR or SENIOR" --> Authorized
    CheckLevel -- "OPERATOR approving OPERATOR" --> Authorized
    CheckLevel -- "OPERATOR attempting SENIOR or ADMIN" --> Forbidden[HTTP 403 Forbidden<br/>Checkpoint Uncorrupted]
```

| Review Level Required | Operator Allowed? | Senior Operator Allowed? | Admin Allowed? |
|---|:---:|:---:|:---:|
| `NONE` (Auto) | Yes | Yes | Yes |
| `OPERATOR` | **Yes** | **Yes** | **Yes** |
| `SENIOR_OPERATOR` | No | **Yes** | **Yes** |
| `ADMIN` | No | No | **Yes** |
