"""Unit tests for RelationsCache (offline, no Instagram network)."""

from __future__ import annotations

import time

import pytest

from instagram_toolkit.cache import RelationsCache
from instagram_toolkit.models import UserRecord


def _user(pk: int, username: str) -> UserRecord:
    return UserRecord(
        pk=pk,
        username=username,
        full_name=username.title(),
        is_private=False,
        is_verified=False,
    )


@pytest.fixture
def sample_map() -> dict[int, UserRecord]:
    return {
        1: _user(1, "alice"),
        2: _user(2, "bob"),
    }


def test_ttl_expiry(sample_map: dict[int, UserRecord]) -> None:
    cache = RelationsCache(ttl=0.05, enabled=True)
    cache.set("followers", sample_map, complete=True)
    assert cache.get("followers") is not None
    time.sleep(0.06)
    assert cache.get("followers") is None
    assert cache.is_complete("followers") is False


def test_require_complete_skips_partial(sample_map: dict[int, UserRecord]) -> None:
    cache = RelationsCache(ttl=60.0)
    cache.set("followers", sample_map, complete=False, fetch_amount=50)
    assert cache.get("followers") is not None
    assert cache.get("followers", require_complete=True) is None
    assert cache.is_complete("followers") is False


def test_partial_set_does_not_satisfy_complete_get(
    sample_map: dict[int, UserRecord],
) -> None:
    cache = RelationsCache(ttl=60.0)
    cache.set("following", sample_map, complete=False, fetch_amount=10)
    # Default get may return partial; complete consumers must opt in.
    partial = cache.get("following", require_complete=False)
    complete = cache.get("following", require_complete=True)
    assert partial is not None
    assert len(partial) == 2
    assert complete is None


def test_complete_set_satisfies_require_complete(
    sample_map: dict[int, UserRecord],
) -> None:
    cache = RelationsCache(ttl=60.0)
    cache.set("followers", sample_map, complete=True, fetch_amount=0)
    got = cache.get("followers", require_complete=True)
    assert got is not None
    assert got[1].username == "alice"
    assert cache.is_complete("followers") is True


def test_refuses_demote_complete_to_partial(
    sample_map: dict[int, UserRecord],
) -> None:
    cache = RelationsCache(ttl=60.0)
    cache.set("followers", sample_map, complete=True, fetch_amount=0)
    smaller = {1: _user(1, "alice")}
    cache.set("followers", smaller, complete=False, fetch_amount=1)
    got = cache.get("followers", require_complete=True)
    assert got is not None
    assert len(got) == 2
    assert cache.is_complete("followers") is True


def test_invalidate_relations_clears_both_keys(
    sample_map: dict[int, UserRecord],
) -> None:
    cache = RelationsCache(ttl=60.0)
    cache.set("followers", sample_map, complete=True)
    cache.set("following", sample_map, complete=False, fetch_amount=5)
    cache.set("other", sample_map, complete=True)

    cache.invalidate_relations()

    assert cache.get("followers") is None
    assert cache.get("following") is None
    assert cache.get("other") is not None


def test_status_contains_full_and_partial(
    sample_map: dict[int, UserRecord],
) -> None:
    cache = RelationsCache(ttl=60.0)
    cache.set("followers", sample_map, complete=True)
    cache.set("following", {3: _user(3, "carol")}, complete=False, fetch_amount=1)

    status = cache.status()
    assert "full" in status
    assert "partial" in status
    assert "followers" in status
    assert "following" in status


def test_status_empty_and_disabled() -> None:
    empty = RelationsCache(ttl=60.0)
    assert "vazio" in empty.status().lower() or "Cache vazio" in empty.status()

    disabled = RelationsCache(ttl=60.0, enabled=False)
    disabled.set("followers", {1: _user(1, "x")}, complete=True)
    assert disabled.get("followers") is None
    assert "desabilitado" in disabled.status().lower() or "--no-cache" in disabled.status()


def test_resolve_fetch_limit_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from instagram_toolkit.config import resolve_fetch_limit

    monkeypatch.delenv("INSTAGRAM_FETCH_LIMIT", raising=False)
    assert resolve_fetch_limit() == 0

    monkeypatch.setenv("INSTAGRAM_FETCH_LIMIT", "500")
    assert resolve_fetch_limit() == 500

    monkeypatch.setenv("INSTAGRAM_FETCH_LIMIT", "0")
    assert resolve_fetch_limit() == 0

    monkeypatch.setenv("INSTAGRAM_FETCH_LIMIT", "-10")
    assert resolve_fetch_limit() == 0

    monkeypatch.setenv("INSTAGRAM_FETCH_LIMIT", "not-a-number")
    assert resolve_fetch_limit() == 0

    monkeypatch.setenv("INSTAGRAM_FETCH_LIMIT", "  ")
    assert resolve_fetch_limit() == 0
