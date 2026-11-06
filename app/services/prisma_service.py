"""Prisma Speech‑to‑Text service.

Implements the official Gnani Prisma STT endpoint:
    POST https://api.vachana.ai/stt/v3
Headers:
    X-API-Key-ID: <api_key>
Multipart form‑data fields:
    audio_file   – the audio file (WAV/MP3/OGG/etc.)
    model        – optional, e.g. "prisma‑v3.0"
    language_code – optional, e.g. "en" or "indic-auto"

The service returns the plain transcript string or raises ``GnaniAPIError``.
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

class GnaniAPIError(RuntimeError):
    """Raised when the Gnani API returns a non‑200 status or an unexpected payload."""

class PrismaSTTService:
    def __init__(self, api_key: Optional[str] = None, stt_url: Optional[str] = None, model: Optional[str] = None, language_code: Optional[str] = None):
        self.api_key = api_key or os.getenv("GNANI_API_KEY", "")
        self.stt_url = stt_url or os.getenv("GNANI_STT_URL", "https://api.vachana.ai/stt/v3")
        self.model = model or os.getenv("GNANI_STT_MODEL", "prisma-v3.0")
        self.language_code = language_code or os.getenv("GNANI_STT_LANGUAGE_CODE", "en-IN")
        self.timeout = int(os.getenv("GNANI_TIMEOUT_SECONDS", "6"))

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your-gnani-api-key-here")

    def transcribe(self, audio_path: str) -> str:
        """Upload *audio_path* and return the transcript.

        The request follows Gnani's official schema – ``audio_file`` is the field name
        for the file, and we also send ``model`` and ``language_code`` as regular form
        data.  On success the JSON response contains a ``transcript`` key.
        """
        if not self.is_configured():
            raise GnaniAPIError("Gnani API key not configured")

        headers = {"X-API-Key-ID": self.api_key}
        files = {"audio_file": (os.path.basename(audio_path), open(audio_path, "rb"), "application/octet-stream")}
        data = {"model": self.model, "language_code": self.language_code}
        try:
            resp = requests.post(self.stt_url, headers=headers, files=files, data=data, timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            logger.error("Prisma STT network request failed: %s", e)
            raise GnaniAPIError(f"Prisma STT request failed: {e}")
        finally:
            # Ensure the file handle is closed regardless of request outcome
            files["audio_file"][1].close()

        if resp.status_code != 200:
            # Attempt to pull a helpful message from the JSON payload
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise GnaniAPIError(f"Prisma STT request failed {resp.status_code}: {err}")

        try:
            payload = resp.json()
            # The official field is "transcript" (some variants use "text")
            transcript = payload.get("transcript")
            if transcript is None:
                transcript = payload.get("text", "")
            return str(transcript).strip()
        except ValueError as e:
            raise GnaniAPIError(f"Invalid JSON from Prisma STT: {e}")
