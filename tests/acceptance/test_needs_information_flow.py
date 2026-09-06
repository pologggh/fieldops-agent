"""Acceptance Test 2: Needs Information and Multi-turn Clarification Flow."""

import uuid
from fieldops.db.models import ServiceRequest


def test_needs_information_multi_turn_clarification(
    client, operator_headers, customer_alpha, test_db_session
):
    # Step 1: Customer Alpha starts conversation with incomplete info (missing location and preferred_time)
    conv_res = client.post(
        "/customer/conversations",
        headers=customer_alpha["headers"],
        json={"initial_message": "Water pipe is leaking under the kitchen floor."},
    )
    assert conv_res.status_code == 201, conv_res.text
    conv_data = conv_res.json()
    conv_id = conv_data["id"]
    assert conv_data["status"] == "active"
    assert conv_data["draft"]["is_complete"] is False
    assert "location" in conv_data["draft"]["missing_fields"]
    assert "preferred_time" in conv_data["draft"]["missing_fields"]

    # Step 2: Turn 2 - Customer supplies location
    turn2 = client.post(
        f"/customer/conversations/{conv_id}/messages",
        headers=customer_alpha["headers"],
        json={
            "content": "The apartment is located in Shibuya.",
            "client_message_id": str(uuid.uuid4()),
        },
    )
    assert turn2.status_code == 200, turn2.text
    turn2_data = turn2.json()
    assert turn2_data["draft"]["location"] == "Shibuya"
    assert "location" not in turn2_data["draft"]["missing_fields"]
    assert "preferred_time" in turn2_data["draft"]["missing_fields"]
    assert turn2_data["draft"]["is_complete"] is False

    # Step 3: Turn 3 - Customer supplies preferred time
    turn3 = client.post(
        f"/customer/conversations/{conv_id}/messages",
        headers=customer_alpha["headers"],
        json={
            "content": "Tomorrow morning works best for me.",
            "client_message_id": str(uuid.uuid4()),
        },
    )
    assert turn3.status_code == 200, turn3.text
    turn3_data = turn3.json()
    assert turn3_data["draft"]["preferred_time"].lower() == "tomorrow morning"
    assert turn3_data["draft"]["missing_fields"] == []
    assert turn3_data["draft"]["is_complete"] is True
    assert turn3_data["status"] == "awaiting_confirmation"

    # Step 4: Customer confirms the complete draft
    confirm_res = client.post(
        f"/customer/conversations/{conv_id}/confirm",
        headers=customer_alpha["headers"],
    )
    assert confirm_res.status_code in (200, 201), confirm_res.text
    sr_id = confirm_res.json()["service_request_id"]
    assert sr_id is not None

    # Step 5: Operator verifies complete ServiceRequest
    test_db_session.expire_all()
    sr = test_db_session.query(ServiceRequest).filter_by(id=sr_id).first()
    assert sr is not None
    assert sr.location == "Shibuya"
    assert sr.service_type == "Plumbing"
    assert sr.customer_id == customer_alpha["id"]
