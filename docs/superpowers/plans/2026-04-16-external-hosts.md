# External Hosts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow admins and hosts to assign dates to people who aren't on Discord, storing just a name, with no warnings fired and a clear "not on Discord" label in all displays.

**Architecture:** Three-file change. `EventDate.is_assigned` is broadened to treat a non-empty `host_username` (with no `host_discord_id`) as assigned. A new `name` parameter on `/hosting signup` routes to a new `_signup_external` path. `/schedule` uses a small helper to render external hosts as plain text. Cancel flow skips the ownership check for external-host dates. No sheet schema changes.

**Tech Stack:** Python 3.12, discord.py, gspread, pytest, ruff

---

### Task 1: Broaden `EventDate.is_assigned` for external hosts

**Files:**
- Modify: `src/models/models.py:25-27`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_models.py` after `test_event_date_with_empty_host_id_is_not_assigned`:

```python
def test_event_date_with_username_only_is_assigned():
    e = EventDate(date=date(2025, 1, 1), host_username="Jane")
    assert e.is_assigned is True


def test_event_date_with_neither_id_nor_username_is_not_assigned():
    e = EventDate(date=date(2025, 1, 1), host_discord_id="", host_username=None)
    assert e.is_assigned is False
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```
pytest tests/test_models.py::test_event_date_with_username_only_is_assigned tests/test_models.py::test_event_date_with_neither_id_nor_username_is_not_assigned -v
```

Expected: both FAIL

- [ ] **Step 3: Update `is_assigned` in `src/models/models.py`**

```python
# Replace lines 25-27 (the is_assigned property):
@property
def is_assigned(self) -> bool:
    return bool(self.host_discord_id or self.host_username)
```

- [ ] **Step 4: Run all model tests**

```
pytest tests/test_models.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/models.py tests/test_models.py
git commit -m "feat: treat username-only EventDate as assigned (external host support)"
```

---

### Task 2: Update `/schedule` to display external hosts

**Files:**
- Modify: `src/commands/schedule.py`
- Test: `tests/test_schedule_cmd.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_schedule_cmd.py`:

```python
@pytest.mark.asyncio
async def test_schedule_specific_date_external_host(cache: MagicMock) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="", host_username="Jane")
    cache.get_event = MagicMock(return_value=ev)
    cmd = build_command(cache)
    interaction = make_interaction()
    with (
        patch("src.commands.schedule.is_member", return_value=True),
        patch("src.commands.schedule.is_host", return_value=True),
    ):
        await cmd.callback(interaction, weeks=None, date="2025-06-10", user=None)
    args, _ = interaction.response.send_message.call_args
    assert "Jane" in args[0]
    assert "not on Discord" in args[0]
    assert "<@" not in args[0]


@pytest.mark.asyncio
async def test_schedule_full_view_shows_external_host(cache: MagicMock) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="", host_username="Jane")
    cache.all_events = MagicMock(return_value=[ev])
    cmd = build_command(cache)
    interaction = make_interaction()
    with (
        patch("src.commands.schedule.is_member", return_value=True),
        patch("src.commands.schedule.is_host", return_value=True),
        patch("src.commands.schedule.today_la", return_value=date(2025, 6, 10)),
    ):
        await cmd.callback(interaction, weeks=1, date=None, user=None)
    args, _ = interaction.response.send_message.call_args
    assert "Jane" in args[0]
    assert "not on Discord" in args[0]
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```
pytest tests/test_schedule_cmd.py::test_schedule_specific_date_external_host tests/test_schedule_cmd.py::test_schedule_full_view_shows_external_host -v
```

Expected: both FAIL

- [ ] **Step 3: Add `_host_display` helper and apply it in `src/commands/schedule.py`**

Add this function at module level (before `build_command`):

```python
def _host_display(ev) -> str:
    if ev.host_discord_id:
        return f"<@{ev.host_discord_id}>"
    return f"{ev.host_username} (not on Discord)"
```

Then in `build_command`, replace the two render locations:

```python
# Line ~52 (single-date assigned display):
# Before:
content = f"**{format_display(d)}** → <@{ev.host_discord_id}>"
# After:
content = f"**{format_display(d)}** → {_host_display(ev)}"

# Line ~89 (full schedule view):
# Before:
who = f"<@{ev.host_discord_id}>"
if ev.recurring_pattern_id:
    who += " 🔁"
# After:
who = _host_display(ev)
if ev.recurring_pattern_id:
    who += " 🔁"
