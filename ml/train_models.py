"""
SYRI AI - Machine Learning Training and Evaluation Pipeline
Trains, compares, and serializes independent models:
1. Model 1 (Savings Analysis): Ridge vs RandomForest vs GradientBoosting on Dataset A.
2. Model 2 (Expense Forecasting): Chronological split (2015-2017 train, 2018 test) on Dataset B.
3. Model 3 (Unusual Expense Detection): Isolation Forest + Statistical bounds on Dataset B.
Saves models with Joblib to ml/saved_models/ and saves evaluation metadata.
"""

import os
import json
import logging
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
MODELS_DIR = os.path.join(BASE_DIR, "ml", "saved_models")
os.makedirs(MODELS_DIR, exist_ok=True)

SAVINGS_MODEL_FILE = os.path.join(MODELS_DIR, "savings_model.joblib")
EXPENSE_MODEL_FILE = os.path.join(MODELS_DIR, "expense_forecast_model.joblib")
ANOMALY_MODEL_FILE = os.path.join(MODELS_DIR, "anomaly_detector.joblib")
METADATA_FILE = os.path.join(MODELS_DIR, "evaluation_metadata.json")


def train_model1_savings():
    """
    Train Model 1: Financial Savings Analysis on Dataset A.
    Target: Desired_Savings (Savings Capacity in INR).
    Features: Demographics and raw expense breakdown.
    Strictly NO target leakage (No Disposable_Income, No Desired_Savings_Percentage, No Potential_Savings_*).
    """
    logger.info("--- TRAINING MODEL 1: SAVINGS CAPACITY (Dataset A) ---")
    data_path = os.path.join(PROCESSED_DIR, "personal_finance_clean.csv")
    if not os.path.exists(data_path):
        from ml.preprocess import preprocess_personal_finance
        preprocess_personal_finance()

    df = pd.read_csv(data_path)

    target_col = "Desired_Savings"
    y = df[target_col].values

    cat_cols = ["Occupation", "City_Tier"]
    num_cols = [
        "Age", "Dependents", "Rent", "Loan_Repayment", "Insurance",
        "Groceries", "Transport", "Eating_Out", "Entertainment",
        "Utilities", "Healthcare", "Education", "Miscellaneous",
        "Total_Expenses", "Expense_to_Income_Ratio"
    ]
    feature_cols = cat_cols + num_cols
    X = df[feature_cols]

    # 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    # Preprocessing transformer
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore"), cat_cols)
        ]
    )

    candidate_algorithms = {
        "Ridge": Ridge(alpha=1.0),
        "RandomForest": RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
    }

    evaluations = {}
    best_name = None
    best_pipe = None
    best_mae = float("inf")

    for name, algo in candidate_algorithms.items():
        pipe = Pipeline(steps=[
            ("preprocessor", preprocessor),
            ("regressor", algo)
        ])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)

        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = float(r2_score(y_test, y_pred))

        evaluations[name] = {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2": round(r2, 4)
        }
        logger.info("Model 1 [%s]: MAE=%.2f, RMSE=%.2f, R2=%.4f", name, mae, rmse, r2)

        if mae < best_mae:
            best_mae = mae
            best_name = name
            best_pipe = pipe

    # Feature Importance (if best is tree-based or linear)
    regressor = best_pipe.named_steps["regressor"]
    feature_names = num_cols.copy()
    cat_encoder = best_pipe.named_steps["preprocessor"].named_transformers_["cat"]
    cat_encoded_names = list(cat_encoder.get_feature_names_out(cat_cols))
    all_features = feature_names + cat_encoded_names

    importances = {}
    if hasattr(regressor, "feature_importances_"):
        for fname, imp in zip(all_features, regressor.feature_importances_):
            importances[fname] = round(float(imp), 4)
    elif hasattr(regressor, "coef_"):
        for fname, coef in zip(all_features, regressor.coef_):
            importances[fname] = round(float(coef), 4)

    # Save model bundle
    bundle = {
        "pipeline": best_pipe,
        "best_algorithm": best_name,
        "features": feature_cols,
        "evaluations": evaluations,
        "feature_importances": importances,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "train_samples": len(X_train),
        "test_samples": len(X_test)
    }
    joblib.dump(bundle, SAVINGS_MODEL_FILE)
    logger.info("Saved Model 1 bundle to %s (Best: %s)", SAVINGS_MODEL_FILE, best_name)

    return {
        "model": "Model 1 - Savings Analysis",
        "best_algorithm": best_name,
        "evaluations": evaluations,
        "top_features": sorted(importances.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    }


def train_model2_expense_forecasting():
    """
    Train Model 2: Time-Aware Expense Forecasting on Dataset B.
    Target: daily_amount (Daily household expenditure in INR).
    Features: Temporal calendar features and backward-looking rolling statistics.
    Split: Strictly Chronological (2015-01-01 to 2017-12-31 Train, 2018-01-01 to 2018-12-09 Test).
    Zero temporal lookahead leakage.
    """
    logger.info("--- TRAINING MODEL 2: TIME-AWARE EXPENSE FORECASTING (Dataset B) ---")
    data_path = os.path.join(PROCESSED_DIR, "daily_expenses_aggregated.csv")
    if not os.path.exists(data_path):
        from ml.preprocess import preprocess_household_transactions
        preprocess_household_transactions()

    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    feature_cols = [
        "day_of_week", "is_weekend", "day_of_month", "month",
        "rolling_7d_avg", "rolling_30d_avg", "lag_1d", "lag_7d"
    ]
    target_col = "daily_amount"

    # Strictly Chronological Split
    split_date = pd.to_datetime("2018-01-01")
    train_mask = df["date"] < split_date
    test_mask = df["date"] >= split_date

    X_train = df.loc[train_mask, feature_cols]
    y_train = df.loc[train_mask, target_col].values
    X_test = df.loc[test_mask, feature_cols]
    y_test = df.loc[test_mask, target_col].values

    preprocessor = StandardScaler()

    candidate_algorithms = {
        "Ridge": Ridge(alpha=10.0),
        "RandomForest": RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=80, max_depth=3, learning_rate=0.08, random_state=42)
    }

    evaluations = {}
    best_name = None
    best_pipe = None
    best_mae = float("inf")

    for name, algo in candidate_algorithms.items():
        pipe = Pipeline(steps=[
            ("scaler", preprocessor),
            ("regressor", algo)
        ])
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)
        y_pred = np.clip(y_pred, 0, None)

        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        r2 = float(r2_score(y_test, y_pred))

        evaluations[name] = {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2": round(r2, 4)
        }
        logger.info("Model 2 [%s]: MAE=%.2f, RMSE=%.2f, R2=%.4f (Chronological test)", name, mae, rmse, r2)

        if mae < best_mae:
            best_mae = mae
            best_name = name
            best_pipe = pipe

    # Save model bundle
    bundle = {
        "pipeline": best_pipe,
        "best_algorithm": best_name,
        "features": feature_cols,
        "evaluations": evaluations,
        "train_period": f"{df.loc[train_mask, 'date'].min().strftime('%Y-%m-%d')} to {df.loc[train_mask, 'date'].max().strftime('%Y-%m-%d')}",
        "test_period": f"{df.loc[test_mask, 'date'].min().strftime('%Y-%m-%d')} to {df.loc[test_mask, 'date'].max().strftime('%Y-%m-%d')}",
        "train_samples": int(train_mask.sum()),
        "test_samples": int(test_mask.sum()),
        "trained_at": datetime.now(timezone.utc).isoformat()
    }
    joblib.dump(bundle, EXPENSE_MODEL_FILE)
    logger.info("Saved Model 2 bundle to %s (Best: %s)", EXPENSE_MODEL_FILE, best_name)

    return {
        "model": "Model 2 - Expense Forecasting",
        "best_algorithm": best_name,
        "evaluations": evaluations,
        "train_period": bundle["train_period"],
        "test_period": bundle["test_period"],
        "train_samples": bundle["train_samples"],
        "test_samples": bundle["test_samples"]
    }


