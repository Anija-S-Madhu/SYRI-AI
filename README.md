# SYRI AI

## Personal Financial Intelligence Platform

SYRI AI is an AI-powered personal financial intelligence web application designed to help users track income and expenses, manage category budgets, detect transaction anomalies, forecast upcoming monthly spending, and interact with a voice-enabled financial assistant. The application combines Scikit-learn machine learning models with Gnani AI speech and language services to deliver data-driven financial insights.

---

## Challenge Acknowledgement

SYRI AI was developed as a project submission for participating in the **Great Indian AI Internship Challenge 2026 by Gnani AI**.

This project was built solely as a submission for participation in the challenge. It does not represent or claim selection for, receipt of, or completion of an internship.

---

## Demonstration Data Notice

All transactions, account balances, income figures, and category records displayed in demonstration walkthroughs or loaded into the development database are simulated sample data for testing and demonstration purposes. No real bank accounts, cards, payment gateways, or financial institutions are connected to this application.

---

## Gnani AI Integrations and Status

SYRI AI integrates with Gnani AI services across three capabilities: Speech-to-Text (STT), Text-to-Speech (TTS), and Multilingual Financial Reasoning.

| Capability | Service | Endpoint / Model Identifier | Live API Status | Fallback Status |
|---|---|---|---|---|
| Speech-to-Text (STT) | Gnani Prisma STT | `https://api.vachana.ai/stt/v3`<br>Model: `prisma-v3.0` | Live integration operational | Not applicable (requires audio input) |
| Text-to-Speech (TTS) | Gnani Timbre TTS | `https://api.vachana.ai/api/v1/tts/inference`<br>Model: `timbre-v2.5` (Voice: `Nalini`) | Live integration operational | Client-side visual text display |
| Multilingual Reasoning | Gnani Evon 30B | `https://api.vachana.ai/v1/chat/completions`<br>Model: `gnani/gnani-evon-v3.3-30B-A3B` | Live API unavailable (API access/scope limitation) | Local deterministic reasoning engine operational |

### Prisma Speech-to-Text (STT)
- Source implementation: `app/services/prisma_service.py`
- Operational status: Verified and functional via live API calls.
- Details: Transcribes audio queries recorded from the user's browser microphone. Uploads multipart audio data (`audio_file`) with language code (`en-IN`) and model (`prisma-v3.0`) authenticated using the `X-API-Key-ID` header. Supports audio formats up to 5 MB, including WAV, MP3, OGG, WebM, M4A, and FLAC.

### Timbre Text-to-Speech (TTS)
- Source implementation: `app/services/timbre_service.py`
- Operational status: Verified and functional via live API calls.
- Details: Converts AI assistant text responses into spoken audio using Gnani Timbre (`timbre-v2.5`, voice `Nalini`, language `en-IN`).
- Audio processing: Gnani Timbre returns raw 16-bit linear PCM at 24,000 Hz in stereo (2 channels). The service wraps this raw PCM byte stream with a standard 24 kHz stereo RIFF/WAV header to provide valid container formatting for in-browser audio playback.

### Evon Multilingual Reasoning (30B)
- Source implementation: `app/services/evon_service.py`
- Operational status: Live API unavailable; local reasoning fallback active.
- Details: A complete client implementation is present targeting `gnani/gnani-evon-v3.3-30B-A3B` at `https://api.vachana.ai/v1/chat/completions`. However, live API inference could not be enabled due to an API access/scope limitation on the challenge credentials (the provided API key does not grant access to the Evon chat completions endpoint).
- Local fallback implementation: To ensure uninterrupted application functionality, `app/services/evon_service.py` implements a local rule-based reasoning engine:
  - Synthesizes Scikit-learn ML metrics into a structured 3-point natural-language explanation covering forecast analysis, overrun risks, and savings recommendations.
  - Answers conversational financial queries grounded strictly in verified user database metrics (income, expenses, active categories, balance).
  - Supports query understanding and responses in English and Malayalam.

---

## Machine Learning and Analytics Pipeline

SYRI AI uses an offline Scikit-learn machine learning pipeline (`ml/`) trained on public benchmark datasets. ML training and inference operate locally without external API dependencies.

