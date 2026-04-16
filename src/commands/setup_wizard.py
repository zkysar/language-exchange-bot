from __future__ import annotations

import json
from typing import Optional

import discord
from discord import app_commands, ui

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.utils.auth import is_owner
from src.utils.config_meta import SETTINGS, validate_setting


def _channel_mention(cid: Optional[str]) -> str:
    return f"<#{cid}>" if cid else "*not set*"


def _role_mentions(guild: Optional[discord.Guild], ids: list[int]) -> str:
    if not ids:
        return "*none*"
    if guild:
        names = []
        for rid in ids:
            role = guild.get_role(rid)
            names.append(role.mention if role else f"`{rid}`")
        return ", ".join(names)
    return ", ".join(f"`{r}`" for r in ids)


class SetupWizardView(ui.View):
    def __init__(
        self,
        sheets: SheetsService,
        cache: CacheService,
        interaction: discord.Interaction,
    ) -> None:
        super().__init__(timeout=1800)
        self.sheets = sheets
        self.cache = cache
        self.original_interaction = interaction
        self.step = 0

    def _build_roles_embed(self) -> discord.Embed:
        cfg = self.cache.config
        guild = self.original_interaction.guild
        embed = discord.Embed(
            title="Setup — Step 1/4: Roles",
            description="Let's set up who can do what.\n\nSelect roles for each bucket below, or skip to keep current values.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Admin", value=_role_mentions(guild, cfg.admin_role_ids), inline=True)
        embed.add_field(name="Host", value=_role_mentions(guild, cfg.host_role_ids), inline=True)
        embed.add_field(name="Member", value=_role_mentions(guild, cfg.member_role_ids), inline=True)
        return embed

    def _build_channels_embed(self) -> discord.Embed:
        cfg = self.cache.config
        embed = discord.Embed(
            title="Setup — Step 2/4: Channels",
            description="Where should I post?\n\nSelect channels below, or skip to keep current values.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Schedule channel", value=_channel_mention(cfg.schedule_channel_id))
        embed.add_field(name="Warnings channel", value=_channel_mention(cfg.warnings_channel_id))
        return embed

    def _build_schedule_embed(self) -> discord.Embed:
        cfg = self.cache.config
        embed = discord.Embed(
            title="Setup — Step 3/4: Schedule Settings",
            description="How should warnings work?\n\nUse defaults or customize each setting.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Daily check time", value=cfg.daily_check_time, inline=True)
        embed.add_field(name="Timezone", value=cfg.daily_check_timezone, inline=True)
        embed.add_field(name="Passive warning days", value=str(cfg.warning_passive_days), inline=True)
        embed.add_field(name="Urgent warning days", value=str(cfg.warning_urgent_days), inline=True)
        embed.add_field(name="Schedule window", value=f"{cfg.schedule_window_weeks} weeks", inline=True)
        embed.add_field(
            name="Meeting pattern",
            value=cfg.meeting_pattern or "*not set — all dates shown*",
            inline=True,
        )
        return embed

    def _build_summary_embed(self) -> discord.Embed:
        cfg = self.cache.config
        guild = self.original_interaction.guild
        embed = discord.Embed(
            title="Setup — Step 4/4: Summary",
            description="Here's your configuration.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Roles",
            value=(
                f"Admin: {_role_mentions(guild, cfg.admin_role_ids)}\n"
                f"Host: {_role_mentions(guild, cfg.host_role_ids)}\n"
                f"Member: {_role_mentions(guild, cfg.member_role_ids)}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Schedule: {_channel_mention(cfg.schedule_channel_id)}\n"
                f"Warnings: {_channel_mention(cfg.warnings_channel_id)}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Schedule",
            value=(
                f"Check time: {cfg.daily_check_time} ({cfg.daily_check_timezone})\n"
                f"Passive warning: {cfg.warning_passive_days} days\n"
                f"Urgent warning: {cfg.warning_urgent_days} days\n"
                f"Window: {cfg.schedule_window_weeks} weeks\n"
                f"Meeting pattern: {cfg.meeting_pattern or '*not set*'}"
            ),
            inline=False,
        )
        return embed

    async def _show_step(self, interaction: discord.Interaction) -> None:
        self.clear_items()

        if self.step == 0:
            embed = self._build_roles_embed()
            for bucket_label, bucket_key in [("Admin", "admin"), ("Host", "host"), ("Member", "member")]:
                select = _RoleSelectForBucket(self, bucket_key, placeholder=f"Select {bucket_label} roles...")
                self.add_item(select)
            self.add_item(_NextButton(self, label="Next"))

        elif self.step == 1:
            embed = self._build_channels_embed()
            self.add_item(_ChannelSelectForSetting(self, "schedule_channel_id", placeholder="Select schedule channel..."))
            self.add_item(_ChannelSelectForSetting(self, "warnings_channel_id", placeholder="Select warnings channel..."))
            self.add_item(_NextButton(self, label="Next"))

        elif self.step == 2:
            embed = self._build_schedule_embed()
            self.add_item(_MeetingPatternButton(self))
            self.add_item(_CustomizeButton(self))
            self.add_item(_NextButton(self, label="Use defaults & finish"))

        else:
            embed = self._build_summary_embed()
            self.add_item(_DoneButton(self))

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        self.clear_items()
        embed = discord.Embed(title="Setup timed out", color=discord.Color.grayed_out())
        try:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        except discord.HTTPException:
            pass


class _NextButton(ui.Button):
    def __init__(self, wizard: SetupWizardView, label: str = "Next") -> None:
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        self.wizard.step += 1
        await self.wizard._show_step(interaction)


class _DoneButton(ui.Button):
    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__(style=discord.ButtonStyle.success, label="Looks good!")
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        self.wizard.clear_items()
        self.wizard.stop()
        embed = discord.Embed(
            title="Setup complete!",
            description="Use `/config show` to review settings or `/config <group>` to change individual values.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self.wizard)


class _RoleSelectForBucket(ui.RoleSelect):
    def __init__(self, wizard: SetupWizardView, bucket: str, **kwargs) -> None:
        super().__init__(min_values=0, max_values=10, **kwargs)
        self.wizard = wizard
        self.bucket = bucket
        self._config_key = {
            "admin": "admin_role_ids",
            "host": "host_role_ids",
            "member": "member_role_ids",
        }[bucket]

    async def callback(self, interaction: discord.Interaction) -> None:
        ids = [r.id for r in self.values]
        try:
            self.wizard.sheets.update_configuration(
                self._config_key, json.dumps(sorted(ids)), type_="json"
            )
            await self.wizard.cache.refresh(force=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to save roles: {e}", ephemeral=True
            )
            return
        names = ", ".join(r.name for r in self.values) or "*cleared*"
        await interaction.response.send_message(
            f"Set **{self.bucket}** roles to: {names}", ephemeral=True
        )


class _ChannelSelectForSetting(ui.ChannelSelect):
    def __init__(self, wizard: SetupWizardView, config_key: str, **kwargs) -> None:
        super().__init__(
            min_values=0,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            **kwargs,
        )
        self.wizard = wizard
        self._config_key = config_key

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values:
            ch = self.values[0]
            try:
                self.wizard.sheets.update_configuration(
                    self._config_key, str(ch.id), type_="string"
                )
                await self.wizard.cache.refresh(force=True)
            except Exception as e:
                await interaction.response.send_message(
                    f"Failed to save channel: {e}", ephemeral=True
                )
                return
            await interaction.response.send_message(
                f"Set to {ch.mention}", ephemeral=True
            )
        else:
            await interaction.response.send_message("No channel selected.", ephemeral=True)


class _ScheduleModal(ui.Modal, title="Customize Schedule Settings"):
    check_time = ui.TextInput(label="Daily check time (HH:MM)", placeholder="09:00", max_length=5)
    timezone = ui.TextInput(label="Timezone (IANA)", placeholder="America/Los_Angeles", max_length=50)
    passive_days = ui.TextInput(label="Passive warning days (1-30)", placeholder="7", max_length=2)
    urgent_days = ui.TextInput(label="Urgent warning days (1-14)", placeholder="3", max_length=2)
    window_weeks = ui.TextInput(label="Schedule window weeks (1-12)", placeholder="4", max_length=2)

    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__()
        self.wizard = wizard
        cfg = wizard.cache.config
        self.check_time.default = cfg.daily_check_time
        self.timezone.default = cfg.daily_check_timezone
        self.passive_days.default = str(cfg.warning_passive_days)
        self.urgent_days.default = str(cfg.warning_urgent_days)
        self.window_weeks.default = str(cfg.schedule_window_weeks)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        errors: list[str] = []
        updates: list[tuple[str, str, str]] = []

        for key, field_value in [
            ("daily_check_time", self.check_time.value),
            ("daily_check_timezone", self.timezone.value),
            ("warning_passive_days", self.passive_days.value),
            ("warning_urgent_days", self.urgent_days.value),
            ("schedule_window_weeks", self.window_weeks.value),
        ]:
            ok, val, err = validate_setting(key, field_value.strip())
            if ok:
                meta = SETTINGS[key]
                updates.append((key, val, meta.sheets_type))
            else:
                errors.append(err)

        if errors:
            await interaction.response.send_message(
                "**Validation errors:**\n" + "\n".join(f"- {e}" for e in errors),
                ephemeral=True,
            )
            return

        for key, val, type_ in updates:
            self.wizard.sheets.update_configuration(key, val, type_=type_)
        await self.wizard.cache.refresh(force=True)

        self.wizard.step = 3
        await self.wizard._show_step(interaction)


class _CustomizeButton(ui.Button):
    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label="Customize")
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_ScheduleModal(self.wizard))


