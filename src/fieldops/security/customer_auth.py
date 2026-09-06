"""Customer authentication and security dependency module.

Enforces strict identity boundary between Customer Accounts and Internal Users.
"""

from datetime import datetime, timezone, timedelta
from typing import Any
import bcrypt
import jwt
from fastapi import Header, HTTPException, status
from fieldops.core.config import settings
from fieldops.db.models import Customer, CustomerAccount
from fieldops.db.session import SessionLocal

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM
CUSTOMER_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_customer_token(account: CustomerAccount, customer: Customer) -> str:
    """Generate JWT specifically for Customer Portal accounts."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(account.id),
        "account_type": "customer",
        "type": "customer",
        "customer_id": customer.id,
        "email": account.email,
        "name": customer.name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=CUSTOMER_TOKEN_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_customer_token(token: str) -> dict[str, Any]:
    """Decode and validate a Customer Portal JWT."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "customer" and payload.get("account_type") != "customer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token type for customer access.",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )


def get_current_customer(
    authorization: str | None = Header(None),
) -> tuple[CustomerAccount, Customer]:
    """FastAPI Dependency: Authenticate customer from Bearer JWT.

    Enforces that:
    1. Authorization header is present and valid Bearer token.
    2. Token is of account_type 'customer' (blocks internal operator tokens).
    3. Account exists in database and is_active is True.
    4. Returns verified (CustomerAccount, Customer) tuple.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )

    token = authorization.replace("Bearer ", "").strip()
    payload = decode_customer_token(token)

    account_id = payload.get("sub")
    customer_id = payload.get("customer_id")

    if not account_id or not customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid customer token claims: missing identifier.",
        )
    try:
        aid = int(account_id)
        cid = int(customer_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid customer token claims: malformed identifier.",
        )

    with SessionLocal() as session:
        account = (
            session.query(CustomerAccount)
            .filter_by(id=aid, customer_id=cid)
            .first()
        )
        if not account or not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer account not found or deactivated.",
            )

        customer = session.query(Customer).filter_by(id=account.customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer record not found.",
            )

        # Detach or preserve needed attributes
        session.expunge(account)
        session.expunge(customer)
        return account, customer
