"""
Pipeline API routes.

REST endpoints for starting pipeline runs, streaming events via SSE,
submitting clarification answers, and retrieving results.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import zipfile
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from app.api.auth import require_api_key
from app.config import settings
from app.db import repositories as repo
from app.launcher import app_launcher
from app.pipeline.manager import runner_manager
from app.schemas.customer_config import CustomerConfigV2, SCHEMA_VERSION as DDC_SCHEMA_VERSION
from app.schemas.pipeline_events import EventType, PipelineState

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])

# Terminal event types that signal the SSE stream should close
_TERMINAL_EVENTS = {
    EventType.PIPELINE_COMPLETE.value,
    EventType.PIPELINE_PARTIAL.value,
    EventType.PIPELINE_FAILED.value,
}

_SSE_KEEPALIVE_TIMEOUT = 30.0  # seconds between keepalive pings


@router.post("/start", status_code=201)
async def start_pipeline(body: dict[str, Any] = Body(...)):
    """Start a new pipeline run. Returns the run_id immediately.

    Accepts a DDC CustomerConfigV2 payload (schema_version == "ddc-v1").
    """
    if body.get("schema_version") != DDC_SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Only DDC payloads are supported (schema_version must be '{DDC_SCHEMA_VERSION}').",
        )
    try:
        config = CustomerConfigV2(**body)
    except ValidationError as exc:
        logger.warning("Pipeline start rejected — validation errors: %s", exc.errors())
        raise HTTPException(status_code=422, detail=exc.errors())
    run_id = await runner_manager.start_run(config)
    return {"run_id": run_id, "status": "started"}


@router.get("/{run_id}/events")
async def stream_events(run_id: str):
    """
    Stream pipeline events via Server-Sent Events.

    Replays any existing events first, then streams new events
    from the queue until a terminal event is received.
    """
    entry = runner_manager.get_entry(run_id)

    if entry is None:
        # Check if the run exists in the DB (completed and cleaned up)
        db_run = await repo.get_run(run_id)
        if db_run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Serve historical events from DB
        async def _replay_from_db() -> AsyncGenerator[str, None]:
            events = await repo.get_events(run_id)
            for event_row in events:
                yield json.dumps(event_row, default=str)

        return EventSourceResponse(_replay_from_db())

    # Live run — replay existing events then stream from queue.
    # Events are pushed to BOTH runner.current_run.events and the queue,
    # so anything in the queue at subscription time is also in the replay.
    # Track event_ids to dedupe across the boundary.
    async def _stream() -> AsyncGenerator[str, None]:
        runner = entry.runner
        seen_ids: set[str] = set()

        # Replay events already emitted before this client connected
        if runner.current_run:
            for event in list(runner.current_run.events):
                seen_ids.add(event.event_id)
                yield event.to_sse()

                # If we already have a terminal event, no need to wait on queue
                if event.event_type.value in _TERMINAL_EVENTS:
                    return

        # Stream new events from the queue, skipping any already replayed
        while True:
            try:
                event = await asyncio.wait_for(entry.event_queue.get(), timeout=_SSE_KEEPALIVE_TIMEOUT)
                if event.event_id in seen_ids:
                    continue
                seen_ids.add(event.event_id)
                yield event.to_sse()

                if event.event_type.value in _TERMINAL_EVENTS:
                    return
            except asyncio.TimeoutError:
                # Send keepalive comment to prevent connection timeout
                yield ": keepalive\n\n"

                # Drain any events that arrived during timeout
                while not entry.event_queue.empty():
                    try:
                        event = entry.event_queue.get_nowait()
                        if event.event_id in seen_ids:
                            continue
                        seen_ids.add(event.event_id)
                        yield event.to_sse()
                        if event.event_type.value in _TERMINAL_EVENTS:
                            return
                    except asyncio.QueueEmpty:
                        break

                # Check if pipeline ended while we were waiting
                if runner.current_run and runner.current_run.state in (
                    PipelineState.COMPLETE,
                    PipelineState.FAILED,
                ):
                    return

    return EventSourceResponse(_stream())


@router.post("/{run_id}/clarification")
async def submit_clarification(run_id: str, answers: dict[str, str]):
    """Submit customer answers to clarification questions."""
    try:
        await runner_manager.resume_run(run_id, answers)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"status": "resumed"}


@router.get("/{run_id}/status")
async def get_status(run_id: str):
    """Get the current status of a pipeline run."""
    # Check in-memory runner first
    entry = runner_manager.get_entry(run_id)
    if entry and entry.runner.current_run:
        run = entry.runner.current_run
        return {
            "run_id": run.run_id,
            "state": run.state.value,
            "outcome": run.outcome,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "total_tokens": {
                "input_tokens": run.total_tokens.input_tokens,
                "output_tokens": run.total_tokens.output_tokens,
            },
            "feedback_cycles": run.feedback_cycles,
        }

    # Fall back to database
    db_run = await repo.get_run(run_id)
    if db_run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {
        "run_id": db_run["run_id"],
        "state": db_run["state"],
        "outcome": db_run["outcome"],
        "started_at": db_run["started_at"],
        "completed_at": db_run["completed_at"],
        "total_tokens": {
            "input_tokens": db_run["total_input_tokens"],
            "output_tokens": db_run["total_output_tokens"],
        },
        "feedback_cycles": json.loads(db_run["feedback_cycles_json"]),
    }


@router.get("/{run_id}/output")
async def get_output(run_id: str):
    """
    Get the generated code output for a completed run.

    Returns the manifest with file metadata.
    """
    # Check in-memory runner first
    entry = runner_manager.get_entry(run_id)
    if entry and entry.runner.current_run:
        if entry.runner.current_run.state != PipelineState.COMPLETE:
            raise HTTPException(
                status_code=409,
                detail=f"Run is in state '{entry.runner.current_run.state.value}', not complete",
            )
    else:
        # Check DB
        db_run = await repo.get_run(run_id)
        if db_run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        if db_run["state"] != PipelineState.COMPLETE.value:
            raise HTTPException(
                status_code=409,
                detail=f"Run is in state '{db_run['state']}', not complete",
            )

    # Read manifest from disk
    manifest_path = Path(settings.output_dir) / run_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Output files not found")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail="Failed to read output manifest")
    return manifest


@router.get("/{run_id}/output/download")
async def download_output(run_id: str):
    """Stream a ZIP archive of all generated files for a completed run."""
    output_dir = Path(settings.output_dir) / run_id
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output files not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file() and file_path.name != "manifest.json":
                arcname = file_path.relative_to(output_dir)
                zf.write(file_path, arcname)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{run_id}.zip\""},
    )


# ---------------------------------------------------------------------------
# Generated-app launcher endpoints (Phase A2 of plan_open_generated_app.md).
# Single-machine demo only — fires up a Next.js subprocess locally; not safe
# for the Railway / multi-tenant deployment path.
# ---------------------------------------------------------------------------


@router.post("/{run_id}/launch")
async def launch_app(run_id: str):
    """Stop any prior generated app and launch outputs/{run_id}/.

    Fire-and-poll: returns immediately with state='installing' or
    'starting'; the actual install + start runs as a background task.
    Frontend should poll GET /launch/status until terminal.
    """
    output_dir = Path(settings.output_dir) / run_id
    if not output_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Output directory not found for run {run_id}")
    status = await app_launcher.launch(run_id)
    return status.model_dump()


@router.post("/launcher/stop")
async def stop_app():
    """Stop the currently-running generated app, if any."""
    status = await app_launcher.stop()
    return status.model_dump()


@router.get("/launcher/state")
async def launcher_state():
    """Current state of the generated-app launcher.

    NOTE: deliberately under /launcher/ (not /launch/) so this literal
    path is not shadowed by the parametric /{run_id}/status route.
    """
    return app_launcher.status().model_dump()
