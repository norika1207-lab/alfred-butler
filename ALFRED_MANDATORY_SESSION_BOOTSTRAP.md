<!-- ALFRED_MANDATORY_SESSION_BOOTSTRAP -->
# MANDATORY FIRST STEP FOR ANY ALFRED / AFU / ALICE REQUEST

Before any analysis, file edit, DB write, backend patch, demo edit, iOS change, systemd change, or conclusion about Alfred / Afu / Alice / File Map, run:

```bash
/usr/local/bin/alfred-context-guard
```

This is required even in a new session. Do not patch first and read docs later. See `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`.

<!-- /ALFRED_MANDATORY_SESSION_BOOTSTRAP -->

# ALFRED MANDATORY SESSION BOOTSTRAP / Alfred 強制開場機制

This file is a hard operating rule for every Codex / Claude / AI session touching Alfred / Afu / Alice / personal agent work.

## Absolute Trigger
If the user message or VPS command contains any of these terms:

- Alfred
- alfred
- 阿福
- Afu
- afu
- Alice
- alice
- file map
- File Map
- summary backfill
- smart-search
- Drive materialization
- local model
- Qwen
- Telegram
- LINE

then before conclusions, file edits, DB writes, backend patches, iOS changes, demo edits, or systemd changes, the agent MUST run:

```bash
/usr/local/bin/alfred-context-guard
```

## What the guard enforces
The guard reads and prints Alfred markdown context from `/opt/alfred`, including:

- `/opt/alfred/ALFRED_MANDATORY_SESSION_BOOTSTRAP.md`
- `/opt/alfred/README.md`
- `/opt/alfred/CRITICAL_README.md`
- `/opt/alfred/HANDOFF.md`
- `/opt/alfred/CLAUDE.md`
- `/opt/alfred/STATUS.md`
- `/opt/alfred/ALICE_TO_ALFRED_INTEGRATION.md`
- `/opt/alfred/docs/*.md`
- `/opt/alfred/frontend/*.md`
- any other `/opt/alfred/**/*.md` except generated file payloads under `/opt/alfred/data/files`.

It also prints DB locations, service commands, and file-map runtime checks.

## Non-negotiable rules
- Do not patch first and read docs later.
- Alfred is a personal AI Agent system, not just a chatbot.
- Alice-style File Map + Summary Runtime is core capability, not optional decoration.
- Before touching file search / document understanding, check:
  - `/opt/alfred/backend/main.py`
  - `/api/files/smart-search`
  - `vault_file_summaries`
  - `vault_file_materializations`
  - `vault_files`
  - `drive_index`
  - `mac_files_index`
- Before claiming file-map data is missing, check all DBs:
  - `/opt/alfred/backend/alfred.db`
  - `/opt/alfred/data/alfred.db`
  - `/opt/alfred/data/auth.db`
  - `/opt/alfred/data/users/*.db`
- Any new scheduler or background updater must have a DB status table, health table, README/HANDOFF entry, and systemd verification.

## Required first response behavior
When a user asks about Alfred / Afu / Alice / File Map, the agent should say it is loading mandatory Alfred context, then run the guard. This is required even in a new session.
