"""
Persistência de histórico de seguidores em disco.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config, MAX_SNAPSHOTS
from .models import GrowthStats

logger = logging.getLogger(__name__)


class HistoryStorage:
    """Lê, grava e gerencia backups do histórico de seguidores em disco."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def secure_write_json(
        self,
        file_path: Path,
        data: Any,
        *,
        pretty: bool = False,
    ) -> None:
        """Escrita atômica com permissões restritas (0o600)."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        try:
            temp_path.touch(exist_ok=True)
            try:
                temp_path.chmod(0o600)
            except OSError as e:
                logger.warning("Não foi possível aplicar permissões a %s: %s", temp_path, e)
            with temp_path.open("w", encoding="utf-8") as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            temp_path.replace(file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load(self) -> dict[str, str] | None:
        """Carrega histórico do arquivo principal. Retorna None se inexistente."""
        if not self.config.history_file.exists():
            return None
        try:
            with self.config.history_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.error("Falha ao carregar histórico: %s", e)
            return None

    def save(self, data: dict[str, str]) -> Path | None:
        """Salva histórico, cria backup timestampado e rotaciona snapshots."""
        self.config.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.config.backup_dir / f"followers_{ts}.json"
        meta_path = self.config.backup_dir / f"followers_{ts}.meta.json"
        try:
            self.secure_write_json(backup_path, data)
            self.secure_write_json(
                meta_path,
                {
                    "count": len(data),
                    "timestamp": ts,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.secure_write_json(self.config.history_file, data)
            self._rotate_backups()
            return backup_path
        except OSError as e:
            logger.error("Falha ao salvar histórico: %s", e)
            return None

    def get_growth_stats(self) -> GrowthStats | None:
        """Calcula estatísticas de crescimento a partir dos backups/meta."""
        if not self.config.backup_dir.exists():
            return None
        backup_files = sorted(self.config.backup_dir.glob("followers_*.json"))
        # Ignora sidecars .meta.json (glob followers_*.json pode pegar só data files
        # se meta for followers_*.meta.json — padrão atual evita colisão).
        data_files = [p for p in backup_files if not p.name.endswith(".meta.json")]
        if len(data_files) < 2:
            return None
        if len(data_files) > MAX_SNAPSHOTS:
            logger.warning(
                "Usando apenas os %d snapshots mais recentes de %d disponíveis.",
                MAX_SNAPSHOTS,
                len(data_files),
            )
        snapshots_to_use = data_files[-MAX_SNAPSHOTS:]
        snapshots: list[tuple[datetime, int]] = []
        for path in snapshots_to_use:
            try:
                count = self._snapshot_count(path)
                ts_str = path.stem.replace("followers_", "")
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(
                    tzinfo=timezone.utc
                )
                snapshots.append((ts, count))
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                continue
        if len(snapshots) < 2:
            return None
        snapshots.sort(key=lambda x: x[0])
        start_date, start_count = snapshots[0]
        end_date, end_count = snapshots[-1]
        days = max((end_date - start_date).days, 1)
        change = end_count - start_count
        return {
            "period_days": days,
            "start_count": start_count,
            "end_count": end_count,
            "change": change,
            "daily_average": change / days,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }

    def _snapshot_count(self, backup_path: Path) -> int:
        """Prefere sidecar .meta.json; fallback para len do JSON completo."""
        # followers_TS.json -> followers_TS.meta.json
        meta = backup_path.parent / f"{backup_path.stem}.meta.json"
        if meta.exists():
            with meta.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict) and "count" in payload:
                return int(payload["count"])
        with backup_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return len(raw) if isinstance(raw, dict) else 0

    def _rotate_backups(self) -> None:
        """Mantém no máximo MAX_SNAPSHOTS backups de dados (+ metas associadas)."""
        data_files = sorted(
            p
            for p in self.config.backup_dir.glob("followers_*.json")
            if not p.name.endswith(".meta.json")
        )
        excess = len(data_files) - MAX_SNAPSHOTS
        if excess <= 0:
            return
        for path in data_files[:excess]:
            meta = path.parent / f"{path.stem}.meta.json"
            try:
                path.unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                logger.info("🗑️  Backup antigo removido: %s", path.name)
            except OSError as e:
                logger.warning("Falha ao remover backup %s: %s", path, e)
