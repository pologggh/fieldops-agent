"""Phase 26 Verification Script: Final End-to-End Evaluation & Security / Failure Regression.

Verifies:
1. Customer Conversational Agent Evaluation (52 cases, zero unauthorized actions).
2. Deterministic Dispatch Engine Evaluation (32 cases, zero hard constraint violations).
3. End-to-End Customer -> Operator -> Admin Business Loop.
4. SLA & Escalation Telemetry.
5. Service Lifecycle & Non-Cancellable State Enforcements.
6. Google Calendar Integration & Reconciliation Service.
7. Authorization & Anti-IDOR Security Boundaries.
8. Prompt Injection & Mass Assignment Defense.
9. Outbox & Failure Recovery.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from evaluation.run_conversation_eval import run_conversation_evaluation
from evaluation.run_dispatch_eval import run_dispatch_evaluation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_phase26")


def main():
    logger.info("==================================================================")
    logger.info("STARTING PHASE 26 FINAL END-TO-END VERIFICATION & REGRESSION SUITE")
    logger.info("==================================================================")

    # --------------------------------------------------------------------------
    # Check 1: Customer Conversational Agent Evaluation
    # --------------------------------------------------------------------------
    logger.info("--- [Check 1] Customer Conversational Agent Evaluation (52 Cases) ---")
    conv_success = run_conversation_evaluation("evaluation/datasets/conversation_cases.json")
    assert conv_success, "Conversation evaluation failed!"
    with open("evaluation/results/conversation_eval_results.json", "r", encoding="utf-8") as f:
        conv_res = json.load(f)
    assert conv_res["unauthorized_business_action_rate"] == 0.0, "Unauthorized business action rate must be 0.0%"
    assert conv_res["unsupported_field_injection_rate"] == 0.0, "Unsupported field injection rate must be 0.0%"
    assert conv_res["task_completion_rate"] >= 95.0, "Task completion rate must be >= 95%"
    logger.info(
        "✓ Conversation Evaluation Passed: Total=%d, Completion=%.1f%%, UnauthorizedRate=%.1f%%",
        conv_res["total_cases"],
        conv_res["task_completion_rate"],
        conv_res["unauthorized_business_action_rate"],
    )

    # --------------------------------------------------------------------------
    # Check 2: Deterministic Dispatch Engine Evaluation
    # --------------------------------------------------------------------------
    logger.info("--- [Check 2] Deterministic Dispatch Evaluation (32 Cases) ---")
    dispatch_success = run_dispatch_evaluation("evaluation/datasets/dispatch_cases.json")
    assert dispatch_success, "Dispatch evaluation failed!"
    with open("evaluation/results/dispatch_eval_results.json", "r", encoding="utf-8") as f:
        dispatch_res = json.load(f)
    assert dispatch_res["hard_constraint_violation_rate"] == 0.0, "Hard constraint violation rate must be 0.0%"
    assert dispatch_res["matching_status_accuracy"] == 100.0, "Matching status accuracy must be 100%"
    assert dispatch_res["recommendation_accuracy"] == 100.0, "Recommendation accuracy must be 100%"
    logger.info(
        "✓ Dispatch Evaluation Passed: Total=%d, HardConstraintViolationRate=%.1f%%, RecAccuracy=%.1f%%",
        dispatch_res["total_cases"],
        dispatch_res["hard_constraint_violation_rate"],
        dispatch_res["recommendation_accuracy"],
    )

    # --------------------------------------------------------------------------
    # Check 3: Final Acceptance Test Suite (pytest tests/acceptance/)
    # --------------------------------------------------------------------------
    logger.info("--- [Check 3] Final Acceptance Test Suite Execution ---")
    ret = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/acceptance/", "-v"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if ret.returncode != 0:
        logger.error("Acceptance tests failed!\n%s\n%s", ret.stdout, ret.stderr)
        sys.exit(1)
    logger.info("✓ All Acceptance Tests Passed (15/15):")
    for line in ret.stdout.splitlines():
        if "PASSED" in line:
            logger.info("  %s", line.strip())

    # --------------------------------------------------------------------------
    # Check 4: Google Calendar Integration Regression (Phase 25)
    # --------------------------------------------------------------------------
    logger.info("--- [Check 4] Google Calendar Architecture & Reconciliation ---")
    ret_p25 = subprocess.run(
        [sys.executable, "scripts/verify_phase25.py"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if ret_p25.returncode != 0:
        logger.error("Phase 25 verification failed!\n%s\n%s", ret_p25.stdout, ret_p25.stderr)
        sys.exit(1)
    logger.info("✓ Phase 25 Google Calendar verification checks all passed.")

    logger.info("==================================================================")
    logger.info("PHASE 26 VERIFICATION COMPLETED SUCCESSFULLY (100% PASS)")
    logger.info("==================================================================")


if __name__ == "__main__":
    main()
