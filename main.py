#!/usr/bin/env python3
"""
Instagram Toolkit v3.0 - Ponto de entrada.
Responsabilidade única: parse de argumentos + wiring de dependências.
"""

import argparse
import logging

from dotenv import load_dotenv
from instagrapi import Client

from instagram_toolkit.actions import ActionsService
from instagram_toolkit.auth import AuthService
from instagram_toolkit.cache import RelationsCache
from instagram_toolkit.cli.handlers import MenuHandlers
from instagram_toolkit.cli.menu import InteractiveMenu
from instagram_toolkit.config import DEFAULT_TTL, AuthenticationError, Config
from instagram_toolkit.rate_limiter import RateLimiter
from instagram_toolkit.relations import RelationsService
from instagram_toolkit.storage import HistoryStorage
from instagram_toolkit.tracker import TrackerService


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Instagram Toolkit v3.0",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--watch", type=int, metavar="MIN", help="Inicia no modo watch")
    parser.add_argument("--track", action="store_true", help="Executa rastreamento uma vez e sai")
    parser.add_argument("--no-cache", action="store_true", help="Desabilita cache em memória")
    parser.add_argument(
        "--cache-ttl", type=int, default=int(DEFAULT_TTL), metavar="SEG",
        help=f"TTL do cache em segundos (padrão: {int(DEFAULT_TTL)})",
    )
    return parser


def wire_dependencies(config: Config, cache: RelationsCache) -> tuple:
    """Instancia e conecta todas as dependências da aplicação."""
    client = Client()
    storage = HistoryStorage(config)
    auth = AuthService(config, storage)
    rate_limiter = RateLimiter()
    relations = RelationsService(client, cache, storage)
    tracker = TrackerService(client, storage)
    actions = ActionsService(client, cache, relations, rate_limiter)
    handlers = MenuHandlers(relations, actions, tracker, storage, cache)
    menu = InteractiveMenu(handlers, cache)
    return client, auth, handlers, menu, tracker


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    args = build_arg_parser().parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           INSTAGRAM TOOLKIT v3.0 - Production Ready         ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    config = Config()
    cache = RelationsCache(ttl=args.cache_ttl, enabled=not args.no_cache)

    if not cache.enabled:
        print("⚠️  Modo --no-cache ativo: refetch completo em cada operação.")
    else:
        print(f"📊 Cache ativo com TTL de {cache.ttl}s.")

    client, auth, handlers, menu, tracker = wire_dependencies(config, cache)

    try:
        auth.authenticate(client)
        print(f"\n👋 Logado como: @{client.username} (ID: {client.user_id})")

        if args.watch:
            from instagram_toolkit.cli.handlers import _watch_loop
            _watch_loop(handlers.run_tracker, args.watch)
        elif args.track:
            handlers.run_tracker()
        else:
            menu.run()

    except AuthenticationError as exc:
        print(f"\n❌ Falha na Autenticação: {exc}")
    except KeyboardInterrupt:
        print("\n👋 Encerrado pelo usuário.")
    except Exception as e:
        print(f"\n💥 ERRO FATAL: {e}")


if __name__ == "__main__":
    main()
