<p align="center">
  <img src="assets/alfred_hero.png" alt="Alfred — Zero-interface voice butler" width="180">
</p>

<h1 align="center">Alfred 阿福</h1>

<p align="center">
  <strong>A zero-interface voice butler. The opposite of a chatbot.</strong>
</p>

<p align="center">
  <a href="README.md"><strong>English</strong></a>
  ·
  <a href="README.zh-TW.md"><strong>繁體中文</strong></a>
</p>

<p align="center">
  <a href="PITCH.md"><strong>Pitch</strong></a>
  ·
  <a href="ALFRED_SOUL.md"><strong>Soul</strong></a>
  ·
  <a href="SCENARIOS.md"><strong>Scenarios</strong></a>
  ·
  <a href="HANDOFF.md"><strong>API</strong></a>
  ·
  <a href="ENGINEERING.md"><strong>Engineering Notes</strong></a>
  ·
  <a href="DEMO_DAY.md"><strong>Demo Runbook</strong></a>
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/badge/status-open%20technical%20preview-111827">
  <img alt="Platform" src="https://img.shields.io/badge/platform-iOS%2017%2B-0f766e">
  <img alt="iOS" src="https://img.shields.io/badge/Swift-5.9-orange">
  <img alt="Backend" src="https://img.shields.io/badge/backend-FastAPI%20%2F%20Python-3776AB">
  <img alt="Voice" src="https://img.shields.io/badge/UX-voice--first-7c3aed">
  <img alt="Zero-UI" src="https://img.shields.io/badge/UI-zero%20interface-f97316">
</p>

---

## The Problem

Every AI assistant waits for you to ask. The people who actually care about you don't.

ChatGPT, Copilot, Gemini, Claude — they all open with *"Hi, how can I help you today?"* That's an assistant. It magnifies your work but only when you have time to speak.

A butler doesn't ask what you need. He notices.

```text
Assistant: "What can I do for you today?"
Butler:    "Sir, your mother called twice with no message.
            You might want to ring her back this evening."
```

The difference isn't tone. It's the **direction of initiative**.

## What Alfred Is

Alfred is an iOS voice butler with a FastAPI backend. Three rules govern every design decision. Break any one and it's no longer Alfred.

### 1. Zero interface
No menus. No dashboard. No chat log. Just voice.

Visual surfaces appear only when something *must* be seen — a document Alfred is reading aloud, a photo from your library, large translation text for the person across from you, or an authorization screen. **The interface itself is friction.**

### 2. Bridge, not proxy
Alfred doesn't make decisions for you. He keeps human-to-human care from breaking under load.

He won't reply to your mother for you. But he will say:
*"Your mother hasn't heard from you in three days. Want me to send her 'I'll come home for dinner tonight' in your words?"*

### 3. Always one step ahead
He doesn't wait for *"remind me."* He shows up before you need him.

## A Day With Alfred

**07:15 — Morning**
> "Sir, your wife leaves at 7:40. Remind her to take the umbrella — thunderstorms after six. Your son is on day two of midterms — math, he was at his desk until eleven last night. I've pre-ordered breakfast from the place you pass on the way out."

**14:32 — Mid-day, you're at the office**
> "The laundry just finished. Milk is low — added to tonight's list. Your mother called at three with no message. Might be worth a callback."

**18:50 — Evening**
> "Sir, you haven't sat down for more than twenty minutes since 9:12 this morning. Your son got home, but hasn't said a word since walking in. The exam probably didn't go well."

→ Full scenarios: [SCENARIOS.md](SCENARIOS.md)

## Architecture

```
   ┌──────────────┐          ┌─────────────────────┐         ┌──────────────────┐
   │  iOS client  │   voice  │  Alfred backend     │  LLM    │  Gemini · Claude │
   │  (Swift)     │ ───────► │  (FastAPI · Python) │ ──────► │  OpenAI          │
   │              │          │                     │         └──────────────────┘
   │  · Whisper   │          │  · JWT (HS256)      │         ┌──────────────────┐
   │  · ElevenLabs│ ◄─────── │  · Per-user SQLite  │  TTS    │  ElevenLabs      │
   │  · Ambient   │   audio  │  · Background jobs  │ ──────► │  (cloned voice)  │
   │    recorder  │          │  · Action gate      │         └──────────────────┘
   └──────────────┘          │  · Vault encryption │
                             └──────────┬──────────┘
                                        │
                            ┌───────────┴────────────┐
                            ▼                        ▼
                    Google Calendar          LINE · Telegram
                    Gmail · Drive            Twilio voice
                    Family Location          HealthKit
```

**Key technical choices**

- **Voice-first**: Whisper STT, ElevenLabs cloned voice, no chat scrolling UI
- **Background cognition**: ambient recorder (120s chunks), location worker, reminder poller
- **Action gate**: irreversible actions (send, pay, publish, delete) require approval
- **Per-user isolation**: each user has their own SQLite vault
- **Crash-resilient backend**: `systemd` auto-restart, SIGHUP-safe

Deep dive: [ENGINEERING.md](ENGINEERING.md) · [HANDOFF.md](HANDOFF.md)

## Repo Layout

```
alfred-butler/
├── Alfred/                      iOS Swift sources (current)
│   ├── Core/                    ViewModel, API, audio, ambient, photos, location
│   ├── Features/                Chat, Auth, Photos, Office, Family, Translate
│   └── Resources/               voice_bank/, manifest, onboarding audio
├── Alfred.xcodeproj
├── backend/                     FastAPI server
│   ├── main.py                  HTTP routes, chat orchestration
│   ├── gcal_service.py          Google Calendar / Gmail / Drive
│   ├── line_service.py
│   ├── call_service.py          Twilio voice
│   ├── indexer/                 file/document indexer for retrieval
│   ├── scrapers/                e-commerce price comparison agents
│   └── .env.example             env var template
├── frontend/                    Web PWA + admin
└── scripts/                     e2e test, backup
```

## Quick Start

> Backend and iOS app run separately. You'll need a server (your own VPS) and Xcode.

**Backend (Python 3.11+)**

```bash
cd backend
cp .env.example .env
# fill in your API keys (Google, OpenAI, ElevenLabs, LINE, Twilio, ...)
pip install -r requirements.txt
python main.py            # binds to 0.0.0.0:9001
```

**iOS app**

```bash
open Alfred.xcodeproj
# Edit Alfred/Core/*.swift → replace YOUR_BACKEND_HOST with your backend URL
# Set your Apple Developer team ID in target signing
# Build to a physical device (microphone, AVAudioSession needs real hardware)
```

## Status

Open technical preview. Backend stable; iOS client in private TestFlight.

## License

See [LICENSE](LICENSE).

## Credits

Built by [@norika1207-lab](https://github.com/norika1207-lab), with one human and a fleet of AI agents. Cousin projects:

- [**afu-brain**](https://github.com/norika1207-lab/afu-brain) — safety gate + memory layer that Alfred routes through
- [**alfred-system**](https://github.com/norika1207-lab/alfred-system) — broader personal-AI architecture reference
