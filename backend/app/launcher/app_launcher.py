"""AppLauncher singleton.

Owns the lifecycle of the currently-running generated app subprocess.
Single-app-at-a-time: a new launch first stops the prior process.

Subprocess design:
- `npm install` uses asyncio.create_subprocess_exec so it doesn't block the
  event loop during the 30–60 s native compile.
- `npm run dev` uses subprocess.Popen and is NOT awaited; its PID is stashed.
- Both run with start_new_session=True so they become process-group leaders.
  Stopping uses os.killpg(getpgid(pid), SIGTERM) — plain SIGTERM to `npm`
  does NOT propagate to the `next dev` grandchild.
- "Install complete" is detected via node_modules/.package-lock.json
  (npm writes it last), not just node_modules/.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


LaunchState = Literal[
    "idle", "installing", "starting", "running", "stopping", "error"
]


class LaunchStatus(BaseModel):
    state: LaunchState = "idle"
    run_id: str | None = None
    port: int | None = None
    url: str | None = None
    pid: int | None = None
    started_at: str | None = None
    error: str | None = None


# Tunables.
_PORT_RANGE_START = 3100
_PORT_RANGE_END = 3199
_INSTALL_TIMEOUT_S = 180
_START_READY_TIMEOUT_S = 45
_STOP_SIGKILL_GRACE_S = 5
_READY_POLL_INTERVAL_S = 0.5


def _pick_free_port() -> int | None:
    """Find a free TCP port in [_PORT_RANGE_START, _PORT_RANGE_END]."""
    for port in range(_PORT_RANGE_START, _PORT_RANGE_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return None


def _node_modules_installed(app_dir: Path) -> bool:
    """npm writes .package-lock.json into node_modules last. A bare
    node_modules/ might mean a half-done install."""
    return (app_dir / "node_modules" / ".package-lock.json").exists()


def _kill_process_group(pid: int, sig: int) -> bool:
    """Send `sig` to the process group led by `pid`. Returns True if signal
    was delivered (process existed). False if process is already gone."""
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return False
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False


class AppLauncher:
    """Singleton managing one running generated app at a time."""

    def __init__(self) -> None:
        self._status = LaunchStatus()
        self._popen: subprocess.Popen | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # --- Read-only ------------------------------------------------------

    def status(self) -> LaunchStatus:
        return self._status.model_copy()

    # --- Lifecycle ------------------------------------------------------

    async def launch(self, run_id: str) -> LaunchStatus:
        """Stop any prior app, then start the one at outputs/{run_id}/.
        Returns the status snapshot immediately after kicking off the
        background task. Frontend should poll /launch/status."""
        async with self._lock:
            app_dir = Path(settings.output_dir) / run_id
            if not app_dir.is_dir():
                self._status = LaunchStatus(
                    state="error",
                    run_id=run_id,
                    error=f"Output directory not found: outputs/{run_id}",
                )
                return self.status()

            # Stop prior synchronously so we don't compete for ports.
            if self._popen is not None or self._status.state not in ("idle", "error"):
                await self._stop_locked()

            initial_state: LaunchState = (
                "starting" if _node_modules_installed(app_dir) else "installing"
            )
            self._status = LaunchStatus(
                state=initial_state,
                run_id=run_id,
                started_at=datetime.now(timezone.utc).isoformat(),
            )

            # Cancel any prior background task (defensive).
            if self._task and not self._task.done():
                self._task.cancel()
            self._task = asyncio.create_task(self._run_lifecycle(run_id, app_dir))

            return self.status()

    async def stop(self) -> LaunchStatus:
        async with self._lock:
            await self._stop_locked()
            return self.status()

    async def shutdown(self) -> None:
        """Called on FastAPI lifespan close. Best-effort cleanup."""
        try:
            await self.stop()
        except Exception:
            logger.exception("AppLauncher shutdown error (ignored)")

    # --- Internals ------------------------------------------------------

    async def _stop_locked(self) -> None:
        """Caller must hold self._lock."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

        if self._popen is not None and self._popen.poll() is None:
            self._status = self._status.model_copy(update={"state": "stopping"})
            pid = self._popen.pid
            sent = _kill_process_group(pid, signal.SIGTERM)
            if sent:
                deadline = time.monotonic() + _STOP_SIGKILL_GRACE_S
                while time.monotonic() < deadline:
                    if self._popen.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
                if self._popen.poll() is None:
                    _kill_process_group(pid, signal.SIGKILL)
                    try:
                        self._popen.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        logger.warning("Process %d survived SIGKILL grace", pid)
        self._popen = None
        self._status = LaunchStatus(state="idle")

    async def _run_lifecycle(self, run_id: str, app_dir: Path) -> None:
        """Background task: install (if needed) → start → ready or error."""
        try:
            log_path = app_dir / ".aegis-launcher.log"
            log_fh = open(log_path, "ab")
            try:
                if not _node_modules_installed(app_dir):
                    ok = await self._npm_install(app_dir, log_fh)
                    if not ok:
                        return  # _set_error already called

                port = _pick_free_port()
                if port is None:
                    self._set_error(
                        f"No free port in {_PORT_RANGE_START}..{_PORT_RANGE_END}"
                    )
                    return

                self._status = self._status.model_copy(
                    update={"state": "starting", "port": port}
                )

                proc = subprocess.Popen(
                    ["npm", "run", "dev", "--", "-p", str(port)],
                    cwd=str(app_dir),
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                self._popen = proc

                ready = await self._wait_for_ready(port)
                if not ready:
                    self._set_error(
                        f"Generated app didn't respond on port {port} within "
                        f"{_START_READY_TIMEOUT_S} s. See {log_path}."
                    )
                    return

                self._status = self._status.model_copy(
                    update={
                        "state": "running",
                        "port": port,
                        "url": f"http://localhost:{port}",
                        "pid": proc.pid,
                    }
                )
            finally:
                try:
                    log_fh.close()
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Launch lifecycle failed")
            self._set_error(f"Unexpected launcher error: {e}")

    async def _npm_install(self, app_dir: Path, log_fh) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "npm", "install",
            cwd=str(app_dir),
            stdout=log_fh,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            rc = await asyncio.wait_for(proc.wait(), timeout=_INSTALL_TIMEOUT_S)
        except asyncio.TimeoutError:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._set_error(
                f"npm install timed out after {_INSTALL_TIMEOUT_S} s. "
                f"Check {app_dir}/.aegis-launcher.log."
            )
            return False

        if rc != 0:
            self._set_error(
                f"npm install failed with exit {rc}. "
                f"Check {app_dir}/.aegis-launcher.log."
            )
            return False
        return True

    async def _wait_for_ready(self, port: int) -> bool:
        url = f"http://localhost:{port}/"
        deadline = time.monotonic() + _START_READY_TIMEOUT_S
        async with httpx.AsyncClient(timeout=2.0) as client:
            while time.monotonic() < deadline:
                if self._popen is not None and self._popen.poll() is not None:
                    return False  # child died
                try:
                    r = await client.get(url)
                    if r.status_code < 500:
                        return True
                except (httpx.HTTPError, OSError):
                    pass
                await asyncio.sleep(_READY_POLL_INTERVAL_S)
        return False

    def _set_error(self, msg: str) -> None:
        self._status = self._status.model_copy(
            update={"state": "error", "error": msg}
        )


app_launcher = AppLauncher()
