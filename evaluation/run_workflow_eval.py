"""End-to-End Workflow Business Path Evaluation Runner (Phase 11).

Evaluates the LangGraph FieldOps state machine against reference business scenarios:
- Task Completion Rate
- Expected Final State Accuracy
- Correct Conditional Edge Routing Rate
- Unexpected Failure / Crash Rate
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure 'src' and root are on PYTHONPATH
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from fieldops.application.field_service_workflow import (
    resume_field_service_workflow,
    run_field_service_workflow,
)
from fieldops.db.models import Appointment, ServiceRequest
from fieldops.db.session import Base
from fieldops.llm.schemas import ParsedServiceRequest
from scripts.seed import seed_customers, seed_technicians


def evaluate_workflows(
    dataset_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute end-to-end workflow evaluations using mock parsing to test business logic deterministically."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    total_cases = len(cases)
    print(f"\n========================================================")
    print(f"  FieldOps Agent — Business Workflow Evaluation")
    print(f"  Cases: {total_cases} | Multi-Step LangGraph Orchestration")
    print(f"========================================================\n")

    correct_final_states = 0
    correct_approvals = 0
    correct_appointments = 0
    completed_without_crash = 0
    failed_cases: list[dict[str, Any]] = []

    start_time = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{idx}")
        desc = case.get("description", "")
        parsed_in = case["parsed_input"]
        cust = case["customer"]
        decision = case.get("operator_decision")
        precondition = case.get("precondition_booking")

        exp_wf_status = case["expected_workflow_status"]
        exp_appr_status = case.get("expected_approval_status")
        exp_appt_created = case.get("expected_appointment_created", False)

        # Create clean in-memory database session for each isolated scenario
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with TestingSessionLocal() as session:
            seed_customers(session)
            seed_technicians(session)
            session.commit()

        # Patch all session dependencies
        with patch("fieldops.application.persistence.SessionLocal", TestingSessionLocal), \
             patch("fieldops.agent.nodes.match_technicians.SessionLocal", TestingSessionLocal), \
             patch("fieldops.agent.nodes.check_schedule.SessionLocal", TestingSessionLocal), \
             patch("fieldops.agent.nodes.build_appointment_proposal.SessionLocal", TestingSessionLocal), \
             patch("fieldops.agent.nodes.finalize_appointment.SessionLocal", TestingSessionLocal), \
             patch("fieldops.agent.nodes.handle_rejection.SessionLocal", TestingSessionLocal), \
             patch("fieldops.db.session.SessionLocal", TestingSessionLocal):

            mock_parsed = ParsedServiceRequest(
                service_type=parsed_in.get("service_type"),
                urgency=parsed_in.get("urgency"),
                location=parsed_in.get("location"),
                required_skills=parsed_in.get("required_skills", []),
                preferred_time=parsed_in.get("preferred_time"),
                problem_description=parsed_in.get("problem_description", "Test desc"),
            )

            actual_wf_status = None
            actual_appr_status = None
            actual_appt_id = None

            try:
                with patch(
                    "fieldops.agent.nodes.parse_request.parse_service_request",
                    return_value=mock_parsed,
                ):
                    req_id = f"eval-{case_id}"
                    paused_state = run_field_service_workflow(
                        message=mock_parsed.problem_description or "Test message",
                        customer_name=cust["name"],
                        email=cust["email"],
                        phone=cust.get("phone"),
                        request_id=req_id,
                    )

                if paused_state.get("workflow_status") == "waiting_for_approval" and decision:
                    # Check if precondition booking is requested to trigger race conflict
                    if precondition == "conflict_proposed_slot":
                        prop = paused_state.get("appointment_proposal")
                        if prop:
                            with TestingSessionLocal() as db:
                                other_sr = ServiceRequest(
                                    customer_id=1,
                                    raw_message="Other concurrent booking",
                                    service_type="HVAC",
                                    urgency="high",
                                    location="Shinjuku",
                                    status="scheduled",
                                )
                                db.add(other_sr)
                                db.flush()

                                conflict_appt = Appointment(
                                    service_request_id=other_sr.id,
                                    technician_id=prop["technician_id"],
                                    start_time=datetime.fromisoformat(prop["start_time"]),
                                    end_time=datetime.fromisoformat(prop["end_time"]),
                                    status="scheduled",
                                )
                                db.add(conflict_appt)
                                db.commit()

                    final_state = resume_field_service_workflow(
                        request_id=req_id,
                        decision=decision,
                    )
                else:
                    final_state = paused_state

                actual_wf_status = final_state.get("workflow_status")
                actual_appr_status = final_state.get("approval_status")
                actual_appt_id = final_state.get("appointment_id")
                completed_without_crash += 1

            except Exception as e:
                failed_cases.append({
                    "id": case_id,
                    "description": desc,
                    "error": str(e),
                })
                print(f"[{idx:02d}/{total_cases:02d}] {case_id} -> CRASH: {e}")
                continue

        # Evaluate correctness
        status_ok = (actual_wf_status == exp_wf_status)
        approval_ok = (actual_appr_status == exp_appr_status)
        appt_ok = (bool(actual_appt_id) == exp_appt_created)

        if status_ok:
            correct_final_states += 1
        if approval_ok:
            correct_approvals += 1
        if appt_ok:
            correct_appointments += 1

        case_passed = status_ok and approval_ok and appt_ok
        marker = "PASS" if case_passed else "FAIL"
        print(f"[{idx:02d}/{total_cases:02d}] {case_id} -> {marker} (Final Status: '{actual_wf_status}', Expected: '{exp_wf_status}')")

        if not case_passed:
            failed_cases.append({
                "id": case_id,
                "description": desc,
                "expected": {
                    "workflow_status": exp_wf_status,
                    "approval_status": exp_appr_status,
                    "appointment_created": exp_appt_created,
                },
                "actual": {
                    "workflow_status": actual_wf_status,
                    "approval_status": actual_appr_status,
                    "appointment_created": bool(actual_appt_id),
                },
            })

    total_duration = round(time.perf_counter() - start_time, 2)
    completion_rate = round((completed_without_crash / total_cases) * 100, 1)
    state_accuracy = round((correct_final_states / total_cases) * 100, 1)
    approval_accuracy = round((correct_approvals / total_cases) * 100, 1)

    summary = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "failed_count": len(failed_cases),
        "duration_seconds": total_duration,
        "metrics": {
            "task_completion_rate_pct": completion_rate,
            "final_state_accuracy_pct": state_accuracy,
            "approval_status_accuracy_pct": approval_accuracy,
            "unexpected_crash_count": total_cases - completed_without_crash,
        },
        "failed_cases": failed_cases,
    }

    print("\n--------------------------------------------------------")
    print(f"  WORKFLOW EVALUATION METRICS")
    print("--------------------------------------------------------")
    print(f"  Total Scenarios Evaluated:          {total_cases}")
    print(f"  Task Completion Rate:               {completion_rate}%")
    print(f"  Final State Accuracy:               {state_accuracy}%")
    print(f"  Approval Status Accuracy:           {approval_accuracy}%")
    print(f"  Unexpected Crash Count:             {total_cases - completed_without_crash}")
    print(f"  Evaluation Duration:                {total_duration}s")
    print("--------------------------------------------------------")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Results saved to: {output_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate End-to-End Business Workflows.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=project_root / "evaluation" / "datasets" / "workflow_cases.json",
        help="Path to workflow test dataset JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "results" / "workflow_eval_latest.json",
        help="Path to write evaluation results JSON",
    )
    args = parser.parse_args()

    evaluate_workflows(dataset_path=args.dataset, output_path=args.output)


if __name__ == "__main__":
    main()
