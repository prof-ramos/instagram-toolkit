"""
Persistência de histórico de seguidores em disco.
Extraído de InstagramService para respeitar SRP.
"""

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

    def secure_write_json(self, file_path: Path, data: Any) -> None:
        """Escrita atômica com permissões restritas (0o600)."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(".tmp")
        try:
            temp_path.touch(exist_ok=True)
            try:
                temp_path.chmod(0o600)
            except OSError as e:
                logger.warning("Não foi possível aplicar permissões a %s: %s", temp_path, e)
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
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
        except Exception as e:
            logger.error("Falha ao carregar histórico: %s", e)
            return None

    def save(self, data: dict[str, str]) -> Path | None:
        """Salva histórico e cria backup timestampado."""
        self.config.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.config.backup_dir / f"followers_{ts}.json"
        try:
            self.secure_write_json(backup_path, data)
            self.secure_write_json(self.config.history_file, data)
            return backup_path
        except Exception as e:
            logger.error("Falha ao salvar histórico: %s", e)
            return None

    def get_growth_stats(self) -> GrowthStats | None:
        """Calcula estatísticas de crescimento a partir dos backups."""
        if not self.config.backup_dir.exists():
            return None
        backup_files = sorted(self.config.backup_dir.glob("followers_*.json"))
        if len(backup_files) < 2:
            return None
        if len(backup_files) > MAX_SNAPSHOTS:
            logger.warning(
                "Usando apenas os %d snapshots mais recentes de %d disponíveis.",
                MAX_SNAPSHOTS, len(backup_files),
            )
        snapshots_to_use = backup_files[-MAX_SNAPSHOTS:]
        snapshots: list[tuple[datetime, int]] = []
        for path in snapshots_to_use:
            try:
                with path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                ts_str = path.stem.replace("followers_", "")
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                snapshots.append((ts, len(raw)))
            except Exception:
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
