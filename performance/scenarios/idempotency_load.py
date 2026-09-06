"""Locust scenario: Idempotency Concurrency and Cache-Hit Performance.

Evaluates throughput and latency of cached responses vs new creations
under identical Idempotency-Key reuse.
"""

import uuid
from locust import HttpUser, between, task

SHARED_KEYS = [f"shared-idempotency-key-{i}" for i in range(1, 11)]

PAYLOAD = {
    "name": "Idempotency Test User",
    "email": "idempotency_perf@example.com",
    "phone": "+81-90-9999-8888",
    "message": "AC repair needed in Shinjuku this afternoon",
}


class IdempotencyLoadUser(HttpUser):
    wait_time = between(0.05, 0.2)

    def on_start(self) -> None:
        self.count = 0

    @task(4)
    def test_shared_key_cache_hit(self) -> None:
        """Repeatedly request with fixed keys to measure idempotency cache-hit throughput."""
        key = SHARED_KEYS[self.count % len(SHARED_KEYS)]
        self.count += 1

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": key,
        }

        with self.client.post(
            "/service-requests",
            json=PAYLOAD,
            headers=headers,
            name="[POST] /service-requests (Idempotency Hit)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code == 409:
                # Concurrent in-flight request
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def test_fresh_key(self) -> None:
        """Send request with fresh unique key."""
        fresh_key = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": fresh_key,
        }
        self.client.post(
            "/service-requests",
            json=PAYLOAD,
            headers=headers,
            name="[POST] /service-requests (Fresh Key)",
        )
