"""
Unit and integration tests for Scikit-learn ML pipeline, Gnani AI service,
AI Advisor integration, Analytics, and CSV Reports.
"""

import json
from datetime import date
from decimal import Decimal
import unittest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models.user import User
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.budget import Budget
from ml.pipeline import (
    train_expense_forecaster,
    predict_user_insights,
    extract_transactions_df,
    engineer_features
)
from app.services.gnani_service import GnaniAIService
from app.services.ai_advisor import get_user_ai_financial_advisory, handle_user_financial_question


class TestAIMLAnalytics(unittest.TestCase):
    """Test suite covering ML, Gnani AI, Analytics and Reports."""

    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed User 1 (Alice)
        self.user1 = User(username="alice", email="alice@example.com")
        self.user1.set_password("password123")
        db.session.add(self.user1)

        # Seed User 2 (Bob)
        self.user2 = User(username="bob", email="bob@example.com")
        self.user2.set_password("password123")
        db.session.add(self.user2)
        db.session.commit()

        # Seed Categories for Alice
        self.cat_salary = Category(user_id=self.user1.id, name="Salary", type="income")
        self.cat_food = Category(user_id=self.user1.id, name="Food", type="expense")
        self.cat_rent = Category(user_id=self.user1.id, name="Rent", type="expense")
        db.session.add_all([self.cat_salary, self.cat_food, self.cat_rent])

        # Seed Categories for Bob
        self.cat_bob_food = Category(user_id=self.user2.id, name="Food", type="expense")
        db.session.add(self.cat_bob_food)
        db.session.commit()

        # Seed Transactions for Alice
        t1 = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_salary.id,
            type="income",
            amount=Decimal("50000.00"),
            description="Monthly Pay",
            date=date(2026, 11, 1)
        )
        t2 = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="expense",
            amount=Decimal("3500.00"),
            description="Groceries",
            date=date(2026, 11, 2)
        )
        t3 = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_rent.id,
            type="expense",
            amount=Decimal("15000.00"),
            description="Apartment Rent",
            date=date(2026, 11, 3)
        )

        # Seed Transactions for Bob
        t_bob = Transaction(
            user_id=self.user2.id,
            category_id=self.cat_bob_food.id,
            type="expense",
            amount=Decimal("99999.00"),
            description="Bob Super Secret Expense",
            date=date(2026, 11, 4)
        )

        db.session.add_all([t1, t2, t3, t_bob])

        # Seed Budget for Alice
        b1 = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("5000.00"),
            month=11,
            year=2026
        )
        db.session.add(b1)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login_alice(self):
        return self.client.post("/login", data={
            "email": "alice@example.com",
            "password": "password123"
        }, follow_redirects=True)

    def test_ml_pipeline_training_and_metrics(self):
        """Verify Scikit-learn model trains, compares candidates, and outputs valid metrics."""
        metadata = train_expense_forecaster(force_retrain=True)
        self.assertIn("best_model", metadata)
        self.assertIn(metadata["best_model"], ["RandomForest", "GradientBoosting", "Ridge"])
        self.assertIn("evaluation", metadata)
        for model_name, metrics in metadata["evaluation"].items():
            self.assertIn("mae", metrics)
            self.assertIn("rmse", metrics)
            self.assertGreaterEqual(metrics["mae"], 0)

    def test_ml_pipeline_user_predictions_and_isolation(self):
        """Verify ML pipeline computes isolated insights for Alice without leaking Bob's data."""
        insights = predict_user_insights(self.user1.id)
        self.assertEqual(insights["user_id"], self.user1.id)
        self.assertEqual(insights["historical_expense"], 18500.0)  # 3500 + 15000
        self.assertEqual(insights["historical_income"], 50000.0)
        self.assertNotIn("Bob Super Secret Expense", str(insights))
        self.assertGreater(insights["forecasted_next_month_expense"], 0)
        self.assertIn("savings_rate_percent", insights)
        self.assertIn(insights["risk_level"], ["Low", "Moderate", "High", "Critical"])

    def test_gnani_service_fallback_explanation(self):
        """Gnani service gracefully falls back to structured local NLG when no key is set."""
        service = GnaniAIService(api_key="")
        self.assertFalse(service.is_configured())

        ml_data = {
            "forecasted_next_month_expense": 18500.0,
            "savings_rate_percent": 63.0,
            "spending_behavior": "Frugal / High Saver",
            "risk_level": "Low",
            "budget_overrun_risks": []
        }
        res = service.explain_ml_predictions(ml_data)
        self.assertEqual(res["status"], "success")
        self.assertIn("SYRI AI Intelligent Engine", res["source"])
        self.assertIn("18,500.00", res["explanation"])

    def test_ai_advisor_combined_pipeline(self):
        """Full pipeline: DB Data -> ML Model -> Predictions -> Gnani Contextualization."""
        advisory = get_user_ai_financial_advisory(self.user1.id)
        self.assertEqual(advisory["user_id"], self.user1.id)
        self.assertIn("ml_predictions", advisory)
        self.assertIn("gnani_explanation", advisory)
        self.assertIn("financial_summary", advisory)
        self.assertEqual(advisory["financial_summary"]["balance"], 31500.0)

    def test_ai_assistant_question_answering(self):
        """Test conversational Q&A on user's financial metrics."""
        ans = handle_user_financial_question(self.user1.id, "How much did I spend?")
        self.assertIn("answer", ans)
        self.assertIn("18,500.00", ans["answer"])

    def test_analytics_page_renders_for_logged_in_user(self):
        """Analytics page loads successfully with charts, forecasts, and AI advisor."""
        self.login_alice()
        res = self.client.get("/analytics")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Financial Analytics", res.data)
        self.assertIn(b"categoryChart", res.data)
        self.assertIn(b"AI Financial Advisory", res.data)

    def test_reports_page_and_csv_export(self):
        """Reports page loads and CSV export streams Alice's transactions only."""
        self.login_alice()
        res_rep = self.client.get("/reports")
        self.assertEqual(res_rep.status_code, 200)
        self.assertIn(b"Export CSV Statement", res_rep.data)

        res_csv = self.client.get("/reports/export-csv")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, "text/csv")
        csv_text = res_csv.data.decode("utf-8")
        self.assertIn("Monthly Pay", csv_text)
        self.assertIn("Groceries", csv_text)
        self.assertIn("Apartment Rent", csv_text)
        # Ensure Bob's data is strictly NOT in Alice's CSV export
        self.assertNotIn("Bob Super Secret Expense", csv_text)

    def test_analytics_api_endpoints(self):
        """Verify /api/analytics and /api/ai/ask JSON endpoints."""
        self.login_alice()
        # GET /api/analytics
        res = self.client.get("/api/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("ml_predictions", data)
        self.assertIn("gnani_explanation", data)

        # POST /api/ai/ask
        res_ask = self.client.post("/api/ai/ask", json={"question": "What is my balance?"})
        self.assertEqual(res_ask.status_code, 200)
        ans_data = res_ask.get_json()
        self.assertIn("answer", ans_data)
        self.assertIn("31,500.00", ans_data["answer"])

        # Retrain endpoint
        res_retrain = self.client.post("/api/ml/retrain")
        self.assertEqual(res_retrain.status_code, 200)
        retrain_data = res_retrain.get_json()
        self.assertIn("metadata", retrain_data)


if __name__ == "__main__":
    unittest.main()
