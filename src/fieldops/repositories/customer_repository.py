from sqlalchemy import select
from sqlalchemy.orm import Session

from fieldops.db.models import Customer


class CustomerRepository:
    """Repository for Customer data access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, customer_id: int) -> Customer | None:
        """Find a customer by primary key ID."""
        return self.session.get(Customer, customer_id)

    def get_by_email(self, email: str) -> Customer | None:
        """Find a customer by unique email address."""
        stmt = select(Customer).where(Customer.email == email)
        return self.session.scalar(stmt)

    def create(self, name: str, email: str, phone: str | None = None) -> Customer:
        """Create and persist a new customer."""
        customer = Customer(name=name, email=email, phone=phone)
        self.session.add(customer)
        self.session.flush()
        return customer
