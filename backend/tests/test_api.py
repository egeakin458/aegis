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
            mock_repo.get_events = AsyncMock(return_value=[
                {"event_id": "e1", "event_type": "pipeline_started", "message": "Started"},
                {"event_id": "e2", "event_type": "pipeline_complete", "message": "Done"},
            ])

            response = client.get("/api/pipeline/run-old/events")

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]


# ============================================================
# Health check (existing endpoint sanity)
# ============================================================

class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