### Model Overview

| Model Identifier | Task | Selected Algorithm | Benchmark Dataset | Validation Metrics |
|---|---|---|---|---|
| Model 1: Savings Analysis | Benchmark Savings Capacity Estimation | GradientBoosting Regressor | Indian Personal Finance (`Dataset A`) | MAE: 664.03 INR<br>RMSE: 2287.67 INR<br>R2: 0.9276 |
| Model 2: Expense Forecasting | Time-Aware 30-Day Expense Projection | RandomForest Regressor | Daily Household Transactions (`Dataset B`) | MAE: 2838.46 INR<br>RMSE: 6835.21 INR<br>Split: Chronological (2015-2017 train, 2018 test) |
| Model 3: Anomaly Detection | Unusual Expense Spike Identification | Isolation Forest + Category IQR | Daily Household Transactions (`Dataset B`) | Contamination: 0.03<br>Evaluated across 2,173 transactions |
| Model 4: Budget Run-Rate | Category Budget Overrun Risk Estimation | Daily Burn-Rate Analytics | User SQLite Transaction Records | Projected monthly category total vs. budget limit |

### Detailed Model Descriptions

1. Model 1 (Savings Capacity Regressor):
   - Compared Ridge, RandomForest, and GradientBoosting algorithms; GradientBoosting achieved the lowest MAE (664.03 INR).
   - Trained on `data/processed/personal_finance_clean.csv`.
   - Prevents target leakage by excluding disposable income and potential savings columns, using only demographic and category expense features.

2. Model 2 (Time-Aware Expense Forecaster):
   - Evaluated Ridge, RandomForest, and GradientBoosting; RandomForest achieved the lowest MAE (2838.46 INR).
   - Trained on `data/processed/daily_expenses_aggregated.csv` using strict chronological splitting (training on 2015-2017 data, testing on 2018 data) to prevent temporal lookahead bias.
   - Computes backward-looking rolling statistics (`rolling_7d_avg`, `rolling_30d_avg`, `lag_1d`, `lag_7d`, day of week, day of month, month, weekend indicator).
   - Handles cold-start accounts (<5 transactions) using daily spending velocity baselines.

3. Model 3 (Unusual Expense Anomaly Detector):
   - Employs an Isolation Forest model (contamination rate 0.03) combined with category-specific 95th percentile and IQR thresholds to flag statistically anomalous expense entries.

4. Spending Behavior Classification:
   - Evaluates the user's computed savings rate (net savings divided by total income) into four categories:
     - Frugal / High Saver: Savings rate >= 30% (Low Risk)
     - Balanced Spender: Savings rate 10% to 29.9% (Moderate Risk)
     - Living Paycheck to Paycheck: Savings rate 0% to 9.9% (High Risk)
     - Deficit Spender: Savings rate < 0% (Critical Risk)

---

## Core Application Features

- Financial Dashboard: Overview cards for total recorded income, total expenses, available liquid balance, monthly savings, and recent transactions.
- Transaction Management: Full CRUD interface for income and expense transactions with Decimal numeric precision, date validation, category association, and user ownership isolation.
- Category Management: Income and expense categories with per-user unique name constraints and deletion safeguards that prevent removing categories referenced by active transactions.
- Monthly Budgets: Per-category monthly spending limits, progress bars, utilization percentages, remaining balances, and overrun warnings.
- Analytics and Visualizations: Interactive Chart.js doughnut chart for category spending distribution, budget overrun risk table, and on-demand ML model retraining (`POST /api/ml/retrain`).
- Voice Assistant: In-browser audio recording, speech transcription via Gnani Prisma STT, query reasoning via Evon fallback, and speech output via Gnani Timbre TTS.
- Statements and Export: Auditable transaction table and CSV statement download (`GET /reports/export-csv`).
- User Authentication: Secure password hashing with Werkzeug, session persistence with Flask-Login, and user-isolated database queries.

---

## System Architecture

