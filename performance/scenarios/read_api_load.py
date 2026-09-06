"""Locust scenario: High-concurrency Read API performance testing.

Measures baseline capability of FastAPI application, health probes, and metrics scraping
without full workflow orchestration overhead.
"""

from locust import HttpUser, between, task


class ReadApiUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task(5)
    def test_health(self) -> None:
        """Liveness probe test."""
        self.client.get("/health", name="[GET] /health")

    @task(3)
    def test_ready(self) -> None:
        """Readiness probe test checking PostgreSQL and Redis."""
        self.client.get("/ready", name="[GET] /ready")

    @task(1)
    def test_metrics(self) -> None:
        """Prometheus metrics exposition endpoint."""
        self.client.get("/metrics", name="[GET] /metrics")
