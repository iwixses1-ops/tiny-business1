# -*- coding: utf-8 -*-
"""Точка входа Tiny Business — версия с Mini App.

Запускает ОДНОВРЕМЕННО:
  • FastAPI-сервер (backend/main.py) — раздаёт API и frontend Mini App
  • Telegram-бота (bot/main.py) — кнопка «Играть» и команды

Оба процесса работают в одном event loop, поэтому одной команды достаточно.
Подходит для Bothost (Главный файл = run.py) и для обычного VPS.

Запуск:
    python run.py            # сервер + бот (нужно для Mini App)
    python run.py --server   # только FastAPI
    python run.py --bot      # только бот (без веб-сервера)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiny Business launcher")
    parser.add_argument("--server", action="store_true", help="Только FastAPI")
    parser.add_argument("--bot", action="store_true", help="Только бот")
    args = parser.parse_args()

    # Корень проекта в sys.path, чтобы импортировать backend и bot
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    if args.server:
        _run_server()
    elif args.bot:
        _run_bot()
    else:
        _run_both()


def _run_server() -> None:
    """Запуск только FastAPI (блокирующий)."""
    import uvicorn

    from backend.config import config

    print(f"Starting FastAPI on http://{config.BACKEND_HOST}:{config.BACKEND_PORT}")
    uvicorn.run(
        "backend.main:app",
        host=config.BACKEND_HOST,
        port=config.BACKEND_PORT,
        reload=False,
    )


async def _run_server_async() -> None:
    """Запуск FastAPI как asyncio-задачи (для параллельной работы с ботом)."""
    import uvicorn

    from backend.config import config

    cfg = uvicorn.Config(
        "backend.main:app",
        host=config.BACKEND_HOST,
        port=config.BACKEND_PORT,
        log_level="info",
    )
    server = uvicorn.Server(cfg)
    await server.serve()


async def _run_bot_process() -> None:
    from bot.main import main as bot_main

    await bot_main()


def _run_bot() -> None:
    """Запуск только бота (long polling)."""
    from backend.config import config

    if not config.BOT_TOKEN:
        print("ERROR: BOT_TOKEN не задан. Добавь токен и перезапусти.")
        return

    try:
        asyncio.run(_run_bot_process())
    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")


def _run_both() -> None:
    """Сервер и бот параллельно в одном event loop."""
    from backend.config import config

    async def _safe(coro, name: str) -> None:
        """
        Запускает корутину и НЕ даёт её падению уронить остальные.

        На хостинге бывает, что порт занят прокси хостинга — тогда сервер
        не поднимется, но бот должен продолжать работать.
        """
        try:
            await coro
        except Exception as e:
            print(f"[{name}] остановлен с ошибкой: {e}")

    async def _both():
        jobs = [_safe(_run_server_async(), "Веб-сервер")]
        # Бот стартует, если задан токен и включён BOT_AUTO_START.
        if config.BOT_TOKEN and config.BOT_AUTO_START:
            jobs.append(_safe(_run_bot_process(), "Бот"))
        await asyncio.gather(*jobs)

    print(f"Starting server on http://{config.BACKEND_HOST}:{config.BACKEND_PORT}")
    if not config.BOT_TOKEN:
        print("WARNING: BOT_TOKEN не задан — бот не стартует (будет только сервер).")
    elif not config.BOT_AUTO_START:
        print("WARNING: BOT_AUTO_START=false — бот не стартует (будет только сервер).")
    try:
        asyncio.run(_both())
    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")


if __name__ == "__main__":
    main()