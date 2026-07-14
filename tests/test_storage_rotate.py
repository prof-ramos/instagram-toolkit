"""Unit tests for HistoryStorage backup rotation (offline, tmp_path only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from instagram_toolkit.config import MAX_SNAPSHOTS, Config
from instagram_toolkit.storage import HistoryStorage


def _storage(tmp_path: Path) -> HistoryStorage:
    config = Config(
        history_file=tmp_path / "followers_history.json",
        backup_dir=tmp_path / "history_backups",
    )
    return HistoryStorage(config)


def _seed_backups(storage: HistoryStorage, count: int) -> list[Path]:
    """Create timestamped data (+ meta) backups without going through save()."""
    storage.config.backup_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(count):
        ts = f"20260101_{i:06d}"
        data_path = storage.config.backup_dir / f"followers_{ts}.json"
        meta_path = storage.config.backup_dir / f"followers_{ts}.meta.json"
        payload = {str(j): f"user{j}" for j in range(i + 1)}
        storage.secure_write_json(data_path, payload)
        storage.secure_write_json(
            meta_path,
            {"count": len(payload), "timestamp": ts},
        )
        paths.append(data_path)
    return paths


def test_rotate_backups_removes_oldest_when_over_max(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    created = _seed_backups(storage, MAX_SNAPSHOTS + 3)

    storage._rotate_backups()

    remaining = sorted(
        p
        for p in storage.config.backup_dir.glob("followers_*.json")
        if not p.name.endswith(".meta.json")
    )
    assert len(remaining) == MAX_SNAPSHOTS
    # Oldest excess should be gone
    for old in created[:3]:
        assert not old.exists()
        meta = old.parent / f"{old.stem}.meta.json"
        assert not meta.exists()
    # Newest MAX_SNAPSHOTS kept
    for kept in created[3:]:
        assert kept.exists()


def test_rotate_backups_noop_when_at_or_under_max(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    created = _seed_backups(storage, MAX_SNAPSHOTS)

    storage._rotate_backups()

    remaining = [
        p
        for p in storage.config.backup_dir.glob("followers_*.json")
        if not p.name.endswith(".meta.json")
    ]
    assert len(remaining) == MAX_SNAPSHOTS
    assert all(p.exists() for p in created)


def test_save_writes_history_backup_meta_and_rotates(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    # Pre-fill to force rotation on next saves past the cap
    _seed_backups(storage, MAX_SNAPSHOTS)

    data = {"101": "alice", "102": "bob"}
    backup_path = storage.save(data)

    assert backup_path is not None
    assert backup_path.exists()
    assert storage.config.history_file.exists()
    meta = backup_path.parent / f"{backup_path.stem}.meta.json"
    assert meta.exists()

    data_files = [
        p
        for p in storage.config.backup_dir.glob("followers_*.json")
        if not p.name.endswith(".meta.json")
    ]
    assert len(data_files) == MAX_SNAPSHOTS

    loaded = storage.load()
    assert loaded == data


def test_save_multiple_times_never_exceeds_max_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Distinct second timestamps so each save creates a unique backup file."""
    from datetime import datetime, timedelta, timezone, tzinfo

    import instagram_toolkit.storage as storage_mod

    storage = _storage(tmp_path)
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    tick = {"i": 0}

    def fake_now(tz: tzinfo | None = None) -> datetime:
        current = base + timedelta(seconds=tick["i"])
        tick["i"] += 1
        if tz is not None:
            return current.astimezone(tz) if current.tzinfo else current.replace(tzinfo=tz)
        return current

    monkeypatch.setattr(storage_mod, "datetime", type("DT", (), {"now": staticmethod(fake_now)})())

    for i in range(MAX_SNAPSHOTS + 5):
        result = storage.save({str(i): f"u{i}"})
        assert result is not None

    data_files = [
        p
        for p in storage.config.backup_dir.glob("followers_*.json")
        if not p.name.endswith(".meta.json")
    ]
    meta_files = list(storage.config.backup_dir.glob("followers_*.meta.json"))
    assert len(data_files) == MAX_SNAPSHOTS
    assert len(meta_files) == MAX_SNAPSHOTS
