"""Unit and integration tests for Gnani Evon (30B) reasoning service."""

import unittest
from unittest.mock import patch, MagicMock

from app.services.evon_service import EvonReasoningService, EVON_DEFAULT_MODEL


class TestEvonService(unittest.TestCase):
    def setUp(self):
        self.service = EvonReasoningService()
        self.sample_context = {
            "total_income": 95000.0,
            "total_expenses": 38400.0,
            "balance": 56600.0,
            "categories": ["Rent", "Groceries", "Utilities"],
            "recent_summary": "Rent: ₹20,000.00, Groceries: ₹8,400.00",
            "forecasted_expense": 41500.0
        }

    def test_model_identifier(self):
        """Model identifier should be the official Gnani Evon 30B identifier."""
        self.assertEqual(self.service.model, EVON_DEFAULT_MODEL)
        self.assertEqual(self.service.model, "gnani/gnani-evon-v3.3-30B-A3B")

    def test_is_configured_behavior(self):
        """Check configuration check with and without environment variables."""
        with patch.dict("os.environ", {"GNANI_API_KEY": "test-key-123"}, clear=True):
            svc = EvonReasoningService()
            self.assertTrue(svc.is_configured())

        with patch.dict("os.environ", {}, clear=True):
            svc = EvonReasoningService()
            self.assertFalse(svc.is_configured())

    def test_local_reasoning_english_balance(self):
        """Local Evon reasoning provides accurate answer in English for balance questions."""
        result = self.service._local_evon_reasoning(self.sample_context, "What is my current balance?")
        self.assertEqual(result["status"], "success")
        self.assertIn("Gnani Evon 30B", result["source"])
        self.assertEqual(result["model"], EVON_DEFAULT_MODEL)
        self.assertIn("56,600", result["answer"])

    def test_local_reasoning_english_income(self):
        """Local Evon reasoning provides accurate answer in English for income questions."""
        result = self.service._local_evon_reasoning(self.sample_context, "How much income do I have?")
        self.assertEqual(result["status"], "success")
        self.assertIn("95,000", result["answer"])

    def test_local_reasoning_malayalam_balance(self):
        """Local Evon reasoning responds in Malayalam when query is in Malayalam."""
        malayalam_query = "എന്റെ ബാലൻസ് എത്രയാണ്?"
        result = self.service._local_evon_reasoning(self.sample_context, malayalam_query)
        self.assertEqual(result["status"], "success")
        self.assertIn("Gnani Evon 30B", result["source"])
        self.assertIn("56,600", result["answer"])
        # Malayalam words should be present in the response
        self.assertTrue(any(ord(c) >= 0x0D00 and ord(c) <= 0x0D7F for c in result["answer"]))

    def test_local_reasoning_malayalam_expense(self):
        """Local Evon reasoning handles Malayalam expense queries."""
        malayalam_query = "എന്റെ ആകെ ചിലവ് എത്രയാണ്?"
        result = self.service._local_evon_reasoning(self.sample_context, malayalam_query)
        self.assertEqual(result["status"], "success")
        self.assertIn("38,400", result["answer"])
        self.assertTrue(any(ord(c) >= 0x0D00 and ord(c) <= 0x0D7F for c in result["answer"]))

    def test_local_ml_explanation(self):
        """Local ML explanation synthesizes RandomForest, GradientBoosting, and Isolation Forest."""
        ml_data = {
            "forecasted_next_month_expense": 41250.0,
            "spending_behavior": "Within Budget",
            "risk_level": "Low",
            "savings_rate_percent": 38.5,
            "cold_start": False,
            "budget_overrun_risks": [],
            "unusual_transactions": []
        }
        result = self.service._local_ml_explanation(ml_data)
        self.assertEqual(result["status"], "success")
        self.assertIn("Gnani Evon 30B", result["source"])
        self.assertEqual(result["model"], EVON_DEFAULT_MODEL)
        self.assertIn("41,250", result["explanation"])
        self.assertIn("38.5%", result["explanation"])

    def test_empty_question_handling(self):
        """Empty questions return friendly prompt."""
        result = self.service.answer_financial_question(self.sample_context, "   ")
        self.assertEqual(result["status"], "empty_question")

    @patch("app.services.evon_service.requests.post")
    def test_api_success_mocked(self, mock_post):
        """When Evon endpoint returns successful chat completion, service parses and returns it."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Based on your verified records, your current balance is Rs 56,600.00."
                    }
                }
            ],
            "model": EVON_DEFAULT_MODEL
        }
        mock_post.return_value = mock_resp

        with patch.dict("os.environ", {"GNANI_API_KEY": "vach_test123"}, clear=True):
            svc = EvonReasoningService()
            res = svc.answer_financial_question(self.sample_context, "What is my balance?")
            self.assertEqual(res["status"], "success")
            self.assertIn("56,600.00", res["answer"])
            self.assertEqual(res["model"], EVON_DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()
