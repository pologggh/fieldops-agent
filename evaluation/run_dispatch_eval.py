"""Evaluation script for Deterministic Dispatch Engine (Phase 26).

Runs 30+ deterministic dispatch evaluation test cases,
computes Hard Constraint Violation Rate, Matching Accuracy,
Recommendation Accuracy, and Soft Constraint Adherence.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from zoneinfo import ZoneInfo

# Add project root and src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from fieldops.core.config import settings
from fieldops.db.models import Appointment, Base, Technician, TechnicianSkill
from fieldops.domain.services.appointment_proposal import AppointmentProposalService
from fieldops.domain.services.scheduling import SchedulingService, has_time_conflict
from fieldops.domain.services.technician_matching import TechnicianMatchingService
from fieldops.domain.services.time_window_parser import TimeWindow
from fieldops.repositories.appointment_repository import AppointmentRepository
from fieldops.repositories.technician_repository import TechnicianRepository


def run_dispatch_evaluation(dataset_path: str = "evaluation/datasets/dispatch_cases.json") -> bool:
    print("=================================================================")
    print("          DETERMINISTIC DISPATCH EVALUATION SUITE (PHASE 26)     ")
    print("=================================================================")

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total_cases = len(cases)
    hard_constraint_violations = 0
    total_hard_constraint_checks = 0

    matching_status_matches = 0
    candidate_set_matches = 0
    recommendation_matches = 0
    soft_constraint_adhered = 0

    results = []

    for c in cases:
        case_id = c["id"]
        name = c["name"]
        req = c["request"]
        techs_data = c["technicians"]
        exp = c["expected"]

        # 1. Setup isolated in-memory SQLite DB
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        try:
            # Seed default customer and service request for appointment FK
            from fieldops.db.models import Customer, ServiceRequest
            customer = Customer(name="Test Customer", email=f"test_{case_id}@example.com")
            session.add(customer)
            session.flush()

            sr = ServiceRequest(
                customer_id=customer.id,
                raw_message="Initial issue",
                service_type="Maintenance",
                urgency="medium",
                location="Tokyo",
                status="open",
            )
            session.add(sr)
            session.flush()

            # Seed technicians & skills
            tech_lookup = {}
            for td in techs_data:
                tech = Technician(
                    id=td["id"],
                    name=td["name"],
                    service_area=td["service_area"],
                    status=td["status"],
                )
                session.add(tech)
                session.flush()
                tech_lookup[tech.id] = td

                for skill_name in td.get("skills", []):
                    session.add(TechnicianSkill(technician_id=tech.id, skill=skill_name))

                # Seed existing appointments
                for appt in td.get("existing_appointments", []):
                    session.add(
                        Appointment(
                            service_request_id=sr.id,
                            technician_id=tech.id,
                            start_time=datetime.fromisoformat(appt["start_time"]),
                            end_time=datetime.fromisoformat(appt["end_time"]),
                            status="scheduled",
                        )
                    )
            session.commit()

            # 2. Run Matching Service
            tech_repo = TechnicianRepository(session)
            matching_service = TechnicianMatchingService(tech_repo)
            match_res = matching_service.match_technicians(
                location=req.get("location"),
                required_skills=req.get("required_skills"),
            )

            # 3. Run Scheduling & Proposal Selection
            appt_repo = AppointmentRepository(session)
            scheduling_service = SchedulingService(appt_repo)

            recommended_tech_id = None
            if match_res.candidate_technician_ids:
                win_data = req.get("window")
                if win_data:
                    window = TimeWindow(
                        start_time=datetime.fromisoformat(win_data["start_time"]),
                        end_time=datetime.fromisoformat(win_data["end_time"]),
                    )
                    sched_res = scheduling_service.check_availability(
                        candidate_technician_ids=match_res.candidate_technician_ids,
                        window=window,
                    )
                    proposal = AppointmentProposalService.select_proposal(
                        available_options=sched_res.available_options
                    )
                    if proposal:
                        recommended_tech_id = proposal["technician_id"]

            # 4. HARD CONSTRAINT CHECKS (Must never be violated)
            case_violations = []

            # Check 4.1: Missing location rule
            total_hard_constraint_checks += 1
            if not req.get("location") or not str(req.get("location")).strip():
                if match_res.matching_status != "needs_location" or match_res.candidate_technician_ids != []:
                    case_violations.append("Missing location must produce needs_location and empty candidates")

            # Check 4.2: Missing skill rule
            total_hard_constraint_checks += 1
            req_skills = [s for s in (req.get("required_skills") or []) if s and str(s).strip()]
            if not req_skills:
                if req.get("location") and str(req.get("location")).strip():
                    if match_res.matching_status != "needs_skill_information" or match_res.candidate_technician_ids != []:
                        case_violations.append("Missing skills must produce needs_skill_information and empty candidates")

            # Check 4.3: Inactive technician exclusion
            for cand_id in match_res.candidate_technician_ids:
                total_hard_constraint_checks += 1
                tech_meta = tech_lookup[cand_id]
                if tech_meta["status"] != "active":
                    case_violations.append(f"Hard Constraint Violated: Inactive technician {cand_id} matched")

            # Check 4.4: Service area mismatch
            if req.get("location") and str(req.get("location")).strip():
                norm_req_loc = str(req["location"]).strip().casefold()
                for cand_id in match_res.candidate_technician_ids:
                    total_hard_constraint_checks += 1
                    tech_meta = tech_lookup[cand_id]
                    if tech_meta["service_area"].strip().casefold() != norm_req_loc:
                        case_violations.append(f"Hard Constraint Violated: Tech {cand_id} area {tech_meta['service_area']} does not match {norm_req_loc}")

            # Check 4.5: Required skills subset rule
            if req_skills:
                norm_req_skills = {s.strip().casefold() for s in req_skills}
                for cand_id in match_res.candidate_technician_ids:
                    total_hard_constraint_checks += 1
                    tech_meta = tech_lookup[cand_id]
                    t_skills = {s.strip().casefold() for s in tech_meta.get("skills", [])}
                    if not norm_req_skills.issubset(t_skills):
                        case_violations.append(f"Hard Constraint Violated: Tech {cand_id} missing required skills")

            # Check 4.6: No overlapping appointment conflict
            if recommended_tech_id is not None:
                total_hard_constraint_checks += 1
                tech_meta = tech_lookup[recommended_tech_id]
                for existing_appt in tech_meta.get("existing_appointments", []):
                    ex_start = datetime.fromisoformat(existing_appt["start_time"])
                    ex_end = datetime.fromisoformat(existing_appt["end_time"])
                    prop_start = datetime.fromisoformat(proposal["start_time"])
                    prop_end = datetime.fromisoformat(proposal["end_time"])
                    if has_time_conflict(prop_start, prop_end, ex_start, ex_end):
                        case_violations.append(f"Hard Constraint Violated: Overlapping slot {prop_start} with {ex_start}")

            if case_violations:
                hard_constraint_violations += len(case_violations)
                print(f"[FAIL-HARD-CONSTRAINT] {case_id}: {case_violations}")

            # 5. EXPECTED COMPARISONS
            stat_match = (match_res.matching_status == exp["matching_status"])
            if stat_match:
                matching_status_matches += 1

            cand_match = (sorted(match_res.candidate_technician_ids) == sorted(exp["candidate_technician_ids"]))
            if cand_match:
                candidate_set_matches += 1

            rec_match = (recommended_tech_id == exp["recommended_technician_id"])
            if rec_match:
                recommendation_matches += 1
                soft_constraint_adhered += 1

            status_flag = "PASS" if (len(case_violations) == 0 and stat_match and cand_match and rec_match) else "FAIL"
            print(f"[{status_flag}] {case_id}: {name} -> Status={match_res.matching_status}, Candidates={match_res.candidate_technician_ids}, Rec={recommended_tech_id}")

            results.append({
                "case_id": case_id,
                "name": name,
                "passed": status_flag == "PASS",
                "matching_status": match_res.matching_status,
                "candidate_technician_ids": match_res.candidate_technician_ids,
                "recommended_technician_id": recommended_tech_id,
                "violations": case_violations,
            })

        finally:
            session.close()

    # Metrics
    hard_violation_rate = (hard_constraint_violations / total_hard_constraint_checks * 100) if total_hard_constraint_checks > 0 else 0.0
    status_accuracy = (matching_status_matches / total_cases * 100)
    candidate_accuracy = (candidate_set_matches / total_cases * 100)
    recommendation_accuracy = (recommendation_matches / total_cases * 100)
    soft_adherence_rate = (soft_constraint_adhered / total_cases * 100)

    print("\n-----------------------------------------------------------------")
    print("                       DISPATCH METRICS                          ")
    print("-----------------------------------------------------------------")
    print(f"Total Test Cases Evaluated:               {total_cases}")
    print(f"Total Hard Constraint Checks:             {total_hard_constraint_checks}")
    print(f"Hard Constraint Violations:               {hard_constraint_violations}")
    print(f"Hard Constraint Violation Rate:           {hard_violation_rate:.1f}% (Required: 0.0%)")
    print(f"Matching Status Accuracy:                 {status_accuracy:.1f}%")
    print(f"Candidate Set Match Accuracy:             {candidate_accuracy:.1f}%")
    print(f"Recommendation Accuracy:                  {recommendation_accuracy:.1f}%")
    print(f"Soft Constraint Adherence:                {soft_adherence_rate:.1f}%")
    print("=================================================================")

    # Enforce zero violation baseline
    assert hard_violation_rate == 0.0, f"FATAL: Hard constraint violation rate is {hard_violation_rate}% > 0.0%!"

    out_dir = Path("evaluation/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "dispatch_eval_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_cases": total_cases,
            "total_hard_constraint_checks": total_hard_constraint_checks,
            "hard_constraint_violations": hard_constraint_violations,
            "hard_constraint_violation_rate": hard_violation_rate,
            "matching_status_accuracy": status_accuracy,
            "candidate_set_accuracy": candidate_accuracy,
            "recommendation_accuracy": recommendation_accuracy,
            "soft_constraint_adherence": soft_adherence_rate,
            "cases": results,
        }, f, indent=2)
    print(f"Saved evaluation results to {out_file}")

    return True


if __name__ == "__main__":
    success = run_dispatch_evaluation()
    sys.exit(0 if success else 1)
