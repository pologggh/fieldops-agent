import logging
import sqlite3
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver

from fieldops.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_CHECKPOINTER: BaseCheckpointSaver | None = None
_POSTGRES_POOL = None


def reset_checkpointer() -> None:
    """Reset cached checkpointer and connection pool (primarily for testing)."""
    global _DEFAULT_CHECKPOINTER, _POSTGRES_POOL
    if _POSTGRES_POOL is not None:
        try:
            _POSTGRES_POOL.close()
        except Exception as e:
            logger.warning("Error closing Postgres checkpoint pool: %s", e)
        _POSTGRES_POOL = None
    _DEFAULT_CHECKPOINTER = None


def get_checkpointer(
    db_path: str | None = None,
    backend: Literal["sqlite", "postgres"] | None = None,
) -> BaseCheckpointSaver:
    """Initialize or return the persistent checkpointer for LangGraph workflows.

    Supports:
    - Shared PostgreSQL checkpointer (PostgresSaver) for multi-replica, stateless API deployments.
    - Local SQLite checkpointer (SqliteSaver) for isolated unit tests or single-node development.

    Args:
        db_path: Optional custom path to SQLite database. If provided, forces SQLite backend.
        backend: Explicitly select 'postgres' or 'sqlite'. If None, uses settings.CHECKPOINTER_BACKEND.

    Returns:
        Configured BaseCheckpointSaver instance (PostgresSaver or SqliteSaver).
    """
    global _DEFAULT_CHECKPOINTER, _POSTGRES_POOL

    # If an explicit SQLite path is passed, always use dedicated SQLite saver
    if db_path is not None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        return saver

    chosen_backend = backend or settings.CHECKPOINTER_BACKEND

    if _DEFAULT_CHECKPOINTER is not None:
        return _DEFAULT_CHECKPOINTER

    if chosen_backend == "postgres":
        logger.info("Initializing shared PostgreSQL checkpointer with pool")
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        dsn = settings.postgres_dsn
        _POSTGRES_POOL = ConnectionPool(
            conninfo=dsn,
            max_size=settings.CHECKPOINT_POSTGRES_POOL_SIZE,
            kwargs={"autocommit": True},
        )
        saver = PostgresSaver(_POSTGRES_POOL)
        saver.setup()
        _DEFAULT_CHECKPOINTER = saver
        return _DEFAULT_CHECKPOINTER

    # Default: SQLite
    path = settings.CHECKPOINT_DB_PATH
    logger.info("Initializing persistent SQLite checkpointer at %s", path)
    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    _DEFAULT_CHECKPOINTER = saver
    return _DEFAULT_CHECKPOINTER
