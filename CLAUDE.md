# Language Exchange Bot — Claude guide

Discord bot for scheduling meetup hosts, backed by Google Sheets. Python 3.12, discord.py, gspread. Deployed on Fly.io.

## Canonical sources of truth

Multiple places describe the same behavior and they **drift**. When they disagree, this is the priority order:

1. Running code in `src/`
2. `specs/001-discord-host-scheduler/spec.md` and `data-model.md`
3. `README.md`
4. Google Sheets `Configuration` tab (runtime config, not behavior)

**After any behavior change**, check whether `README.md`, the spec, and the running Sheet's Configuration defaults still match. Call out drift explicitly — do not silently let it accumulate. There is a known backlog of contradictions between spec and code; flag new ones rather than adding to the pile.

## Project layout

- `src/bot.py` — entry point
- `src/commands/` — one file per slash command (`schedule.py`, `volunteer.py`, `warnings_cmd.py`, `help_cmd.py`, `config_cmd.py`, `setup_wizard.py`, `sync.py`, `reset.py`, `unvolunteer.py`, `sheet.py`)
- `src/services/` — `sheets_service.py` (gspread I/O), `discord_service.py`, `cache_service.py`, `warning_service.py`
- `src/utils/` — `auth.py` (role resolution), `date_parser.py`, `pattern_parser.py`, `config_meta.py`, `logger.py`
- `src/models/models.py` — domain models
- `tests/` — pytest. Sparse coverage; `sheets_service`, `auth`, and `date_parser` are the three modules worth expanding. Don't chase coverage for low-risk code.
- `specs/001-discord-host-scheduler/` — spec, plan, tasks, data-model

## Known hotspot: command UX

`/help`, `/schedule`, `/config`, and `/warnings` have been revised repeatedly in isolated PRs, each breaking the last. Before touching any of them, ask me whether we should scope to the one command or do a pass across all of them. Don't tweak command UX in a vacuum.

## Workflow preferences

- **Planning**: for anything beyond a one-line fix, restate the task in 2 sentences and list the files you'll touch before editing. For multi-step work, use the brainstorming/planning skills.
- **Tests**: run `pytest` before claiming done. If adding a feature to `sheets_service`, `auth`, or `date_parser`, add a test — those are the high-risk modules.
- **Lint**: ruff is configured in `ruff.toml` (line-length 120). Run `ruff check src/ tests/` before pushing — CI has failed on this multiple times.
- **Branch protection**: `main` requires PR + green CI. This is intentional (project continues after I leave). Don't treat merge blocks as surprises.

## The Google Sheet

The bot reads config from a `Configuration` tab at runtime. When code behavior changes (new command, changed default, new config key), the Sheet's schema or defaults may need updating too. I usually have to do this manually — call it out at the end of any behavior-changing change so I don't forget.

Role IDs (`member_role_ids`, `host_role_ids`, `admin_role_ids`) live in the Sheet as JSON arrays. `auth.py` resolves them.

## Conventions

- All dates are `America/Los_Angeles`. Never use naive datetimes.
- Ephemeral Discord responses for admin and error cases; public for normal confirmations.
- Don't add features beyond what I asked for. Don't add docstrings, type hints, or comments to code you didn't change.