class _MeetingPatternModal(ui.Modal, title="Set Meeting Pattern"):
    pattern = ui.TextInput(
        label="Meeting pattern",
        placeholder="e.g. every wednesday, every 2nd tuesday",
        max_length=80,
        required=False,
    )

    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__()
        self.wizard = wizard
        cfg = wizard.cache.config
        self.pattern.default = cfg.meeting_pattern or ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.pattern.value.strip()
        ok, val, err = validate_setting("meeting_pattern", value)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        self.wizard.sheets.update_configuration("meeting_pattern", val, type_="string")
        await self.wizard.cache.refresh(force=True)
        await self.wizard._show_step(interaction)


class _MeetingPatternButton(ui.Button):
    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label="Set meeting pattern")
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_MeetingPatternModal(self.wizard))


def build_command(sheets: SheetsService, cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="setup", description="Guided setup wizard for bot configuration")
    async def setup_cmd(interaction: discord.Interaction) -> None:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message("This command is owner-only.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this in a server.", ephemeral=True)
            return

        view = SetupWizardView(sheets, cache, interaction)
        embed = view._build_roles_embed()
        for bucket_label, bucket_key in [("Admin", "admin"), ("Host", "host"), ("Member", "member")]:
            select = _RoleSelectForBucket(view, bucket_key, placeholder=f"Select {bucket_label} roles...")
            view.add_item(select)
        view.add_item(_NextButton(view, label="Next"))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    return setup_cmd
