"""Tests for Gnani Voice APIs: Prisma Speech-to-Text and Timbre Text-to-Speech."""

import io
import unittest
from unittest.mock import patch, MagicMock

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models.user import User


class TestVoiceAPI(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test user
        self.user = User(username="voice_tester", email="voice@syri.ai")
        self.user.set_password("SecurePass123!")
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user.id)
            sess["_fresh"] = True

    # ----------------------------------------------------
    # Authentication & Access Control
    # ----------------------------------------------------
    def test_voice_transcribe_requires_login(self):
        """Unauthenticated requests to /api/ai/voice/transcribe must be redirected to login."""
        res = self.client.post("/api/ai/voice/transcribe")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_voice_speak_requires_login(self):
        """Unauthenticated requests to /api/ai/voice/speak must be redirected to login."""
        res = self.client.post("/api/ai/voice/speak", json={"text": "Hello"})
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    # ----------------------------------------------------
    # Prisma STT Endpoint Validation & Functionality
    # ----------------------------------------------------
    def test_transcribe_missing_file(self):
        """Missing audio_file payload returns 400 Bad Request."""
        self._login()
        res = self.client.post("/api/ai/voice/transcribe", data={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("No audio_file provided", res.get_json()["error"])

    def test_transcribe_empty_file(self):
        """Empty audio file returns 400 Bad Request."""
        self._login()
        data = {"audio_file": (io.BytesIO(b""), "recording.wav")}
        res = self.client.post("/api/ai/voice/transcribe", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_transcribe_unsupported_extension(self):
        """Unsupported file extension returns 400 Bad Request."""
        self._login()
        data = {"audio_file": (io.BytesIO(b"dummy data"), "malicious.exe")}
        res = self.client.post("/api/ai/voice/transcribe", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Unsupported audio format", res.get_json()["error"])

    @patch("app.services.prisma_service.requests.post")
    def test_transcribe_success_mocked(self, mock_post):
        """Mocked successful Prisma STT response returns 200 with transcript."""
        self._login()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "transcript": "How much did I spend on groceries?",
            "model": "prisma-v3.0"
        }
        mock_post.return_value = mock_resp

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-valid-key" if k == "GNANI_API_KEY" else d):
            data = {"audio_file": (io.BytesIO(b"RIFFdummywavdata"), "test.wav")}
            res = self.client.post("/api/ai/voice/transcribe", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 200)
            json_data = res.get_json()
            self.assertEqual(json_data["transcript"], "How much did I spend on groceries?")

    @patch("app.services.prisma_service.requests.post")
    def test_transcribe_api_error_returns_502(self, mock_post):
        """Prisma API non-200 returns 502 with error details."""
        self._login()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "Gnani internal server error"}
        mock_post.return_value = mock_resp

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-valid-key" if k == "GNANI_API_KEY" else d):
            data = {"audio_file": (io.BytesIO(b"RIFFdummywavdata"), "test.wav")}
            res = self.client.post("/api/ai/voice/transcribe", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 502)
            self.assertIn("Speech transcription error", res.get_json()["error"])

    # ----------------------------------------------------
    # Timbre TTS Endpoint Validation & Functionality
    # ----------------------------------------------------
    def test_speak_missing_text(self):
        """Empty or missing text returns 400 Bad Request."""
        self._login()
        res = self.client.post("/api/ai/voice/speak", json={"text": ""})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Text parameter is required", res.get_json()["error"])

    def test_speak_too_long_text(self):
        """Text exceeding length limit returns 400 Bad Request."""
        self._login()
        res = self.client.post("/api/ai/voice/speak", json={"text": "A" * 2500})
        self.assertEqual(res.status_code, 400)
        self.assertIn("character limit", res.get_json()["error"])

    @patch("app.services.timbre_service.requests.post")
    def test_speak_success_mocked(self, mock_post):
        """Mocked successful Timbre TTS response returns 200 with audio/wav."""
        self._login()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        mock_post.return_value = mock_resp

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-valid-key" if k == "GNANI_API_KEY" else d):
            res = self.client.post("/api/ai/voice/speak", json={"text": "You spent 500 rupees on food."})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content_type, "audio/wav")
            self.assertTrue(res.data.startswith(b"RIFF"))

    @patch("app.services.timbre_service.requests.post")
    def test_speak_empty_audio_returns_502(self, mock_post):
        """Empty audio content from Timbre returns 502 Bad Gateway."""
        self._login()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""
        mock_post.return_value = mock_resp

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-valid-key" if k == "GNANI_API_KEY" else d):
            res = self.client.post("/api/ai/voice/speak", json={"text": "Hello"})
            self.assertEqual(res.status_code, 502)
            self.assertIn("Empty audio content", res.get_json()["error"])

    @patch("app.services.timbre_service.requests.post")
    def test_speak_timeout_returns_502(self, mock_post):
        """Network timeout during Timbre request returns 502 Bad Gateway."""
        import requests
        self._login()
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-valid-key" if k == "GNANI_API_KEY" else d):
            res = self.client.post("/api/ai/voice/speak", json={"text": "Hello"})
            self.assertEqual(res.status_code, 502)
            self.assertIn("Voice synthesis error", res.get_json()["error"])

    @patch("app.services.timbre_service.requests.post")
    def test_speak_api_error_returns_502(self, mock_post):
        """Timbre API non-200 returns 502 with error details."""
        self._login()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"success": False, "message": "Voice synthesis failed"}
        mock_post.return_value = mock_resp

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-valid-key" if k == "GNANI_API_KEY" else d):
            res = self.client.post("/api/ai/voice/speak", json={"text": "Test speech synthesis"})
            self.assertEqual(res.status_code, 502)
            self.assertIn("Voice synthesis error", res.get_json()["error"])

    # ----------------------------------------------------
    # Unified Three-Model Voice Workflow: /api/ai/voice/ask
    # (Prisma STT -> Evon 30B -> Timbre TTS)
    # ----------------------------------------------------
    def test_voice_ask_requires_login(self):
        """Unauthenticated requests to /api/ai/voice/ask must be redirected to login."""
        res = self.client.post("/api/ai/voice/ask")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_voice_ask_missing_file(self):
        """Missing audio_file payload in /api/ai/voice/ask returns 400 Bad Request."""
        self._login()
        res = self.client.post("/api/ai/voice/ask", data={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("No audio_file provided", res.get_json()["error"])

    @patch("app.services.timbre_service.TimbreTTSService.synthesize")
    @patch("app.services.prisma_service.PrismaSTTService.transcribe")
    def test_voice_ask_full_three_model_pipeline(self, mock_transcribe, mock_synthesize):
        """Verify the full 3-model chain:
        1. Prisma STT transcribes audio to question text.
        2. Evon 30B generates financial reasoning response.
        3. Timbre TTS synthesizes response into audio bytes.
        """
        self._login()
        mock_transcribe.return_value = "What is my current balance?"
        mock_synthesize.return_value = b"RIFFtestwavbytes"

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-key" if k == "GNANI_API_KEY" else d):
            data = {"audio_file": (io.BytesIO(b"dummyvoiceaudio"), "user_audio.wav")}
            res = self.client.post("/api/ai/voice/ask", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 200)

            json_data = res.get_json()
            self.assertEqual(json_data["status"], "success")
            self.assertEqual(json_data["transcript"], "What is my current balance?")
            self.assertIn("answer", json_data)
            self.assertIn("evon", json_data["model"].lower())
            self.assertTrue(json_data["has_audio"])
            self.assertIsNotNone(json_data["audio_base64"])

    @patch("app.services.timbre_service.TimbreTTSService.synthesize")
    @patch("app.services.prisma_service.PrismaSTTService.transcribe")
    def test_voice_ask_malayalam_query(self, mock_transcribe, mock_synthesize):
        """Verify 3-model chain handles Malayalam queries correctly."""
        self._login()
        mock_transcribe.return_value = "എന്റെ ബാലൻസ് എത്രയാണ്?"
        mock_synthesize.return_value = b"RIFFmalayalamwavbytes"

        with patch("os.getenv", side_effect=lambda k, d=None: "mock-key" if k == "GNANI_API_KEY" else d):
            data = {"audio_file": (io.BytesIO(b"dummyvoiceaudio"), "user_malayalam.wav")}
            res = self.client.post("/api/ai/voice/ask", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 200)

            json_data = res.get_json()
            self.assertEqual(json_data["status"], "success")
            self.assertEqual(json_data["transcript"], "എന്റെ ബാലൻസ് എത്രയാണ്?")
            self.assertIn("answer", json_data)
            self.assertTrue(json_data["has_audio"])


if __name__ == "__main__":
    unittest.main()
