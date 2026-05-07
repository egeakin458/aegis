"""
API key authentication dependency for /api/pipeline routes.

Contract:
- If settings.api_key == "", authentication is disabled (dev mode).
- Otherwise, requests must include `Authorization: Bearer <api_key>`.

SSE note: this is a header-only dependency. The frontend uses
@microsoft/fetch-event-source (not native EventSource), which supports custom
headers, so a `?token=` query-string fallback is intentionally NOT provided —
query-string tokens leak into logs, browser history, and Referer headers.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(authorization: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency that enforces a Bearer token matching settings.api_key.

    Returns None on success; raises HTTPException(401) on failure.
    Disabled when settings.api_key is the empty string.
    """
    expected = settings.api_key
    if not expected:
        # Auth disabled — dev mode.
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    provided = authorization[len("Bearer "):].strip()
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
