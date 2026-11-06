"""Timbre Text-to-Speech service.

Implements the official Gnani Timbre TTS endpoint:
    POST https://api.vachana.ai/api/v1/tts/inference
Headers:
    X-API-Key-ID: <api_key>
    Content-Type: application/json
JSON Body:
    model: "timbre-v2.5"
    text: "<plain text string>"
    language: "en-IN"
    voice: "Nalini"
    audio_format: "wav"

Note: Gnani Timbre delivers raw 16-bit linear PCM at 24000 Hz in stereo (2 channels).
When interpreted as 16000 Hz mono:
1. Playback speed dropped to 33% of natural speed (speech sounded deep, slow, and slurred).
2. Interleaved stereo channels played sequentially into a mono sink, producing a sample-delayed
   comb-filter effect (hollow echo, reverberation, and distortion).

This service wraps the raw PCM in a matching 24000 Hz stereo RIFF/WAV header (or downmixes to clean mono),
delivering natural, crisp, crystal-clear speech.
"""

import io
import os
import wave
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class GnaniAPIError(RuntimeError):
    """Raised when the Gnani API returns an error or invalid payload."""


def _wrap_pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 2, sampwidth: int = 2) -> bytes:
    """Wraps raw 16-bit linear PCM byte stream into standard RIFF WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class TimbreTTSService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        tts_url: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        audio_format: Optional[str] = None,
        sampling_rate: Optional[str] = None,
        channels: Optional[int] = None,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY", "")
        self.tts_url = tts_url or os.getenv(
            "GNANI_TTS_URL", "https://api.vachana.ai/api/v1/tts/inference"
        )
        self.model = model or os.getenv("GNANI_TTS_MODEL", "timbre-v2.5")
        self.language = language or os.getenv("GNANI_TTS_LANGUAGE", "en-IN")
        self.voice = voice or os.getenv("GNANI_TTS_VOICE", "Nalini")
        self.audio_format = audio_format or os.getenv("GNANI_TTS_FORMAT", "wav")
        # Gnani Timbre's native audio output is 24000 Hz, 2-channel (stereo) 16-bit PCM
        self.sampling_rate = sampling_rate or os.getenv("GNANI_TTS_SAMPLE_RATE", "24000")
        self.channels = channels or int(os.getenv("GNANI_TTS_CHANNELS", "2"))
        self.timeout = int(os.getenv("GNANI_TIMEOUT_SECONDS", "8"))

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your-gnani-api-key-here")

    def synthesize(self, text: str) -> bytes:
        """Synthesize *text* to playable WAV audio bytes using Gnani Timbre.

        Args:
            text: Plain text string to synthesize (max 2000 chars recommended).

        Returns:
            bytes: Valid, playable RIFF WAV audio data.

        Raises:
            GnaniAPIError: If API key is missing, API returns non-200, or payload invalid.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            raise GnaniAPIError("Text to synthesize cannot be empty.")

        if not self.is_configured():
            raise GnaniAPIError("Gnani API key not configured")

        headers = {
            "X-API-Key-ID": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "text": clean_text[:2000],  # guard against excessively long prompts
            "language": self.language,
            "voice": self.voice,
            "audio_format": self.audio_format,
        }

        try:
            resp = requests.post(
                self.tts_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as e:
            logger.error("Timbre TTS network request failed: %s", e)
            raise GnaniAPIError(f"Timbre TTS request failed: {e}")

        logger.info(
            "Timbre TTS response: status=%d, content_length=%d, container=%s",
            resp.status_code,
            len(resp.content) if resp.content else 0,
            resp.headers.get("x-audio-container", "unknown"),
        )

        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            logger.error("Timbre TTS returned %d: %s", resp.status_code, err)
            raise GnaniAPIError(f"Timbre TTS failed ({resp.status_code}): {err}")

        raw_content = resp.content
        if not raw_content or len(raw_content) == 0:
            raise GnaniAPIError("Empty audio content received from Timbre TTS")

        # If already formatted with standard RIFF or ID3 header, return directly
        if raw_content.startswith(b"RIFF") or raw_content.startswith(b"ID3") or raw_content.startswith(b"\xff\xfb"):
            return raw_content

        # Timbre returns raw 16-bit linear PCM; package it into verified 24 kHz stereo RIFF/WAV
        try:
            sample_rate_int = int(self.sampling_rate)
        except (ValueError, TypeError):
            sample_rate_int = 24000

        wav_bytes = _wrap_pcm_to_wav(raw_content, sample_rate=sample_rate_int, channels=self.channels)
        logger.info(
            "Encapsulated %d raw PCM bytes into %d RIFF WAV bytes (rate=%d, channels=%d)",
            len(raw_content),
            len(wav_bytes),
            sample_rate_int,
            self.channels,
        )
        return wav_bytes
