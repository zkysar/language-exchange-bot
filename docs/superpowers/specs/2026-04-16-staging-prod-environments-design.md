# Design: Staging + Production Environments

**Date:** 2026-04-16  
**Status:** Approved

## Summary

Add a production environment (real Discord server) alongside the existing development environment (test server). Dev tracks `main` and auto-deploys on every push. Prod is pinned to explicit git tags — promotion is `git tag vX.Y.Z && git push origin vX.Y.Z`.

## Environment Mapping

| | Dev (existing) | Prod (new) |
|---|---|---|
| Fly.io app | `discord-host-scheduler` | `discord-host-scheduler-prod` |
| Fly config | `fly.toml` | `fly.prod.toml` |
| Deploy trigger | push to `main` | push of `v*` tag |
| Discord bot | existing bot | new bot (Discord dev portal) |
| Google Sheet | existing Sheet | new copy of Sheet |
| Discord server | test server | real server |

## Code Changes

### 1. New `fly.prod.toml`

Identical to `fly.toml` except the app name:

```toml
app = "discord-host-scheduler-prod"
primary_region = "sjc"

[build]

[processes]
  app = "python -m src.bot"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"

[deploy]
  strategy = "immediate"
```

### 2. Updated `.github/workflows/deploy.yml`

Three changes:

- **Remove** the `tag` job (auto-increments patch tag on every main push — would accidentally trigger prod deploys)
- **Rename** `deploy` → `deploy-dev`, keep targeting `fly.toml`
- **Add** `deploy-prod` job, triggers on `v*` tag pushes, targets `fly.prod.toml`

The `on:` block gains `tags: ['v*']` so `check` and `test` also run on tag pushes, giving prod deploys a CI gate.

```yaml
on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

jobs:
  # check and test jobs unchanged

  deploy-dev:
    name: Deploy to Fly.io (dev)
    needs: [check, test]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    # ... flyctl deploy --remote-only --config fly.toml

  deploy-prod:
    name: Deploy to Fly.io (prod)
    needs: [check, test]
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
    # ... flyctl deploy --remote-only --config fly.prod.toml
```

## Manual One-Time Setup (not automated)

1. **Create prod Discord bot**: Discord dev portal → New Application → Bot tab → Reset Token. Invite to real server via OAuth2 URL Generator (scopes: `bot` + `applications.commands`).
2. **Copy Google Sheet**: Duplicate existing Sheet for prod environment.
3. **Create Fly app**: `fly apps create discord-host-scheduler-prod`
4. **Set Fly secrets on prod app**:
   ```bash
   fly secrets set DISCORD_BOT_TOKEN=<prod-token> -a discord-host-scheduler-prod
   fly secrets set GOOGLE_SHEETS_SPREADSHEET_ID=<prod-sheet-id> -a discord-host-scheduler-prod
   # + GOOGLE_SHEETS_CREDENTIALS_FILE or equivalent
   ```
5. **GitHub secrets**: `FLY_API_TOKEN` already covers both apps (Fly tokens are org-scoped).

## Promotion Workflow

```bash
# When main is in a state you want on the real server:
git tag v1.2.3
git push origin v1.2.3
# → CI runs check + test → deploy-prod fires → prod Fly app updates
```

## Cost

No additional cost. Fly.io free tier includes 3 shared-cpu-1x 256MB VMs. Current usage is 1; adding prod brings it to 2.

## What Does Not Change

- Bot source code — zero changes
- Dev deploy behavior — identical to today
- Fly secrets on the dev app — untouched
- Google Sheets schema — same structure, just a separate Sheet
