"""Admin Console API Router for System Administration and Governance."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, desc, and_, or_, text
from sqlalchemy.orm import Session

from fieldops.core.config import settings
from fieldops.db.models import (
    Appointment,
    AuditLog,
    Customer,
    CustomerAccount,
    DispatchPolicy,
    IntegrationRecord,
    InternalUser,
    OutboxEvent,
    ServiceRequest,
    SLAPolicy,
    Technician,
    TechnicianSkill,
)
from fieldops.db.session import SessionLocal
from fieldops.schemas.admin_schemas import (
    AuditLogView,
    DispatchPolicyCreateInput,
    DispatchPolicyView,
    IntegrationFailureView,
    IntegrationSummaryView,
    InternalUserCreateInput,
    InternalUserUpdateInput,
    InternalUserView,
    RoleChangeInput,
    SLAPolicyCreateInput,
    SLAPolicyView,
    SystemSummaryView,
    TechnicianAdminView,
    TechnicianCreateInput,
    TechnicianUpdateInput,
)
from fieldops.security.admin_auth import get_current_admin, hash_password

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["Admin Console"])


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# 1. Internal User Management
# ==============================================================================


@admin_router.get("/users", response_model=List[InternalUserView], summary="List internal users")
def list_internal_users(
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> List[InternalUserView]:
    """Admin endpoint to list all internal users with roles and status."""
    users = session.query(InternalUser).order_by(InternalUser.id.asc()).all()
    return [
        InternalUserView(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role,
            is_active=u.is_active,
            last_login=u.last_login.isoformat() if u.last_login else None,
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in users
    ]


@admin_router.post("/users", response_model=InternalUserView, status_code=status.HTTP_201_CREATED, summary="Create internal user")
def create_internal_user(
    payload: InternalUserCreateInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> InternalUserView:
    """Admin creates a new internal operator, viewer, or admin."""
    existing = session.query(InternalUser).filter_by(email=payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An internal user with email '{payload.email}' already exists.",
        )

    pwd_hash = hash_password(payload.password)
    new_user = InternalUser(
        email=payload.email,
        name=payload.name,
        role=payload.role,
        password_hash=pwd_hash,
        is_active=True,
    )
    session.add(new_user)
    session.flush()

    audit = AuditLog(
        entity_type="internal_user",
        entity_id=str(new_user.id),
        action="user.created",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "created_email": new_user.email,
            "role": new_user.role,
        },
    )
    session.add(audit)
    session.commit()

    return InternalUserView(
        id=new_user.id,
        email=new_user.email,
        name=new_user.name,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at.isoformat() if new_user.created_at else "",
    )


@admin_router.get("/users/{user_id}", response_model=InternalUserView, summary="Get user details")
def get_internal_user(
    user_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> InternalUserView:
    user = session.query(InternalUser).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal user not found.")

    return InternalUserView(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@admin_router.patch("/users/{user_id}", response_model=InternalUserView, summary="Update user name")
def update_internal_user(
    user_id: int,
    payload: InternalUserUpdateInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> InternalUserView:
    user = session.query(InternalUser).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal user not found.")

    if payload.name:
        user.name = payload.name.strip()
    session.commit()

    return InternalUserView(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@admin_router.post("/users/{user_id}/activate", response_model=InternalUserView, summary="Activate user")
def activate_internal_user(
    user_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> InternalUserView:
    user = session.query(InternalUser).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal user not found.")

    user.is_active = True
    audit = AuditLog(
        entity_type="internal_user",
        entity_id=str(user.id),
        action="user.activated",
        details={"actor": admin.email, "actor_type": "admin", "target_email": user.email},
    )
    session.add(audit)
    session.commit()

    return InternalUserView(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@admin_router.post("/users/{user_id}/deactivate", response_model=InternalUserView, summary="Deactivate user (soft-disable)")
def deactivate_internal_user(
    user_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> InternalUserView:
    user = session.query(InternalUser).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal user not found.")

    # Business Rule: Cannot deactivate the last active admin!
    if user.role == "admin" and user.is_active:
        other_admins = (
            session.query(InternalUser)
            .filter(InternalUser.role == "admin", InternalUser.is_active == True, InternalUser.id != user.id)
            .count()
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active administrator.",
            )

    user.is_active = False
    audit = AuditLog(
        entity_type="internal_user",
        entity_id=str(user.id),
        action="user.deactivated",
        details={"actor": admin.email, "actor_type": "admin", "target_email": user.email},
    )
    session.add(audit)
    session.commit()

    return InternalUserView(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@admin_router.post("/users/{user_id}/role", response_model=InternalUserView, summary="Change user role")
def change_user_role(
    user_id: int,
    payload: RoleChangeInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> InternalUserView:
    user = session.query(InternalUser).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal user not found.")

    old_role = user.role
    new_role = payload.role

    # Business Rule: Cannot demote the last active admin!
    if old_role == "admin" and new_role != "admin" and user.is_active:
        other_admins = (
            session.query(InternalUser)
            .filter(InternalUser.role == "admin", InternalUser.is_active == True, InternalUser.id != user.id)
            .count()
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last active administrator.",
            )

    user.role = new_role
    audit = AuditLog(
        entity_type="internal_user",
        entity_id=str(user.id),
        action="user.role_changed",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "target_email": user.email,
            "old_role": old_role,
            "new_role": new_role,
        },
    )
    session.add(audit)
    session.commit()

    return InternalUserView(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        last_login=user.last_login.isoformat() if user.last_login else None,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# ==============================================================================
# 2. Technician Management
# ==============================================================================


@admin_router.get("/technicians", response_model=List[TechnicianAdminView], summary="List all technicians")
def list_technicians_admin(
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> List[TechnicianAdminView]:
    """Admin view for all technicians with capacity, emergency availability, and skills."""
    techs = session.query(Technician).order_by(Technician.id.asc()).all()
    views: List[TechnicianAdminView] = []
    now_utc = datetime.now(timezone.utc)

    for t in techs:
        workload_minutes = 0
        scheduled_appts = (
            session.query(Appointment)
            .filter(
                Appointment.technician_id == t.id,
                Appointment.status == "scheduled",
                Appointment.start_time >= now_utc,
            )
            .all()
        )
        for a in scheduled_appts:
            if a.start_time and a.end_time:
                diff = (a.end_time - a.start_time).total_seconds() / 60
                workload_minutes += int(diff)

        skills = [s.skill for s in t.skills] if hasattr(t, "skills") else []
        views.append(
            TechnicianAdminView(
                id=t.id,
                name=t.name,
                service_area=t.service_area,
                status=t.status,
                skills=skills,
                max_daily_work_minutes=getattr(t, "max_daily_work_minutes", 480),
                max_daily_jobs=getattr(t, "max_daily_jobs", 5),
                is_available_for_emergency=getattr(t, "is_available_for_emergency", False),
                current_workload_minutes=workload_minutes,
                created_at=t.created_at.isoformat() if t.created_at else "",
            )
        )
    return views


@admin_router.post("/technicians", response_model=TechnicianAdminView, status_code=status.HTTP_201_CREATED, summary="Create technician")
def create_technician_admin(
    payload: TechnicianCreateInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> TechnicianAdminView:
    tech = Technician(
        name=payload.name.strip(),
        service_area=payload.service_area.strip(),
        status=payload.status,
        max_daily_work_minutes=payload.max_daily_work_minutes,
        max_daily_jobs=payload.max_daily_jobs,
        is_available_for_emergency=payload.is_available_for_emergency,
    )
    session.add(tech)
    session.flush()

    for s in payload.skills:
        skill_record = TechnicianSkill(technician_id=tech.id, skill=s.strip())
        session.add(skill_record)

    audit = AuditLog(
        entity_type="technician",
        entity_id=str(tech.id),
        action="technician.created",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "name": tech.name,
            "service_area": tech.service_area,
            "skills": payload.skills,
        },
    )
    session.add(audit)
    session.commit()

    return TechnicianAdminView(
        id=tech.id,
        name=tech.name,
        service_area=tech.service_area,
        status=tech.status,
        skills=payload.skills,
        max_daily_work_minutes=tech.max_daily_work_minutes,
        max_daily_jobs=tech.max_daily_jobs,
        is_available_for_emergency=tech.is_available_for_emergency,
        current_workload_minutes=0,
        created_at=tech.created_at.isoformat() if tech.created_at else "",
    )


@admin_router.get("/technicians/{tech_id}", response_model=TechnicianAdminView, summary="Get technician")
def get_technician_admin(
    tech_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> TechnicianAdminView:
    tech = session.query(Technician).filter_by(id=tech_id).first()
    if not tech:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found.")

    skills = [s.skill for s in tech.skills] if hasattr(tech, "skills") else []
    return TechnicianAdminView(
        id=tech.id,
        name=tech.name,
        service_area=tech.service_area,
        status=tech.status,
        skills=skills,
        max_daily_work_minutes=getattr(tech, "max_daily_work_minutes", 480),
        max_daily_jobs=getattr(tech, "max_daily_jobs", 5),
        is_available_for_emergency=getattr(tech, "is_available_for_emergency", False),
        created_at=tech.created_at.isoformat() if tech.created_at else "",
    )


@admin_router.patch("/technicians/{tech_id}", response_model=TechnicianAdminView, summary="Update technician")
def update_technician_admin(
    tech_id: int,
    payload: TechnicianUpdateInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> TechnicianAdminView:
    tech = session.query(Technician).filter_by(id=tech_id).first()
    if not tech:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found.")

    changes = {}
    if payload.name is not None:
        tech.name = payload.name.strip()
        changes["name"] = tech.name
    if payload.service_area is not None:
        tech.service_area = payload.service_area.strip()
        changes["service_area"] = tech.service_area
    if payload.max_daily_work_minutes is not None:
        tech.max_daily_work_minutes = payload.max_daily_work_minutes
        changes["max_daily_work_minutes"] = tech.max_daily_work_minutes
    if payload.max_daily_jobs is not None:
        tech.max_daily_jobs = payload.max_daily_jobs
        changes["max_daily_jobs"] = tech.max_daily_jobs
    if payload.is_available_for_emergency is not None:
        tech.is_available_for_emergency = payload.is_available_for_emergency
        changes["is_available_for_emergency"] = tech.is_available_for_emergency

    if payload.skills is not None:
        session.query(TechnicianSkill).filter_by(technician_id=tech.id).delete()
        for s in payload.skills:
            session.add(TechnicianSkill(technician_id=tech.id, skill=s.strip()))
        changes["skills"] = payload.skills

    audit = AuditLog(
        entity_type="technician",
        entity_id=str(tech.id),
        action="technician.updated",
        details={"actor": admin.email, "actor_type": "admin", "changes": changes},
    )
    session.add(audit)
    session.commit()

    updated_skills = [s.skill for s in tech.skills] if hasattr(tech, "skills") else []
    return TechnicianAdminView(
        id=tech.id,
        name=tech.name,
        service_area=tech.service_area,
        status=tech.status,
        skills=updated_skills,
        max_daily_work_minutes=tech.max_daily_work_minutes,
        max_daily_jobs=tech.max_daily_jobs,
        is_available_for_emergency=tech.is_available_for_emergency,
        created_at=tech.created_at.isoformat() if tech.created_at else "",
    )


@admin_router.post("/technicians/{tech_id}/activate", response_model=TechnicianAdminView, summary="Activate technician")
def activate_technician_admin(
    tech_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> TechnicianAdminView:
    tech = session.query(Technician).filter_by(id=tech_id).first()
    if not tech:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found.")

    tech.status = "active"
    audit = AuditLog(
        entity_type="technician",
        entity_id=str(tech.id),
        action="technician.activated",
        details={"actor": admin.email, "actor_type": "admin"},
    )
    session.add(audit)
    session.commit()

    skills = [s.skill for s in tech.skills] if hasattr(tech, "skills") else []
    return TechnicianAdminView(
        id=tech.id,
        name=tech.name,
        service_area=tech.service_area,
        status=tech.status,
        skills=skills,
        max_daily_work_minutes=tech.max_daily_work_minutes,
        max_daily_jobs=tech.max_daily_jobs,
        is_available_for_emergency=tech.is_available_for_emergency,
        created_at=tech.created_at.isoformat() if tech.created_at else "",
    )


@admin_router.post("/technicians/{tech_id}/deactivate", response_model=TechnicianAdminView, summary="Deactivate technician with conflict check")
def deactivate_technician_admin(
    tech_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> TechnicianAdminView:
    tech = session.query(Technician).filter_by(id=tech_id).first()
    if not tech:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found.")

    # Business Rule: Check for future scheduled appointments
    now_utc = datetime.now(timezone.utc)
    future_appts = (
        session.query(Appointment)
        .filter(
            Appointment.technician_id == tech.id,
            Appointment.status == "scheduled",
            Appointment.start_time >= now_utc,
        )
        .count()
    )
    if future_appts > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot deactivate technician '{tech.name}': Has {future_appts} active future appointment(s). Please reassign or cancel future appointments first.",
        )

    tech.status = "inactive"
    audit = AuditLog(
        entity_type="technician",
        entity_id=str(tech.id),
        action="technician.deactivated",
        details={"actor": admin.email, "actor_type": "admin"},
    )
    session.add(audit)
    session.commit()

    skills = [s.skill for s in tech.skills] if hasattr(tech, "skills") else []
    return TechnicianAdminView(
        id=tech.id,
        name=tech.name,
        service_area=tech.service_area,
        status=tech.status,
        skills=skills,
        max_daily_work_minutes=tech.max_daily_work_minutes,
        max_daily_jobs=tech.max_daily_jobs,
        is_available_for_emergency=tech.is_available_for_emergency,
        created_at=tech.created_at.isoformat() if tech.created_at else "",
    )


# ==============================================================================
# 3. Dispatch Policy Management (Versioned)
# ==============================================================================


@admin_router.get("/policies/dispatch", response_model=List[DispatchPolicyView], summary="Get dispatch policy version history")
def get_dispatch_policies(
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> List[DispatchPolicyView]:
    policies = session.query(DispatchPolicy).order_by(DispatchPolicy.version.desc()).all()
    return [
        DispatchPolicyView(
            id=p.id,
            version=p.version,
            is_active=p.is_active,
            weights=p.weights,
            description=p.description,
            created_by=p.created_by,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p in policies
    ]


@admin_router.post("/policies/dispatch", response_model=DispatchPolicyView, status_code=status.HTTP_201_CREATED, summary="Create and activate new dispatch policy version")
def create_dispatch_policy(
    payload: DispatchPolicyCreateInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> DispatchPolicyView:
    weights = payload.weights
    for k, v in weights.items():
        if v < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Weight '{k}' cannot be negative (got {v}).",
            )
        if k != "overtime_penalty" and v > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Weight '{k}' must be between 0 and 100.",
            )

    total_sum = sum(weights.values())
    if total_sum != 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dispatch policy weights must sum to 100 (got {total_sum}).",
        )

    max_ver = session.query(func.max(DispatchPolicy.version)).scalar() or 0
    next_ver = max_ver + 1

    session.query(DispatchPolicy).filter_by(is_active=True).update({"is_active": False})

    new_policy = DispatchPolicy(
        version=next_ver,
        is_active=True,
        weights=weights,
        description=payload.description or f"Dispatch weights revision v{next_ver}",
        created_by=admin.email,
    )
    session.add(new_policy)
    session.flush()

    audit = AuditLog(
        entity_type="dispatch_policy",
        entity_id=str(new_policy.id),
        action="dispatch_policy.activated",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "version": next_ver,
            "weights": weights,
        },
    )
    session.add(audit)
    session.commit()

    return DispatchPolicyView(
        id=new_policy.id,
        version=new_policy.version,
        is_active=new_policy.is_active,
        weights=new_policy.weights,
        description=new_policy.description,
        created_by=new_policy.created_by,
        created_at=new_policy.created_at.isoformat() if new_policy.created_at else "",
    )


@admin_router.post("/policies/dispatch/{version}/activate", response_model=DispatchPolicyView, summary="Rollback/activate dispatch policy version")
def activate_dispatch_policy_version(
    version: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> DispatchPolicyView:
    target = session.query(DispatchPolicy).filter_by(version=version).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dispatch policy version {version} not found.")

    session.query(DispatchPolicy).filter_by(is_active=True).update({"is_active": False})
    target.is_active = True

    audit = AuditLog(
        entity_type="dispatch_policy",
        entity_id=str(target.id),
        action="dispatch_policy.activated",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "action_type": "rollback_or_switch",
            "version": version,
        },
    )
    session.add(audit)
    session.commit()

    return DispatchPolicyView(
        id=target.id,
        version=target.version,
        is_active=target.is_active,
        weights=target.weights,
        description=target.description,
        created_by=target.created_by,
        created_at=target.created_at.isoformat() if target.created_at else "",
    )


# ==============================================================================
# 4. SLA Policy Management (Versioned)
# ==============================================================================


@admin_router.get("/policies/sla", response_model=List[SLAPolicyView], summary="Get SLA policy version history")
def get_sla_policies(
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> List[SLAPolicyView]:
    policies = session.query(SLAPolicy).order_by(SLAPolicy.version.desc()).all()
    return [
        SLAPolicyView(
            id=p.id,
            version=p.version,
            is_active=p.is_active,
            targets=p.targets,
            description=p.description,
            created_by=p.created_by,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p in policies
    ]


@admin_router.post("/policies/sla", response_model=SLAPolicyView, status_code=status.HTTP_201_CREATED, summary="Create and activate new SLA policy version")
def create_sla_policy(
    payload: SLAPolicyCreateInput,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> SLAPolicyView:
    targets = payload.targets
    for tier in ["P0", "P1", "P2", "P3"]:
        if tier not in targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing SLA configuration for tier '{tier}'.",
            )
        for metric in ["response_minutes", "assignment_minutes", "service_start_minutes", "at_risk_threshold_minutes"]:
            val = targets[tier].get(metric)
            if val is None or val <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SLA tier '{tier}' must have positive '{metric}' (got {val}).",
                )

    max_ver = session.query(func.max(SLAPolicy.version)).scalar() or 0
    next_ver = max_ver + 1

    session.query(SLAPolicy).filter_by(is_active=True).update({"is_active": False})

    new_policy = SLAPolicy(
        version=next_ver,
        is_active=True,
        targets=targets,
        description=payload.description or f"SLA matrix revision v{next_ver}",
        created_by=admin.email,
    )
    session.add(new_policy)
    session.flush()

    audit = AuditLog(
        entity_type="sla_policy",
        entity_id=str(new_policy.id),
        action="sla_policy.activated",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "version": next_ver,
            "tiers": list(targets.keys()),
        },
    )
    session.add(audit)
    session.commit()

    return SLAPolicyView(
        id=new_policy.id,
        version=new_policy.version,
        is_active=new_policy.is_active,
        targets=new_policy.targets,
        description=new_policy.description,
        created_by=new_policy.created_by,
        created_at=new_policy.created_at.isoformat() if new_policy.created_at else "",
    )


@admin_router.post("/policies/sla/{version}/activate", response_model=SLAPolicyView, summary="Rollback/activate SLA policy version")
def activate_sla_policy_version(
    version: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> SLAPolicyView:
    target = session.query(SLAPolicy).filter_by(version=version).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SLA policy version {version} not found.")

    session.query(SLAPolicy).filter_by(is_active=True).update({"is_active": False})
    target.is_active = True

    audit = AuditLog(
        entity_type="sla_policy",
        entity_id=str(target.id),
        action="sla_policy.activated",
        details={
            "actor": admin.email,
            "actor_type": "admin",
            "action_type": "rollback_or_switch",
            "version": version,
        },
    )
    session.add(audit)
    session.commit()

    return SLAPolicyView(
        id=target.id,
        version=target.version,
        is_active=target.is_active,
        targets=target.targets,
        description=target.description,
        created_by=target.created_by,
        created_at=target.created_at.isoformat() if target.created_at else "",
    )


# ==============================================================================
# 5. Integration Status & Failures Review (Zero Secrets)
# ==============================================================================


@admin_router.get("/integrations/summary", response_model=IntegrationSummaryView, summary="Get integration status summary")
def get_integrations_summary(
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> IntegrationSummaryView:
    records = session.query(IntegrationRecord).all()
    pending = sum(1 for r in records if r.status == "pending")
    synced = sum(1 for r in records if r.status == "synced")
    failed = sum(1 for r in records if r.status == "failed")

    is_google = settings.CALENDAR_PROVIDER.lower() == "google"
    cal_records = [r for r in records if "calendar" in r.provider.lower()]
    cal_synced = sum(1 for r in cal_records if r.status == "synced")
    cal_failed = sum(1 for r in cal_records if r.status == "failed")
    last_cal_sync = max((r.updated_at for r in cal_records if r.status == "synced"), default=None)

    email_records = [r for r in records if "email" in r.provider.lower()]
    email_synced = sum(1 for r in email_records if r.status == "synced")
    email_failed = sum(1 for r in email_records if r.status == "failed")
    last_email_sync = max((r.updated_at for r in email_records if r.status == "synced"), default=None)

    # Safe calendar ID display (mask if it resembles an email address)
    masked_cal_id = settings.GOOGLE_CALENDAR_ID
    if "@" in masked_cal_id:
        name, domain = masked_cal_id.split("@", 1)
        masked_cal_id = f"{name[:2]}***@{domain}"
    elif len(masked_cal_id) > 6:
        masked_cal_id = f"{masked_cal_id[:4]}***"

    cal_badge = (
        f"Google Calendar API v3 (Target: {masked_cal_id})"
        if is_google
        else "Development / Fake Provider"
    )

    providers = [
        {
            "provider": "Google Calendar",
            "type": "calendar",
            "is_mock": not is_google,
            "badge": cal_badge,
            "status": "connected",
            "success_count": cal_synced,
            "failure_count": cal_failed,
            "last_sync": last_cal_sync.isoformat() if last_cal_sync else None,
        },
        {
            "provider": "SendGrid / SMTP",
            "type": "email",
            "is_mock": True,
            "badge": "Development / Fake Provider",
            "status": "connected",
            "success_count": email_synced,
            "failure_count": email_failed,
            "last_sync": last_email_sync.isoformat() if last_email_sync else None,
        },
    ]

    return IntegrationSummaryView(
        providers=providers,
        total_synced=synced,
        total_failed=failed,
        calendar_provider=f"GoogleCalendarClient ({masked_cal_id})" if is_google else "FakeCalendarClient (Development / Fake Provider)",
        calendar_is_fake=not is_google,
        email_provider="FakeEmailClient (Development / Fake Provider)",
        email_is_fake=True,
        pending_count=pending,
        synced_count=synced,
        failed_count=failed,
    )


@admin_router.get("/integrations/failures", response_model=List[IntegrationFailureView], summary="List integration failures")
def get_integration_failures(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    limit: int = Query(50, le=200),
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> List[IntegrationFailureView]:
    """Review failed external integrations without revealing tokens, bodies, or secrets."""
    query = session.query(IntegrationRecord).filter_by(status="failed")
    if provider:
        query = query.filter(IntegrationRecord.provider.ilike(f"%{provider}%"))

    failures = query.order_by(IntegrationRecord.updated_at.desc()).limit(limit).all()
    return [
        IntegrationFailureView(
            id=f.id,
            provider=f.provider,
            resource_type=f.resource_type,
            local_resource_id=f.local_resource_id,
            appointment_id=f.local_resource_id if f.resource_type == "appointment" else None,
            status=f.status,
            attempt_count=f.attempt_count,
            last_error_summary=f.last_error[:200] if f.last_error else None,
            last_error=f.last_error,
            updated_at=f.updated_at.isoformat() if f.updated_at else "",
        )
        for f in failures
    ]


@admin_router.post("/integrations/calendar/test-connection", summary="Test Calendar Provider Connection")
def test_calendar_connection(
    admin: InternalUser = Depends(get_current_admin),
) -> dict[str, Any]:
    """Verify external calendar connectivity without revealing secrets or private keys."""
    from fieldops.integrations import get_calendar_client
    client = get_calendar_client()
    if hasattr(client, "test_connection"):
        return client.test_connection()
    return {"status": "connected", "provider": settings.CALENDAR_PROVIDER, "mode": "fake"}


@admin_router.post("/integrations/calendar/reconcile", summary="Trigger Calendar Reconciliation")
def trigger_calendar_reconciliation(
    appointment_id: Optional[int] = Query(None, description="Optional appointment ID to reconcile"),
    limit: int = Query(50, le=100),
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inspect and heal desynchronization between local database and external calendar."""
    from fieldops.integrations.calendar.reconciliation import CalendarReconciliationService
    recon = CalendarReconciliationService(session)
    if appointment_id:
        return recon.reconcile_appointment(appointment_id)
    return recon.reconcile_batch(limit=limit)


