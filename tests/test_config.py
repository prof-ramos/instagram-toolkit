"""Unit tests for Config env-var parsing helpers (offline)."""

from __future__ import annotations

import pytest

from instagram_toolkit.config import DEFAULT_TTL, Config, resolve_cache_ttl


@pytest.mark.parametrize(
    "env_value,expected",
    [
        (None, DEFAULT_TTL),
        ("", DEFAULT_TTL),
        ("120", 120.0),
        ("120.5", 120.5),
        ("0", 0.0),
        ("-10", 0.0),
        ("abc", DEFAULT_TTL),
        ("  ", DEFAULT_TTL),
        ("inf", DEFAULT_TTL),
        ("-inf", DEFAULT_TTL),
        ("nan", DEFAULT_TTL),
    ],
)
def test_resolve_cache_ttl_env_policy(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str | None,
    expected: float,
) -> None:
    if env_value is None:
        monkeypatch.delenv("INSTAGRAM_CACHE_TTL", raising=False)
    else:
        monkeypatch.setenv("INSTAGRAM_CACHE_TTL", env_value)
    assert resolve_cache_ttl() == expected


def test_config_construction_never_raises_on_invalid_cache_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTAGRAM_CACHE_TTL", "not-a-number")
    config = Config()
    assert config.cache_ttl == DEFAULT_TTL
