"""
Pure unit tests for relations-facing cache policy.

No Instagram network: only RelationsCache + resolve_fetch_limit contracts
that analysis/export/tracker paths rely on (complete vs partial snapshots).
"""

from __future__ import annotations

import pytest

from instagram_toolkit.cache import RelationsCache
from instagram_toolkit.config import resolve_fetch_limit
from instagram_toolkit.models import UserRecord


def _map(*names: str) -> dict[int, UserRecord]:
    return {
        i + 1: UserRecord(
            pk=i + 1,
            username=name,
            full_name=name,
            is_private=False,
            is_verified=False,
        )
        for i, name in enumerate(names)
    }


def test_preview_partial_must_not_poison_analysis_get() -> None:
    """Listagens limitadas (partial) não servem análises que exigem full."""
    cache = RelationsCache(ttl=120.0)
    preview = _map("a", "b", "c")
    cache.set("followers", preview, complete=False, fetch_amount=50)

    # UI/preview may use default get
    assert cache.get("followers") is not None
    # Tracker / non-followers / mutuals style consumers require complete
    assert cache.get("followers", require_complete=True) is None


def test_full_fetch_replaces_partial_and_serves_analysis() -> None:
    cache = RelationsCache(ttl=120.0)
    cache.set("followers", _map("a"), complete=False, fetch_amount=1)
    full = _map("a", "b", "c", "d")
    cache.set("followers", full, complete=True, fetch_amount=0)

    got = cache.get("followers", require_complete=True)
    assert got is not None
    assert len(got) == 4
    assert cache.is_complete("followers") is True


def test_both_relation_keys_independent_completeness() -> None:
    cache = RelationsCache(ttl=120.0)
    cache.set("followers", _map("f1"), complete=True)
    cache.set("following", _map("g1"), complete=False, fetch_amount=20)

    assert cache.get("followers", require_complete=True) is not None
    assert cache.get("following", require_complete=True) is None
    assert cache.is_complete("followers") is True
    assert cache.is_complete("following") is False


def test_invalidate_relations_forces_refetch_of_both() -> None:
    cache = RelationsCache(ttl=120.0)
    cache.set("followers", _map("f"), complete=True)
    cache.set("following", _map("g"), complete=True)
    cache.invalidate_relations()
    assert cache.get("followers", require_complete=True) is None
    assert cache.get("following", require_complete=True) is None


def test_status_marks_relation_keys_full_or_partial() -> None:
    cache = RelationsCache(ttl=120.0)
    cache.set("followers", _map("f1", "f2"), complete=True)
    cache.set("following", _map("g1"), complete=False, fetch_amount=5)
    text = cache.status()
    assert "followers" in text and "full" in text
    assert "following" in text and "partial" in text


@pytest.mark.parametrize(
    "env_value,expected",
    [
        (None, 0),
        ("", 0),
        ("250", 250),
        ("0", 0),
        ("-1", 0),
        ("abc", 0),
    ],
)
def test_fetch_limit_env_policy(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str | None,
    expected: int,
) -> None:
    if env_value is None:
        monkeypatch.delenv("INSTAGRAM_FETCH_LIMIT", raising=False)
    else:
        monkeypatch.setenv("INSTAGRAM_FETCH_LIMIT", env_value)
    assert resolve_fetch_limit() == expected
