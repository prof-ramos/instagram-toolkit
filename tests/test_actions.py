"""Offline regression tests for follow and unfollow batch actions."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from instagram_toolkit.actions import ActionsService


def _service(*, action_result: bool, resolved_id: int = 42) -> ActionsService:
    client = Mock()
    client.user_follow.return_value = action_result
    client.user_unfollow.return_value = action_result
    relations = Mock()
    relations.resolve_user_id.return_value = resolved_id
    return ActionsService(client, Mock(), relations, Mock())


@pytest.mark.parametrize("method_name", ["auto_follow_back", "mass_unfollow"])
def test_rejected_batch_action_is_failure_without_cache_invalidation(
    method_name: str,
) -> None:
    service = _service(action_result=False)

    count, success, failure = getattr(service, method_name)(["alice"], {"alice": 7})

    assert count == 0
    assert success == []
    assert failure == ["alice (ação recusada pela API)"]
    service.cache.invalidate_relations.assert_not_called()


@pytest.mark.parametrize("method_name", ["auto_follow_back", "mass_unfollow"])
def test_batch_action_resolves_user_id_missing_from_map(method_name: str) -> None:
    service = _service(action_result=True, resolved_id=91)

    count, success, failure = getattr(service, method_name)(["alice"], {})

    assert (count, success, failure) == (1, ["alice"], [])
    service.relations.resolve_user_id.assert_called_once_with("alice")
    service.cache.invalidate_relations.assert_called_once_with()
