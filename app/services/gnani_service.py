"""
Gnani AI API Service
Handles integration with Gnani AI for natural-language financial intelligence,
personalized spending explanations, and contextualizing Scikit-learn ML predictions.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

GNANI_API_KEY = os.environ.get("GNANI_API_KEY", "")
GNANI_API_URL = os.environ.get("GNANI_API_URL", "https://api.gnani.ai/v1/chat/completions")
TIMEOUT_SECONDS = int(os.environ.get("GNANI_TIMEOUT_SECONDS", "6"))


class GnaniAIService:
    """Service to communicate with Gnani AI API with robust offline fallbacks."""

    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key or os.environ.get("GNANI_API_KEY", "")
        self.api_url = api_url or os.environ.get("GNANI_API_URL", "https://api.gnani.ai/v1/chat/completions")

    def is_configured(self):
        """Check if an API key is configured."""
        return bool(self.api_key and self.api_key.strip() and self.api_key != "your-gnani-api-key-here")

    def explain_ml_predictions(self, ml_data):
        """
        Takes machine learning predictions and sends sanitized context to Gnani AI
        to generate an intuitive, natural-language explanation.
        """
        # Build sanitized prompt WITHOUT personal identity (PII-safe)
        forecast = ml_data.get("forecasted_next_month_expense", 0.0)
        savings_rate = ml_data.get("savings_rate_percent", 0.0)
        behavior = ml_data.get("spending_behavior", "Unknown")
        risk = ml_data.get("risk_level", "Unknown")
        overrun_list = ml_data.get("budget_overrun_risks", [])

        overrun_details = []
        for o in overrun_list:
            if o.get("overrun_likely"):
                overrun_details.append(
                    f"- {o.get('category')}: Budget ₹{o.get('budget')}, Projected ₹{o.get('projected_total')} (Exceeds by ₹{round(o.get('projected_total') - o.get('budget'), 2)})"
                )

        overrun_text = "\n".join(overrun_details) if overrun_details else "No current budget overruns projected."

        prompt = (
            "You are SYRI AI's smart financial advisor powered by Gnani AI. "
            "Analyze the following Scikit-learn machine learning outputs for the user's financial profile:\n"
            f"- Next Month Forecasted Expenses: ₹{forecast:.2f}\n"
            f"- Current Savings Rate: {savings_rate}%\n"
            f"- Spending Behavior Classification: {behavior}\n"
            f"- Financial Risk Level: {risk}\n"
            f"- Budget Overrun Alerts:\n{overrun_text}\n\n"
            "Provide a concise, encouraging 3-point explanation:\n"
            "1. What the ML expense prediction means for their budget.\n"
            "2. Specific advice to address any high-risk categories or overruns.\n"
            "3. One actionable tip to improve their savings rate."
        )

        if not self.is_configured():
            logger.info("Gnani API key not configured. Using local intelligent explanation engine.")
            return self._local_ml_explanation(ml_data)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gnani-chat-v1",
                "messages": [
                    {"role": "system", "content": "You are a professional, friendly personal financial advisor."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.6,
                "max_tokens": 400
            }

            response = requests.post(self.api_url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
            if response.status_code == 200:
                result = response.json()
                text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    return {
                        "explanation": text.strip(),
                        "source": "Gnani AI",
                        "status": "success"
                    }

            logger.warning("Gnani AI API returned status %s. Falling back to local engine.", response.status_code)
            return self._local_ml_explanation(ml_data)

        except (requests.RequestException, Exception) as e:
            logger.warning("Gnani AI API request failed (%s). Falling back to local engine.", e)
            return self._local_ml_explanation(ml_data)

    def query_financial_assistant(self, user_context, user_question):
        """
        Answers a user's natural-language financial question based on their actual metrics.
        """
        if not user_question or not user_question.strip():
            return {"answer": "Please ask a question about your finances.", "source": "SYRI AI"}

        if not self.is_configured():
            return self._local_qa_fallback(user_context, user_question)

        prompt = (
            "You are SYRI AI's financial assistant. Answer the user's question accurately using ONLY "
            f"their verified financial data below:\n"
            f"- Total Income: ₹{user_context.get('total_income', 0.0):.2f}\n"
            f"- Total Expenses: ₹{user_context.get('total_expenses', 0.0):.2f}\n"
            f"- Available Balance: ₹{user_context.get('balance', 0.0):.2f}\n"
            f"- Active Categories: {', '.join(user_context.get('categories', []))}\n"
            f"- Recent Expense Summary: {user_context.get('recent_summary', 'None')}\n\n"
            f"User Question: \"{user_question}\"\n\n"
            "Keep the answer concise, practical, and helpful."
        )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gnani-chat-v1",
                "messages": [
                    {"role": "system", "content": "You are a concise, helpful personal finance assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.5,
                "max_tokens": 250
            }
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
            if response.status_code == 200:
                result = response.json()
                text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if text:
                    return {"answer": text.strip(), "source": "Gnani AI", "status": "success"}

            return self._local_qa_fallback(user_context, user_question)

        except Exception as e:
            logger.warning("Gnani API query failed: %s. Using local fallback.", e)
            return self._local_qa_fallback(user_context, user_question)

    def _local_ml_explanation(self, ml_data):
        """Intelligent rule-based explanation when external API is offline or unconfigured."""
        forecast = ml_data.get("forecasted_next_month_expense", 0.0)
        savings_rate = ml_data.get("savings_rate_percent", 0.0)
        behavior = ml_data.get("spending_behavior", "Balanced Spender")
        risk = ml_data.get("risk_level", "Moderate")
        overruns = [o for o in ml_data.get("budget_overrun_risks", []) if o.get("overrun_likely")]

        lines = [
            f"**Machine Learning Forecast Analysis:**",
            f"• Our predictive model estimates your spending for next month will be approximately **₹{forecast:,.2f}**.",
            f"• Your current savings rate is **{savings_rate}%**, classifying your financial profile as **{behavior}** ({risk} risk)."
        ]

        if overruns:
            lines.append("• **Budget Alert:** We identified projected overruns in:")
            for o in overruns:
                diff = o.get("projected_total", 0.0) - o.get("budget", 0.0)
                lines.append(f"   - **{o.get('category')}**: Projected to exceed limit by **₹{diff:,.2f}**.")
            lines.append("• **Actionable Recommendation:** Consider curbing non-essential expenses in flagged categories immediately to bring spending back within your targets.")
        else:
            lines.append("• **Budget Status:** All of your tracked categories are currently within healthy spending boundaries.")
            lines.append("• **Actionable Recommendation:** To grow wealth faster, try channeling at least 15–20% of monthly income directly into emergency savings or low-cost index investments.")

        return {
            "explanation": "\n".join(lines),
            "source": "SYRI AI Intelligent Engine (Local)",
            "status": "success"
        }

    def _local_qa_fallback(self, context, question):
        """Rule-based question answering on actual user financials when offline."""
        q = question.lower()
        income = context.get("total_income", 0.0)
        expense = context.get("total_expenses", 0.0)
        balance = context.get("balance", 0.0)

        if "how much" in q and ("spend" in q or "expense" in q):
            return {
                "answer": f"According to your records, you have spent a total of ₹{expense:,.2f}.",
                "source": "SYRI AI Engine"
            }
        elif "income" in q or "earn" in q or "salary" in q:
            return {
                "answer": f"Your recorded total income is ₹{income:,.2f}.",
                "source": "SYRI AI Engine"
            }
        elif "balance" in q or "remain" in q or "left" in q:
            return {
                "answer": f"Your current available balance is ₹{balance:,.2f} (Income ₹{income:,.2f} minus Expenses ₹{expense:,.2f}).",
                "source": "SYRI AI Engine"
            }
        elif "budget" in q:
            return {
                "answer": f"You can manage and monitor your monthly spending limits from the Budgets page.",
                "source": "SYRI AI Engine"
            }
        else:
            return {
                "answer": f"Based on your profile, you have recorded ₹{income:,.2f} in income and ₹{expense:,.2f} in expenses, leaving ₹{balance:,.2f} available. Keep logging all your expenses to enhance forecast accuracy.",
                "source": "SYRI AI Engine"
            }


gnani_service = GnaniAIService()
