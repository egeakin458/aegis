"""Generated-app launcher.

Spawns a generated Next.js app under `backend/outputs/{run_id}/` as a
subprocess, exposes status to the API, and ensures only one app runs at a
time. Designed for the demo / single-machine deployment; not for
multi-tenant production.

Public surface:
    from app.launcher import app_launcher, LaunchStatus, LaunchState
"""

from .app_launcher import LaunchState, LaunchStatus, app_launcher

__all__ = ["app_launcher", "LaunchState", "LaunchStatus"]
