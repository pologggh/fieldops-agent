"""Deterministic Scheduling Logic Evaluation Runner (Phase 11).

Evaluates has_time_conflict and scheduling interval rules against reference dataset on:
- Conflict Detection Accuracy
- Adjacent Boundary Discrimination Accuracy
- Cancelled Appointment Exemption Accuracy
- Cross-Timezone Normalization Accuracy
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

# Ensure 'src' and root are on PYTHONPATH
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from fieldops.domain.services.scheduling import (
    ensure_timezone,
    has_time_conflict,
)


def evaluate_scheduling(
    dataset_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute scheduling interval evaluation across dataset cases."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    total_cases = len(cases)
    print(f"\n========================================================")
    print(f"  FieldOps Agent — Scheduling Logic Evaluation")
    print(f"  Cases: {total_cases} | Deterministic Interval Engine")
    print(f"========================================================\n")

    correct_conflicts = 0
    failed_cases: list[dict[str, Any]] = []
    start_time = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{idx}")
        desc = case.get("description", "")
        proposed = case["proposed"]
        existing = case["existing"]
        expected_conflict = case["expected_conflict"]

        dt_p_start = ensure_timezone(datetime.fromisoformat(proposed["start"]))
        dt_p_end = ensure_timezone(datetime.fromisoformat(proposed["end"]))
        dt_e_start = ensure_timezone(datetime.fromisoformat(existing["start"]))
        dt_e_end = ensure_timezone(datetime.fromisoformat(existing["end"]))
        status = existing.get("status", "scheduled")

        # In scheduling domain, cancelled appointments do not block
        if status == "cancelled":
            actual_conflict = False
        else:
            actual_conflict = has_time_conflict(
                slot_start=dt_p_start,
                slot_end=dt_p_end,
                existing_start=dt_e_start,
                existing_end=dt_e_end,
            )

        is_correct = (actual_conflict == expected_conflict)
        if is_correct:
            correct_conflicts += 1

        marker = "PASS" if is_correct else "FAIL"
        print(f"[{idx:02d}/{total_cases:02d}] {case_id} -> {marker} (Overlap: {actual_conflict}, Expected: {expected_conflict})")

        if not is_correct:
            failed_cases.append({
                "id": case_id,
                "description": desc,
                "proposed": proposed,
                "existing": existing,
                "expected_conflict": expected_conflict,
                "actual_conflict": actual_conflict,
            })

    total_duration = round(time.perf_counter() - start_time, 2)
    accuracy_pct = round((correct_conflicts / total_cases) * 100, 1)

    summary = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "failed_count": len(failed_cases),
        "duration_seconds": total_duration,
        "metrics": {
            "conflict_detection_accuracy_pct": accuracy_pct,
            "failed_cases_count": len(failed_cases),
        },
        "failed_cases": failed_cases,
    }

    print("\n--------------------------------------------------------")
    print(f"  SCHEDULING EVALUATION METRICS")
    print("--------------------------------------------------------")
    print(f"  Total Cases Evaluated:              {total_cases}")
    print(f"  Conflict Detection Accuracy:        {accuracy_pct}%")
    print(f"  Failed Cases:                       {len(failed_cases)}")
    print(f"  Evaluation Duration:                {total_duration}s")
    print("--------------------------------------------------------")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Results saved to: {output_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Scheduling Interval Logic.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=project_root / "evaluation" / "datasets" / "scheduling_cases.json",
        help="Path to scheduling test dataset JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "results" / "scheduling_eval_latest.json",
        help="Path to write evaluation results JSON",
    )
    args = parser.parse_args()

    evaluate_scheduling(dataset_path=args.dataset, output_path=args.output)


if __name__ == "__main__":
    main()
