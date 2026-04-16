from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import discord
from discord import app_commands

from src.models.models import EventDate, RecurringPattern
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.services.warning_service import WarningService
from src.utils.auth import is_host
from src.utils.date_parser import (
    format_date,
    format_display,
    parse_iso_date,
    today_la,
)
from src.utils.logger import get_logger
from src.utils.meeting_schedule import (
    align_matches_schedule,
    generate_meeting_dates,
    is_meeting_day,
)
from src.utils.pattern_parser import generate_dates, parse_pattern

log = get_logger(__name__)

_ACTION_CHOICES = [
    app_commands.Choice(name="signup", value="signup"),
    app_commands.Choice(name="cancel", value="cancel"),
]


def build_command(
    sheets: SheetsService,
    cache: CacheService,
    warnings: WarningService,
) -> app_commands.Command:

    async def date_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        action = None
        for opt in interaction.data.get("options", []) or []:
            if opt.get("name") == "action":
                action = opt.get("value")
        if action == "cancel":
            return await _cancel_date_autocomplete(interaction, current, cache)
        return await _signup_date_autocomplete(interaction, current, cache)

    async def pattern_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        action = None
        for opt in interaction.data.get("options", []) or []:
            if opt.get("name") == "action":
                action = opt.get("value")
        if action != "cancel":
            suggestions = [
                "every Monday", "every Tuesday", "every Wednesday",
                "every Thursday", "every Friday", "every Saturday", "every Sunday",
                "every 1st Monday", "every 1st Tuesday", "every 1st Wednesday",
                "every 1st Thursday", "every 1st Friday", "every 1st Saturday", "every 1st Sunday",
                "every 2nd Monday", "every 2nd Tuesday", "every 2nd Wednesday",
                "every 2nd Thursday", "every 2nd Friday", "every 2nd Saturday", "every 2nd Sunday",
                "every 3rd Monday", "every 3rd Tuesday", "every 3rd Wednesday",
                "every 3rd Thursday", "every 3rd Friday", "every 3rd Saturday", "every 3rd Sunday",
                "every 4th Monday", "every 4th Tuesday", "every 4th Wednesday",
                "every 4th Thursday", "every 4th Friday", "every 4th Saturday", "every 4th Sunday",
                "every last Monday", "every last Tuesday", "every last Wednesday",
                "every last Thursday", "every last Friday", "every last Saturday", "every last Sunday",
                "every other Monday", "every other Tuesday", "every other Wednesday",
                "every other Thursday", "every other Friday", "every other Saturday", "every other Sunday",
                "monthly on the 1", "monthly on the 15",
            ]
            choices: List[app_commands.Choice[str]] = []
            for s in suggestions:
                if not current or current.lower() in s.lower():
                    choices.append(app_commands.Choice(name=s, value=s))
                if len(choices) >= 25:
                    break
            return choices
        target_id = None
        for opt in interaction.data.get("options", []) or []:
            if opt.get("name") == "user":
                target_id = opt.get("value")
        if not target_id:
            target_id = str(interaction.user.id)
        await cache.refresh()
        patterns = cache.active_patterns_for(str(target_id))
        choices: List[app_commands.Choice[str]] = []
        for p in patterns:
            label = p.pattern_description
            if current and current.lower() not in label.lower():
                continue
            choices.append(app_commands.Choice(name=label, value=p.pattern_id))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="hosting", description="Sign up for or cancel hosting dates")
    @app_commands.describe(
        action="What to do",
        date="A specific date",
        pattern="Recurring pattern (e.g. 'every 2nd Tuesday')",
        user="Discord user (defaults to you)",
        name="Off-Discord host name (use instead of user for non-Discord participants)",
    )
    @app_commands.choices(action=_ACTION_CHOICES)
    @app_commands.autocomplete(date=date_autocomplete, pattern=pattern_autocomplete)
    async def hosting(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        date: Optional[str] = None,
        pattern: Optional[str] = None,
        user: Optional[discord.User] = None,
        name: Optional[str] = None,
    ) -> None:
        if not is_host(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command requires the host role.", ephemeral=True
            )
            return
        act = action.value

        if name and act == "cancel":
            await interaction.response.send_message(
                "Use the `user` parameter (or omit it) to cancel a date. `name` is only for assigning off-Discord hosts.",
                ephemeral=True,
            )
            return
        if name and user:
            await interaction.response.send_message(
                "Use `name` for off-Discord hosts, or `user` for Discord members — not both.",
                ephemeral=True,
            )
            return
        if name and pattern:
            await interaction.response.send_message(
                "Recurring patterns are not supported for off-Discord hosts. Provide a `date` instead.",
                ephemeral=True,
            )
            return
        if name and not date:
            await interaction.response.send_message(
                "Provide a `date` when assigning an off-Discord host.",
                ephemeral=True,
            )
            return
        if date and pattern:
            await interaction.response.send_message(
                "Provide either a date or a pattern, not both.", ephemeral=True
            )
            return
        if not date and not pattern and not name:
            await interaction.response.send_message(
                "Provide a date or a pattern.", ephemeral=True
            )
            return

        target = user or interaction.user

        if user is not None and user.id != interaction.user.id and not is_host(
            interaction.user, cache.config
        ):
            await interaction.response.send_message(
                "Only hosts or admins can sign up or cancel for another user.",
                ephemeral=True,
            )
            return

        if act == "signup" and name and date:
            await _signup_external(interaction, sheets, cache, name, date)
        elif act == "signup" and date:
            await _signup_date(interaction, sheets, cache, target, date)
        elif act == "signup" and pattern:
            await _signup_recurring(interaction, sheets, cache, target, pattern)
        elif act == "cancel" and date:
            await _cancel_date(interaction, sheets, cache, warnings, target, date)
        elif act == "cancel" and pattern:
            await _cancel_recurring(interaction, sheets, cache, target, pattern)

    return hosting