```text
                    +------------------------------------+
                    |       Browser Client (Web UI)      |
                    |  HTML5 / CSS3 / ES6 / Chart.js     |
                    +-----------------+------------------+
                                      |
                           HTTP / REST / Multipart
                                      |
                                      v
+------------------------------------------------------------------------+
|                          Flask Application Layer                       |
|                                                                        |
|   +-----------------------+                  +---------------------+   |
|   |   Main Routes (Jinja) |                  |   API Routes (JSON) |   |
|   |   /dashboard          |                  |   /api/transactions |   |
|   |   /transactions       |                  |   /api/budgets      |   |
|   |   /budgets            |                  |   /api/analytics    |   |
|   |   /analytics          |                  |   /api/ai/ask       |   |
|   |   /reports            |                  |   /api/ai/voice/*   |   |
|   +-----------+-----------+                  +----------+----------+   |
|               |                                         |              |
|               v                                         v              |
|   +----------------------------------------------------------------+   |
|   |                     Services & Logic Layer                     |   |
|   |                                                                |   |
|   |   +---------------------+             +--------------------+   |   |
|   |   |  Prisma STT Service |             | Timbre TTS Service |   |   |
|   |   +----------+----------+             +---------+----------+   |   |
|   |              |                                  |              |   |
|   |              v                                  v              |   |
|   |   +---------------------+             +--------------------+   |   |
|   |   | Evon 30B Service    |             | AI Advisor Unified |   |   |
|   |   | (Reasoning/Fallback)|<----------->| Pipeline Service   |   |   |
|   |   +---------------------+             +---------+----------+   |   |
|   +-------------------------------------------------|--------------+   |
+-----------------------------------------------------|------------------+
                                                      |
                  +-----------------------------------+--------------------+
                  |                                                        |
                  v                                                        v
+-----------------------------------+    +-------------------------------------+
|        Database (SQLite)          |    |     Scikit-learn ML Subsystem       |
|                                   |    |                                     |
|  - Users (Auth / Passwords)       |    |  - Model 1: Savings (GradientBoost) |
|  - Categories (User Scoped)       |    |  - Model 2: Expense (RandomForest)  |
|  - Transactions (User Scoped)     |    |  - Model 3: Anomaly (Isolation Frst)|
|  - Budgets (User Scoped)          |    |  - Model 4: Overrun Run-Rate Risk   |
+-----------------------------------+    +-------------------------------------+
```

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | HTML5, CSS3, JavaScript (ES6+), Chart.js |
| Backend Framework | Python 3.10+, Flask 3.0+ |
| Database & ORM | SQLite, Flask-SQLAlchemy 3.1+ |
| Authentication | Flask-Login 0.6+, Werkzeug Security |
| Machine Learning | Scikit-learn 1.3+, Joblib |
| Data Processing | Pandas 2.1+, NumPy 1.26+ |
| Speech & Voice AI | Gnani AI Prisma STT, Gnani AI Timbre TTS |
| Configuration & Network | Python-dotenv, Requests |
| Test Framework | Python unittest, unittest.mock |

---

## Project Structure

