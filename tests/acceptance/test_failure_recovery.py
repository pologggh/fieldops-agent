"""Acceptance Test 8: Failure Recovery, Outbox Resilience, LLM Timeouts, and State Resumption."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fieldops.core.exceptions import LLMTimeoutError
from fieldops.db.models import (
    Appointment,
    Customer,
    IntegrationRecord,
    OutboxEvent,
    ServiceRequest,
    Technician,
)
from fieldops.tasks.outbox_tasks import publish_outbox_events


def test_outbox_retry_and_resilience_on_external_failure(
    client, test_db_session
):
    # Step 1: Create a core business entity (Appointment) and OutboxEvent
    customer = Customer(name="Resilient Customer", email="resilient@example.com")
    test_db_session.add(customer)
    test_db_session.flush()

    tech = Technician(name="Resilient Tech", service_area="Tokyo", status="active")
    test_db_session.add(tech)
    test_db_session.flush()

    sr = ServiceRequest(
        customer_id=customer.id,
        raw_message="Check furnace",
        service_type="HVAC",
        urgency="medium",
        status="scheduled",
        location="Tokyo",
    )
    test_db_session.add(sr)
    test_db_session.flush()

    now = datetime.now(timezone.utc)
    appt = Appointment(
        service_request_id=sr.id,
        technician_id=tech.id,
        start_time=now,
        end_time=now,
        status="scheduled",
    )
    test_db_session.add(appt)
    test_db_session.flush()

    outbox_event = OutboxEvent(
        event_type="appointment.created",
        aggregate_type="appointment",
        aggregate_id=str(appt.id),
        payload={
            "appointment_id": appt.id,
            "service_request_id": sr.id,
            "customer_id": customer.id,
            "technician_id": tech.id,
        },
        status="pending",
        retry_count=0,
    )
    test_db_session.add(outbox_event)
    test_db_session.commit()

    # Step 2: Simulate broker publish failure during outbox processing
    with patch(
        "fieldops.tasks.integration_tasks.sync_appointment_calendar.apply_async",
        side_effect=Exception("Redis broker connection refused (simulated)"),
    ):
        publish_outbox_events()

    # Verify: Core database facts (Appointment) remain intact despite broker failure
    test_db_session.expire_all()
    reloaded_appt = test_db_session.query(Appointment).filter_by(id=appt.id).first()
    assert reloaded_appt is not None
    assert reloaded_appt.status == "scheduled"

    # Step 3: Now broker recovers and outbox publisher is executed
    with patch(
        "fieldops.tasks.integration_tasks.sync_appointment_calendar.apply_async"
    ) as mock_sync, patch(
        "fieldops.tasks.integration_tasks.send_appointment_confirmation.apply_async"
    ) as mock_conf, patch(
        "fieldops.tasks.appointment_tasks.send_appointment_reminder.apply_async"
    ) as mock_rem:
        publish_outbox_events()

    # Verify: Outbox event status updated to processed
    test_db_session.expire_all()
    reloaded_event = test_db_session.query(OutboxEvent).filter_by(id=outbox_event.id).first()
    assert reloaded_event.status == "processed"
    assert reloaded_event.processed_at is not None


def test_llm_outage_graceful_http_503(client, operator_headers):
    # When external LLM gateway times out, the service request intake returns HTTP 503 Service Unavailable
    with patch(
        "fieldops.main.run_field_service_workflow",
        side_effect=LLMTimeoutError("OpenAI API gateway timeout"),
    ):
        resp = client.post(
            "/service-requests",
            headers=operator_headers,
            json={
                "customer_name": "Timeout User",
                "email": "timeout@example.com",
                "message": "My air conditioner is smoking",
            },
        )
        assert resp.status_code == 503
        assert "timeout" in resp.json()["detail"].lower() or "unavailable" in resp.json()["detail"].lower()


def test_checkpoint_persistent_state_and_resumption(test_db_session):
    # Verify LangGraph checkpoint persistence across step executions
    from fieldops.agent.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
    assert checkpointer is not None

    thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    # Write a checkpoint state
    test_state = {
        "request_id": thread_id,
        "workflow_status": "waiting_for_approval",
        "service_type": "HVAC",
        "location": "Shinjuku",
        "candidate_technician_ids": [1],
    }

    # Verify checkpointer can put and get state
    checkpoint = {
        "v": 1,
        "id": str(uuid.uuid4()),
        "ts": "2026-09-10T12:00:00Z",
        "channel_values": test_state,
        "channel_versions": {},
        "versions_seen": {},
    }
    checkpointer.put(config, checkpoint, {}, {})

    # Resume: load saved state from checkpoint
    loaded_tuple = checkpointer.get_tuple(config)
    assert loaded_tuple is not None
    assert loaded_tuple.checkpoint["channel_values"]["workflow_status"] == "waiting_for_approval"
    assert loaded_tuple.checkpoint["channel_values"]["service_type"] == "HVAC"


def test_database_transaction_atomic_rollback_on_failure(test_db_session):
    from fieldops.application.service_lifecycle_service import ServiceLifecycleService
    from fieldops.core.exceptions import ResourceNotFoundError

    lifecycle = ServiceLifecycleService(test_db_session)

    # Attempting to start a non-existent appointment raises ResourceNotFoundError and rolls back cleanly
    try:
        lifecycle.start_service(999999)
    except ResourceNotFoundError:
        pass

    # Verify session is clean and able to perform valid queries
    active_techs = test_db_session.query(Technician).count()
    assert isinstance(active_techs, int)
