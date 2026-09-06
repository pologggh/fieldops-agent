"""Deterministic Technician Matching Evaluation Runner (Phase 11).

Evaluates TechnicianMatchingService against reference dataset on:
- Exact Candidate Set Accuracy
- Candidate Precision, Recall, and F1
- Missing Information Handling Accuracy (needs_location, needs_skill_information)
- No Candidate Accuracy
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure 'src' and root are on PYTHONPATH
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from evaluation.metrics import calculate_set_metrics
from fieldops.db.models import Technician
from fieldops.db.session import Base
from fieldops.domain.services.technician_matching import TechnicianMatchingService
from fieldops.repositories.technician_repository import TechnicianRepository
from scripts.seed import seed_technicians


def setup_in_memory_db() -> Session:
    """Setup SQLite in-memory database with standard seed technicians."""
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    seed_technicians(session)
    return session


def evaluate_matching(
    dataset_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute technician matching evaluation across dataset cases."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases: list[dict[str, Any]] = json.load(f)

    session = setup_in_memory_db()
    tech_repo = TechnicianRepository(session)
    matching_service = TechnicianMatchingService(tech_repo)

    total_cases = len(cases)
    print(f"\n========================================================")
    print(f"  FieldOps Agent — Technician Matching Evaluation")
    print(f"  Cases: {total_cases} | Deterministic Rules Engine")
    print(f"========================================================\n")

    exact_matches = 0
    correct_statuses = 0
    total_candidate_p = 0.0
    total_candidate_r = 0.0
    total_candidate_f1 = 0.0

    missing_info_cases = 0
    missing_info_handled = 0

    no_candidate_cases = 0
    no_candidate_handled = 0

    failed_cases: list[dict[str, Any]] = []
    start_time = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{idx}")
        location = case.get("location")
        skills = case.get("required_skills")
        exp_status = case["expected_status"]
        exp_names = case["expected_candidate_names"]

        res = matching_service.match_technicians(location=location, required_skills=skills)

        # Resolve candidate IDs to technician names
        matched_names: list[str] = []
        if res.candidate_technician_ids:
            for tid in res.candidate_technician_ids:
                t = session.get(Technician, tid)
                if t:
                    matched_names.append(t.name)

        status_ok = (res.matching_status == exp_status)
        if status_ok:
            correct_statuses += 1

        set_metrics = calculate_set_metrics(exp_names, matched_names)
        total_candidate_p += set_metrics["precision"]
        total_candidate_r += set_metrics["recall"]
        total_candidate_f1 += set_metrics["f1"]

        exact_set_ok = (set_metrics["f1"] == 1.0)
        if exact_set_ok and status_ok:
            exact_matches += 1

        # Track categories
        if exp_status in ("needs_location", "needs_skill_information"):
            missing_info_cases += 1
            if status_ok:
                missing_info_handled += 1
        elif exp_status == "no_candidates":
            no_candidate_cases += 1
            if status_ok:
                no_candidate_handled += 1

        case_passed = exact_set_ok and status_ok
        marker = "PASS" if case_passed else "FAIL"
        print(f"[{idx:02d}/{total_cases:02d}] {case_id} -> {marker} (Status: {res.matching_status}, Candidates: {matched_names})")

        if not case_passed:
            failed_cases.append({
                "id": case_id,
                "description": case.get("description"),
                "location": location,
                "required_skills": skills,
                "expected": {"status": exp_status, "candidates": exp_names},
                "actual": {"status": res.matching_status, "candidates": matched_names},
            })

    total_duration = round(time.perf_counter() - start_time, 2)

    exact_acc = round((exact_matches / total_cases) * 100, 1)
    status_acc = round((correct_statuses / total_cases) * 100, 1)
    avg_p = round(total_candidate_p / total_cases, 4)
    avg_r = round(total_candidate_r / total_cases, 4)
    avg_f1 = round(total_candidate_f1 / total_cases, 4)

    missing_acc = (
        round((missing_info_handled / missing_info_cases) * 100, 1)
        if missing_info_cases > 0
        else 100.0
    )
    no_cand_acc = (
        round((no_candidate_handled / no_candidate_cases) * 100, 1)
        if no_candidate_cases > 0
        else 100.0
    )

    summary = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total_cases,
        "failed_count": len(failed_cases),
        "duration_seconds": total_duration,
        "metrics": {
            "exact_candidate_set_accuracy_pct": exact_acc,
            "status_accuracy_pct": status_acc,
            "candidate_precision": avg_p,
            "candidate_recall": avg_r,
            "candidate_f1": avg_f1,
            "missing_info_handling_accuracy_pct": missing_acc,
            "no_candidate_accuracy_pct": no_cand_acc,
        },
        "failed_cases": failed_cases,
    }

    print("\n--------------------------------------------------------")
    print(f"  MATCHING EVALUATION METRICS")
    print("--------------------------------------------------------")
    print(f"  Total Cases Evaluated:              {total_cases}")
    print(f"  Exact Candidate Set Accuracy:       {exact_acc}%")
    print(f"  Matching Status Accuracy:           {status_acc}%")
    print(f"  Candidate Precision:                {avg_p}")
    print(f"  Candidate Recall:                   {avg_r}")
    print(f"  Candidate F1 Score:                 {avg_f1}")
    print(f"  Missing Info Handling Accuracy:     {missing_acc}%")
    print(f"  No Candidate Accuracy:              {no_cand_acc}%")
    print(f"  Evaluation Duration:                {total_duration}s")
    print("--------------------------------------------------------")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Results saved to: {output_path}")

    session.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Technician Matching Service.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=project_root / "evaluation" / "datasets" / "matching_cases.json",
        help="Path to matching test dataset JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "results" / "matching_eval_latest.json",
        help="Path to write evaluation results JSON",
    )
    args = parser.parse_args()

    evaluate_matching(dataset_path=args.dataset, output_path=args.output)


if __name__ == "__main__":
    main()
