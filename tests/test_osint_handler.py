"""Offline tests for MenuHandlers.osint_lookup (no real Instagram network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from instagram_toolkit.cli.handlers import MenuHandlers


def _handlers(client=None, rate_limiter=None) -> MenuHandlers:
    return MenuHandlers(
        relations=MagicMock(),
        actions=MagicMock(),
        tracker=MagicMock(),
        storage=MagicMock(),
        cache=MagicMock(),
        client=client or MagicMock(),
        rate_limiter=rate_limiter or MagicMock(),
    )


def test_osint_lookup_cancelled_without_confirmation(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "alice")
    h = _handlers()
    with patch("instagram_toolkit.cli.handlers._confirm", return_value=False):
        h.osint_lookup()
    # Nenhuma chamada de rede deve ocorrer sem confirmação.


def test_osint_lookup_calls_rate_limiter_and_prints_report(monkeypatch) -> None:
    inputs = iter(["alice"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    client = MagicMock()
    rate_limiter = MagicMock()
    h = _handlers(client=client, rate_limiter=rate_limiter)

    with (
        patch("instagram_toolkit.cli.handlers._confirm", return_value=True),
        patch("toutatis_integration.extract_session_id", return_value="sid123"),
        patch("toutatis_integration.osint_profile", return_value={"username": "alice"}) as m_profile,
        patch("toutatis_integration.print_osint_report") as m_report,
    ):
        h.osint_lookup()

    m_profile.assert_called_once()
    assert m_profile.call_args.kwargs["rate_limiter"] is rate_limiter
    m_report.assert_called_once_with({"username": "alice"})


def test_osint_lookup_missing_session_id_prints_error_and_skips_lookup(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "alice")
    h = _handlers()

    with (
        patch("instagram_toolkit.cli.handlers._confirm", return_value=True),
        patch("toutatis_integration.extract_session_id", return_value=None),
        patch("toutatis_integration.osint_profile") as m_profile,
    ):
        h.osint_lookup()

    m_profile.assert_not_called()
