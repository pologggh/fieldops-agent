"""Admin and internal authentication & RBAC security enforcement module.

Ensures strict access control:
- Authenticates internal users (Admin, Operator, Viewer) against database records.
- Enforces role-based permissions (RBAC) across administrative and operational endpoints.
- Rejects expired, invalid, tampered, or cross-boundary (customer) tokens.
- Eliminates all hardcoded test tokens, virtual accounts, and plaintext password fallbacks.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional
import bcrypt
from fastapi import Depends, Header, HTTPException, status
import jwt

from fieldops.core.config import settings
from fieldops.db.models import InternalUser
from fieldops.db.session import SessionLocal

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash. Never fall back to plaintext equality."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Create a signed JWT access token for internal users."""
    to_encode = data.copy()
    if "type" not in to_encode:
        to_encode["type"] = "access"
    expire = datetime.now(timezone.utc) + (
        timedelta(seconds=expires_delta)
        if expires_delta
        else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def get_current_internal_user(
    authorization: str | None = Header(None),
) -> InternalUser:
    """FastAPI Dependency: Authenticate any active internal user (Admin, Operator, Viewer) from Bearer JWT.

    Validates:
    - Authorization header is present and format is 'Bearer <token>' -> 401
    - Token signature and expiration with configured JWT_SECRET -> 401
    - Token boundary: customer tokens cannot access internal endpoints -> 403
    - Required claims: valid user_id/sub -> 401
    - Account exists in database -> 401
    - Account is active -> 403
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing token.",
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate authentication credentials.",
        )

    # Hard token boundary: reject customer tokens immediately with 403 Forbidden
    if payload.get("type") == "customer" or payload.get("account_type") == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer tokens cannot access internal operator endpoints.",
        )

    # Extract user ID
    user_id_raw = payload.get("user_id") or payload.get("sub")
    if not user_id_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token claims: missing user identifier.",
        )

    try:
        user_id = int(user_id_raw)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token claims: malformed user identifier.",
        )

    with SessionLocal() as session:
        user = session.query(InternalUser).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account associated with token was not found.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account has been deactivated.",
            )

        session.expunge(user)
        return user


def require_roles(allowed_roles: list[str]) -> Callable[[InternalUser], InternalUser]:
    """Dependency factory enforcing that current authenticated user holds one of the required roles."""
    def role_checker(
        user: InternalUser = Depends(get_current_internal_user),
    ) -> InternalUser:
        if user.role not in allowed_roles:
            if "admin" in allowed_roles and len(allowed_roles) == 1:
                detail = f"Admin privileges required: current user role '{user.role}' does not have administrative access."
            else:
                detail = f"Operation not permitted. Required role: {', '.join(allowed_roles)}. Your role is '{user.role}'."
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        return user

    return role_checker


# Role-specific FastAPI dependencies
get_current_admin = require_roles(["admin"])
get_current_operator = require_roles(["operator"])
get_current_operator_or_admin = require_roles(["operator", "admin"])
get_current_internal_reader = require_roles(["viewer", "operator", "admin"])
