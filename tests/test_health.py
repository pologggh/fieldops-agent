from fastapi.testclient import TestClient

from fieldops.main import app
from fieldops.db import models


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_import_smoke() -> None:
    assert models.Customer.__tablename__ == "customers"
    assert models.Technician.__tablename__ == "technicians"
    assert models.TechnicianSkill.__tablename__ == "technician_skills"
    assert models.ServiceRequest.__tablename__ == "service_requests"
    assert models.Appointment.__tablename__ == "appointments"
    assert models.AuditLog.__tablename__ == "audit_logs"
