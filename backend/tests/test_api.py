"""
Tests for API routes (app/api/routes.py).

Uses FastAPI TestClient with mocked RunnerManager to test
all 5 pipeline endpoints without real LLM calls.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.pipeline_events import (
    AgentName,
    EventType,
    PipelineEvent,
    PipelineRun,
    PipelineState,
)


@pytest.fixture(autouse=True)
def mock_db():
    """Mock database init/close and startup validation for all tests."""
    with (
        patch("app.main.init_db", new_callable=AsyncMock),
        patch("app.main.close_db", new_callable=AsyncMock),
        patch("app.main.settings"),
        patch("app.api.auth.settings") as mock_auth_settings,
    ):
        mock_auth_settings.api_key = ""
        yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ============================================================
# POST /api/pipeline/start
# ============================================================

class TestStartPipeline:
    def test_start_returns_201_with_run_id(self, client, ddc_ecommerce):
        """POST /start with a valid DDC payload returns 201 + run_id."""
        with patch("app.api.routes.runner_manager") as mock_manager:
            mock_manager.start_run = AsyncMock(return_value="run-abc-123")

            response = client.post(
                "/api/pipeline/start",
                json=ddc_ecommerce.model_dump(mode="json"),
            )

            assert response.status_code == 201
            data = response.json()
            assert data["run_id"] == "run-abc-123"
            assert data["status"] == "started"

    def test_start_without_ddc_schema_version_returns_400(self, client):
        """A payload missing schema_version=ddc-v1 must be rejected with 400."""
        response = client.post("/api/pipeline/start", json={"bad": "data"})
        assert response.status_code == 400

    def test_start_with_invalid_ddc_payload_returns_422(self, client):
        """An invalid DDC payload (schema_version set but content wrong) → 422."""
        response = client.post(
            "/api/pipeline/start",
            json={"schema_version": "ddc-v1", "bad": "data"},
        )
        assert response.status_code == 422

    def test_start_accepts_ddc_payload(self, client, ddc_ecommerce):
        """POST /start must accept a valid CustomerConfigV2 payload."""
        with patch("app.api.routes.runner_manager") as mock_manager:
            mock_manager.start_run = AsyncMock(return_value="run-ddc-001")
            payload = ddc_ecommerce.model_dump(mode="json")
            response = client.post("/api/pipeline/start", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["run_id"] == "run-ddc-001"
            assert data["status"] == "started"


# ============================================================
# POST /api/pipeline/{run_id}/clarification
# ============================================================

class TestSubmitClarification:
    def test_submit_returns_200(self, client):
        with patch("app.api.routes.runner_manager") as mock_manager:
            mock_manager.resume_run = AsyncMock()

            response = client.post(
                "/api/pipeline/run-123/clarification",
                json={"q1": "Yes", "q2": "No"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "resumed"
            mock_manager.resume_run.assert_called_once_with("run-123", {"q1": "Yes", "q2": "No"})

    def test_submit_unknown_run_returns_404(self, client):
        with patch("app.api.routes.runner_manager") as mock_manager:
            mock_manager.resume_run = AsyncMock(side_effect=KeyError("not found"))

            response = client.post(
                "/api/pipeline/run-999/clarification",
                json={"q1": "Yes"},
            )

            assert response.status_code == 404

    def test_submit_wrong_state_returns_409(self, client):
        with patch("app.api.routes.runner_manager") as mock_manager:
            mock_manager.resume_run = AsyncMock(
                side_effect=ValueError("not in CLARIFICATION state")
            )

            response = client.post(
                "/api/pipeline/run-123/clarification",
                json={"q1": "Yes"},
            )

            assert response.status_code == 409


# ============================================================
# GET /api/pipeline/{run_id}/status
# ============================================================

class TestGetStatus:
    def test_status_from_in_memory_runner(self, client):
        with patch("app.api.routes.runner_manager") as mock_manager:
            run = PipelineRun()
            run.state = PipelineState.DEVELOPMENT
            run.total_tokens.input_tokens = 5000
            run.total_tokens.output_tokens = 2000

            mock_entry = MagicMock()
            mock_entry.runner.current_run = run
            mock_manager.get_entry.return_value = mock_entry

            response = client.get(f"/api/pipeline/{run.run_id}/status")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "development"
            assert data["total_tokens"]["input_tokens"] == 5000

    def test_status_falls_back_to_db(self, client):
        with (
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value={
                "run_id": "run-db-123",
                "state": "complete",
                "outcome": "success",
                "started_at": "2026-03-22T10:00:00+00:00",
                "completed_at": "2026-03-22T10:05:00+00:00",
                "total_input_tokens": 8000,
                "total_output_tokens": 3000,
                "feedback_cycles_json": '{"code_revisions": 1, "design_revisions": 0}',
            })

            response = client.get("/api/pipeline/run-db-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "complete"
            assert data["outcome"] == "success"
            assert data["feedback_cycles"]["code_revisions"] == 1

    def test_status_unknown_run_returns_404(self, client):
        with (
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value=None)

            response = client.get("/api/pipeline/run-999/status")

            assert response.status_code == 404


# ============================================================
# GET /api/pipeline/{run_id}/output
# ============================================================

class TestGetOutput:
    def test_output_returns_manifest(self, client, tmp_path):
        with patch("app.api.routes.runner_manager") as mock_manager:
            run = PipelineRun()
            run.state = PipelineState.COMPLETE

            mock_entry = MagicMock()
            mock_entry.runner.current_run = run
            mock_manager.get_entry.return_value = mock_entry

            # Create a manifest file
            run_dir = tmp_path / run.run_id
            run_dir.mkdir()
            manifest = {"project_name": "test-project", "files": []}
            (run_dir / "manifest.json").write_text(json.dumps(manifest))

            with patch("app.api.routes.settings") as mock_settings:
                mock_settings.output_dir = str(tmp_path)
                response = client.get(f"/api/pipeline/{run.run_id}/output")

            assert response.status_code == 200
            assert response.json()["project_name"] == "test-project"

    def test_output_not_complete_returns_409(self, client):
        with patch("app.api.routes.runner_manager") as mock_manager:
            run = PipelineRun()
            run.state = PipelineState.DEVELOPMENT

            mock_entry = MagicMock()
            mock_entry.runner.current_run = run
            mock_manager.get_entry.return_value = mock_entry

            response = client.get(f"/api/pipeline/{run.run_id}/output")

            assert response.status_code == 409

    def test_output_unknown_run_returns_404(self, client):
        with (
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value=None)

            response = client.get("/api/pipeline/run-999/output")

            assert response.status_code == 404

    def test_output_from_db_not_complete_returns_409(self, client):
        with (
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value={
                "run_id": "run-123",
                "state": "failed",
            })

            response = client.get("/api/pipeline/run-123/output")

            assert response.status_code == 409

    def test_output_missing_manifest_returns_404(self, client, tmp_path):
        with patch("app.api.routes.runner_manager") as mock_manager:
            run = PipelineRun()
            run.state = PipelineState.COMPLETE

            mock_entry = MagicMock()
            mock_entry.runner.current_run = run
            mock_manager.get_entry.return_value = mock_entry

            with patch("app.api.routes.settings") as mock_settings:
                mock_settings.output_dir = str(tmp_path)
                response = client.get(f"/api/pipeline/{run.run_id}/output")

            assert response.status_code == 404


# ============================================================
# GET /api/pipeline/{run_id}/events (SSE)
# ============================================================

class TestStreamEvents:
    def test_events_unknown_run_returns_404(self, client):
        with (
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value=None)

            response = client.get("/api/pipeline/run-999/events")

            assert response.status_code == 404

    def test_events_replays_from_db_for_completed_run(self, client):
        """When run is no longer in memory, events are served from DB."""
        with (
            patch("app.api.routes.runner_manager") as mock_manager,
            patch("app.api.routes.repo") as mock_repo,
        ):
            mock_manager.get_entry.return_value = None
            mock_repo.get_run = AsyncMock(return_value={"run_id": "run-old", "state": "complete"})
            # Realistic rows: get_events does SELECT *, so every DB column is
            # present (data stored as a JSON string in data_json, tokens flat).
            mock_repo.get_events = AsyncMock(return_value=[
                {
                    "event_id": "e1", "run_id": "run-old",
                    "timestamp": "2026-06-15T19:50:46.111176+00:00",
                    "agent": "system", "event_type": "pipeline_started",
                    "message": "Started", "data_json": "{}",
                    "input_tokens": 0, "output_tokens": 0,
                    "duration_ms": None, "pipeline_state": "intake",
                },
                {
                    "event_id": "e2", "run_id": "run-old",
                    "timestamp": "2026-06-15T19:58:29.445000+00:00",
                    "agent": "system", "event_type": "pipeline_complete",
                    "message": "Done", "data_json": "{\"final\": true}",
                    "input_tokens": 1450, "output_tokens": 2146,
                    "duration_ms": 26538, "pipeline_state": "complete",
                },
            ])

            response = client.get("/api/pipeline/run-old/events")

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            # DB replay must match the live to_sse() shape the frontend parses:
            # a reshaped `data` object + nested `tokens_used`, never the raw
            # `data_json` string or flat token columns.
            assert '"data_json"' not in response.text
            assert '"data":{"final":true}' in response.text
            assert '"tokens_used":{"input_tokens":1450' in response.text


# ============================================================
# SSE event-id deduplication
# ============================================================

class TestSseDeduplication:
    """Events that fire before a client subscribes land in BOTH
    runner.current_run.events AND entry.event_queue. The SSE handler
    must yield each event_id at most once across the replay phase
    and the live-stream phase.
    """

    def test_event_ids_appear_once_when_queue_repeats_replayed_events(self, client):
        import asyncio

        e1 = PipelineEvent(
            run_id="run-sse-1",
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_STARTED,
            message="Starting...",
        )
        e2 = PipelineEvent(
            run_id="run-sse-1",
            agent=AgentName.REQUIREMENTS_ANALYST,
            event_type=EventType.AGENT_START,
            message="RA starting",
        )
        e_terminal = PipelineEvent(
            run_id="run-sse-1",
            agent=AgentName.SYSTEM,
            event_type=EventType.PIPELINE_COMPLETE,
            message="Done",
        )

        run = PipelineRun(run_id="run-sse-1")
        run.events = [e1, e2]
        run.state = PipelineState.DEVELOPMENT

        runner_mock = MagicMock()
        runner_mock.current_run = run

        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait(e1)
        queue.put_nowait(e2)
        queue.put_nowait(e_terminal)

        entry_mock = MagicMock()
        entry_mock.runner = runner_mock
        entry_mock.event_queue = queue

        with patch("app.api.routes.runner_manager") as mock_manager:
            mock_manager.get_entry.return_value = entry_mock

            response = client.get(
                "/api/pipeline/run-sse-1/events",
                headers={"Accept": "text/event-stream"},
            )
            assert response.status_code == 200

            event_ids: list[str] = []
            for line in response.text.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        try:
                            event_ids.append(json.loads(payload).get("event_id"))
                        except json.JSONDecodeError:
                            pass

            assert len(event_ids) == len(set(event_ids)), (
                f"SSE stream emitted duplicate event_ids: {event_ids}"
            )
            assert set(event_ids) == {e1.event_id, e2.event_id, e_terminal.event_id}


# ============================================================
# Health check (existing endpoint sanity)
# ============================================================

class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
