"""Tests for request idempotency and deduplication (Phase 10)."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fieldops.db.models import IdempotencyRecord, ServiceRequest
from fieldops.llm.schemas import ParsedServiceRequest
from fieldops.main import app
from scripts.seed import seed_customers, seed_technicians
from tests.conftest import TEST_OPERATOR_HEADERS

client = TestClient(app, headers=TEST_OPERATOR_HEADERS)

MOCK_PARSED = ParsedServiceRequest(
    service_type="HVAC",
    urgency="high",
    location="Shinjuku",
    required_skills=["HVAC"],
    preferred_time="tomorrow afternoon",
    problem_description="AC cooling failure",
)


def test_idempotency_first_request_creates_record(test_db_session: Session) -> None:
    """1. First POST /service-requests with Idempotency-Key creates record and ServiceRequest."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=MOCK_PARSED,
    ):
        resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "090-1111-2222",
                "message": "AC cooling failure in Shinjuku tomorrow afternoon",
            },
            headers={"Idempotency-Key": "idemp-key-001"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["customer_id"] is not None
    assert data["service_request_id"] is not None

    # Verify idempotency record exists in database
    rec = test_db_session.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.key == "idemp-key-001")
    ).scalar_one_or_none()

    assert rec is not None
    assert rec.operation == "create_service_request"
    assert rec.status == "completed"
    assert rec.response_payload["service_request_id"] == data["service_request_id"]


def test_idempotency_duplicate_request_returns_cached_without_side_effects(
    test_db_session: Session,
) -> None:
    """2. & 3. Same Idempotency-Key with identical body returns previous response without creating a second ServiceRequest."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    payload = {
        "customer_name": "Alice",
        "email": "alice@example.com",
        "phone": "090-1111-2222",
        "message": "AC cooling failure in Shinjuku tomorrow afternoon",
    }
    headers = {"Idempotency-Key": "idemp-key-002"}

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=MOCK_PARSED,
    ):
        # 1st call
        resp1 = client.post("/service-requests", json=payload, headers=headers)
        assert resp1.status_code == 201
        data1 = resp1.json()

        # 2nd call (retry)
        resp2 = client.post("/service-requests", json=payload, headers=headers)
        assert resp2.status_code in (200, 201)
        data2 = resp2.json()

    # Results match exactly
    assert data1["request_id"] == data2["request_id"]
    assert data1["service_request_id"] == data2["service_request_id"]

    # Verify only 1 ServiceRequest was created in the database
    sr_count = test_db_session.scalar(
        select(func.count(ServiceRequest.id)).where(ServiceRequest.customer_id == 1)
    )
    assert sr_count == 1


def test_idempotency_different_payload_returns_409_conflict(
    test_db_session: Session,
) -> None:
    """4. Same Idempotency-Key with different body returns 409 Conflict due to request hash mismatch."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    headers = {"Idempotency-Key": "idemp-key-003"}

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=MOCK_PARSED,
    ):
        # Initial request: Alice HVAC
        resp1 = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "090-1111-2222",
                "message": "AC cooling failure in Shinjuku tomorrow afternoon",
            },
            headers=headers,
        )
        assert resp1.status_code == 201

        # Tampered / different request with same key: Bob Plumbing
        resp2 = client.post(
            "/service-requests",
            json={
                "customer_name": "Bob",
                "email": "bob@example.com",
                "phone": "090-3333-4444",
                "message": "Completely different plumbing emergency in Shibuya",
            },
            headers=headers,
        )

    assert resp2.status_code == 409
    assert "payload does not match" in resp2.json()["detail"].lower()


def test_idempotency_concurrent_in_flight_returns_409(test_db_session: Session) -> None:
    """5. Concurrent or in-flight request with status='processing' returns 409 Conflict."""
    rec = IdempotencyRecord(
        key="idemp-key-004",
        operation="create_service_request",
        request_hash="dummy-hash-1234",
        status="processing",
    )
    test_db_session.add(rec)
    test_db_session.commit()

    # Pass the matching hash to trigger the processing check
    from fieldops.core.idempotency import compute_request_hash

    payload = {
        "customer_name": "Alice",
        "email": "alice@example.com",
        "phone": "090-1111-2222",
        "message": "AC broken",
    }
    rec.request_hash = compute_request_hash(payload)
    test_db_session.commit()

    resp = client.post(
        "/service-requests",
        json=payload,
        headers={"Idempotency-Key": "idemp-key-004"},
    )
    assert resp.status_code == 409
    assert "currently being processed" in resp.json()["detail"].lower()


def test_idempotency_request_without_header_succeeds(test_db_session: Session) -> None:
    """Request without Idempotency-Key executes normally without idempotency tracking."""
    seed_customers(test_db_session)
    seed_technicians(test_db_session)

    with patch(
        "fieldops.agent.nodes.parse_request.parse_service_request",
        return_value=MOCK_PARSED,
    ):
        resp = client.post(
            "/service-requests",
            json={
                "customer_name": "Alice",
                "email": "alice@example.com",
                "phone": "090-1111-2222",
                "message": "AC cooling failure in Shinjuku tomorrow afternoon",
            },
        )
    assert resp.status_code == 201
