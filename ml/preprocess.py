"""
SYRI AI - Data Preprocessing Pipeline
Preprocesses raw public benchmark datasets into clean, leakage-free datasets.
- Dataset A: data/raw/indian_personal_finance.csv -> data/processed/personal_finance_clean.csv
- Dataset B: data/raw/Daily Household Transactions.csv -> data/processed/household_transactions_clean.csv
"""

import os
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)


def preprocess_personal_finance(
    raw_path=os.path.join(RAW_DIR, "indian_personal_finance.csv"),
    processed_path=os.path.join(PROCESSED_DIR, "personal_finance_clean.csv")
):
    """
    Cleans and preprocesses Dataset A (Indian Personal Finance).
    Strictly eliminates target leakage:
    - Drops 'Desired_Savings_Percentage', 'Disposable_Income', and all 'Potential_Savings_*' columns.
    """
    logger.info("Starting preprocessing for Dataset A: %s", raw_path)
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw file not found: {raw_path}")

    df = pd.read_csv(raw_path)
    orig_shape = df.shape

    # 1. Deduplication
    df = df.drop_duplicates().reset_index(drop=True)

    # 2. String trimming
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()

    # 3. Categorical standardizations
    df["Occupation"] = df["Occupation"].replace({"Self_Employed": "Self-Employed"})
    df["City_Tier"] = df["City_Tier"].replace({"Tier_1": "Tier-1", "Tier_2": "Tier-2", "Tier_3": "Tier-3"})

    # 4. Expense columns
    expense_cols = [
        "Rent", "Loan_Repayment", "Insurance", "Groceries", "Transport",
        "Eating_Out", "Entertainment", "Utilities", "Healthcare",
        "Education", "Miscellaneous"
    ]

    # Non-negative validation
    for col in ["Income"] + expense_cols + ["Desired_Savings"]:
        df[col] = df[col].clip(lower=0.0)

    # 5. Feature Engineering: Total non-discretionary vs discretionary expense
    total_expenses = df[expense_cols].sum(axis=1)
    df["Total_Expenses"] = total_expenses
    df["Expense_to_Income_Ratio"] = (total_expenses / (df["Income"] + 1e-6)).clip(0.0, 5.0)

    # 6. Target Leakage Prevention:
    # Explicitly drop Disposable_Income, Desired_Savings_Percentage, and Potential_Savings_*
    leakage_cols = [
        "Desired_Savings_Percentage",
        "Disposable_Income",
        "Potential_Savings_Groceries",
        "Potential_Savings_Transport",
        "Potential_Savings_Eating_Out",
        "Potential_Savings_Entertainment",
        "Potential_Savings_Utilities",
        "Potential_Savings_Healthcare",
        "Potential_Savings_Education",
        "Potential_Savings_Miscellaneous"
    ]
    existing_leakage = [c for c in leakage_cols if c in df.columns]
    df = df.drop(columns=existing_leakage)

    # 7. Save cleaned dataset
    df.to_csv(processed_path, index=False)
    logger.info(
        "Dataset A preprocessed successfully: %s -> %s (Saved %d rows, %d cols). Dropped %d leakage columns.",
        orig_shape, df.shape, df.shape[0], df.shape[1], len(existing_leakage)
    )
    return df


