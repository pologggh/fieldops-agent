"""Locust scenario: End-to-End Service Request Intake Load Testing.

Measures full workflow orchestration, database persistence, technician matching,
and schedule availability checking using deterministic FakeLLM parser.
"""

import uuid
from locust import HttpUser, between, task

# Fixed pool of test data to avoid unbounded database growth
TEST_ACCOUNTS = [
    {"name": f"Perf User {i}", "email": f"perf_user_{i}@example.com", "phone": f"+81-90-1234-{i:04d}"}
    for i in range(1, 21)
]

TEST_MESSAGES = [
    "AC is blowing warm air in Shinjuku, need technician this afternoon urgently.",
    "Water pipe leaking under kitchen sink in Shibuya, please send plumber tomorrow morning.",
    "Electrical circuit breaker keeps tripping in Yokohama, power outlet sparks.",
    "Office router and network switch down in Minato, no internet connection.",
    "Refrigerator is not cooling properly in Roppongi, need maintenance soon.",
]


class ServiceRequestLoadUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.idx = 0

    @task
    def create_service_request(self) -> None:
        account = TEST_ACCOUNTS[self.idx % len(TEST_ACCOUNTS)]
        message = TEST_MESSAGES[self.idx % len(TEST_MESSAGES)]
        self.idx += 1

        idempotency_key = str(uuid.uuid4())
        payload = {
            "name": account["name"],
            "email": account["email"],
            "phone": account["phone"],
            "message": message,
        }
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        with self.client.post(
            "/service-requests",
            json=payload,
            headers=headers,
            name="[POST] /service-requests",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limit reached (429)")
            else:
                response.failure(f"Unexpected status: {response.status_code} - {response.text[:100]}")
