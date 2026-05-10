"""
Regression tests for config defaults that have a real impact on E2E reliability.

History note: api_timeout was originally 120s, but a smoke run on
benchmark_02_todo_ddc (a 'simple' DDC) measured the Developer agent's
single LLM call at 111.5s — only 7% headroom. Slightly slower API days,
marginally larger DDCs, or one validation retry would push past the
120s cap, triggering APITimeoutError loops via max_llm_retries.

This test pins a minimum that gives realistic headroom.
"""

from __future__ import annotations

from app.config import Settings


class TestApiTimeoutMinimum:
    """The Anthropic SDK per-request timeout must be large enough to cover
    a worst-case Developer agent generation without flapping.

    Field measurement (2026-05-10, benchmark_02_todo_ddc): Developer call
    completed in 111.5s. We require at least 3x that as a floor so headroom
    survives slower API days, larger DDCs, and one validation retry.
    """

    def test_api_timeout_default_provides_3x_headroom_over_observed_developer_call(self):
        observed_developer_seconds = 112  # rounded up from the 111.5s smoke measurement
        settings = Settings()
        assert settings.api_timeout >= observed_developer_seconds * 3, (
            f"api_timeout={settings.api_timeout}s gives less than 3x headroom over "
            f"the observed Developer call ({observed_developer_seconds}s). "
            f"At <3x, normal-day variance can timeout the Developer agent."
        )
