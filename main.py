#!/usr/bin/env python3
"""
Instagram Toolkit - Unificado, Refatorado, Seguro e Completo (v2.4)
"""

import os
import json
import random
import time
import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, ClientError, ClientLoginRequired

# =============================================================================
# DEFINIÇÃO DE TIPOS
# =============================================================================


class FollowerData(TypedDict):
    id: str
    username: str
    full_name: str
    is_private: bool
    is_verified: bool


class GrowthStats(TypedDict):
    period_days: int
    start_count: int
    end_count: int
    change: int
    daily_average: float
    start_date: str
    end_date: str


@dataclass
class TrackerResult:
    is_first_run: bool
    backup_path: Path
    unfollowed: set[str]
    new_followers: set[str]
    history: dict[str, str]
    current_data: dict[str, str]


# =============================================================================
# EXCEÇÕES PERSONALIZADAS
# =============================================================================


class InstagramToolkitError(Exception):
    """Exceção base para o toolkit do Instagram."""


class AuthenticationError(InstagramToolkitError):
    """Exceção para falhas de autenticação."""


class RateLimitError(InstagramToolkitError):
    """Exceção para limites de requisição excedidos."""


class UserNotFoundError(InstagramToolkitError):
    """Exceção quando um usuário não é encontrado."""


# =============================================================================
# CONSTANTES
# =============================================================================

MAX_SNAPSHOTS = 10
FETCH_LIMIT = 500
DEFAULT_TTL = 300


# =============================================================================
# CACHE EM MEMÓRIA COM TTL
# =============================================================================


@dataclass
class _CacheEntry:
    data: Any
    timestamp: float


