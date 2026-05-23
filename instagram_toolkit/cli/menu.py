"""
Menu interativo com dispatch table.
Substitui o if/elif em cascata por um dicionário de handlers.
"""

from typing import Callable

from ..cache import RelationsCache
from .handlers import MenuHandlers


class InteractiveMenu:
    """
    Menu CLI com dispatch table: adicionar uma opção
    é apenas incluir uma entrada no dicionário, sem tocar em if/elif.
    """

    def __init__(self, handlers: MenuHandlers, cache: RelationsCache) -> None:
        self.handlers = handlers
        self.cache = cache
        self._dispatch: dict[str, Callable[[], None]] = {
            "1": handlers.list_followers,
            "2": handlers.list_following,
            "3": handlers.follow_user,
            "4": handlers.unfollow_user,
            "5": handlers.show_user_info,
            "6": handlers.show_non_followers_back,
            "7": handlers.export_followers,
            "8": handlers.export_following,
            "9": handlers.run_tracker,
            "10": handlers.watch_mode,
            "11": handlers.auto_follow_back,
            "12": handlers.mass_unfollow,
            "13": handlers.show_growth_stats,
            "14": handlers.show_recent_posts,
            "15": handlers.show_mutuals,
        }

    def run(self) -> None:
        while True:
            self._show_menu()
            try:
                choice = input("\n👉 Escolha uma opção (0-15): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Saindo...")
                break

            if choice == "0":
                print("\n👋 Até logo!")
                break

            handler = self._dispatch.get(choice)
            if handler:
                handler()
            else:
                print("❌ Opção inválida.")

    def _show_menu(self) -> None:
        print("\n" + "═" * 60)
        print("🚀 INSTAGRAM TOOLKIT v3.0 - MENU PRINCIPAL")
        print("═" * 60)
        print(f"  {self.cache.status()}")
        print("─" * 60)
        print(" 1. 👥 Listar meus seguidores")
        print(" 2. ➡️  Listar quem eu sigo")
        print(" 3. ➕ Seguir usuário (@username ou ID)")
        print(" 4. ➖ Deixar de seguir (@username ou ID)")
        print(" 5. 🔍 Ver informações de um usuário")
        print(" 6. ❌ Quem NÃO me segue de volta")
        print(" 7. 📤 Exportar seguidores (JSON)")
        print(" 8. 📤 Exportar seguidos (JSON)")
        print(" 9. 📊 Rastrear seguidores (ganhos/perdas)")
        print("10. 🔄 Modo Watch (monitoramento automático)")
        print("─" * 60)
        print("11. 🔄 Auto Seguir de Volta")
        print("12. 🧹 Unfollow em massa (não seguidores)")
        print("13. 📈 Estatísticas de crescimento")
        print("14. 📝 Posts recentes de um usuário")
        print("15. 👥 Seguidores mútuos")
        print("─" * 60)
        print(" 0. 🚪 Sair")
        print("═" * 60)
