"""LLM Service Request Parser Evaluation Runner (Phase 11).

Evaluates parse_service_request against reference datasets on:
- Service Type Accuracy
- Urgency Accuracy
- Location Accuracy
- Preferred Time Accuracy
- Required Skills Precision, Recall, and F1
- Hallucination / Unsupported Field Rate
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

from evaluation.metrics import (
    calculate_scalar_accuracy,
    calculate_set_metrics,
    detect_unsupported_hallucination,
)
from fieldops.core.config import settings
from fieldops.llm import parse_service_request
from fieldops.llm.schemas import ParsedServiceRequest


def evaluate_parser(
    dataset_path: Path,
    limit: int | None = None,
    output_path: Path | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Execute parser evaluation across dataset cases and compute quality metrics."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    if limit is not None and limit > 0:
        cases = cases[:limit]

    total_cases = len(cases)
    print(f"\n========================================================")
    print(f"  FieldOps Agent — LLM Parser Evaluation")
    print(f"  Cases: {total_cases} | Model: {settings.OPENAI_MODEL} | Mock: {mock}")
    print(f"========================================================\n")

    correct_service_type = 0
    correct_urgency = 0
    correct_location = 0
    correct_preferred_time = 0

    total_skills_p = 0.0
    total_skills_r = 0.0
    total_skills_f1 = 0.0

    unsupported_location_count = 0
    unsupported_time_count = 0
    non_empty_description_count = 0

    failed_cases: list[dict[str, Any]] = []

    start_eval_time = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{idx}")
        message = case["message"]
        expected = case["expected"]

        t0 = time.perf_counter()
        try:
            if mock or not settings.OPENAI_API_KEY:
                # Mock extraction mode returns ground-truth (simulating ideal baseline)
                predicted = ParsedServiceRequest(
                    service_type=expected["service_type"],
                    urgency=expected["urgency"],
                    location=expected["location"],
                    required_skills=expected["required_skills"],
                    preferred_time=expected["preferred_time"],
                    problem_description=f"Summary of {message[:30]}",
                )
            else:
                predicted = parse_service_request(message)
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        except Exception as e:
            print(f"[{idx}/{total_cases}] {case_id} ERROR: {e}")
            failed_cases.append({
                "id": case_id,
                "input": message,
                "error": str(e),
            })
            continue

        # 1. Scalar checks
        is_st_ok = calculate_scalar_accuracy(expected["service_type"], predicted.service_type)
        is_urg_ok = calculate_scalar_accuracy(expected["urgency"], predicted.urgency)
        is_loc_ok = calculate_scalar_accuracy(expected["location"], predicted.location)
        is_time_ok = calculate_scalar_accuracy(expected["preferred_time"], predicted.preferred_time)

        if is_st_ok:
            correct_service_type += 1
        if is_urg_ok:
            correct_urgency += 1
        if is_loc_ok:
            correct_location += 1
        if is_time_ok:
            correct_preferred_time += 1

        # 2. Set skills check
        skills_scores = calculate_set_metrics(expected["required_skills"], predicted.required_skills)
        total_skills_p += skills_scores["precision"]
        total_skills_r += skills_scores["recall"]
        total_skills_f1 += skills_scores["f1"]

        # 3. Hallucination checks
        has_unsupported_loc = detect_unsupported_hallucination(expected["location"], predicted.location)
        has_unsupported_time = detect_unsupported_hallucination(expected["preferred_time"], predicted.preferred_time)
        if has_unsupported_loc:
            unsupported_location_count += 1
        if has_unsupported_time:
            unsupported_time_count += 1

        # 4. Problem description check
        if predicted.problem_description and predicted.problem_description.strip():
            non_empty_description_count += 1

        # Track failure details
        case_passed = (
            is_st_ok
            and is_urg_ok
            and is_loc_ok
            and is_time_ok
            and skills_scores["f1"] >= 0.99
            and not has_unsupported_loc
            and not has_unsupported_time
        )

        status_marker = "PASS" if case_passed else "FAIL"
        print(f"[{idx:02d}/{total_cases:02d}] {case_id} ({duration_ms}ms) -> {status_marker}")

        if not case_passed:
            failed_cases.append({
                "id": case_id,
                "input": message,
                "expected": expected,
                "actual": {
                    "service_type": predicted.service_type,
                    "urgency": predicted.urgency,
                    "location": predicted.location,
                    "required_skills": predicted.required_skills,
                    "preferred_time": predicted.preferred_time,
                },
                "failures": {
                    "service_type_match": is_st_ok,
                    "urgency_match": is_urg_ok,
                    "location_match": is_loc_ok,
                    "time_match": is_time_ok,
                    "skills_f1": skills_scores["f1"],
                    "unsupported_location": has_unsupported_loc,
                    "unsupported_time": has_unsupported_time,
                },
            })

    total_eval_duration = round(time.perf_counter() - start_eval_time, 2)

    # Compute aggregate percentages
    evaluated_count = max(total_cases, 1)
    service_type_acc = round((correct_service_type / evaluated_count) * 100, 1)
    urgency_acc = round((correct_urgency / evaluated_count) * 100, 1)
    location_acc = round((correct_location / evaluated_count) * 100, 1)
    time_acc = round((correct_preferred_time / evaluated_count) * 100, 1)

    avg_skills_p = round(total_skills_p / evaluated_count, 4)
    avg_skills_r = round(total_skills_r / evaluated_count, 4)
    avg_skills_f1 = round(total_skills_f1 / evaluated_count, 4)

    unsupported_field_rate = round(
        ((unsupported_location_count + unsupported_time_count) / (evaluated_count * 2)) * 100,
        1,
    )
    desc_non_empty_rate = round((non_empty_description_count / evaluated_count) * 100, 1)

    summary = {
        "model": "mock" if mock or not settings.OPENAI_API_KEY else settings.OPENAI_MODEL,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "failed_count": len(failed_cases),
        "duration_seconds": total_eval_duration,
        "metrics": {
            "service_type_accuracy_pct": service_type_acc,
            "urgency_accuracy_pct": urgency_acc,
            "location_accuracy_pct": location_acc,
            "preferred_time_accuracy_pct": time_acc,
            "skills_precision": avg_skills_p,
            "skills_recall": avg_skills_r,
            "skills_f1": avg_skills_f1,
            "unsupported_field_rate_pct": unsupported_field_rate,
            "description_non_empty_rate_pct": desc_non_empty_rate,
        },
        "failed_cases": failed_cases,
    }

    # Print summary table
    print("\n--------------------------------------------------------")
    print(f"  EVALUATION METRIC RESULTS")
    print("--------------------------------------------------------")
    print(f"  Total Cases Evaluated:       {total_cases}")
    print(f"  Service Type Accuracy:       {service_type_acc}%")
    print(f"  Urgency Accuracy:            {urgency_acc}%")
    print(f"  Location Accuracy:           {location_acc}%")
    print(f"  Preferred Time Accuracy:     {time_acc}%")
    print(f"  Skills Precision:            {avg_skills_p}")
    print(f"  Skills Recall:               {avg_skills_r}")
    print(f"  Skills F1 Score:             {avg_skills_f1}")
    print(f"  Unsupported Field Rate:      {unsupported_field_rate}%")
    print(f"  Description Non-Empty Rate:  {desc_non_empty_rate}%")
    print(f"  Evaluation Duration:         {total_eval_duration}s")
    print("--------------------------------------------------------")

    if failed_cases:
        print(f"\n[!] Failed Cases ({len(failed_cases)}):")
        for fc in failed_cases:
            print(f"\nCASE {fc['id']}:")
            print(f"  Input:    {fc['input']}")
            if "expected" in fc and "actual" in fc:
                print(f"  Expected: {fc['expected']}")
                print(f"  Actual:   {fc['actual']}")
            elif "error" in fc:
                print(f"  Error:    {fc['error']}")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Results saved to: {output_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate LLM Service Request Parser.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=project_root / "evaluation" / "datasets" / "parser_cases.json",
        help="Path to parser test dataset JSON",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of cases to evaluate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "results" / "parser_eval_latest.json",
        help="Path to write evaluation results JSON",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Execute in mock mode using ground truth",
    )
    args = parser.parse_args()

    evaluate_parser(
        dataset_path=args.dataset,
        limit=args.limit,
        output_path=args.output,
        mock=args.mock,
    )


if __name__ == "__main__":
    main()