class RelationsCache:
    """
    Cache em memória para followers/following com TTL configurável.
    Invalida automaticamente após operações de follow/unfollow.
    """

    def __init__(self, ttl: float = DEFAULT_TTL, enabled: bool = True) -> None:
        self.ttl = ttl
        self.enabled = enabled
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self.ttl:
            del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: Any) -> None:
        if not self.enabled:
            return
        self._store[key] = _CacheEntry(data=data, timestamp=time.monotonic())

    def invalidate(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    def invalidate_relations(self) -> None:
        """Invalida cache de followers e following (chamado após follow/unfollow)."""
        self.invalidate("followers", "following")

    def status(self) -> str:
        if not self.enabled:
            return "🛈 Cache desabilitado (--no-cache)"
        now = time.monotonic()
        entries = []
        for key, entry in self._store.items():
            remaining = max(0, int(self.ttl - (now - entry.timestamp)))
            entries.append(f"{key}: {remaining}s")
        if not entries:
            return "📦 Cache vazio"
        return "📊 Cache: " + " | ".join(entries)


# =============================================================================
# CONFIGURAÇÃO E SERVIÇO
# =============================================================================


@dataclass
class Config:
    username: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_USERNAME"))
    password: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_PASSWORD"))
    session_id: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_SESSION_ID"))
    settings_file: Path = field(default_factory=lambda: Path("instagrapi.json"))
    cookies_file: Path = field(default_factory=lambda: Path("cookies.json"))
    history_file: Path = field(default_factory=lambda: Path("followers_history.json"))
    backup_dir: Path = field(default_factory=lambda: Path("history_backups"))


class InstagramService:
    def __init__(self, config: Config, cache: RelationsCache) -> None:
        self.config = config
        self.cache = cache
        self.cl = Client()

    def random_delay(self, min_sec: float = 1.8, max_sec: float = 3.8) -> None:
        time.sleep(random.uniform(min_sec, max_sec))

    def authenticate(self) -> bool:
        if self.config.session_id:
            print("🔑 Tentando autenticação via Session ID...")
            try:
                self.cl.login_by_sessionid(self.config.session_id)
                print("✅ Autenticado com Session ID!")
                return True
            except Exception as e:
                print(f"⚠️  Falha no Session ID: {e}")

        if self.config.cookies_file.exists():
            print(f"🍪 Carregando cookies de {self.config.cookies_file}...")
            try:
                with self.config.cookies_file.open("r", encoding="utf-8") as f:
                    cookies_data = json.load(f)

                match cookies_data:
                    case list():
                        formatted = {
                            c["name"]: c["value"]
                            for c in cookies_data
                            if isinstance(c, dict) and "name" in c and "value" in c
                        }
                    case dict():
                        formatted = cookies_data
                    case _:
                        formatted = {}

                self.cl.set_cookies(formatted)
                self.cl.get_timeline_feed()
                print("✅ Autenticado via cookies!")
                return True
            except Exception as e:
                print(f"⚠️  Falha nos cookies: {e}")

        if self.config.settings_file.exists():
            print(f"📁 Carregando sessão salva de {self.config.settings_file}...")
            try:
                self.cl.load_settings(str(self.config.settings_file))
                self.cl.get_timeline_feed()
                print("✅ Sessão carregada do cache!")
                return True
            except Exception:
                print("⚠️  Sessão expirada.")

        if self.config.username and self.config.password:
            print("🔐 Fazendo login com usuário e senha...")
            try:
                self.cl.login(self.config.username, self.config.password)
                self._secure_write_json(
                    self.config.settings_file, self.cl.get_settings()
                )
                print("✅ Login realizado e sessão salva!")
                return True
            except ChallengeRequired:
                raise AuthenticationError(
                    "Desafio de segurança detectado. Resolva no app do Instagram."
                )
            except ClientLoginRequired:
                raise AuthenticationError("Credenciais inválidas.")
            except Exception as e:
                raise AuthenticationError(f"Erro no login: {e}") from e

        raise AuthenticationError(
            "Nenhuma forma de autenticação funcionou.\n"
            "Configure INSTAGRAM_SESSION_ID, cookies.json ou usuário/senha."
        )

    def _secure_write_json(self, file_path: Path, data: Any) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(".tmp")
        try:
            temp_path.touch(exist_ok=True)
            try:
                temp_path.chmod(0o600)
            except OSError as e:
                logging.warning(
                    "Não foi possível aplicar permissões seguras ao arquivo %s: %s",
                    temp_path,
                    e,
                )
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def resolve_user_id(self, identifier: str | int) -> int | None:
        identifier_str = str(identifier).strip().lstrip("@")
        if identifier_str.isdigit():
            return int(identifier_str)
        try:
            return int(self.cl.user_id_from_username(identifier_str))
        except Exception as e:
            print(f"❌ Não foi possível resolver @{identifier_str}: {e}")
            return None

    # -------------------------------------------------------------------------
    # FETCHES CENTRALIZADOS COM CACHE
    # -------------------------------------------------------------------------

    def get_my_followers(self, limit: int = FETCH_LIMIT) -> dict[int, Any]:
        """Busca seguidores com cache. Emite aviso se resultado foi truncado."""
        cached = self.cache.get("followers")
        if cached is not None:
            logging.debug("📊 [cache hit] followers (%d entradas)", len(cached))
            return cached
        print(f"📥 Buscando seguidores (limite: {limit})...")
        data = self.cl.user_followers(self.cl.user_id, amount=limit)
        if len(data) >= limit:
            logging.warning(
                "⚠️  Resultado pode estar truncado: %d seguidores retornados "
                "(limite=%d). Use --no-cache e aumente FETCH_LIMIT se necessário.",
                len(data), limit,
            )
        self.cache.set("followers", data)
        return data

    def get_my_following(self, limit: int = FETCH_LIMIT) -> dict[int, Any]:
        """Busca seguidos com cache. Emite aviso se resultado foi truncado."""
        cached = self.cache.get("following")
        if cached is not None:
            logging.debug("📊 [cache hit] following (%d entradas)", len(cached))
            return cached
        print(f"📥 Buscando seguidos (limite: {limit})...")
        data = self.cl.user_following(self.cl.user_id, amount=limit)
        if len(data) >= limit:
            logging.warning(
                "⚠️  Resultado pode estar truncado: %d seguidos retornados "
                "(limite=%d). Use --no-cache e aumente FETCH_LIMIT se necessário.",
                len(data), limit,
            )
        self.cache.set("following", data)
        return data

    def get_relations_parallel(self) -> tuple[dict[int, Any], dict[int, Any]]:
        """
        Busca followers e following em paralelo, usando cache quando possível.
        Se ambos estão em cache, não faz nenhuma chamada de rede.
        """
        cached_followers = self.cache.get("followers")
        cached_following = self.cache.get("following")

        if cached_followers is not None and cached_following is not None:
            logging.debug("📊 [cache hit] followers + following (sem chamada de rede)")
            return cached_followers, cached_following

        user_id = self.cl.user_id
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures: dict[str, Any] = {}
            if cached_followers is None:
                futures["followers"] = executor.submit(
                    self.cl.user_followers, user_id, amount=FETCH_LIMIT
                )
            if cached_following is None:
                futures["following"] = executor.submit(
                    self.cl.user_following, user_id, amount=FETCH_LIMIT
                )
            if "followers" in futures:
                cached_followers = futures["followers"].result()
                self.cache.set("followers", cached_followers)
            if "following" in futures:
                cached_following = futures["following"].result()
                self.cache.set("following", cached_following)

        return cached_followers, cached_following  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # API PÚBLICA
    # -------------------------------------------------------------------------

    def get_followers(self, target_id: int | None = None, limit: int = 50) -> dict[int, Any]:
        if target_id is None:
            return self.get_my_followers(limit=limit)
        return self.cl.user_followers(target_id, amount=limit)

    def get_following(self, target_id: int | None = None, limit: int = 50) -> dict[int, Any]:
        if target_id is None:
            return self.get_my_following(limit=limit)
        return self.cl.user_following(target_id, amount=limit)

    def follow(self, user_id: int) -> bool:
        result = self.cl.user_follow(user_id)
        self.cache.invalidate_relations()
        return result

    def unfollow(self, user_id: int) -> bool:
        result = self.cl.user_unfollow(user_id)
        self.cache.invalidate_relations()
        return result

    def get_user_info(self, user_id: int) -> Any:
        return self.cl.user_info(user_id)

    def get_non_followers_back(self) -> list[str]:
        followers, following = self.get_relations_parallel()
        following_set = {u.username for u in following.values()}
        followers_set = {u.username for u in followers.values()}
        return sorted(following_set - followers_set)

    def export_followers(self, filename: Path) -> int:
        followers = self.get_my_followers(limit=FETCH_LIMIT)
        data = [
            {
                "id": pk,
                "username": u.username,
                "full_name": u.full_name,
                "is_private": u.is_private,
                "is_verified": u.is_verified,
            }
            for pk, u in followers.items()
        ]
        self._secure_write_json(filename, data)
        return len(data)

    def load_history(self) -> dict[str, str] | None:
        if not self.config.history_file.exists():
            return None
        try:
            with self.config.history_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def save_history(self, data: dict[str, str]) -> Path | None:
        self.config.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = self.config.backup_dir / f"followers_{ts}.json"
        try:
            self._secure_write_json(backup_path, data)
            self._secure_write_json(self.config.history_file, data)
            return backup_path
        except Exception:
            return None

    def get_all_followers_safe(self, user_id: int, max_retries: int = 3) -> dict[int, Any]:
        """Usado exclusivamente pelo tracker (não usa cache, precisa de dado fresco)."""
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                print(f"📥 Carregando seguidores para rastreamento... (tentativa {attempt})")
                followers = self.cl.user_followers(user_id, amount=0)
                print(f"✅ {len(followers)} seguidores carregados.")
                return followers
            except ClientError as e:
                last_exc = e
                if "rate" in str(e).lower():
                    wait = 45 * attempt
                    print(f"⏳ Rate limit. Aguardando {wait}s...")
                    time.sleep(wait)
                else:
                    raise
            except Exception as e:
                last_exc = e
                if attempt == max_retries:
                    raise
                print(f"⚠️ Erro: {e}. Tentando novamente...")
                time.sleep(8)
        raise RuntimeError(
            f"Falha ao carregar seguidores após {max_retries} tentativas."
        ) from last_exc

    def run_tracker(self) -> TrackerResult:
        current = self.get_all_followers_safe(self.cl.user_id)
        current_data = {str(pk): u.username for pk, u in current.items()}
        history = self.load_history()

        if history is None:
            backup = self.save_history(current_data)
            if backup is None:
                raise RuntimeError("Falha ao salvar histórico inicial.")
            return TrackerResult(
                is_first_run=True,
                backup_path=backup,
                unfollowed=set(),
                new_followers=set(),
                history={},
                current_data={},
            )

        old = set(history.keys())
        new = set(current_data.keys())
        unfollowed = old - new
        new_followers = new - old

        backup = self.save_history(current_data)
        if backup is None:
            raise RuntimeError("Falha ao salvar histórico atualizado.")
        return TrackerResult(
            is_first_run=False,
            backup_path=backup,
            unfollowed=unfollowed,
            new_followers=new_followers,
            history=history,
            current_data=current_data,
        )

    def get_auto_follow_back_candidates(self) -> tuple[list[str], dict[str, int]]:
        followers, following = self.get_relations_parallel()
        followers_map = {u.username: pk for pk, u in followers.items()}
        following_set = {u.username for u in following.values()}
        candidates = sorted(followers_map.keys() - following_set)
        id_map = {username: followers_map[username] for username in candidates}
        return candidates, id_map

    def auto_follow_back(
        self, usernames: list[str], id_map: dict[str, int]
    ) -> tuple[int, list[str], list[str]]:
        success: list[str] = []
        failure: list[str] = []
        for username in usernames:
            try:
                user_id = id_map.get(username) or self.resolve_user_id(username)
                if user_id is None:
                    raise UserNotFoundError(f"Usuário @{username} não encontrado")
                self.follow(user_id)
                success.append(username)
                self.random_delay(2.5, 4.5)
            except Exception as e:
                failure.append(f"{username} ({e})")
        return len(success), success, failure

    def get_mass_unfollow_candidates(self) -> tuple[list[str], dict[str, int]]:
        followers, following = self.get_relations_parallel()
        followers_set = {u.username for u in followers.values()}
        following_map = {u.username: pk for pk, u in following.items()}
        candidates = sorted(following_map.keys() - followers_set)
        id_map = {username: following_map[username] for username in candidates}
        return candidates, id_map

    def mass_unfollow_non_followers(
        self, usernames: list[str], id_map: dict[str, int]
    ) -> tuple[int, list[str], list[str]]:
        success: list[str] = []
        failure: list[str] = []
        for username in usernames:
            try:
                user_id = id_map.get(username) or self.resolve_user_id(username)
                if user_id is None:
                    raise UserNotFoundError(f"Usuário @{username} não encontrado")
                self.unfollow(user_id)
                success.append(username)
                self.random_delay(3.0, 5.0)
            except Exception as e:
                failure.append(f"{username} ({e})")
        return len(success), success, failure

    def get_growth_stats(self) -> GrowthStats | None:
        if not self.config.backup_dir.exists():
            return None
        backup_files = sorted(self.config.backup_dir.glob("followers_*.json"))
        if len(backup_files) < 2:
            return None
        if len(backup_files) > MAX_SNAPSHOTS:
            logging.warning(
                "Usando apenas os %d snapshots mais recentes de %d disponíveis.",
                MAX_SNAPSHOTS, len(backup_files),
            )
        snapshots_to_use = backup_files[-MAX_SNAPSHOTS:]
        snapshots: list[tuple[datetime, int]] = []
        for path in snapshots_to_use:
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                ts_str = path.stem.replace("followers_", "")
                ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                snapshots.append((ts, len(data)))
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

    def export_following(self, filename: Path) -> int:
        following = self.get_my_following(limit=FETCH_LIMIT)
        data: list[FollowerData] = [
            {
                "id": str(pk),
                "username": user.username,
                "full_name": user.full_name,
                "is_private": user.is_private,
                "is_verified": user.is_verified,
            }
            for pk, user in following.items()
        ]
        self._secure_write_json(filename, data)
        return len(data)

    def get_recent_posts(self, user_id: int, count: int = 6) -> list[Any]:
        return self.cl.user_medias(user_id, amount=count)

    def get_mutuals(self) -> list[str]:
        followers, following = self.get_relations_parallel()
        following_set = {u.username for u in following.values()}
        follower_set = {u.username for u in followers.values()}
        return sorted(following_set & follower_set)


# =============================================================================
# CLI INTERACTION
# =============================================================================


class InstagramToolkitCLI:
    def __init__(self, service: InstagramService) -> None:
        self.service = service

    def run_menu(self) -> None:
        while True:
            self.show_menu()
            try:
                choice = input("\n👉 Escolha uma opção (0-15): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Saindo...")
                break

            if choice == "0":
                print("\n👋 Até logo! Sessão salva automaticamente.")
                break
            elif choice == "1":
                limit_input = input("Quantos mostrar? (Enter = 50): ").strip()
                limit = int(limit_input) if limit_input.isdigit() else 50
                self.list_followers(limit)
            elif choice == "2":
                limit_input = input("Quantos mostrar? (Enter = 50): ").strip()
                limit = int(limit_input) if limit_input.isdigit() else 50
                self.list_following(limit)
            elif choice == "3":
                target = input("Username (@) ou ID: ").strip()
                if target:
                    self.follow_user(target)
            elif choice == "4":
                target = input("Username (@) ou ID: ").strip()
                if target:
                    self.unfollow_user(target)
            elif choice == "5":
                target = input("Username (@) ou ID: ").strip()
                if target:
                    self.get_user_info(target)
            elif choice == "6":
                self.get_non_followers_back()
            elif choice == "7":
                self.export_followers()
            elif choice == "8":
                self.export_following()
            elif choice == "9":
                self.run_tracker()
            elif choice == "10":
                mins_input = input("Intervalo em minutos (padrão 30): ").strip()
                mins = int(mins_input) if mins_input.isdigit() else 30
                self.watch_mode(mins)
            elif choice == "11":
                max_str = input("Máximo de usuários para seguir de volta (padrão 30): ").strip()
                max_follow = int(max_str) if max_str.isdigit() else 30
                self.auto_follow_back(max_follow)
            elif choice == "12":
                max_str = input("Máximo de usuários para deixar de seguir (padrão 25): ").strip()
                max_unfollow = int(max_str) if max_str.isdigit() else 25
                self.mass_unfollow_non_followers(max_unfollow)
            elif choice == "13":
                self.show_growth_stats()
            elif choice == "14":
                target = input("Username (@) ou ID: ").strip()
                if target:
                    self.show_recent_posts(target)
            elif choice == "15":
                self.show_mutuals()
            else:
                print("❌ Opção inválida.")

    def show_menu(self) -> None:
        print("\n" + "═" * 60)
        print("🚀 INSTAGRAM TOOLKIT v2.4 - MENU PRINCIPAL")
        print("═" * 60)
        print(f"  {self.service.cache.status()}")
        print("─" * 60)
        print(" 1. 👥 Listar meus seguidores")
        print(" 2. ➡️  Listar quem eu sigo")
        print(" 3. ➕ Seguir usuário (@username ou ID)")
        print(" 4. ➖ Deixar de seguir (@username ou ID)")
        print(" 5. 🔍 Ver informações completas de um usuário")
        print(" 6. ❌ Quem NÃO me segue de volta")
        print(" 7. 📤 Exportar todos os meus seguidores (JSON)")
        print(" 8. 📤 Exportar quem eu sigo (JSON)")
        print(" 9. 📊 Rastrear seguidores agora (detectar perdas/ganhos)")
        print("10. 🔄 Iniciar Modo Watch (monitoramento automático)")
        print("─" * 60)
        print("11. 🔄 Auto Seguir de Volta (quem te segue mas você não)")
        print("12. 🧹 Deixar de seguir em massa quem não te segue de volta")
        print("13. 📈 Exibir estatísticas de crescimento de seguidores")
        print("14. 📝 Exibir posts recentes de um usuário")
        print("15. 👥 Exibir seguidores mútuos")
        print("─" * 60)
        print(" 0. 🚪 Sair")
        print("═" * 60)

    def list_followers(self, limit: int) -> None:
        print(f"\n👥 Listando seguidores (limitado a {limit})...")
        try:
            followers = self.service.get_followers(limit=limit)
            for i, (pk, user) in enumerate(list(followers.items())[:limit], 1):
                print(f"   {i:2d}. @{user.username:<28} (ID: {pk})")
            print(f"   Total retornado: {len(followers)}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def list_following(self, limit: int) -> None:
        print(f"\n➡️  Listando quem você segue (limitado a {limit})...")
        try:
            following = self.service.get_following(limit=limit)
            for i, (pk, user) in enumerate(list(following.items())[:limit], 1):
                print(f"   {i:2d}. @{user.username:<28} (ID: {pk})")
            print(f"   Total retornado: {len(following)}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def follow_user(self, identifier: str) -> None:
        user_id = self.service.resolve_user_id(identifier)
        if not user_id:
            return
        print(f"\n➕ Seguindo @{identifier}...")
        try:
            self.service.follow(user_id)
            print("✅ Sucesso!")
            self.service.random_delay()
        except Exception as e:
            print(f"❌ Erro: {e}")

    def unfollow_user(self, identifier: str) -> None:
        user_id = self.service.resolve_user_id(identifier)
        if not user_id:
            return
        print(f"\n➖ Deixando de seguir @{identifier}...")
        try:
            self.service.unfollow(user_id)
            print("✅ Sucesso!")
            self.service.random_delay()
        except Exception as e:
            print(f"❌ Erro: {e}")

    def get_user_info(self, identifier: str) -> None:
        user_id = self.service.resolve_user_id(identifier)
        if not user_id:
            return
        try:
            user = self.service.get_user_info(user_id)
            print(f"\n📋 @{user.username} (ID: {user.pk})")
            print(f"   Nome: {user.full_name}")
            print(f"   Seguidores: {user.follower_count:,}  |  Seguindo: {user.following_count:,}")
            print(f"   Posts: {user.media_count:,}")
            print(f"   Bio: {user.biography[:120]}{'...' if len(user.biography) > 120 else ''}")
            print(f"   Verificado: {'✅' if user.is_verified else '❌'}  |  Privado: {'🔒' if user.is_private else '🌍'}")
            if user.external_url:
                print(f"   Website: {user.external_url}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def get_non_followers_back(self) -> None:
        print("\n🔍 Analisando quem não te segue de volta...")
        try:
            not_back = self.service.get_non_followers_back()
            if not_back:
                print(f"\n❌ {len(not_back)} pessoas que NÃO te seguem de volta:")
                for i, name in enumerate(not_back, 1):
                    print(f"   {i:3d}. @{name}")
            else:
                print("✅ Todos que você segue te seguem de volta! 🎉")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def export_followers(self) -> None:
        filename = Path(f"followers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        print(f"\n📤 Exportando seguidores para {filename}...")
        try:
            count = self.service.export_followers(filename)
            print(f"✅ {count} seguidores exportados!")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def export_following(self) -> None:
        filename = Path(f"following_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        print(f"\n📤 Exportando lista de quem eu sigo para {filename}...")
        try:
            count = self.service.export_following(filename)
            print(f"✅ {count} contas exportadas!")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def run_tracker(self) -> None:
        print(f"\n🕒 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando rastreamento...")
        try:
            res = self.service.run_tracker()
            if res.is_first_run:
                print("🆕 Primeira execução! Histórico de seguidores salvo.")
                print(f"📁 Backup: {res.backup_path}")
                return
            print("\n" + "=" * 58)
            print("📊 RESULTADO DO RASTREAMENTO")
            print("=" * 58)
            if res.unfollowed:
                print(f"\n❌ {len(res.unfollowed)} pessoas pararam de te seguir:")
                for uid in sorted(res.unfollowed):
                    print(f"   • @{res.history.get(uid, '?')} (ID: {uid})")
            else:
                print("\n✅ Ninguém parou de te seguir.")
            if res.new_followers:
                print(f"\n✨ {len(res.new_followers)} novos seguidores:")
                for uid in sorted(res.new_followers):
                    print(f"   • @{res.current_data[uid]} (ID: {uid})")
            else:
                print("\nℹ️  Nenhum novo seguidor.")
            print(f"\n💾 Histórico atualizado + backup: {res.backup_path}")
            print("=" * 58)
        except Exception as e:
            print(f"❌ Erro no rastreamento: {e}")

    def watch_mode(self, interval_minutes: int) -> None:
        print(f"🔄 Modo WATCH ativado — verificando a cada {interval_minutes} minutos.")
        print("   Pressione Ctrl+C para parar.\n")
        try:
            while True:
                self.run_tracker()
                print(f"\n⏳ Próxima verificação em {interval_minutes} minutos...\n")
                time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\n👋 Watch mode encerrado.")

    def auto_follow_back(self, max_follow: int) -> None:
        print("\n🔄 Iniciando Auto Seguir de Volta...")
        try:
            candidates, id_map = self.service.get_auto_follow_back_candidates()
            if not candidates:
                print("✅ Você já segue de volta todos os seus seguidores!")
                return
            print(f"Encontrados {len(candidates)} seguidores que você não segue de volta.")
            to_follow = candidates[:max_follow]
            confirm = input(f"Deseja seguir de volta os primeiros {len(to_follow)}? (s/n): ").strip().lower()
            if confirm != "s":
                print("Operação cancelada.")
                return
            print(f"\nSeguindo {len(to_follow)} usuários...")
            total, success, failure = self.service.auto_follow_back(to_follow, id_map)
            if success:
                print("\n✅ Seguindo de volta com sucesso:")
                for name in success:
                    print(f"   • @{name}")
            if failure:
                print("\n❌ Falhas ao seguir:")
                for fail in failure:
                    print(f"   • {fail}")
            print(f"\n🎉 Processo concluído! {total} usuários seguidos de volta.")
        except Exception as e:
            print(f"❌ Erro ao rodar auto follow back: {e}")

    def mass_unfollow_non_followers(self, max_unfollow: int) -> None:
        print("\n🧹 Iniciando cancelamento de seguimento em massa...")
        try:
            candidates, id_map = self.service.get_mass_unfollow_candidates()
            if not candidates:
                print("✅ Não há usuários para deixar de seguir!")
                return
            print(f"Encontrados {len(candidates)} usuários que não te seguem de volta.")
            to_unfollow = candidates[:max_unfollow]
            confirm = input(f"Deseja deixar de seguir os primeiros {len(to_unfollow)}? (s/n): ").strip().lower()
            if confirm != "s":
                print("Operação cancelada.")
                return
            print(f"\nDeixando de seguir {len(to_unfollow)} usuários...")
            total, success, failure = self.service.mass_unfollow_non_followers(to_unfollow, id_map)
            if success:
                print("\n✅ Deixou de seguir com sucesso:")
                for name in success:
                    print(f"   • @{name}")
            if failure:
                print("\n❌ Falhas ao deixar de seguir:")
                for fail in failure:
                    print(f"   • {fail}")
            print(f"\n🎉 Processo concluído! Deixou de seguir {total} usuários.")
        except Exception as e:
            print(f"❌ Erro ao rodar mass unfollow: {e}")

    def show_growth_stats(self) -> None:
        print("\n📈 Calculando estatísticas de crescimento...")
        try:
            stats = self.service.get_growth_stats()
            if stats is None:
                print("❌ Histórico insuficiente. Execute o rastreamento (opção 9) pelo menos duas vezes.")
                return
            print("\n📈 Relatório de Crescimento de Seguidores")
            print(f"Período      : {stats['start_date']} → {stats['end_date']} ({stats['period_days']} dias)")
            print(f"Início       : {stats['start_count']:,} seguidores")
            print(f"Fim          : {stats['end_count']:,} seguidores")
            print(f"Alteração    : {stats['change']:+} ({stats['daily_average']:+.1f}/dia)")
        except Exception as e:
            print(f"❌ Erro ao calcular estatísticas: {e}")

    def show_recent_posts(self, identifier: str) -> None:
        user_id = self.service.resolve_user_id(identifier)
        if user_id is None:
            return
        limit_str = input("Quantos posts exibir? (padrão 6): ").strip()
        count = int(limit_str) if limit_str.isdigit() else 6
        print(f"\n📝 Buscando os últimos {count} posts de @{identifier}...")
        try:
            medias = self.service.get_recent_posts(user_id, count)
            for i, media in enumerate(medias, 1):
                date_str = datetime.fromtimestamp(media.taken_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                print(f"\n{i}. 📅 {date_str}")
                print(f"   ❤️ {media.like_count:,}   💬 {media.comment_count:,}")
                if media.caption_text:
                    caption = media.caption_text[:90] + ("..." if len(media.caption_text) > 90 else "")
                    print(f"   📝 {caption}")
        except Exception as e:
            print(f"❌ Erro ao buscar posts: {e}")

    def show_mutuals(self) -> None:
        print("\n👥 Calculando seguidores mútuos...")
        try:
            mutuals = self.service.get_mutuals()
            if mutuals:
                print(f"\n👥 {len(mutuals)} seguidores mútuos:")
                for i, username in enumerate(mutuals, 1):
                    print(f"   {i:3d}. @{username}")
            else:
                print("❌ Nenhum seguidor mútuo encontrado.")
        except Exception as e:
            print(f"❌ Erro ao calcular mútuos: {e}")


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================


def main() -> None:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Instagram Toolkit v2.4 - Production-ready management & analytics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--watch", type=int, metavar="MIN", help="Inicia diretamente no modo watch")
    parser.add_argument("--track", action="store_true", help="Executa apenas o rastreamento uma vez")
    parser.add_argument("--no-cache", action="store_true", help="Desabilita cache em memória (força refetch a cada opção)")
    parser.add_argument("--cache-ttl", type=int, default=DEFAULT_TTL, metavar="SEG", help=f"TTL do cache em segundos (padrão: {DEFAULT_TTL})")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           INSTAGRAM TOOLKIT v2.4 - Production Ready         ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    cache = RelationsCache(ttl=args.cache_ttl, enabled=not args.no_cache)
    if not cache.enabled:
        print("⚠️  Modo --no-cache ativo: todas as opções farão refetch completo.")
    else:
        print(f"📊 Cache ativo com TTL de {cache.ttl}s. Use --no-cache para desabilitar.")

    config = Config()
    service = InstagramService(config, cache)

    try:
        service.authenticate()
        print(f"\n👋 Logado como: @{service.cl.username} (ID: {service.cl.user_id})")

        cli = InstagramToolkitCLI(service)
        if args.watch:
            cli.watch_mode(args.watch)
        elif args.track:
            cli.run_tracker()
        else:
            cli.run_menu()

    except AuthenticationError as exc:
        print(f"\n❌ Falha na Autenticação: {exc}")
    except KeyboardInterrupt:
        print("\n👋 Programa encerrado pelo usuário.")
    except Exception as e:
        print(f"\n💥 ERRO FATAL: {e}")


if __name__ == "__main__":
    main()
