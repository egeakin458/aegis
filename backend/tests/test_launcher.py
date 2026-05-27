"""
Tests for the generated-app launcher.

Mocks subprocess so no real `npm install` runs in CI.
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import sys
from app.launcher.app_launcher import AppLauncher, _node_modules_installed
from app.main import app

# The package __init__.py re-exports the `app_launcher` SINGLETON with the
# same name as this submodule. So `app.launcher.app_launcher` (attribute
# lookup) returns the singleton; the actual module object is only
# reachable via sys.modules.
launcher_mod = sys.modules["app.launcher.app_launcher"]


@pytest.fixture(autouse=True)
def _disable_auth_and_db():
    """Match test_api.py — disable auth + db init for these tests."""
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


# ---------------------------------------------------------------------------
# Unit tests for AppLauncher (in-memory, mocked subprocess).
# ---------------------------------------------------------------------------


def test_status_is_idle_initially():
    launcher = AppLauncher()
    s = launcher.status()
    assert s.state == "idle"
    assert s.pid is None
    assert s.url is None


@pytest.mark.asyncio
async def test_launch_unknown_run_id_returns_error_state(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher_mod.settings, "output_dir", str(tmp_path))
    launcher = AppLauncher()
    s = await launcher.launch("does-not-exist")
    assert s.state == "error"
    assert s.run_id == "does-not-exist"
    assert s.error and "not found" in s.error.lower()


@pytest.mark.asyncio
async def test_launch_kicks_off_background_task_for_valid_run(tmp_path, monkeypatch):
    """A valid output dir should transition to installing/starting and spawn a task."""
    run_dir = tmp_path / "run-abc"
    run_dir.mkdir()
    monkeypatch.setattr(launcher_mod.settings, "output_dir", str(tmp_path))

    launcher = AppLauncher()

    # Stub the lifecycle so it does nothing (we just want to verify launch kicks off).
    async def _noop(*a, **kw):
        return None
    launcher._run_lifecycle = _noop  # type: ignore[assignment]

    s = await launcher.launch("run-abc")
    # node_modules absent → initial state is "installing".
    assert s.state == "installing"
    assert s.run_id == "run-abc"
    assert s.started_at is not None
    # Background task was created.
    assert launcher._task is not None


@pytest.mark.asyncio
async def test_launch_initial_state_is_starting_when_install_marker_present(
    tmp_path, monkeypatch
):
    run_dir = tmp_path / "run-cached"
    (run_dir / "node_modules").mkdir(parents=True)
    (run_dir / "node_modules" / ".package-lock.json").write_text("{}")
    monkeypatch.setattr(launcher_mod.settings, "output_dir", str(tmp_path))

    launcher = AppLauncher()

    async def _noop(*a, **kw):
        return None
    launcher._run_lifecycle = _noop  # type: ignore[assignment]

    s = await launcher.launch("run-cached")
    assert s.state == "starting"


@pytest.mark.asyncio
async def test_stop_when_idle_is_noop():
    launcher = AppLauncher()
    s = await launcher.stop()
    assert s.state == "idle"


@pytest.mark.asyncio
async def test_stop_kills_process_group(monkeypatch):
    launcher = AppLauncher()
    # Pretend a child is running.
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.pid = 99999
    # poll() called: once in stop_locked initial check (alive), then in the
    # SIGTERM grace loop once (dead).
    fake_proc.poll = MagicMock(side_effect=[None, 0, 0])
    launcher._popen = fake_proc
    launcher._status = launcher._status.model_copy(update={"state": "running", "pid": 99999})

    signals_sent: list[int] = []

    def fake_killer(pid: int, sig: int) -> bool:
        signals_sent.append(sig)
        return True

    monkeypatch.setattr(launcher_mod, "_kill_process_group", fake_killer)

    s = await launcher.stop()

    assert signal.SIGTERM in signals_sent
    assert signal.SIGKILL not in signals_sent  # process died after SIGTERM
    assert s.state == "idle"
    assert launcher._popen is None


@pytest.mark.asyncio
async def test_relaunch_stops_prior(monkeypatch, tmp_path):
    """A second launch() while one is running must first stop the prior."""
    run1 = tmp_path / "run-1"
    run1.mkdir()
    run2 = tmp_path / "run-2"
    run2.mkdir()
    monkeypatch.setattr(launcher_mod.settings, "output_dir", str(tmp_path))

    launcher = AppLauncher()

    async def _noop(*a, **kw):
        return None
    launcher._run_lifecycle = _noop  # type: ignore[assignment]

    # First launch.
    await launcher.launch("run-1")
    # Simulate prior process for the second launch to stop.
    fake_proc = MagicMock(spec=subprocess.Popen)
    fake_proc.pid = 42
    fake_proc.poll = MagicMock(side_effect=[None, 0, 0])  # alive, dead-in-loop, dead-final-check
    launcher._popen = fake_proc
    launcher._status = launcher._status.model_copy(update={"state": "running", "pid": 42})

    signals_sent: list[int] = []
    def fake_killer(pid: int, sig: int) -> bool:
        signals_sent.append(sig)
        return True
    monkeypatch.setattr(launcher_mod, "_kill_process_group", fake_killer)

    s = await launcher.launch("run-2")

    # The prior process was signalled before run-2 took over.
    assert signal.SIGTERM in signals_sent
    assert s.run_id == "run-2"


def test_node_modules_installed_requires_lockfile(tmp_path):
    d = tmp_path / "app"
    (d / "node_modules").mkdir(parents=True)
    # Bare node_modules — not enough.
    assert not _node_modules_installed(d)
    (d / "node_modules" / ".package-lock.json").write_text("{}")
    assert _node_modules_installed(d)


# ---------------------------------------------------------------------------
# API integration via TestClient.
# ---------------------------------------------------------------------------


def test_get_launcher_state_endpoint(client):
    r = client.get("/api/pipeline/launcher/state")
    assert r.status_code == 200
    data = r.json()
    assert data["state"] == "idle"


def test_stop_endpoint_when_idle_is_idempotent(client):
    r = client.post("/api/pipeline/launcher/stop")
    assert r.status_code == 200
    assert r.json()["state"] == "idle"


def test_launch_endpoint_404_on_unknown_run_id(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.api.routes.settings.output_dir", str(tmp_path))
    r = client.post("/api/pipeline/run-does-not-exist/launch")
    assert r.status_code == 404


def test_launch_endpoint_kicks_off_for_valid_dir(client, monkeypatch, tmp_path):
    run_dir = tmp_path / "happy"
    run_dir.mkdir()
    monkeypatch.setattr("app.api.routes.settings.output_dir", str(tmp_path))
    # Stub launcher.launch to return a known status without touching subprocess.
    from app.launcher.app_launcher import LaunchStatus

    fake_status = LaunchStatus(
        state="installing", run_id="happy", started_at="2026-05-27T00:00:00+00:00"
    )
    with patch("app.api.routes.app_launcher.launch", new_callable=AsyncMock, return_value=fake_status):
        r = client.post("/api/pipeline/happy/launch")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "installing"
    assert body["run_id"] == "happy"