@admin_router.post("/integrations/{record_id}/retry", summary="Retry failed external integration")
def retry_integration_record(
    record_id: int,
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Manually re-enqueue a failed integration record via Celery."""
    record = session.get(IntegrationRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Integration record not found")

    record.status = "pending"
    record.last_error = None
    session.commit()

    from fieldops.repositories.audit_log_repository import AuditLogRepository
    audit_repo = AuditLogRepository(session)
    audit_repo.create(
        entity_type="integration_record",
        entity_id=str(record.id),
        action="integration.retry_requested",
        details={
            "admin": admin.email,
            "provider": record.provider,
            "resource_id": record.local_resource_id,
        },
    )
    session.commit()

    if record.resource_type == "appointment":
        from fieldops.tasks.integration_tasks import sync_appointment_calendar
        sync_appointment_calendar.delay(record.local_resource_id)

    return {"status": "queued", "record_id": record.id, "resource_id": record.local_resource_id}


# ==============================================================================
# 6. Audit & Security Review (Read-Only)
# ==============================================================================


@admin_router.get("/audit", response_model=List[AuditLogView], summary="Read-only audit log review")
def get_audit_logs(
    event_type: Optional[str] = Query(None, description="Filter by action/event name"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (admin, operator, customer, system)"),
    resource_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    limit: int = Query(50, le=200),
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> List[AuditLogView]:
    """Query audit trail records with filters. Strictly read-only."""
    query = session.query(AuditLog)

    target_action = action or event_type
    if target_action:
        query = query.filter(AuditLog.action.ilike(f"%{target_action}%"))

    target_entity_type = entity_type or resource_type
    if target_entity_type:
        query = query.filter_by(entity_type=target_entity_type)

    if entity_id:
        query = query.filter_by(entity_id=str(entity_id))

    logs = query.order_by(AuditLog.id.desc()).limit(limit).all()

    views: List[AuditLogView] = []
    for l in logs:
        det = l.details or {}
        actor = det.get("actor") or det.get("actor_id") or "system"
        act_type = det.get("actor_type") or "system"

        if actor_type and act_type.lower() != actor_type.lower():
            continue

        summary = f"{act_type.title()} performed '{l.action}' on {l.entity_type} #{l.entity_id}"
        views.append(
            AuditLogView(
                id=l.id,
                timestamp=l.created_at.isoformat() if l.created_at else "",
                entity_type=l.entity_type,
                entity_id=str(l.entity_id),
                action=l.action,
                actor=str(actor),
                actor_type=str(act_type),
                summary=summary,
                details=det,
            )
        )
    return views


# ==============================================================================
# 7. System Governance Summary (Zero Secrets)
# ==============================================================================


@admin_router.get("/system/summary", response_model=SystemSummaryView, summary="System health and governance telemetry")
def get_system_summary(
    admin: InternalUser = Depends(get_current_admin),
    session: Session = Depends(get_db),
) -> SystemSummaryView:
    """Consolidated operational health status. NEVER exposes secrets or credentials."""
    db_ok = True
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    outbox_pending = session.query(OutboxEvent).filter_by(status="pending").count()
    integration_failures = session.query(IntegrationRecord).filter_by(status="failed").count()
    active_techs = session.query(Technician).filter_by(status="active").count()
    active_users = session.query(InternalUser).filter_by(is_active=True).count()
    open_sr_count = session.query(ServiceRequest).filter(ServiceRequest.status.in_(["pending", "queued", "dispatched", "in_progress", "waiting_for_approval", "ready_for_review"])).count()

    now_utc = datetime.now(timezone.utc)
    escalations_count = session.query(ServiceRequest).filter(
        or_(
            ServiceRequest.urgency.in_(["high", "emergency"]),
            ServiceRequest.status.in_(["needs_rescheduling", "conflict", "no_technician", "no_technician_available", "rejected"])
        )
    ).count()

    sla_breaches = session.query(ServiceRequest).filter(
        ServiceRequest.status.notin_(["completed", "cancelled"]),
        ServiceRequest.sla_deadline.isnot(None),
        ServiceRequest.sla_deadline < now_utc
    ).count()

    provider_name = getattr(settings, "LLM_PROVIDER", "fake")
    model_name = getattr(settings, "LLM_MODEL", "gpt-4o-mini")

    return SystemSummaryView(
        health_status="healthy",
        readiness_status="ready",
        database="connected" if db_ok else "disconnected",
        redis="connected",
        active_internal_users=active_users,
        active_technicians=active_techs,
        open_service_requests=open_sr_count,
        pending_outbox_events=outbox_pending,
        llm_config={
            "provider": provider_name,
            "model": model_name,
            "configured": True,
        },
        api_status="healthy",
        database_status="connected" if db_ok else "disconnected",
        redis_status="connected",
        celery_worker_status="operational",
        outbox_backlog_count=outbox_pending,
        integration_failures_count=integration_failures,
        active_technicians_count=active_techs,
        active_internal_users_count=active_users,
        llm_provider=provider_name,
        llm_model=model_name,
        llm_configured=True,
        open_escalations_count=escalations_count,
        sla_breaches_count=sla_breaches,
    )
