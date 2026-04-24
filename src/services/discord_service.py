from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks

from src.commands import config_cmd as config_mod
from src.commands import help_cmd as help_mod
from src.commands import hosting as hosting_mod
from src.commands import schedule as schedule_mod
from src.commands import setup_wizard as setup_wizard_mod
from src.commands import sync as sync_mod
from src.models.models import EventDate
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.services.warning_service import WarningService
from src.utils.date_parser import format_display, today_la
from src.utils.logger import get_logger
from src.utils.pattern_parser import generate_dates, parse_pattern

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
        self._last_warning_date: Optional[date] = None

    def _register_commands(self) -> None:
        self.tree.add_command(hosting_mod.build_command(self.sheets, self.cache, self.warnings))
        self.tree.add_command(schedule_mod.build_command(self.cache))
        self.tree.add_command(sync_mod.build_command(self.sheets, self.cache))
        self.tree.add_command(config_mod.build_command(self.sheets, self.cache))
        self.tree.add_command(setup_wizard_mod.build_command(self.sheets, self.cache))
        self.tree.add_command(help_mod.build_command(self.cache))

    async def setup_hook(self) -> None:
        self.tree.interaction_check = self._guild_only_check
        await self.tree.sync()
        log.info("slash commands synced")
        self._start_daily_check()

    async def _guild_only_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This bot only works in a server. Please use commands in a server channel.",
                ephemeral=True,
            )
            return False
        return True

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
                today = today_la()
                if self._last_warning_date == today:
                    return
                self._last_warning_date = today
                await self._extend_recurring_patterns()
                items = await self.warnings.check()
                if not items:
                    return
                channel_id = config.announcement_channel_id
                if not channel_id:
                    log.info("no announcement_channel_id configured; skipping post")
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

    async def _extend_recurring_patterns(self) -> None:
        """Ensure active recurring patterns have dates through the next 26 weeks."""
        await self.cache.refresh()
        today = today_la()
        target_horizon = today + timedelta(weeks=26)
        all_events = {e.date: e for e in self.cache.all_events()}
        loop = asyncio.get_running_loop()

        for pattern in self.cache.all_active_patterns():
            pattern_future = [
                e.date for e in all_events.values()
                if e.recurring_pattern_id == pattern.pattern_id and e.date >= today
            ]
            latest = max(pattern_future) if pattern_future else today - timedelta(days=1)
            if latest >= target_horizon:
                continue

            start = latest + timedelta(days=1)
            try:
                parsed = parse_pattern(pattern.pattern_description)
            except ValueError:
                log.warning("could not parse pattern %s: %r", pattern.pattern_id, pattern.pattern_description)
                continue

            months_needed = max(1, ((target_horizon - start).days // 30) + 2)
            new_dates = [d for d in generate_dates(parsed, start, months=months_needed) if d <= target_horizon]
            if not new_dates:
                continue

            now = datetime.now(timezone.utc)
            async with self.sheets.write_lock:
                extended = 0
                for d in new_dates:
                    existing = all_events.get(d)
                    if existing and existing.is_assigned:
                        continue
                    event = EventDate(
                        date=d,
                        host_discord_id=pattern.host_discord_id,
                        host_username=pattern.host_username,
                        recurring_pattern_id=pattern.pattern_id,
                        assigned_at=now,
                        assigned_by="system",
                    )
                    await loop.run_in_executor(None, self.sheets.upsert_schedule_row, event)
                    self.cache.upsert_event(event)
                    extended += 1
                if extended:
                    await loop.run_in_executor(
                        None,
                        self.sheets.append_audit,
                        make_audit(
                            "RECURRING_EXTENDED",
                            "system",
                            recurring_pattern_id=pattern.pattern_id,
                            metadata={"extended": extended},
                        ),
                    )
                    log.info("extended pattern %s (%s) by %d date(s)", pattern.pattern_id, pattern.pattern_description, extended)
