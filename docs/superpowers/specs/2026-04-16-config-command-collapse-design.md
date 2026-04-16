# Design: Collapse `/config` into a single flat command

**Date:** 2026-04-16  
**Status:** Approved

## Summary

Replace the `/config` subcommand group (`show`, `set`, `roles`) with a single `/config` command whose `action` parameter drives behavior. Role management is folded in — no separate subcommand needed.

## Command interface

```
/config [action] [key] [value]
```

All parameters are optional. Defaults: `action=get`, `key=<all>`.

| Param | Type | Required | Choices |
|-------|------|----------|---------|
| `action` | string | no | `get`, `set`, `add`, `remove` |
| `key` | string | no | all SETTINGS keys + `admin`, `host`, `member` |
| `value` | string | no | free text, channel mention, role mention |

### Behavior by action

| action | key | value | result |
|--------|-----|-------|--------|
| `get` (default) | omitted | — | show all settings (equivalent to old `show`) |
| `get` | scalar key | — | show that one setting |
| `get` | role bucket | — | show roles in that bucket |
| `set` | scalar key | new value | update that setting |
| `add` | role bucket | role mention or ID | add role to bucket |
| `remove` | role bucket | role mention or ID | remove role from bucket |

## Validation (runtime, since Discord can't enforce cross-param constraints)

- `set` + role bucket key → error: "Use `add` or `remove` for roles"
- `add`/`remove` + scalar key → error: "Use `set` for this setting"
- `add`/`remove` with no `value` → error: "Provide a role mention"
- `set` with no `value` → error: "Provide a value"
- `value` for role actions must parse as `<@&id>` mention or bare integer role ID
- `value` for channel settings must parse as `<#id>` mention or bare integer channel ID

`action:get` with no `key` is always valid — shows everything.

`clear` is intentionally omitted. Users remove roles one at a time with `remove`.

## Key choices

`KEY_CHOICES` replaces the old `SETTING_CHOICES` + `BUCKET_CHOICES`. It combines:
- All keys from `SETTINGS` (scalars and channels), using `SettingMeta.label` as display name
- Three role buckets: `admin` → "Admin roles", `host` → "Host roles", `member` → "Member roles"

Total: 10 choices (7 settings + 3 buckets), well within Discord's 25-choice limit.

## Autocomplete

`value` autocomplete unchanged: only activates when `key == "daily_check_timezone"`, returns matching IANA timezone strings (up to 25).

## Files changed

### `src/commands/config_cmd.py`

- Delete `build_group()` and the `app_commands.Group`.
- Add `build_command(sheets, cache)` returning a single `@app_commands.command`.
- Replace `BUCKETS`, `BUCKET_CHOICES`, `ACTION_CHOICES`, `SETTING_CHOICES` with `ROLE_BUCKETS` dict and a unified `KEY_CHOICES` list.
- Inline the small helpers (`_current_role_ids`, `_persist_roles`) — they're 3–5 lines each.
- Keep `_parse_channel` as a module-level helper (still needed for channel settings).
- Keep `_TZ_CACHE` for timezone autocomplete.

### `src/services/discord_service.py`

- Line 47: change `config_mod.build_group(...)` → `config_mod.build_command(...)`.

### `src/utils/config_meta.py`

- No changes.

## No behavior changes

- Auth guard (owner-only) is unchanged.
- All responses remain ephemeral.
- Sheet persistence logic is identical.
- `show` output format (the grouped display) is preserved under `get` with no key.

## Testing

No new test module needed (config command has no existing tests and is low-risk UI code). Manual smoke test: verify `get`, `set`, `add`, `remove` all work; verify error messages for invalid action/key combos.
