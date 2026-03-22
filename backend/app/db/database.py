"""
Async SQLite database connection management.

Handles connection lifecycle and schema initialization.
Uses aiosqlite for async operations with Python's built-in sqlite3.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

_connection: aiosqlite.Connection | None = None

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    state TEXT NOT NULL DEFAULT 'intake',
    outcome TEXT,
    customer_config_json TEXT NOT NULL,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    feedback_cycles_json TEXT DEFAULT '{"code_revisions":0,"design_revisions":0}'
);

CREATE TABLE IF NOT EXISTS pipeline_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT DEFAULT '{}',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    duration_ms INTEGER,
    pipeline_state TEXT,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_events_run_id ON pipeline_events(run_id);
"""


async def init_db(db_path: str | None = None) -> None:
    """Initialize the database: open connection and create tables."""
    global _connection
    path = db_path or settings.database_path
    logger.info("Initializing database at %s", path)
    _connection = await aiosqlite.connect(path)
    _connection.row_factory = aiosqlite.Row
    await _connection.executescript(SCHEMA_SQL)
    await _connection.commit()


async def get_connection() -> aiosqlite.Connection:
    """Get the active database connection."""
    if _connection is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _connection


async def close_db() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
        logger.info("Database connection closed.")