```text
SYRI_AI/
|-- app/
|   |-- __init__.py                # Flask application factory
|   |-- config.py                  # Environment and database configurations
|   |-- extensions.py              # SQLAlchemy and LoginManager instances
|   |-- models/
|   |   |-- __init__.py            # Model registry
|   |   |-- user.py                # User model with password hashing
|   |   |-- category.py            # Category model with user constraints
|   |   |-- transaction.py         # Transaction model with Decimal precision
|   |   |-- budget.py              # Budget model with monthly constraints
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- main.py                # Jinja2 template page routes
|   |   |-- api.py                 # REST JSON and Voice API endpoints
|   |-- services/
|   |   |-- __init__.py
|   |   |-- prisma_service.py      # Gnani Prisma STT integration
|   |   |-- timbre_service.py      # Gnani Timbre TTS integration
|   |   |-- evon_service.py        # Gnani Evon 30B reasoning & fallback engine
|   |   |-- gnani_service.py       # Gnani chat completions client
|   |   |-- ai_advisor.py          # Unified ML + Advisory orchestration
|   |-- static/
|   |   |-- css/
|   |   |   |-- style.css          # Application stylesheet
|   |   |-- js/
|   |   |   |-- app.js             # Client-side UI and modal interactions
|   |-- templates/
|   |   |-- base.html              # Base HTML layout
|   |   |-- index.html             # Landing page
|   |   |-- login.html             # Login view
|   |   |-- register.html          # Registration view
|   |   |-- dashboard.html         # Main dashboard overview
|   |   |-- transactions.html      # Transaction CRUD interface
|   |   |-- categories.html        # Category management interface
|   |   |-- budgets.html           # Budget management interface
|   |   |-- analytics.html         # Analytics, charts, and voice assistant
|   |   |-- reports.html           # Financial reports and statement export
|   |-- utils/
|       |-- __init__.py
|       |-- auth.py                # Authentication helper utilities
|-- data/
|   |-- raw/                       # Benchmark raw datasets
|   |   |-- indian_personal_finance.csv
|   |   |-- Daily Household Transactions.csv
|   |-- processed/                 # Cleaned training datasets
|       |-- personal_finance_clean.csv
|       |-- household_transactions_clean.csv
|       |-- daily_expenses_aggregated.csv
|       |-- monthly_expenses_aggregated.csv
|-- instance/
|   |-- syri.db                    # SQLite database file (auto-generated)
|-- ml/
|   |-- __init__.py
|   |-- preprocess.py              # Benchmark dataset cleaning scripts
|   |-- train_models.py            # ML training, evaluation, and serialization
|   |-- pipeline.py                # Production prediction pipeline
|   |-- saved_models/              # Serialized model bundles and metadata
|       |-- savings_model.joblib
|       |-- expense_forecast_model.joblib
|       |-- anomaly_detector.joblib
|       |-- evaluation_metadata.json
|-- tests/
|   |-- __init__.py
|   |-- test_ai_ml_analytics.py    # ML, analytics, and reporting tests
|   |-- test_budgets.py            # Budget route and logic tests
|   |-- test_categories.py         # Category route and constraint tests
|   |-- test_evon_service.py       # Evon client and reasoning tests
|   |-- test_transactions_api.py   # Transaction REST API tests
|   |-- test_voice_api.py          # Prisma and Timbre voice endpoint tests
|-- .env.example                   # Environment configuration template
|-- .gitignore                     # Git ignore rules
|-- README.md                      # Project documentation
|-- requirements.txt               # Python package dependencies
|-- run.py                         # Application entry point
```

---

## API Reference

### Web Routes

| Route | Methods | Description |
|---|---|---|
| `/` | GET | Welcome landing page |
| `/register` | GET, POST | User account registration |
| `/login` | GET, POST | User authentication |
| `/logout` | GET | Session termination |
| `/dashboard` | GET | Financial summary dashboard |
| `/transactions` | GET, POST | Transaction listing and creation |
| `/categories` | GET, POST | Category listing and creation |
| `/categories/<id>/edit` | POST | Edit category name or type |
| `/categories/<id>/delete` | POST | Delete category (protected against active references) |
| `/budgets` | GET, POST | Budget listing and creation |
| `/budgets/<id>/edit` | POST | Edit budget allocation |
| `/budgets/<id>/delete` | POST | Delete budget allocation |
| `/analytics` | GET | Analytics, ML predictions, and AI advisor |
| `/reports` | GET | Transaction statements |
| `/reports/export-csv` | GET | Download transaction history as CSV |

### REST and Voice API Endpoints

| Endpoint | Method | Auth Required | Description |
|---|---|---|---|
| `/api/health` | GET | No | Service health check |
| `/api/transactions` | GET, POST | Yes | List or create transactions |
| `/api/transactions/<id>` | GET, PUT, DELETE | Yes | Retrieve, update, or delete a transaction |
| `/api/categories` | GET, POST | Yes | List or create categories |
| `/api/categories/<id>` | GET, PUT, DELETE | Yes | Retrieve, update, or delete a category |
| `/api/budgets` | GET, POST | Yes | List or create category budgets |
| `/api/budgets/<id>` | GET, PUT, DELETE | Yes | Retrieve, update, or delete a budget |
| `/api/analytics` | GET | Yes | Full ML predictions and advisory payload |
| `/api/ai/ask` | POST | Yes | Conversational financial Q&A (text input) |
| `/api/ml/retrain` | POST | Yes | Trigger on-demand retraining of ML models |
| `/api/ai/voice/transcribe` | POST | Yes | Transcribe voice recording via Gnani Prisma STT |
| `/api/ai/voice/speak` | POST | Yes | Synthesize text to WAV audio via Gnani Timbre TTS |
| `/api/ai/voice/ask` | POST | Yes | Unified voice loop: Audio -> Prisma STT -> Evon Reasoning -> Timbre TTS |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git