def train_model3_anomaly_detection():
    """
    Train Model 3: Unusual Expense Detection on Dataset B.
    Uses Isolation Forest to detect statistical anomalies in transaction values.
    Calculates category-specific IQR and 95th percentile bounds.
    """
    logger.info("--- TRAINING MODEL 3: UNUSUAL EXPENSE ANOMALY DETECTOR (Dataset B) ---")
    data_path = os.path.join(PROCESSED_DIR, "household_transactions_clean.csv")
    if not os.path.exists(data_path):
        from ml.preprocess import preprocess_household_transactions
        preprocess_household_transactions()

    df = pd.read_csv(data_path)
    expense_df = df[df["type"] == "expense"].copy()

    # Log amount to compress extreme skewness
    expense_df["log_amount"] = np.log1p(expense_df["amount"])

    # Features: log amount, day of week, is_weekend
    X = expense_df[["log_amount", "day_of_week", "is_weekend"]].values

    # Isolation Forest (3% contamination target)
    iso_forest = IsolationForest(contamination=0.03, random_state=42)
    iso_forest.fit(X)

    # Compute category-specific 95th percentile thresholds
    cat_thresholds = {}
    for cat, group in expense_df.groupby("category_clean"):
        cat_thresholds[cat] = {
            "median": round(float(group["amount"].median()), 2),
            "q75": round(float(group["amount"].quantile(0.75)), 2),
            "p95": round(float(group["amount"].quantile(0.95)), 2),
            "max": round(float(group["amount"].max()), 2),
            "count": int(len(group))
        }

    preds = iso_forest.predict(X)
    anomaly_count = int((preds == -1).sum())

    bundle = {
        "model": iso_forest,
        "category_thresholds": cat_thresholds,
        "anomaly_count_training": anomaly_count,
        "contamination": 0.03,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(expense_df)
    }
    joblib.dump(bundle, ANOMALY_MODEL_FILE)
    logger.info(
        "Saved Model 3 bundle to %s (Detected %d anomalies in %d historical expenses)",
        ANOMALY_MODEL_FILE, anomaly_count, len(expense_df)
    )

    return {
        "model": "Model 3 - Unusual Expense Anomaly Detector",
        "algorithm": "Isolation Forest + Category IQR Bounds",
        "contamination": 0.03,
        "historical_anomalies_flagged": anomaly_count,
        "total_expenses_analyzed": len(expense_df)
    }


def train_all_models():
    """Executes training of all 3 models and compiles evaluation metadata."""
    m1 = train_model1_savings()
    m2 = train_model2_expense_forecasting()
    m3 = train_model3_anomaly_detection()

    all_metadata = {
        "version": "2.0.0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model1_savings": m1,
        "model2_expense_forecasting": m2,
        "model3_anomaly_detection": m3,
        "notes": [
            "Model 1 trained on Dataset A with strict zero-leakage feature isolation.",
            "Model 2 trained on Dataset B with strict chronological splitting (2015-2017 train, 2018 test).",
            "Model 3 trained on Dataset B using Isolation Forest for statistical anomaly detection.",
            "Artificial bootstrap generator completely removed."
        ]
    }

    with open(METADATA_FILE, "w") as f:
        json.dump(all_metadata, f, indent=2)

    logger.info("Saved consolidated evaluation metadata to %s", METADATA_FILE)
    return all_metadata


if __name__ == "__main__":
    meta = train_all_models()
    print("\n--- MODEL TRAINING & EVALUATION REPORT ---")
    print(json.dumps(meta, indent=2))
