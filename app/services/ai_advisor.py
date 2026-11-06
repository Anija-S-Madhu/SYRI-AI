"""
SYRI AI - Unified AI Advisor Service
Orchestrates the full pipeline:
Database Records -> ML Pipeline -> Predictions -> Gnani AI -> Natural-Language Explanation.
"""

from ml.pipeline import predict_user_insights, train_expense_forecaster
from .gnani_service import gnani_service
from .evon_service import evon_service
from ..models.transaction import Transaction
from ..models.category import Category
from ..extensions import db


def get_user_ai_financial_advisory(user_id):
    """
    Executes the full combined pipeline for the authenticated user.
    1. Extracts real database data for user_id.
    2. Runs the independent Scikit-learn ML pipeline.
    3. Feeds predictions to Gnani AI for natural-language contextualization.
    4. Returns a comprehensive intelligence payload.
    """
    # 1. Generate ML predictions & risk insights
    ml_insights = predict_user_insights(user_id)

    # 2. Gnani AI Evon (30B) reasoning contextualization
    try:
        evon_result = evon_service.explain_ml_predictions(ml_insights)
    except Exception:
        evon_result = gnani_service.explain_ml_predictions(ml_insights)

    # 3. Assemble unified payload
    return {
        "user_id": user_id,
        "ml_predictions": {
            "forecasted_next_month_expense": ml_insights["forecasted_next_month_expense"],
            "spending_behavior": ml_insights["spending_behavior"],
            "risk_level": ml_insights["risk_level"],
            "savings_rate_percent": ml_insights["savings_rate_percent"],
            "category_breakdown": ml_insights["category_breakdown"],
            "budget_overrun_risks": ml_insights["budget_overrun_risks"],
            "model_used": ml_insights["model_used"],
            "cold_start": ml_insights.get("cold_start", False),
            "unusual_transactions": ml_insights.get("unusual_transactions", []),
            "benchmark_savings_capacity": ml_insights.get("benchmark_savings_capacity", 0.0),
            "models_active": ml_insights.get("models_active", {
                "model1_savings": "GradientBoosting",
                "model2_expense_forecasting": "RandomForest",
                "model3_anomaly_detection": "Isolation Forest"
            })
        },
        "gnani_explanation": {
            "text": evon_result.get("explanation", ""),
            "source": evon_result.get("source", "Gnani Evon 30B"),
            "status": evon_result.get("status", "success"),
            "model": evon_result.get("model", evon_service.model)
        },
        "financial_summary": {
            "historical_expense": ml_insights["historical_expense"],
            "historical_income": ml_insights["historical_income"],
            "balance": ml_insights["historical_income"] - ml_insights["historical_expense"],
            "transaction_count": ml_insights["transaction_count"]
        }
    }


def handle_user_financial_question(user_id, question):
    """
    Handles a user's conversational question to the AI assistant using only
    their authenticated financial metrics.
    """
    # Gather sanitized financial context
    txs = Transaction.query.filter_by(user_id=user_id).all()
    cats = [c.name for c in Category.query.filter_by(user_id=user_id).all()]

    total_income = sum(float(t.amount) for t in txs if t.type == "income")
    total_expenses = sum(float(t.amount) for t in txs if t.type == "expense")
    balance = total_income - total_expenses

    recent_summary = ", ".join(
        f"{t.description or 'Item'}: ₹{float(t.amount):.2f}"
        for t in sorted(txs, key=lambda x: x.date, reverse=True)[:3]
    ) or "None recorded"

    context = {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "categories": cats,
        "recent_summary": recent_summary
    }

    try:
        return evon_service.answer_financial_question(context, question)
    except Exception:
        return gnani_service.query_financial_assistant(context, question)
