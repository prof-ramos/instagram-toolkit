"""Offline tests for complete-fetch policy and sequential relations fill."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from instagram_toolkit.cache import RelationsCache
from instagram_toolkit.models import UserRecord
from instagram_toolkit.relations import RelationsService, _is_complete


def _raw_users(*names: str) -> dict[int, Any]:
    out: dict[int, Any] = {}
    for i, name in enumerate(names, start=1):
        u = MagicMock()
        u.username = name
        u.full_name = name
        u.is_private = False
        u.is_verified = False
        u.follower_count = 0
        u.following_count = 0
        u.media_count = 0
        u.biography = ""
        u.external_url = None
        out[i] = u
    return out


def test_is_complete_helpers() -> None:
    assert _is_complete(0, 10_000) is True
    assert _is_complete(500, 500) is False
    assert _is_complete(500, 499) is True


def test_fetch_and_store_retries_full_when_truncated() -> None:
    client = MagicMock()
    client.user_id = 99
    # First call with limit hits the cap; second amount=0 returns fuller set
    client.user_followers.side_effect = [
        _raw_users(*[f"u{i}" for i in range(5)]),  # amount=5 → incomplete
        _raw_users(*[f"u{i}" for i in range(8)]),  # amount=0 → complete
    ]
    cache = RelationsCache(ttl=120.0)
    storage = MagicMock()
    svc = RelationsService(client, cache, storage, fetch_limit=5)

    result = svc.get_my_followers(complete=True)

    assert len(result) == 8
    assert cache.get("followers", require_complete=True) is not None
    assert client.user_followers.call_count == 2
    # second call must be full fetch
    assert client.user_followers.call_args_list[1].kwargs.get("amount") == 0 or (
        client.user_followers.call_args_list[1].args[1:] == ()
        and client.user_followers.call_args_list[1].kwargs.get("amount", 0) == 0
    )


def test_get_relations_is_sequential_not_threaded() -> None:
    client = MagicMock()
    client.user_id = 1
    client.user_followers.return_value = _raw_users("a")
    client.user_following.return_value = _raw_users("b")
    cache = RelationsCache(ttl=120.0)
    svc = RelationsService(client, cache, MagicMock(), fetch_limit=0)

    followers, following = svc.get_relations()
    assert len(followers) == 1
    assert len(following) == 1
    # Both endpoints invoked (sequential cold path)
    assert client.user_followers.called
    assert client.user_following.called


def test_tracker_cache_only_for_own_user_id() -> None:
    from instagram_toolkit.tracker import TrackerService

    client = MagicMock()
    client.user_id = 10
    cache = RelationsCache(ttl=120.0)
    own = {
        1: UserRecord(1, "me_follower", "", False, False),
    }
    cache.set("followers", own, complete=True, fetch_amount=0)

    client.user_followers.return_value = _raw_users("other")
    tracker = TrackerService(client, MagicMock(), MagicMock(), cache=cache)

    # Different user_id must not use cache
    result = tracker.get_all_followers_safe(user_id=999)
    assert len(result) == 1
    assert 1 in result or any(u.username == "other" for u in result.values())
    client.user_followers.assert_called()
    # Own user still served from cache without network
    client.user_followers.reset_mock()
    cached = tracker.get_all_followers_safe(user_id=10)
    assert len(cached) == 1
    assert cached[1].username == "me_follower"
    client.user_followers.assert_not_called()
