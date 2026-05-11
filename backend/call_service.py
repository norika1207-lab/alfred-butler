"""
Alfred AI Call Service
Twilio Voice + OpenAI Realtime API bridge
Flow: Alfred → Twilio REST → restaurant phone → Twilio Media Streams WS → OpenAI Realtime WS
"""

import asyncio
import json
import os
import uuid
import websockets
from fastapi import WebSocket

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
SERVER_HOST = os.getenv("SERVER_HOST", "alfred.YOUR_SERVER_IP.nip.io")

REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"

# In-memory call registry: call_id → {status, phone, name, purpose, transcript, result, sid}
active_calls: dict = {}


def twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)


def create_call(phone: str, name: str, purpose: str) -> str:
    """Register a new call and trigger Twilio outbound dial. Returns call_id."""
    from twilio.rest import Client

    call_id = str(uuid.uuid4())[:8]
    active_calls[call_id] = {
        "status": "initiated",
        "phone": phone,
        "name": name,
        "purpose": purpose,
        "transcript": "",
        "result": "",
        "sid": "",
    }

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    twiml_url = f"https://{SERVER_HOST}/alfred/api/twiml/{call_id}"
    status_url = f"https://{SERVER_HOST}/alfred/api/call_status/{call_id}"

    call = client.calls.create(
        to=phone,
        from_=TWILIO_PHONE_NUMBER,
        url=twiml_url,
        status_callback=status_url,
        status_callback_method="POST",
    )
    active_calls[call_id]["sid"] = call.sid
    return call_id


def get_call(call_id: str) -> dict:
    return active_calls.get(call_id, {})


def session_instructions(name: str, purpose: str) -> str:
    return f"""You are Alfred, a refined British butler placing a phone call on behalf of your employer.

Your task: {purpose}
You are calling: {name}

Guidelines:
- Speak naturally in Traditional Chinese (Mandarin) if they speak Chinese, otherwise English
- Be polite, warm, and professional — like a seasoned butler
- State your purpose clearly and concisely within the first two sentences
- If making a reservation: confirm under the name "Chen", ask for date, time, and party size confirmation
- If checking availability: ask directly and thank them
- Keep the call under 2 minutes
- When done, say goodbye politely and allow the call to end"""


async def bridge(twilio_ws: WebSocket, call_id: str):
    """Bridge Twilio Media Streams WebSocket ↔ OpenAI Realtime API"""
    call = active_calls.get(call_id, {})
    purpose = call.get("purpose", "")
    name = call.get("name", "")

    transcript_parts: list[str] = []
    stream_sid: str | None = None

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(REALTIME_URL, additional_headers=headers) as oai_ws:

            # Configure session: G.711 μ-law on both sides (no transcoding needed)
            await oai_ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": "alloy",
                    "instructions": session_instructions(name, purpose),
                    "modalities": ["text", "audio"],
                    "input_audio_transcription": {"model": "whisper-1"},
                    "temperature": 0.7,
                }
            }))

            active_calls.setdefault(call_id, {})["status"] = "in_progress"

            # Buffer audio deltas until stream_sid arrives
            audio_buffer: list[str] = []

            async def from_twilio():
                nonlocal stream_sid
                greeting_triggered = False
                while True:
                    try:
                        raw = await twilio_ws.receive_text()
                    except Exception:
                        break
                    data = json.loads(raw)
                    event = data.get("event")

                    if event == "start":
                        stream_sid = data["start"]["streamSid"]
                        # Flush any buffered audio to Twilio now that we have stream_sid
                        for payload in audio_buffer:
                            await twilio_ws.send_text(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": payload},
                            }))
                        audio_buffer.clear()
                        # Trigger Alfred to speak NOW (stream_sid is set)
                        if not greeting_triggered:
                            greeting_triggered = True
                            await oai_ws.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text",
                                                 "text": "The call just connected. Greet them and state your purpose now."}]
                                }
                            }))
                            await oai_ws.send(json.dumps({"type": "response.create"}))

                    elif event == "media":
                        await oai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }))
                    elif event == "stop":
                        break

                try:
                    await oai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                except Exception:
                    pass

            async def from_openai():
                async for raw in oai_ws:
                    data = json.loads(raw)
                    t = data.get("type", "")

                    if t == "response.audio.delta":
                        payload = data["delta"]
                        if stream_sid:
                            await twilio_ws.send_text(json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": payload},
                            }))
                        else:
                            # stream_sid not ready yet — buffer
                            audio_buffer.append(payload)

                    elif t == "response.audio_transcript.done":
                        text = data.get("transcript", "").strip()
                        if text:
                            transcript_parts.append(f"Alfred: {text}")

                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = data.get("transcript", "").strip()
                        if text:
                            transcript_parts.append(f"對方: {text}")

            await asyncio.gather(from_twilio(), from_openai())

    except Exception as e:
        active_calls.setdefault(call_id, {})["result"] = f"通話錯誤：{e}"
    finally:
        rec = active_calls.setdefault(call_id, {})
        transcript = "\n".join(transcript_parts)
        rec["transcript"] = transcript
        if not rec.get("result"):
            rec["result"] = _summarize(transcript, name, purpose)
        rec["status"] = "completed"


def _summarize(transcript: str, name: str, purpose: str) -> str:
    """Generate a brief result summary from transcript (synchronous, Claude not available here)."""
    if not transcript:
        return f"已完成對{name}的電話。"
    lines = transcript.split("\n")
    key = [l for l in lines if "確認" in l or "訂位" in l or "可以" in l or "sorry" in l.lower()]
    if key:
        return key[-1]
    return f"通話完成，共{len(lines)}輪對話。"