def preprocess_household_transactions(
    raw_path=os.path.join(RAW_DIR, "Daily Household Transactions.csv"),
    processed_path=os.path.join(PROCESSED_DIR, "household_transactions_clean.csv"),
    daily_path=os.path.join(PROCESSED_DIR, "daily_expenses_aggregated.csv"),
    monthly_path=os.path.join(PROCESSED_DIR, "monthly_expenses_aggregated.csv")
):
    """
    Cleans and preprocesses Dataset B (Daily Household Transactions).
    - Removes 9 duplicates
    - Parses dates
    - Standardizes categories and transaction flow types
    - Produces transaction-level, daily-aggregated, and monthly-aggregated datasets
    """
    logger.info("Starting preprocessing for Dataset B: %s", raw_path)
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw file not found: {raw_path}")

    df = pd.read_csv(raw_path)
    orig_count = len(df)

    # 1. Deduplication
    df = df.drop_duplicates().reset_index(drop=True)
    dedup_count = len(df)

    # 2. Date parsing
    df["Date"] = pd.to_datetime(df["Date"], format="mixed", errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    # 3. Text cleaning
    for col in ["Mode", "Category", "Subcategory", "Note", "Income/Expense", "Currency"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 4. Standardize Type
    type_map = {
        "Expense": "expense",
        "Income": "income",
        "Transfer-Out": "transfer_out"
    }
    df["type"] = df["Income/Expense"].map(type_map).fillna("expense")

    # 5. Clean Amount
    df["amount"] = pd.to_numeric(df["Amount"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df = df.dropna(subset=["amount"])
    df["amount"] = df["amount"].clip(lower=0.01)

    # 6. Category mapping & standardizing
    cat_cleaning = {
        "subscription": "Subscriptions",
        "Food": "Food & Dining",
        "Transportation": "Transportation",
        "Household": "Household & Utilities",
        "Health": "Healthcare",
        "Apparel": "Shopping & Apparel",
        "Salary": "Salary & Income",
        "Investment": "Investments",
        "Gift": "Gifts & Donations",
        "Other": "Other"
    }
    df["category_clean"] = df["Category"].replace(cat_cleaning)

    # 7. Date features
    df["day_of_month"] = df["Date"].dt.day
    df["day_of_week"] = df["Date"].dt.day_of_week
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["month"] = df["Date"].dt.month
    df["year"] = df["Date"].dt.year
    df["year_month"] = df["Date"].dt.to_period("M").astype(str)

    # Save transaction-level clean file
    df.to_csv(processed_path, index=False)

    # 8. Aggregate Daily Expenses (for Time-Series Forecasting Model 2)
    expense_mask = df["type"] == "expense"
    daily_expenses = df[expense_mask].groupby(df["Date"].dt.date).agg(
        daily_amount=("amount", "sum"),
        tx_count=("amount", "count")
    ).reset_index()
    daily_expenses["date"] = pd.to_datetime(daily_expenses["Date"])
    daily_expenses["day_of_week"] = daily_expenses["date"].dt.day_of_week
    daily_expenses["is_weekend"] = daily_expenses["day_of_week"].isin([5, 6]).astype(int)
    daily_expenses["day_of_month"] = daily_expenses["date"].dt.day
    daily_expenses["month"] = daily_expenses["date"].dt.month
    daily_expenses["year"] = daily_expenses["date"].dt.year

    # Rolling statistics strictly looking backwards (no lookahead leakage)
    daily_expenses = daily_expenses.sort_values("date").reset_index(drop=True)
    daily_expenses["rolling_7d_avg"] = daily_expenses["daily_amount"].shift(1).rolling(7, min_periods=1).mean().fillna(daily_expenses["daily_amount"].median())
    daily_expenses["rolling_30d_avg"] = daily_expenses["daily_amount"].shift(1).rolling(30, min_periods=1).mean().fillna(daily_expenses["daily_amount"].median())
    daily_expenses["lag_1d"] = daily_expenses["daily_amount"].shift(1).fillna(daily_expenses["daily_amount"].median())
    daily_expenses["lag_7d"] = daily_expenses["daily_amount"].shift(7).fillna(daily_expenses["daily_amount"].median())

    daily_expenses.to_csv(daily_path, index=False)

    # 9. Aggregate Monthly Expenses (by YearMonth and Category)
    monthly_expenses = df[expense_mask].groupby(["year_month", "category_clean"]).agg(
        monthly_amount=("amount", "sum"),
        tx_count=("amount", "count")
    ).reset_index()
    monthly_expenses.to_csv(monthly_path, index=False)

    logger.info(
        "Dataset B preprocessed successfully: %d rows -> %d clean rows (removed %d duplicates). "
        "Created daily aggregated (%d days) and monthly aggregated (%d rows).",
        orig_count, dedup_count, orig_count - dedup_count, len(daily_expenses), len(monthly_expenses)
    )
    return df, daily_expenses, monthly_expenses


def run_all_preprocessing():
    """Executes all data preprocessing pipelines."""
    df_a = preprocess_personal_finance()
    df_b, daily_b, monthly_b = preprocess_household_transactions()
    return {
        "dataset_a": {"rows": len(df_a), "cols": df_a.shape[1], "file": "personal_finance_clean.csv"},
        "dataset_b": {"rows": len(df_b), "cols": df_b.shape[1], "file": "household_transactions_clean.csv"},
        "daily_b": {"rows": len(daily_b), "cols": daily_b.shape[1], "file": "daily_expenses_aggregated.csv"},
        "monthly_b": {"rows": len(monthly_b), "cols": monthly_b.shape[1], "file": "monthly_expenses_aggregated.csv"}
    }


if __name__ == "__main__":
    results = run_all_preprocessing()
    print("\nPreprocessing Results Summary:")
    for k, v in results.items():
        print(f"  {k}: {v['rows']} rows, {v['cols']} cols ({v['file']})")
