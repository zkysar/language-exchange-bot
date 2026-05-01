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
from src.models.models import Configuration, EventDate
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.services.warning_service import WarningService
from src.utils.date_parser import format_display, today_la
from src.utils.logger import get_logger
from src.utils.meeting_schedule import generate_meeting_dates
from src.utils.pattern_parser import generate_dates, parse_pattern

log = get_logger(__name__)


def should_post_schedule(
    config: Configuration,
    now: datetime,
    last_at: Optional[datetime],
) -> bool:
    """Pure due-check for the recurring schedule announcement.

    `now` must be timezone-aware. `last_at` is either None or tz-aware
    (the sheets loader rejects tz-naive values).
    """
    interval_days = config.schedule_announcement_interval_days
    lookahead_weeks = config.schedule_announcement_lookahead_weeks
    if not interval_days or not lookahead_weeks:
        return False
    try:
        target_hour, target_minute = map(int, config.daily_check_time.split(":"))
    except ValueError:
        return False
    if (now.hour, now.minute) < (target_hour, target_minute):
        return False
    if last_at is None:
        return True
    return (now - last_at) >= timedelta(days=interval_days)


def build_schedule_lines(
    config: Configuration,
    events_by_date: dict[date, EventDate],
    start: date,
    lookahead_weeks: int,
) -> Optional[list[str]]:
    """Build the schedule announcement body, or None if there's nothing to post."""
    end = start + timedelta(days=lookahead_weeks * 7 - 1)
    meeting_dates = generate_meeting_dates(config, start, end)
    if meeting_dates is not None and not meeting_dates:
        return None
    header = (
        f"🗓️ **Upcoming schedule ({lookahead_weeks}w)** — "
        f"{format_display(start)} to {format_display(end)}"
    )
    lines = [header]
    day = start
    while day <= end:
        if meeting_dates is not None and day not in meeting_dates:
            day += timedelta(days=1)
            continue
        ev = events_by_date.get(day)
        if ev and ev.is_assigned:
            who = f"<@{ev.host_discord_id}>" if ev.host_discord_id else ev.host_username
            lines.append(f"- {format_display(day)} — {who}")
        else:
            lines.append(f"- {format_display(day)} — *open*")
        day += timedelta(days=1)
    return lines


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
        self._last_schedule_post_at: Optional[datetime] = None

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
        import os
        from hashlib import sha256
        from pathlib import Path

        import cairosvg

        icon_filename = "bot-icon-prod.svg" if os.environ.get("BOT_ENV") == "prod" else "bot-icon.svg"
        icon_path = Path(__file__).resolve().parents[2] / "assets" / icon_filename
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
                today = today_la()

                # Schedule announcement: state-based trigger, independent of warnings.
                await self._maybe_post_schedule_announcement(config, now, today)

                # Warnings: strict-minute trigger + in-memory once-per-day guard.
                target_hour, target_minute = map(int, config.daily_check_time.split(":"))
                if now.hour != target_hour or now.minute != target_minute:
                    return
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

    async def _maybe_post_schedule_announcement(
        self, config: Configuration, now: datetime, today: date
    ) -> None:
        channel_id = config.announcement_channel_id
        if not channel_id:
            return
        last_at = self._last_schedule_post_at or config.last_schedule_announcement_at
        if not should_post_schedule(config, now, last_at):
            return
        # Stamp in-memory guard BEFORE any await to prevent same-process double-fire
        # while the sheet writeback + cache refresh are in flight.
        self._last_schedule_post_at = now
        try:
            await self.cache.refresh()
            events_by_date = {e.date: e for e in self.cache.all_events()}
            lines = build_schedule_lines(
                config,
                events_by_date,
                today,
                config.schedule_announcement_lookahead_weeks,
            )
            if not lines:
                return
            channel = self.get_channel(int(channel_id))
            if not channel:
                return
            await channel.send("\n".join(lines))
            async with self.sheets.write_lock:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    self.sheets.update_configuration,
                    "last_schedule_announcement_at",
                    now.isoformat(),
                    "string",
                )
            await self.cache.refresh(force=True)
        except Exception:
            log.exception("schedule announcement failed")

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
