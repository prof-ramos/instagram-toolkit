"""
Handlers individuais para cada opção do menu CLI.
Substitui o if/elif em cascata por um dispatch table limpo.
"""

import functools
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..actions import ActionsService
    from ..cache import RelationsCache
    from ..relations import RelationsService
    from ..storage import HistoryStorage
    from ..tracker import TrackerService

logger = logging.getLogger(__name__)


def cli_safe(func: Callable[..., Any]) -> Callable[..., Any]:
    """Catch Exception, log a warning, and keep the interactive menu alive."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.warning("Erro em %s", func.__name__, exc_info=True)
            print(f"❌ Erro em {func.__name__}. Veja o log para detalhes.")
            return None

    return wrapper


class MenuHandlers:
    """
    Handlers de UI para o menu interativo.
    Cada método público corresponde a uma opção do menu.
    """

    def __init__(
        self,
        relations: "RelationsService",
        actions: "ActionsService",
        tracker: "TrackerService",
        storage: "HistoryStorage",
        cache: "RelationsCache",
    ) -> None:
        self.relations = relations
        self.actions = actions
        self.tracker = tracker
        self.storage = storage
        self.cache = cache

    # ------------------------------------------------------------------
    # LISTAGENS
    # ------------------------------------------------------------------

    @cli_safe
    def list_followers(self) -> None:
        limit = _ask_int("Quantos mostrar? (Enter = 50): ", default=50)
        print(f"\n👥 Listando seguidores (limite: {limit})...")
        followers = self.relations.get_followers(limit=limit)
        for i, (pk, user) in enumerate(list(followers.items())[:limit], 1):
            print(f"   {i:2d}. @{user.username:<28} (ID: {pk})")
        print(f"   Total: {len(followers)}")

    @cli_safe
    def list_following(self) -> None:
        limit = _ask_int("Quantos mostrar? (Enter = 50): ", default=50)
        print(f"\n➡️  Listando seguidos (limite: {limit})...")
        following = self.relations.get_following(limit=limit)
        for i, (pk, user) in enumerate(list(following.items())[:limit], 1):
            print(f"   {i:2d}. @{user.username:<28} (ID: {pk})")
        print(f"   Total: {len(following)}")

    @cli_safe
    def show_non_followers_back(self) -> None:
        print("\n🔍 Analisando quem não te segue de volta...")
        not_back = self.relations.get_non_followers_back()
        if not_back:
            print(f"\n❌ {len(not_back)} pessoas que NÃO te seguem de volta:")
            for i, name in enumerate(not_back, 1):
                print(f"   {i:3d}. @{name}")
        else:
            print("✅ Todos que você segue te seguem de volta! 🎉")

    @cli_safe
    def show_mutuals(self) -> None:
        print("\n👥 Calculando seguidores mútuos...")
        mutuals = self.relations.get_mutuals()
        if mutuals:
            print(f"\n👥 {len(mutuals)} seguidores mútuos:")
            for i, username in enumerate(mutuals, 1):
                print(f"   {i:3d}. @{username}")
        else:
            print("❌ Nenhum seguidor mútuo encontrado.")

    # ------------------------------------------------------------------
    # AÇÕES INDIVIDUAIS
    # ------------------------------------------------------------------

    @cli_safe
    def follow_user(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        print(f"\n➕ Seguindo @{identifier}...")
        self.actions.follow(user_id)
        print("✅ Sucesso!")

    @cli_safe
    def unfollow_user(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        print(f"\n➖ Deixando de seguir @{identifier}...")
        self.actions.unfollow(user_id)
        print("✅ Sucesso!")

    @cli_safe
    def show_user_info(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        user = self.relations.get_user_info(user_id)
        print(f"\n📋 @{user.username} (ID: {user.pk})")
        print(f"   Nome      : {user.full_name}")
        print(
            f"   Seguidores: {user.follower_count:,}  |  "
            f"Seguindo: {user.following_count:,}"
        )
        print(f"   Posts     : {user.media_count:,}")
        bio = user.biography[:120] + ("..." if len(user.biography) > 120 else "")
        print(f"   Bio       : {bio}")
        print(
            f"   Verificado: {'✅' if user.is_verified else '❌'}  |  "
            f"Privado: {'🔒' if user.is_private else '🌍'}"
        )
        if user.external_url:
            print(f"   Website   : {user.external_url}")

    @cli_safe
    def show_recent_posts(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        count = _ask_int("Quantos posts exibir? (padrão 6): ", default=6)
        print(f"\n📝 Buscando os últimos {count} posts de @{identifier}...")
        medias = self.relations.get_user_medias(user_id, count)
        for i, media in enumerate(medias, 1):
            taken = media.taken_at
            if isinstance(taken, (int, float)):
                taken = datetime.fromtimestamp(taken, tz=timezone.utc)
            elif getattr(taken, "tzinfo", None) is None:
                taken = taken.replace(tzinfo=timezone.utc)
            date_str = taken.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
            print(f"\n{i}. 📅 {date_str}")
            print(f"   ❤️ {media.like_count:,}   💬 {media.comment_count:,}")
            if media.caption_text:
                caption = media.caption_text[:90] + (
                    "..." if len(media.caption_text) > 90 else ""
                )
                print(f"   📝 {caption}")

    # ------------------------------------------------------------------
    # EXPORTAÇÕES
    # ------------------------------------------------------------------

    @cli_safe
    def export_followers(self) -> None:
        filename = Path(
            f"followers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        print(f"\n📤 Exportando seguidores para {filename}...")
        count = self.relations.export_followers(filename)
        print(f"✅ {count} seguidores exportados!")

    @cli_safe
    def export_following(self) -> None:
        filename = Path(
            f"following_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        print(f"\n📤 Exportando seguidos para {filename}...")
        count = self.relations.export_following(filename)
        print(f"✅ {count} contas exportadas!")

    # ------------------------------------------------------------------
    # TRACKER E ESTATÍSTICAS
    # ------------------------------------------------------------------

    @cli_safe
    def run_tracker(self) -> None:
        print(
            f"\n🕒 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "Iniciando rastreamento..."
        )
        res = self.tracker.run()
        if res.is_first_run:
            print("🆕 Primeira execução! Histórico salvo.")
            print(f"📁 Backup: {res.backup_path}")
            return
        print("\n" + "=" * 58)
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
        print(f"\n💾 Backup: {res.backup_path}")
        print("=" * 58)

    @cli_safe
    def watch_mode(self) -> None:
        interval = _ask_int("Intervalo em minutos (padrão 30): ", default=30)
        if interval <= 0:
            print("❌ Intervalo deve ser maior que zero.")
            return
        from .watch import run_watch_loop

        run_watch_loop(self.run_tracker, interval)

    @cli_safe
    def show_growth_stats(self) -> None:
        print("\n📈 Calculando estatísticas de crescimento...")
        stats = self.storage.get_growth_stats()
        if stats is None:
            print(
                "❌ Histórico insuficiente. Execute o rastreamento pelo menos 2 vezes."
            )
            return
        print("\n📈 Relatório de Crescimento")
        print(
            f"Período   : {stats['start_date']} → {stats['end_date']} "
            f"({stats['period_days']} dias)"
        )
        print(f"Início    : {stats['start_count']:,} seguidores")
        print(f"Fim       : {stats['end_count']:,} seguidores")
        print(f"Alteração : {stats['change']:+} ({stats['daily_average']:+.1f}/dia)")

    # ------------------------------------------------------------------
    # AÇÕES EM MASSA
    # ------------------------------------------------------------------

    @cli_safe
    def auto_follow_back(self) -> None:
        print("\n🔄 Buscando candidatos para seguir de volta...")
        candidates, id_map = self.relations.get_auto_follow_back_candidates()
        if not candidates:
            print("✅ Você já segue de volta todos os seus seguidores!")
            return
        max_follow = _ask_int(
            f"Encontrados {len(candidates)}. Quantos seguir de volta? (padrão 30): ",
            default=30,
        )
        to_follow = candidates[:max_follow]
        if not _confirm(f"Confirmar seguir {len(to_follow)} usuários?"):
            print("Cancelado.")
            return
        total, success, failure = self.actions.auto_follow_back(to_follow, id_map)
        _print_bulk_result("seguidos de volta", success, failure, total)

    @cli_safe
    def mass_unfollow(self) -> None:
        print("\n🧹 Buscando candidatos para unfollow...")
        candidates, id_map = self.relations.get_mass_unfollow_candidates()
        if not candidates:
            print("✅ Não há usuários para deixar de seguir!")
            return
        max_unfollow = _ask_int(
            f"Encontrados {len(candidates)}. Quantos deixar de seguir? (padrão 25): ",
            default=25,
        )
        to_unfollow = candidates[:max_unfollow]
        if not _confirm(f"Confirmar unfollow de {len(to_unfollow)} usuários?"):
            print("Cancelado.")
            return
        total, success, failure = self.actions.mass_unfollow(to_unfollow, id_map)
        _print_bulk_result("removidos", success, failure, total)


# =============================================================================
# HELPERS PRIVADOS
# =============================================================================


def _ask_int(prompt: str, default: int) -> int:
    raw = input(prompt).strip()
    return int(raw) if raw.isdigit() else default


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} (s/n): ").strip().lower() == "s"


def _print_bulk_result(
    label: str, success: list[str], failure: list[str], total: int
) -> None:
    if success:
        print(f"\n✅ {total} usuários {label}:")
        for name in success:
            print(f"   • @{name}")
    if failure:
        print(f"\n❌ {len(failure)} falhas:")
        for fail in failure:
            print(f"   • {fail}")
    print(f"\n🎉 Concluído! {total} {label}.")
