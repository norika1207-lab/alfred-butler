# Alfred Product Architecture

Last updated: 2026-05-17

Alfred is the product. It is a voice-first private butler that can also work
through LINE and web when speaking is inconvenient. The iOS app must not become
the whole brain. It should be a stable owner-facing surface backed by a shared
event router, owner identity, file vault, task queue, and approval gate.

## Product Spine

```text
iOS voice / LINE / Web / group LINE
  -> Unified Event Router
  -> Owner Identity
  -> Afu Brain decision
  -> Capability Runtime
       -> Alfred native skills
       -> Alice/GX10 office runtime
       -> File Vault
       -> Calendar / Drive / OCR / Meeting / Web
  -> MASL Approval Gate
  -> Response Composer
  -> Voice / LINE / App Card / Web
  -> Feedback + Learning
```

## Non-Negotiable Rules

1. Push-to-talk voice must work before any ambient or background mode.
2. Alfred must not speak while the same audio path is recording for command
   recognition.
3. File search must route to a prepared file map before any general LLM answer.
4. A file request returns candidates first; opening, sending, deleting, or
   sharing a file is a separate approval-gated action.
5. LINE and iOS voice must share the same intent and file-search contract.
6. If a user rejects a candidate page, those file keys are penalized and the
   next page is returned.
7. If a category is exhausted, the search expands to secondary terms. For
   example: contract -> notary / authorization / MOU.
8. Dashboards are a fuse box for diagnosis, not the primary user experience.

## Minimum Sellable Product

The first App Store-quality build must prove these flows:

```text
1. Hold avatar -> speak -> STT -> response -> TTS from speaker.
2. Ask "find the contract" -> file_search intent, not contract-review intent.
3. Return five file candidates with stable ids.
4. User says "not these" -> reject previous ids, return next five.
5. User selects one -> bind selected_file_id.
6. User asks for summary -> read cached summary or enqueue summary job.
7. Long work uses async task + push/status, never blocks the webhook path.
```

Features such as all-day ambient listening, GPS behavior, HealthKit, family
features, and proactive reminders are valuable only after this spine is stable.

## Alice/GX10 Runtime Role

Alice is not a competing product. It is Alfred's office/local runtime mode.
Alfred should expose it internally as capability names such as:

```text
office.file.search
office.file.summary
office.file.materialize
office.drive.index
office.meeting.transcribe
office.calendar.read
office.web.search
```

The GX10 file-map runtime is the reference implementation for serious file
retrieval:

```text
Drive materialization
-> text extraction
-> algorithmic digest
-> summary backfill
-> SQLite FTS5/trigram search
-> optional local Qwen rewrite/rerank
-> top candidates
```

Alfred should use this through a bridge. It should not rebuild file search in
the iOS app and should not ask a general model to guess file names.

## iOS Boundaries

The iOS app owns:

```text
Audio session coordination
Speech input
Speech output
Owner consent and permissions
Small visual cards only when needed
```

The iOS app does not own:

```text
Global identity merge
File vault indexing
Long-running OCR or summary jobs
Group vault ownership
Provider failover
Admin diagnostics
```

## File Search Contract

Every file search response should carry:

```json
{
  "search_session_id": "string",
  "query": "original user text",
  "intent": "file_search",
  "category": "contract",
  "fallback_level": 0,
  "page_size": 5,
  "candidates": [
    {
      "file_key": "stable id",
      "title": "filename",
      "source": "google_drive | line_group | local_desktop | upload",
      "path_hint": "redacted or user-safe location",
      "score": 123.4,
      "matched_keywords": ["合約", "客戶"],
      "summary": "short cached summary"
    }
  ]
}
```

Follow-up messages must resolve against the active `search_session_id`:

```text
"不是"      -> reject current candidates and return next page
"下一頁"    -> return next page
"第 3 個"   -> select candidate 3
"唸摘要"    -> summarize selected candidate
```

## iOS File Vault State

The app keeps file retrieval as a first-class butler task, not a normal chat
turn. When `AfuBrainGate` returns `file_search` or `file_summary`, iOS routes
the message through the file-vault path and keeps a short active window for
follow-up phrases:

```text
"找合約"  -> file-vault turn, visual result card, short spoken guidance
"不是"    -> same file-vault turn, reject current page
"要"      -> same file-vault turn, next page
"第二份"  -> same file-vault turn, analyze selected candidate
"唸摘要"  -> same file-vault turn, summarize selected or last file
```

This preserves Alfred's zero-interface behavior: the voice reply stays short,
the screen holds the candidate list, and the owner can continue by voice or
LINE without restarting the search.

## Review Checklist Before Shipping

```text
[ ] Push-to-talk works on device.
[ ] TTS plays through speaker.
[ ] Alfred does not record itself while speaking.
[ ] File search is observable in logs with intent, route, score, and page.
[ ] LINE long tasks do not depend on the reply token after the initial ack.
[ ] Owner identity is not tied only to one device id.
[ ] Dangerous final actions are approval-gated.
[ ] App Store privacy text matches actual microphone, AI, Drive, and location use.
```
