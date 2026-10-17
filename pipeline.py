"""
Gully Commentator - the whole pipeline in one file.

voice clip --> Saaras (STT) --> Sarvam-105B (commentary JSON) --> Bulbul (TTS) --> audio

Three Sarvam calls, in order. That's the entire app.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field

from sarvamai import SarvamAI

# Load a local .env if python-dotenv is installed and the file exists.
# The key is read from the environment only — never passed as an argument.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; a plain `export` works too
    pass

# ---------------------------------------------------------------------------
# Config (all overridable from the environment, keys never hard-coded)
# ---------------------------------------------------------------------------

STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")   # saaras:v3 or saaras:v4
STT_MODE = os.getenv("SARVAM_STT_MODE", "codemix")       # transcribe|translate|verbatim|translit|codemix
CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b")
TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")   # bulbul:v3 (short names) or bulbul:v4-flash (persona IDs)

# bulbul:v3 short-name speakers, safe for every supported language.
# For extra "stadium energy" on Hindi you can switch TTS_MODEL to bulbul:v4-flash
# and set the speaker to "ratan_hi_sports" (see README).
SPEAKER_BY_LANG = {
    "hi-IN": "shubh",
    "ta-IN": "ratan",
    "te-IN": "ratan",
    "kn-IN": "ratan",
    "ml-IN": "shubh",
    "mr-IN": "ratan",
    "bn-IN": "rehan",
    "gu-IN": "ratan",
    "pa-IN": "mani",
    "od-IN": "shubh",
    "en-IN": "ratan",
}
DEFAULT_SPEAKER = "shubh"

LANGUAGE_NAMES = {
    "hi-IN": "Hindi", "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "mr-IN": "Marathi", "bn-IN": "Bengali", "gu-IN": "Gujarati",
    "pa-IN": "Punjabi", "od-IN": "Odia", "en-IN": "English",
}

# ---------------------------------------------------------------------------
# The one thing that makes this app "Gully Commentator" instead of "an ASR demo".
# Persona lives here, costs zero build time, and is one string to tweak.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a "gully uncle" cricket commentator — the loud, over-the-top \
uncle who commentates every mohalla match from behind the stumps. You are dramatic, \
funny, and treat a Sunday gully game like it is the World Cup final. You pepper your \
lines with cricket slang ("kya shot hai!", "clean bowled!", "the crowd has gone mad!") \
and you are never neutral — every ball is either a disaster or a miracle.

You will receive a short spoken clip transcribed from a live gully match. It may be \
Hindi, Tamil, or a code-mixed mix of an Indian language and English, and it may be \
messy (crowd noise, stumbles, half-sentences).

Rewrite it as ONE punchy commentary line in the SAME language the speaker used \
(same script, same language mix — do not translate to English unless the clip was in \
English). Keep it to 1-2 sentences. Add the drama; do not invent a different event \
than what was said.

Respond with ONLY a JSON object, no markdown, exactly these keys:
{
  "minute":  "<match minute if the clip mentions one, else 'unknown'>",
  "player":  "<the player's name if mentioned, else 'unknown'>",
  "event":   "<2-4 word label, e.g. 'header goal', 'clean bowled', 'wide ball'>",
  "commentary": "<your one dramatic line, in the speaker's language>"
}"""


@dataclass
class CommentatorResult:
    transcript: str
    language_code: str
    minute: str = "unknown"
    player: str = "unknown"
    event: str = "unknown"
    commentary: str = ""
    audio: bytes = b""
    raw_json: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def get_client() -> SarvamAI:
    """Build a Sarvam client from the environment. Never takes a key argument."""
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set. Export it in your shell "
            "(export SARVAM_API_KEY=...) or put it in a .env file. "
            "Never paste the key into chat or commit it."
        )
    return SarvamAI(api_subscription_key=key)


# ---------------------------------------------------------------------------
# Step 1 - Saaras: audio in, transcript out
# ---------------------------------------------------------------------------

def transcribe(audio_bytes: bytes, language_code: str = "unknown",
               client: SarvamAI | None = None) -> tuple[str, str]:
    """Return (transcript, detected_language_code).

    language_code="unknown" lets Saaras auto-detect the language, which is the
    whole point here — the user never picks a language.
    """
    client = client or get_client()
    resp = client.speech_to_text.transcribe(
        file=("clip.wav", audio_bytes),      # short clips only; REST caps at 30s
        model=STT_MODEL,
        mode=STT_MODE,
        language_code=language_code,
    )
    detected = resp.language_code or (language_code if language_code != "unknown" else "hi-IN")
    return resp.transcript, detected


# ---------------------------------------------------------------------------
# Step 2 - Sarvam-105B: transcript in, commentary JSON out
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in ```json fences. Be forgiving."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def commentate(transcript: str, language_code: str,
               client: SarvamAI | None = None) -> dict:
    """Return {minute, player, event, commentary}."""
    client = client or get_client()
    lang_name = LANGUAGE_NAMES.get(language_code, "the speaker's language")
    user_prompt = (
        f"Detected language: {lang_name} ({language_code}).\n"
        f"Transcript of the clip:\n\"\"\"{transcript}\"\"\"\n\n"
        f"Give me the commentary JSON now, with the commentary line in {lang_name}."
    )
    resp = client.chat.completions(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1000,          # was 400
        reasoning_effort=None,    # add this line
        response_format={"type": "json_object"},

    )
    content = resp.choices[0].message.content or "{}"
    data = _extract_json(content)
    return {
        "minute": str(data.get("minute", "unknown")),
        "player": str(data.get("player", "unknown")),
        "event": str(data.get("event", "unknown")),
        "commentary": str(data.get("commentary", "")).strip(),
    }


# ---------------------------------------------------------------------------
# Step 3 - Bulbul: commentary in, playable audio out
# ---------------------------------------------------------------------------

def speak(text: str, language_code: str, client: SarvamAI | None = None) -> bytes:
    """Return WAV bytes of the spoken commentary."""
    client = client or get_client()
    speaker = SPEAKER_BY_LANG.get(language_code, DEFAULT_SPEAKER)
    resp = client.text_to_speech.convert(
        text=text,
        language_code=language_code,
        speaker=speaker,
        model=TTS_MODEL,
        pace=1.15,                 # a touch faster — commentators don't dawdle
        temperature=0.7,           # a bit more expressive
        speech_sample_rate=24000,
    )
    return base64.b64decode(resp.audios[0])


# ---------------------------------------------------------------------------
# The one flow, start to finish
# ---------------------------------------------------------------------------

def run(audio_bytes: bytes, client: SarvamAI | None = None) -> CommentatorResult:
    client = client or get_client()
    transcript, lang = transcribe(audio_bytes, client=client)
    data = commentate(transcript, lang, client=client)
    audio = speak(data["commentary"], lang, client=client)
    return CommentatorResult(
        transcript=transcript,
        language_code=lang,
        minute=data["minute"],
        player=data["player"],
        event=data["event"],
        commentary=data["commentary"],
        audio=audio,
        raw_json=data,
    )