async def _signup_date_autocomplete(
    interaction: discord.Interaction, current: str, cache: CacheService
) -> List[app_commands.Choice[str]]:
    await cache.refresh()
    today = today_la()
    horizon = today + timedelta(weeks=12)
    events = {e.date: e for e in cache.all_events()}

    meeting_dates = generate_meeting_dates(cache.config, today, horizon)

    choices: List[app_commands.Choice[str]] = []
    for i in range((horizon - today).days + 1):
        d = today + timedelta(days=i)
        if meeting_dates is not None and d not in meeting_dates:
            continue
        ev = events.get(d)
        if ev and ev.is_assigned:
            continue
        label = format_display(d)
        if current and current.lower() not in label.lower() and current not in format_date(d):
            continue
        choices.append(app_commands.Choice(name=label, value=format_date(d)))
        if len(choices) >= 25:
            break
    return choices


async def _signup_date(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    target: discord.abc.User,
    date_str: str,
) -> None:
    try:
        d = parse_iso_date(date_str)
    except ValueError:
        await interaction.response.send_message(
            f"Invalid date `{date_str}`. Pick one from the autocomplete list.",
            ephemeral=True,
        )
        return
    if d < today_la():
        await interaction.response.send_message(
            "Cannot sign up for a past date.", ephemeral=True
        )
        return
    if not is_meeting_day(d, cache.config):
        await interaction.response.send_message(
            f"**{format_display(d)}** is not a meeting day. "
            f"Exchange meets: `{cache.config.meeting_schedule}`.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    async with sheets.write_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, cache.sheets.load_schedule)
        await cache.refresh(force=True)
        existing = cache.get_event(d)
        if existing and existing.is_assigned:
            await interaction.followup.send(
                f"**{format_display(d)}** is already assigned to "
                f"<@{existing.host_discord_id}>."
            )
            return
        now = datetime.now(timezone.utc)
        event = EventDate(
            date=d,
            host_discord_id=str(target.id),
            host_username=target.display_name,
            assigned_at=now,
            assigned_by=str(interaction.user.id),
        )
        try:
            await loop.run_in_executor(None, sheets.upsert_schedule_row, event)
            await loop.run_in_executor(
                None,
                sheets.append_audit,
                make_audit(
                    "VOLUNTEER",
                    str(interaction.user.id),
                    target_user_discord_id=str(target.id),
                    event_date=d,
                ),
            )
            cache.upsert_event(event)
        except Exception:
            log.exception("volunteer write failed")
            await interaction.followup.send(
                "Failed to update schedule. Please try again later."
            )
            return

    await interaction.followup.send(
        f"<@{target.id}> is now hosting on **{format_display(d)}**."
    )


async def _signup_external(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    name: str,
    date_str: str,
) -> None:
    try:
        d = parse_iso_date(date_str)
    except ValueError:
        await interaction.response.send_message(
            f"Invalid date `{date_str}`. Pick one from the autocomplete list.",
            ephemeral=True,
        )
        return
    if d < today_la():
        await interaction.response.send_message(
            "Cannot sign up for a past date.", ephemeral=True
        )
        return

    await interaction.response.defer()
    async with sheets.write_lock:
        loop = asyncio.get_running_loop()
        await cache.refresh(force=True)
        existing = cache.get_event(d)
        if existing and existing.is_assigned:
            if existing.host_discord_id:
                who = f"<@{existing.host_discord_id}>"
            else:
                who = f"{existing.host_username} (not on Discord)"
            await interaction.followup.send(
                f"**{format_display(d)}** is already assigned to {who}."
            )
            return
        now = datetime.now(timezone.utc)
        event = EventDate(
            date=d,
            host_discord_id="",
            host_username=name,
            assigned_at=now,
            assigned_by=str(interaction.user.id),
        )
        try:
            await loop.run_in_executor(None, sheets.upsert_schedule_row, event)
            await loop.run_in_executor(
                None,
                sheets.append_audit,
                make_audit(
                    "VOLUNTEER_EXTERNAL",
                    str(interaction.user.id),
                    event_date=d,
                    metadata={"external_name": name},
                ),
            )
            cache.upsert_event(event)
        except Exception:
            log.exception("external volunteer write failed")
            await interaction.followup.send(
                "Failed to update schedule. Please try again later."
            )
            return

    await interaction.followup.send(
        f"**{name}** (not on Discord) is now hosting on **{format_display(d)}**.\n"
        f"> If this person is on Discord, use the `user` parameter instead."
    )


async def _signup_recurring(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    target: discord.abc.User,
    pattern_str: str,
) -> None:
    try:
        parsed = parse_pattern(pattern_str)
    except ValueError:
        await interaction.response.send_message(
            "Pattern not recognized. Try formats like `every 2nd Tuesday` or "
            "`monthly on the 1st`.",
            ephemeral=True,
        )
        return

    start = today_la() + timedelta(days=1)
    ok, reason = align_matches_schedule(pattern_str, cache.config, start)
    if not ok:
        await interaction.response.send_message(reason, ephemeral=True)
        return
    dates = generate_dates(parsed, start, months=3)
    if not dates:
        await interaction.response.send_message(
            "No matching dates in the next 3 months.", ephemeral=True
        )
        return

    await cache.refresh()
    existing = {e.date: e for e in cache.all_events()}
    conflicts = [d for d in dates if d in existing and existing[d].is_assigned]
    available = [d for d in dates if d not in conflicts]

    preview_lines = [f"Pattern: `{pattern_str}` → {len(dates)} matches (next 3 months)"]
    preview_lines.append(f"**Will assign ({len(available)}):**")
    for d in available[:15]:
        preview_lines.append(f"- {format_display(d)}")
    if conflicts:
        preview_lines.append(f"**Conflicts ({len(conflicts)}):**")
        for d in conflicts[:10]:
            ev = existing[d]
            preview_lines.append(f"- {format_display(d)} → <@{ev.host_discord_id}>")

    view = _ConfirmView(sheets, cache, target, interaction.user, parsed, available)
    await interaction.response.send_message("\n".join(preview_lines), view=view)
    view.message = await interaction.original_response()


class _ConfirmView(discord.ui.View):
    def __init__(
        self,
        sheets: SheetsService,
        cache: CacheService,
        target: discord.abc.User,
        invoker: discord.abc.User,
        parsed,
        dates: List[date],
    ) -> None:
        super().__init__(timeout=120)
        self.sheets = sheets
        self.cache = cache
        self.target = target
        self.invoker = invoker
        self.parsed = parsed
        self.dates = dates
        self._done = False
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message("Only the invoker can confirm.", ephemeral=True)
            return
        if self._done:
            await interaction.response.send_message("Already confirmed.", ephemeral=True)
            return
        self._done = True
        await interaction.response.defer()
        async with self.sheets.write_lock:
            loop = asyncio.get_running_loop()
            pattern_id = str(uuid.uuid4())
            pattern = RecurringPattern(
                pattern_id=pattern_id,
                host_discord_id=str(self.target.id),
                host_username=self.target.display_name,
                pattern_description=self.parsed.description,
                pattern_rule=json.dumps({
                    "kind": self.parsed.kind,
                    "weekday": self.parsed.weekday,
                    "nth": self.parsed.nth,
                    "day_of_month": self.parsed.day_of_month,
                }),
                start_date=self.dates[0] if self.dates else today_la(),
                created_at=datetime.now(timezone.utc),
                is_active=True,
            )
            try:
                await loop.run_in_executor(None, self.sheets.append_pattern, pattern)
                now = datetime.now(timezone.utc)
                assigned = 0
                for d in self.dates:
                    current = self.cache.get_event(d)
                    if current and current.is_assigned:
                        continue
                    event = EventDate(
                        date=d,
                        host_discord_id=str(self.target.id),
                        host_username=self.target.display_name,
                        recurring_pattern_id=pattern_id,
                        assigned_at=now,
                        assigned_by=str(self.invoker.id),
                    )
                    await loop.run_in_executor(None, self.sheets.upsert_schedule_row, event)
                    self.cache.upsert_event(event)
                    assigned += 1
                await loop.run_in_executor(
                    None,
                    self.sheets.append_audit,
                    make_audit(
                        "VOLUNTEER_RECURRING",
                        str(self.invoker.id),
                        target_user_discord_id=str(self.target.id),
                        recurring_pattern_id=pattern_id,
                        metadata={"count": assigned},
                    ),
                )
                self.cache.add_pattern(pattern)
            except Exception:
                log.exception("recurring commit failed")
                await interaction.followup.send(
                    "Failed to create recurring assignment. Please try again later."
                )
                return
        self.stop()
        await interaction.followup.send(
            f"Created recurring pattern for <@{self.target.id}>: {assigned} dates assigned."
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message("Only the invoker can cancel.", ephemeral=True)
            return
        self.stop()
        await interaction.response.send_message("Cancelled.", ephemeral=True)


async def _cancel_date_autocomplete(
    interaction: discord.Interaction, current: str, cache: CacheService
) -> List[app_commands.Choice[str]]:
    await cache.refresh()
    today = today_la()
    target_id = None
    for opt in interaction.data.get("options", []) or []:
        if opt.get("name") == "user":
            target_id = opt.get("value")
    explicit_user = bool(target_id)
    if not target_id:
        target_id = str(interaction.user.id)
    choices: List[app_commands.Choice[str]] = []
    for ev in sorted(cache.all_events(), key=lambda e: e.date):
        if not ev.is_assigned or ev.date < today:
            continue
        if ev.host_discord_id:
            if str(ev.host_discord_id) != str(target_id):
                continue
            label = format_display(ev.date)
        else:
            # External host date — only show when no user was specified
            if explicit_user:
                continue
            label = f"{format_display(ev.date)} — {ev.host_username} (not on Discord)"
        if current and current.lower() not in label.lower() and current not in format_date(ev.date):
            continue
        choices.append(app_commands.Choice(name=label, value=format_date(ev.date)))
        if len(choices) >= 25:
            break
    return choices


async def _cancel_date(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    warnings: WarningService,
    target: discord.abc.User,
    date_str: str,
) -> None:
    try:
        d = parse_iso_date(date_str)
    except ValueError:
        await interaction.response.send_message("Invalid date.", ephemeral=True)
        return

    await interaction.response.defer()
    async with sheets.write_lock:
        loop = asyncio.get_running_loop()
        await cache.refresh(force=True)
        ev = cache.get_event(d)
        if not ev or not ev.is_assigned:
            await interaction.followup.send(f"No one is scheduled on **{format_display(d)}**.")
            return
        if ev.host_discord_id and str(ev.host_discord_id) != str(target.id):
            await interaction.followup.send(
                f"<@{target.id}> is not assigned on **{format_display(d)}** "
                f"(assigned: <@{ev.host_discord_id}>)."
            )
            return
        try:
            await loop.run_in_executor(None, sheets.clear_schedule_assignment, d)
            await loop.run_in_executor(
                None,
                sheets.append_audit,
                make_audit(
                    "UNVOLUNTEER",
                    str(interaction.user.id),
                    target_user_discord_id=str(target.id),
                    event_date=d,
                ),
            )
            cache.remove_event_assignment(d)
        except Exception:
            log.exception("unvolunteer failed")
            await interaction.followup.send(
                "Failed to cancel hosting. Please try again later."
            )
            return

    if ev.host_discord_id:
        removed = f"<@{ev.host_discord_id}>"
    else:
        removed = f"**{ev.host_username}** (not on Discord)"
    msg = f"Removed {removed} from **{format_display(d)}**."
    try:
        items = await warnings.check()
        urgent = [w for w in items if w.event_date == d and w.severity == "urgent"]
        if urgent:
            msg += "\n⚠️ This date is within the urgent warning window."
    except Exception:
        log.exception("warning check failed")
    await interaction.followup.send(msg)


async def _cancel_recurring(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    target: discord.abc.User,
    pattern_id: str,
) -> None:
    await cache.refresh()
    patterns = cache.active_patterns_for(str(target.id))
    match = next((p for p in patterns if p.pattern_id == pattern_id), None)
    if not match:
        await interaction.response.send_message(
            "Pattern not found or already inactive.", ephemeral=True
        )
        return

    await interaction.response.defer()
    async with sheets.write_lock:
        loop = asyncio.get_running_loop()
        today = today_la()
        await loop.run_in_executor(None, sheets.deactivate_pattern, match.pattern_id)
        cleared = await loop.run_in_executor(
            None, sheets.delete_future_pattern_rows, match.pattern_id, today
        )
        cache.deactivate_pattern(match.pattern_id)
        await loop.run_in_executor(
            None,
            sheets.append_audit,
            make_audit(
                "UNVOLUNTEER_RECURRING",
                str(interaction.user.id),
                target_user_discord_id=str(target.id),
                recurring_pattern_id=match.pattern_id,
                metadata={"cleared": cleared},
            ),
        )
        cache.invalidate()
        await cache.refresh(force=True)

    await interaction.followup.send(
        f"Deactivated pattern \"{match.pattern_description}\" for <@{target.id}>, "
        f"cleared {cleared} future date(s)."
    )
