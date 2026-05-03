"""
Database repository functions for pipeline runs and events.

Provides async CRUD operations backed by SQLite via aiosqlite.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.customer_config import CustomerConfigV2
from app.schemas.pipeline_events import PipelineEvent, PipelineRun

from .database import get_connection


async def save_run(run: PipelineRun, customer_config: CustomerConfigV2) -> None:
    """Insert a new pipeline run record."""
    conn = await get_connection()
    await conn.execute(
        """
        INSERT INTO pipeline_runs
            (run_id, started_at, state, outcome, customer_config_json,
             total_input_tokens, total_output_tokens, feedback_cycles_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.run_id,
            run.started_at.isoformat(),
            run.state.value,
            run.outcome,
            customer_config.model_dump_json(),
            run.total_tokens.input_tokens,
            run.total_tokens.output_tokens,
            json.dumps(run.feedback_cycles),
        ),
    )
    await conn.commit()


async def update_run(run: PipelineRun) -> None:
    """Update an existing pipeline run record."""
    conn = await get_connection()
    await conn.execute(
        """
        UPDATE pipeline_runs
        SET state = ?,
            completed_at = ?,
            outcome = ?,
            total_input_tokens = ?,
            total_output_tokens = ?,
            feedback_cycles_json = ?
        WHERE run_id = ?
        """,
        (
            run.state.value,
            run.completed_at.isoformat() if run.completed_at else None,
            run.outcome,
            run.total_tokens.input_tokens,
            run.total_tokens.output_tokens,
            json.dumps(run.feedback_cycles),
            run.run_id,
        ),
    )
    await conn.commit()


async def get_run(run_id: str) -> dict[str, Any] | None:
    """Retrieve a pipeline run by ID. Returns dict or None."""
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def save_event(event: PipelineEvent) -> None:
    """Insert a pipeline event record."""
    conn = await get_connection()
    await conn.execute(
        """
        INSERT INTO pipeline_events
            (event_id, run_id, timestamp, agent, event_type, message,
             data_json, input_tokens, output_tokens, duration_ms, pipeline_state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            event.run_id,
            event.timestamp.isoformat(),
            event.agent.value,
            event.event_type.value,
            event.message,
            json.dumps(event.data),
            event.tokens_used.input_tokens if event.tokens_used else 0,
            event.tokens_used.output_tokens if event.tokens_used else 0,
            event.duration_ms,
            event.pipeline_state.value if event.pipeline_state else None,
        ),
    )
    await conn.commit()


async def get_events(run_id: str) -> list[dict[str, Any]]:
    """Retrieve all events for a pipeline run, ordered by timestamp."""
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT * FROM pipeline_events WHERE run_id = ? ORDER BY timestamp",
        (run_id,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
