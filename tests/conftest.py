from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fieldops.db.session import Base
import fieldops.db.models  # Ensures all models are registered in Base.metadata
from fieldops.tasks.celery_app import celery_app

# Configure Celery for unit/integration tests: eager execution avoids hanging when Redis broker is offline
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)

from fieldops.core.config import settings
settings.RATE_LIMIT_ENABLED = False



@pytest.fixture(autouse=True)
def test_db_session() -> Generator[Session, None, None]:
    """Provide a shared in-memory SQLite database and patch SessionLocal across application tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    with patch("fieldops.application.persistence.SessionLocal", TestingSessionLocal), \
         patch("fieldops.agent.nodes.match_technicians.SessionLocal", TestingSessionLocal), \
         patch("fieldops.agent.nodes.check_schedule.SessionLocal", TestingSessionLocal), \
         patch("fieldops.agent.nodes.build_appointment_proposal.SessionLocal", TestingSessionLocal), \
         patch("fieldops.agent.nodes.finalize_appointment.SessionLocal", TestingSessionLocal), \
         patch("fieldops.agent.nodes.handle_rejection.SessionLocal", TestingSessionLocal), \
         patch("fieldops.main.SessionLocal", TestingSessionLocal), \
         patch("fieldops.tasks.appointment_tasks.SessionLocal", TestingSessionLocal), \
         patch("fieldops.tasks.integration_tasks.SessionLocal", TestingSessionLocal), \
         patch("fieldops.tasks.outbox_tasks.SessionLocal", TestingSessionLocal), \
         patch("fieldops.intake.service.SessionLocal", TestingSessionLocal), \
         patch("fieldops.api.admin_console.SessionLocal", TestingSessionLocal), \
         patch("fieldops.security.admin_auth.SessionLocal", TestingSessionLocal), \
         patch("fieldops.api.customer_portal.SessionLocal", TestingSessionLocal), \
         patch("fieldops.api.customer_conversations.SessionLocal", TestingSessionLocal), \
         patch("fieldops.security.customer_auth.SessionLocal", TestingSessionLocal), \
         patch("fieldops.agent.subgraphs.escalation_subgraph.SessionLocal", TestingSessionLocal), \
         patch("fieldops.db.session.SessionLocal", TestingSessionLocal):
        with TestingSessionLocal() as session:
            # Seed default test users so internal endpoint calls in legacy unit tests can authenticate
            if not session.query(fieldops.db.models.InternalUser).filter_by(id=1).first():
                session.add(fieldops.db.models.InternalUser(
                    id=1,
                    email="operator@fieldops.com",
                    name="Test Operator",
                    role="operator",
                    password_hash="$2b$12$WSkG1rJfV17b6ys9u.b7NuEwqWhlvytbJFKT0GuOvyCiryd9UCou2",
                    is_active=True,
                ))
            if not session.query(fieldops.db.models.InternalUser).filter_by(id=2).first():
                session.add(fieldops.db.models.InternalUser(
                    id=2,
                    email="admin@fieldops.com",
                    name="Test Admin",
                    role="admin",
                    password_hash="$2b$12$WSkG1rJfV17b6ys9u.b7NuEwqWhlvytbJFKT0GuOvyCiryd9UCou2",
                    is_active=True,
                ))
            session.commit()
            yield session


    Base.metadata.drop_all(engine)
    engine.dispose()


from fieldops.security.admin_auth import create_access_token

TEST_OPERATOR_TOKEN = create_access_token({
    "sub": "1",
    "role": "operator",
    "email": "operator@fieldops.com",
})
TEST_ADMIN_TOKEN = create_access_token({
    "sub": "2",
    "role": "admin",
    "email": "admin@fieldops.com",
})

TEST_OPERATOR_HEADERS = {"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"}
TEST_ADMIN_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}


@pytest.fixture
def operator_token():
    return TEST_OPERATOR_TOKEN


@pytest.fixture
def operator_headers():
    return dict(TEST_OPERATOR_HEADERS)


@pytest.fixture
def admin_token():
    return TEST_ADMIN_TOKEN


@pytest.fixture
def admin_headers():
    return dict(TEST_ADMIN_HEADERS)

