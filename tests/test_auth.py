"""Unit tests for AuthService fallback chain (offline, tmp_path only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from instagrapi.exceptions import ChallengeRequired, ClientLoginRequired

from instagram_toolkit.auth import AuthService
from instagram_toolkit.config import AuthenticationError, Config
from instagram_toolkit.storage import HistoryStorage


def _config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        username=None,
        password=None,
        session_id=None,
        settings_file=tmp_path / "instagrapi.json",
        cookies_file=tmp_path / "cookies.json",
    )
    base.update(overrides)
    return Config(**base)


def _service(tmp_path: Path, **overrides) -> AuthService:
    config = _config(tmp_path, **overrides)
    storage = HistoryStorage(config)
    return AuthService(config, storage)


def test_authenticate_succeeds_via_session_id(tmp_path: Path) -> None:
    svc = _service(tmp_path, session_id="abc%3A123")
    client = MagicMock()

    assert svc.authenticate(client) is True
    client.login_by_sessionid.assert_called_once_with("abc:123")


def test_session_id_failure_falls_through_to_no_auth_error(tmp_path: Path) -> None:
    svc = _service(tmp_path, session_id="bad")
    client = MagicMock()
    client.login_by_sessionid.side_effect = ClientLoginRequired("nope")

    with pytest.raises(AuthenticationError, match="Nenhuma forma de autenticação"):
        svc.authenticate(client)


def test_load_cookies_dict_accepts_list_format(tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text(
        '[{"name": "sessionid", "value": "sid%3A1"}, {"name": "csrftoken", "value": "x"}]'
    )
    svc = _service(tmp_path, cookies_file=cookies_file)

    assert svc._load_cookies_dict() == {"sessionid": "sid%3A1", "csrftoken": "x"}


def test_load_cookies_dict_accepts_plain_dict_format(tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text('{"sessionid": "sid123"}')
    svc = _service(tmp_path, cookies_file=cookies_file)

    assert svc._load_cookies_dict() == {"sessionid": "sid123"}


def test_try_cookies_missing_sessionid_key_returns_false(tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text('{"csrftoken": "x"}')
    svc = _service(tmp_path, cookies_file=cookies_file)
    client = MagicMock()

    assert svc._try_cookies(client) is False
    client.login_by_sessionid.assert_not_called()


def test_try_saved_session_success(tmp_path: Path) -> None:
    settings_file = tmp_path / "instagrapi.json"
    settings_file.write_text("{}")
    svc = _service(tmp_path, settings_file=settings_file)
    client = MagicMock()

    assert svc._try_saved_session(client) is True
    client.load_settings.assert_called_once_with(str(settings_file))
    client.get_timeline_feed.assert_called_once()


def test_try_saved_session_expired_returns_false(tmp_path: Path) -> None:
    settings_file = tmp_path / "instagrapi.json"
    settings_file.write_text("{}")
    svc = _service(tmp_path, settings_file=settings_file)
    client = MagicMock()
    client.get_timeline_feed.side_effect = ChallengeRequired("expired")

    assert svc._try_saved_session(client) is False


def test_try_credentials_success_persists_settings(tmp_path: Path) -> None:
    settings_file = tmp_path / "instagrapi.json"
    svc = _service(tmp_path, username="u", password="p", settings_file=settings_file)
    client = MagicMock()
    client.get_settings.return_value = {"cookies": {}}

    assert svc._try_credentials(client) is True
    client.login.assert_called_once_with("u", "p")
    assert settings_file.exists()


def test_try_credentials_challenge_required_raises_authentication_error(
    tmp_path: Path,
) -> None:
    svc = _service(tmp_path, username="u", password="p")
    client = MagicMock()
    client.login.side_effect = ChallengeRequired("challenge")

    with pytest.raises(AuthenticationError, match="Desafio de segurança"):
        svc._try_credentials(client)
