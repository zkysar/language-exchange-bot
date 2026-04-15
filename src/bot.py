from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

from src.services.cache_service import CacheService
from src.services.discord_service import SchedulerBot
from src.services.sheets_service import SheetsService
from src.utils.logger import get_logger, setup_logging


async def amain() -> None:
    setup_logging()
    log = get_logger("bot")
    load_dotenv()

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        log.error("DISCORD_BOT_TOKEN not set")
        sys.exit(1)

    sheets = SheetsService()
    sheets.ensure_sheets()
    cache = CacheService(sheets)
    await cache.refresh(force=True)

    bot = SchedulerBot(sheets, cache)
    try:
        await bot.start(token)
    finally:
        await bot.close()


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
