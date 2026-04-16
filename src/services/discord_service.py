from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks

from src.commands import help_cmd as help_mod
from src.commands import listdates as listdates_mod
from src.commands import reset as reset_mod
from src.commands import schedule as schedule_mod
from src.commands import setup as setup_mod
from src.commands import sheet as sheet_mod
from src.commands import sync as sync_mod
from src.commands import unvolunteer as unvolunteer_mod
from src.commands import volunteer as volunteer_mod
from src.commands import warnings_cmd as warnings_mod
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.warning_service import WarningService
from src.utils.date_parser import format_display
from src.utils.logger import get_logger

log = get_logger(__name__)


class SchedulerBot(discord.Client):
    def __init__(self, sheets: SheetsService, cache: CacheService) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.sheets = sheets
        self.cache = cache
        self.warnings = WarningService(cache)
        self.tree = app_commands.CommandTree(self)
        self._register_commands()
        self._daily_task: Optional[tasks.Loop] = None

    def _register_commands(self) -> None:
        self.tree.add_command(volunteer_mod.build_group(self.sheets, self.cache))
        self.tree.add_command(unvolunteer_mod.build_group(self.sheets, self.cache, self.warnings))
        self.tree.add_command(schedule_mod.build_command(self.cache))
        self.tree.add_command(listdates_mod.build_command(self.cache))
        self.tree.add_command(warnings_mod.build_command(self.cache, self.warnings))
        self.tree.add_command(sync_mod.build_command(self.sheets, self.cache))
        self.tree.add_command(reset_mod.build_command(self.sheets, self.cache))
        self.tree.add_command(setup_mod.build_group(self.sheets, self.cache))
        self.tree.add_command(sheet_mod.build_command())
        self.tree.add_command(help_mod.build_command(self.cache))

    async def setup_hook(self) -> None:
        await self.tree.sync()
        log.info("slash commands synced")
        self._start_daily_check()

    async def on_ready(self) -> None:
        log.info("bot ready as %s (%s)", self.user, self.user.id if self.user else "?")
        await self._sync_avatar()

    async def _sync_avatar(self) -> None:
        from hashlib import sha256
        from pathlib import Path

        import cairosvg

        icon_path = Path(__file__).resolve().parents[2] / "assets" / "bot-icon.svg"
        if not icon_path.exists():
            log.warning("bot icon not found at %s", icon_path)
            return

        svg_bytes = icon_path.read_bytes()
        png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=512, output_height=512)
        new_hash = sha256(png_bytes).hexdigest()[:16]

        if getattr(self, "_avatar_hash", None) == new_hash:
            return

        try:
            await self.user.edit(avatar=png_bytes)
            self._avatar_hash = new_hash
            log.info("bot avatar updated")
        except Exception:
            log.warning("failed to update avatar (rate-limited?)", exc_info=True)

    def _start_daily_check(self) -> None:
        @tasks.loop(minutes=1)
        async def daily_check_loop() -> None:
            try:
                config = self.cache.config
                tz = ZoneInfo(config.daily_check_timezone)
                now = datetime.now(tz)
                target_hour, target_minute = map(int, config.daily_check_time.split(":"))
                if now.hour != target_hour or now.minute != target_minute:
                    return
                items = await self.warnings.check()
                if not items:
                    return
                channel_id = config.warnings_channel_id
                if not channel_id:
                    log.info("no warnings_channel_id configured; skipping post")
                    return
                channel = self.get_channel(int(channel_id))
                if not channel:
                    return
                lines = ["**Daily warning check**"]
                host_mentions = " ".join(f"<@&{rid}>" for rid in config.host_role_ids)
                admin_mentions = " ".join(f"<@&{rid}>" for rid in config.admin_role_ids)
                urgent_pings = " ".join(filter(None, [host_mentions, admin_mentions]))
                for w in items:
                    icon = "🚨" if w.severity == "urgent" else "⚠️"
                    lines.append(f"{icon} {format_display(w.event_date)} ({w.days_until}d) — {w.severity}")
                if any(w.severity == "urgent" for w in items) and urgent_pings:
                    lines.append(urgent_pings)
                await channel.send("\n".join(lines))
            except Exception:
                log.exception("daily check failed")

        daily_check_loop.start()
        self._daily_task = daily_check_loop
