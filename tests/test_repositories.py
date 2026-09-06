from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fieldops.db.models import Base, Customer, Technician, TechnicianSkill
from fieldops.repositories.customer_repository import CustomerRepository
from fieldops.repositories.technician_repository import TechnicianRepository
from scripts.seed import run_seed


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a fresh in-memory SQLite database session for repository testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(engine)


def test_customer_repository_get_by_email(db_session: Session) -> None:
    repo = CustomerRepository(db_session)
    repo.create(name="Alice", email="alice@example.com", phone="090-1111-2222")
    db_session.commit()

    customer = repo.get_by_email("alice@example.com")
    assert customer is not None
    assert customer.name == "Alice"
    assert customer.email == "alice@example.com"

    non_existent = repo.get_by_email("unknown@example.com")
    assert non_existent is None


def test_customer_repository_get_by_id(db_session: Session) -> None:
    repo = CustomerRepository(db_session)
    created = repo.create(name="Bob", email="bob@example.com")
    db_session.commit()

    customer = repo.get_by_id(created.id)
    assert customer is not None
    assert customer.id == created.id
    assert customer.name == "Bob"


def test_technician_repository_list_active(db_session: Session) -> None:
    repo = TechnicianRepository(db_session)
    repo.create(name="Ken Tanaka", service_area="Shinjuku", status="active")
    repo.create(name="Inactive Tech", service_area="Shinjuku", status="inactive")
    db_session.commit()

    active_techs = repo.list_active()
    assert len(active_techs) == 1
    assert active_techs[0].name == "Ken Tanaka"
    assert active_techs[0].status == "active"


def test_technician_repository_find_by_service_area(db_session: Session) -> None:
    repo = TechnicianRepository(db_session)
    repo.create(name="Ken Tanaka", service_area="Shinjuku", status="active")
    repo.create(name="Yuki Sato", service_area="Shinjuku", status="active")
    repo.create(name="Haru Suzuki", service_area="Yokohama", status="active")
    db_session.commit()

    shinjuku_techs = repo.find_by_service_area("Shinjuku")
    shinjuku_names = {t.name for t in shinjuku_techs}
    assert shinjuku_names == {"Ken Tanaka", "Yuki Sato"}

    yokohama_techs = repo.find_by_service_area("Yokohama")
    assert len(yokohama_techs) == 1
    assert yokohama_techs[0].name == "Haru Suzuki"


def test_technician_repository_skills_query(db_session: Session) -> None:
    repo = TechnicianRepository(db_session)
    tech = repo.create(name="Haru Suzuki", service_area="Yokohama", status="active")
    db_session.flush()

    skill_hvac = TechnicianSkill(technician_id=tech.id, skill="HVAC")
    skill_elec = TechnicianSkill(technician_id=tech.id, skill="Electrical")
    db_session.add_all([skill_hvac, skill_elec])
    db_session.commit()

    tech_with_skills = repo.get_by_id(tech.id, load_skills=True)
    assert tech_with_skills is not None
    skills = {s.skill for s in tech_with_skills.skills}
    assert skills == {"HVAC", "Electrical"}


def test_seed_idempotency(db_session: Session) -> None:
    # Run first seed
    run_seed(db_session)

    cust_repo = CustomerRepository(db_session)
    tech_repo = TechnicianRepository(db_session)

    assert cust_repo.get_by_email("alice@example.com") is not None
    assert cust_repo.get_by_email("bob@example.com") is not None

    shinjuku_techs = tech_repo.find_by_service_area("Shinjuku", load_skills=True)
    assert len(shinjuku_techs) == 2

    yokohama_techs = tech_repo.find_by_service_area("Yokohama", load_skills=True)
    assert len(yokohama_techs) == 1
    assert {s.skill for s in yokohama_techs[0].skills} == {"HVAC", "Electrical"}

    # Run second seed to verify idempotency (no duplicates inserted)
    run_seed(db_session)

    # Counts should remain identical
    all_active = tech_repo.list_active()
    assert len(all_active) == 3
