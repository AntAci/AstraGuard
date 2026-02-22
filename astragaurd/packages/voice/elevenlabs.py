#!/usr/bin/env python3
"""ElevenLabs text-to-speech integration for voice briefings.

Uses urllib.request (no extra dependencies). Returns base64 data URI
of MP3 audio, or a skipped status if the API key is missing or the call fails.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict

LOGGER = logging.getLogger(__name__)

_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
_DEFAULT_MODEL = "eleven_turbo_v2_5"
_TIMEOUT_S = 8


def _build_ssl_context() -> ssl.SSLContext:
    ca_bundle = os.environ.get("ASTRA_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if ca_bundle:
        try:
            return ssl.create_default_context(cafile=ca_bundle)
        except Exception:
            pass
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _clean_env_key(name: str) -> str:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper.startswith("YOUR_") or "PLACEHOLDER" in upper or "REPLACE" in upper:
        return ""
    return raw


def synthesize_speech(text: str) -> Dict[str, Any]:
    """Synthesize speech from text using ElevenLabs TTS API.

    Returns:
        dict with keys: provider, status, audio_url (data URI or None), script_text
    """
    api_key = _clean_env_key("ELEVENLABS_API_KEY")
    if not api_key:
        LOGGER.info("ElevenLabs skipped: ELEVENLABS_API_KEY not set")
        return {"provider": "elevenlabs", "status": "skipped", "audio_url": None, "script_text": text}

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", _DEFAULT_VOICE_ID).strip() or _DEFAULT_VOICE_ID
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = json.dumps({
        "text": text[:5000],  # ElevenLabs limit safety
        "model_id": model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode("utf-8")

    req = urllib.request.Request(url=url, method="POST", data=body, headers=headers)

    try:
        ssl_ctx = _build_ssl_context()
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S, context=ssl_ctx) as resp:
            mp3_bytes = resp.read()
        b64 = base64.b64encode(mp3_bytes).decode("ascii")
        audio_url = f"data:audio/mpeg;base64,{b64}"
        LOGGER.info("ElevenLabs TTS success (%d bytes)", len(mp3_bytes))
        return {"provider": "elevenlabs", "status": "ok", "audio_url": audio_url, "script_text": text}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
        LOGGER.warning("ElevenLabs TTS failed: %s", err)
        return {"provider": "elevenlabs", "status": "error", "audio_url": None, "script_text": text}
