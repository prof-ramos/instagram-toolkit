"""
Handlers individuais para cada opção do menu CLI.
Substitui o if/elif em cascata por um dispatch table limpo.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..actions import ActionsService
    from ..cache import RelationsCache
    from ..relations import RelationsService
    from ..storage import HistoryStorage
    from ..tracker import TrackerService

logger = logging.getLogger(__name__)


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

    def list_followers(self) -> None:
        limit = _ask_int("Quantos mostrar? (Enter = 50): ", default=50)
        print(f"\n👥 Listando seguidores (limite: {limit})...")
        try:
            followers = self.relations.get_followers(limit=limit)
            for i, (pk, user) in enumerate(list(followers.items())[:limit], 1):
                print(f"   {i:2d}. @{user.username:<28} (ID: {pk})")
            print(f"   Total: {len(followers)}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def list_following(self) -> None:
        limit = _ask_int("Quantos mostrar? (Enter = 50): ", default=50)
        print(f"\n➡️  Listando seguidos (limite: {limit})...")
        try:
            following = self.relations.get_following(limit=limit)
            for i, (pk, user) in enumerate(list(following.items())[:limit], 1):
                print(f"   {i:2d}. @{user.username:<28} (ID: {pk})")
            print(f"   Total: {len(following)}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def show_non_followers_back(self) -> None:
        print("\n🔍 Analisando quem não te segue de volta...")
        try:
            not_back = self.relations.get_non_followers_back()
            if not_back:
                print(f"\n❌ {len(not_back)} pessoas que NÃO te seguem de volta:")
                for i, name in enumerate(not_back, 1):
                    print(f"   {i:3d}. @{name}")
            else:
                print("✅ Todos que você segue te seguem de volta! 🎉")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def show_mutuals(self) -> None:
        print("\n👥 Calculando seguidores mútuos...")
        try:
            mutuals = self.relations.get_mutuals()
            if mutuals:
                print(f"\n👥 {len(mutuals)} seguidores mútuos:")
                for i, username in enumerate(mutuals, 1):
                    print(f"   {i:3d}. @{username}")
            else:
                print("❌ Nenhum seguidor mútuo encontrado.")
        except Exception as e:
            print(f"❌ Erro: {e}")

    # ------------------------------------------------------------------
    # AÇÕES INDIVIDUAIS
    # ------------------------------------------------------------------

    def follow_user(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        print(f"\n➕ Seguindo @{identifier}...")
        try:
            self.actions.follow(user_id)
            print("✅ Sucesso!")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def unfollow_user(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        print(f"\n➖ Deixando de seguir @{identifier}...")
        try:
            self.actions.unfollow(user_id)
            print("✅ Sucesso!")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def show_user_info(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        try:
            user = self.relations.cl.user_info(user_id)
            print(f"\n📋 @{user.username} (ID: {user.pk})")
            print(f"   Nome      : {user.full_name}")
            print(f"   Seguidores: {user.follower_count:,}  |  Seguindo: {user.following_count:,}")
            print(f"   Posts     : {user.media_count:,}")
            bio = user.biography[:120] + ("..." if len(user.biography) > 120 else "")
            print(f"   Bio       : {bio}")
            print(f"   Verificado: {'✅' if user.is_verified else '❌'}  |  Privado: {'🔒' if user.is_private else '🌍'}")
            if user.external_url:
                print(f"   Website   : {user.external_url}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def show_recent_posts(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        user_id = self.relations.resolve_user_id(identifier)
        if not user_id:
            return
        count = _ask_int("Quantos posts exibir? (padrão 6): ", default=6)
        print(f"\n📝 Buscando os últimos {count} posts de @{identifier}...")
        try:
            medias = self.relations.cl.user_medias(user_id, amount=count)
            for i, media in enumerate(medias, 1):
                date_str = datetime.fromtimestamp(
                    media.taken_at, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M")
                print(f"\n{i}. 📅 {date_str}")
                print(f"   ❤️ {media.like_count:,}   💬 {media.comment_count:,}")
                if media.caption_text:
                    caption = media.caption_text[:90] + (
                        "..." if len(media.caption_text) > 90 else ""
                    )
                    print(f"   📝 {caption}")
        except Exception as e:
            print(f"❌ Erro: {e}")

    # ------------------------------------------------------------------
    # EXPORTAÇÕES
    # ------------------------------------------------------------------

    def export_followers(self) -> None:
        filename = Path(f"followers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        print(f"\n📤 Exportando seguidores para {filename}...")
        try:
            count = self.relations.export_followers(filename)
            print(f"✅ {count} seguidores exportados!")
        except Exception as e:
            print(f"❌ Erro: {e}")

    def export_following(self) -> None:
        filename = Path(f"following_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        print(f"\n📤 Exportando seguidos para {filename}...")
        try:
            count = self.relations.export_following(filename)
            print(f"✅ {count} contas exportadas!")
        except Exception as e:
            print(f"❌ Erro: {e}")

    # ------------------------------------------------------------------
    # TRACKER E ESTATÍSTICAS
    # ------------------------------------------------------------------

    def run_tracker(self) -> None:
        print(f"\n🕒 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando rastreamento...")
        try:
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
        except Exception as e:
            print(f"❌ Erro no rastreamento: {e}")

    def watch_mode(self) -> None:
        interval = _ask_int("Intervalo em minutos (padrão 30): ", default=30)
        _watch_loop(self.run_tracker, interval)

    def show_growth_stats(self) -> None:
        print("\n📈 Calculando estatísticas de crescimento...")
        try:
            stats = self.storage.get_growth_stats()
            if stats is None:
                print("❌ Histórico insuficiente. Execute o rastreamento pelo menos 2 vezes.")
                return
            print("\n📈 Relatório de Crescimento")
            print(f"Período   : {stats['start_date']} → {stats['end_date']} ({stats['period_days']} dias)")
            print(f"Início    : {stats['start_count']:,} seguidores")
            print(f"Fim       : {stats['end_count']:,} seguidores")
            print(f"Alteração : {stats['change']:+} ({stats['daily_average']:+.1f}/dia)")
        except Exception as e:
            print(f"❌ Erro: {e}")

    # ------------------------------------------------------------------
    # AÇÕES EM MASSA
    # ------------------------------------------------------------------

    def auto_follow_back(self) -> None:
        print("\n🔄 Buscando candidatos para seguir de volta...")
        try:
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
        except Exception as e:
            print(f"❌ Erro: {e}")

    def mass_unfollow(self) -> None:
        print("\n🧹 Buscando candidatos para unfollow...")
        try:
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
        except Exception as e:
            print(f"❌ Erro: {e}")


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


def _watch_loop(tracker_fn: object, interval_minutes: int) -> None:
    import time
    print(f"🔄 Watch mode ativo — verificando a cada {interval_minutes} min. Ctrl+C para parar.\n")
    try:
        while True:
            tracker_fn()  # type: ignore[operator]
            print(f"\n⏳ Próxima verificação em {interval_minutes} min...\n")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\n👋 Watch mode encerrado.")