### Installation and Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/SYRI_AI.git
   cd SYRI_AI
   ```

2. Create and activate a virtual environment:
   - On Windows:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - On macOS or Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Copy `.env.example` to `.env`:
   - On Windows:
     ```powershell
     copy .env.example .env
     ```
   - On macOS or Linux:
     ```bash
     cp .env.example .env
     ```

### Environment Variable Reference

The application reads configuration from environment variables (loaded via `.env`):

| Variable | Required | Default Value | Description |
|---|---|---|---|
| `FLASK_APP` | No | `run.py` | Flask entry point script |
| `FLASK_ENV` | No | `development` | Flask runtime environment (`development`, `production`) |
| `SECRET_KEY` | Recommended | `dev-secret-key-change-in-production` | Secret key for Flask session security |
| `DATABASE_URL` | No | `sqlite:///instance/syri.db` | SQLAlchemy database connection URI |
| `GNANI_API_KEY` | For voice features | None | API key for Gnani AI Vachana platform |
| `GNANI_API_URL` | No | `https://api.vachana.ai/v1/chat/completions` | Gnani chat completions endpoint |
| `GNANI_EVON_API_URL` | No | Falls back to `GNANI_API_URL` | Optional override for Evon chat completions endpoint |
| `GNANI_EVON_API_KEY` | No | Falls back to `GNANI_API_KEY` | Optional override for Evon API key |
| `GNANI_TIMEOUT_SECONDS` | No | `6` (API) / `8` (Voice) | Request timeout in seconds for Gnani API calls |
| `GNANI_STT_URL` | No | `https://api.vachana.ai/stt/v3` | Endpoint for Gnani Prisma STT |
| `GNANI_STT_MODEL` | No | `prisma-v3.0` | Model identifier for Prisma STT |
| `GNANI_STT_LANGUAGE_CODE` | No | `en-IN` | Language code for Prisma STT |
| `GNANI_TTS_URL` | No | `https://api.vachana.ai/api/v1/tts/inference` | Endpoint for Gnani Timbre TTS |
| `GNANI_TTS_MODEL` | No | `timbre-v2.5` | Model identifier for Timbre TTS |
| `GNANI_TTS_VOICE` | No | `Nalini` | Voice profile for Timbre TTS |
| `GNANI_TTS_LANGUAGE` | No | `en-IN` | Language setting for Timbre TTS |
| `GNANI_TTS_SAMPLE_RATE` | No | `24000` | Audio sample rate for Timbre TTS in Hz |
| `GNANI_TTS_CHANNELS` | No | `2` | Audio channel count for Timbre TTS (stereo) |
| `GNANI_EVON_MODEL` | No | `gnani/gnani-evon-v3.3-30B-A3B` | Model identifier for Evon reasoning engine |

### Retraining Machine Learning Models

Pre-trained model bundles are provided in `ml/saved_models/`. To retrain all models from the benchmark datasets:

```bash
python -m ml.train_models
```

### Running the Application

Start the local Flask development server:

```bash
python run.py
```

The application will be accessible at `http://127.0.0.1:5000`.

---

## Running Automated Tests

SYRI AI includes automated test suites covering authentication, REST APIs, ML pipeline operations, budget management, and voice endpoints:

```bash
python -m unittest discover -s tests
```

To run individual test files:

```bash
python -m unittest tests/test_transactions_api.py
python -m unittest tests/test_categories.py
python -m unittest tests/test_budgets.py
python -m unittest tests/test_ai_ml_analytics.py
python -m unittest tests/test_evon_service.py
python -m unittest tests/test_voice_api.py
```

---

## License

This project was developed for participation in the Great Indian AI Internship Challenge 2026 by Gnani AI.
All rights reserved.