```

- [ ] **Step 4: Run all schedule tests**

```
pytest tests/test_schedule_cmd.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/commands/schedule.py tests/test_schedule_cmd.py
git commit -m "feat: display external hosts as 'Name (not on Discord)' in /schedule"
```

---

### Task 3: Add external host signup to `/hosting`

**Files:**
- Modify: `src/commands/hosting.py`
- Test: `tests/test_hosting_cmd.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_hosting_cmd.py`:

```python
# ── external host signup ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_external_with_user_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    other = MagicMock(spec=discord.User)
    other.id = 2
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(
            interaction, action=_SIGNUP, date="2025-06-10", name="Jane", user=other
        )
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_signup_external_with_pattern_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(
            interaction, action=_SIGNUP, pattern="every monday", name="Jane"
        )
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_signup_external_without_date_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_SIGNUP, name="Jane")
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_signup_external_happy_path(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.get_event.return_value = None
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(
            interaction, action=_SIGNUP, date="2025-06-10", name="Jane"
        )
    sheets.upsert_schedule_row.assert_called_once()
    call_args = sheets.upsert_schedule_row.call_args[0][0]
    assert call_args.host_discord_id == ""
    assert call_args.host_username == "Jane"
    cache.upsert_event.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Jane" in args[0]
    assert "not on Discord" in args[0]
    assert "user" in args[0].lower()  # hint present


@pytest.mark.asyncio
async def test_signup_external_already_assigned_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="99")
    cache.get_event.return_value = ev
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(
            interaction, action=_SIGNUP, date="2025-06-10", name="Jane"
        )
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "already" in args[0].lower() or "assigned" in args[0].lower()


@pytest.mark.asyncio
async def test_cancel_external_host_date_allowed(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="", host_username="Jane")
    cache.get_event.return_value = ev
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, date="2025-06-10")
    sheets.clear_schedule_assignment.assert_called_once()
    cache.remove_event_assignment.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Jane" in args[0]
    assert "not on Discord" in args[0]
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```
pytest tests/test_hosting_cmd.py::test_signup_external_with_user_rejected tests/test_hosting_cmd.py::test_signup_external_with_pattern_rejected tests/test_hosting_cmd.py::test_signup_external_without_date_rejected tests/test_hosting_cmd.py::test_signup_external_happy_path tests/test_hosting_cmd.py::test_signup_external_already_assigned_sends_error tests/test_hosting_cmd.py::test_cancel_external_host_date_allowed -v
```

Expected: all FAIL

- [ ] **Step 3: Add `_signup_external` function to `src/commands/hosting.py`**

Add this function after `_signup_date` (before `_signup_recurring`):

```python
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
```

- [ ] **Step 4: Update the `hosting` command callback to add `name` parameter and routing**

In `build_command`, update the `@app_commands.command` decorator describe block and the callback signature:

```python
@app_commands.describe(
    action="What to do",
    date="A specific date",
    pattern="Recurring pattern (e.g. 'every 2nd Tuesday')",
    user="Discord user (defaults to you)",
    name="Off-Discord host name (use instead of user for non-Discord participants)",
)
```

Update the callback signature:
```python
async def hosting(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    date: Optional[str] = None,
    pattern: Optional[str] = None,
    user: Optional[discord.User] = None,
    name: Optional[str] = None,
) -> None:
```

Replace the validation block (everything after the `is_host` check, before the `act = action.value` line) with:

```python
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
```

Replace the routing block (starting from `act = action.value`) with:

```python
    act = action.value
    target = user or interaction.user

    if user is not None and user.id != interaction.user.id and not is_admin(
        interaction.user, cache.config
    ):
        await interaction.response.send_message(
            "Only admins can sign up or cancel for another user.",
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
```

- [ ] **Step 5: Update `_cancel_date` to allow canceling external host dates**

In `_cancel_date`, replace the ownership check and the final message with:

```python
    # Existing ownership check — skip it for external host dates
    if ev.host_discord_id and str(ev.host_discord_id) != str(target.id):
        await interaction.followup.send(
            f"<@{target.id}> is not assigned on **{format_display(d)}** "
            f"(assigned: <@{ev.host_discord_id}>)."
        )
        return
```

And replace the final message line:

```python
    # Before:
    msg = f"Removed <@{target.id}> from **{format_display(d)}**."

    # After:
    if ev.host_discord_id:
        removed = f"<@{ev.host_discord_id}>"
    else:
        removed = f"**{ev.host_username}** (not on Discord)"
    msg = f"Removed {removed} from **{format_display(d)}**."
```

- [ ] **Step 6: Run all hosting tests**

```
pytest tests/test_hosting_cmd.py -v
```

Expected: all PASS

- [ ] **Step 7: Run the full test suite and lint**

```
pytest -v
ruff check src/ tests/
```

Expected: all PASS, no lint errors

- [ ] **Step 8: Commit**

```bash
git add src/commands/hosting.py tests/test_hosting_cmd.py
git commit -m "feat: add external host support to /hosting with name parameter"
```
