"""SYRI AI - API routes (JSON endpoints)."""

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models.category import Category
from ..models.transaction import Transaction
from ..models.budget import Budget

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Return the API health status."""
    return jsonify(
        {
            "status": "ok",
            "app": "SYRI AI",
        }
    ), 200


def transaction_to_dict(transaction):
    """Convert a transaction model instance to a JSON-friendly dictionary."""
    return {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "category_id": transaction.category_id,
        "category_name": transaction.category.name if transaction.category else "Uncategorized",
        "type": transaction.type,
        "amount": str(transaction.amount),
        "description": transaction.description,
        "date": transaction.date.isoformat(),
        "created_at": (
            transaction.created_at.isoformat()
            if transaction.created_at
            else None
        ),
    }


def validate_transaction_data(data, existing=None):
    """Validate transaction data and return normalized fields or an error."""
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object."

    transaction_type = data.get(
        "type",
        existing.type if existing else None,
    )

    if transaction_type not in ("income", "expense"):
        return None, "Type must be 'income' or 'expense'."

    raw_amount = data.get(
        "amount",
        existing.amount if existing else None,
    )

    try:
        amount = Decimal(str(raw_amount))
        if not amount.is_finite() or amount <= 0:
            return None, "Amount must be a positive number."
        if amount.as_tuple().exponent < -2:
            return None, "Amount can have at most 2 decimal places."
        if amount >= Decimal("10000000000"):
            return None, "Amount is too large."
        amount = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None, "Enter a valid amount."

    raw_date = data.get(
        "date",
        existing.date.isoformat() if existing else None,
    )

    try:
        transaction_date = date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return None, "Date must use YYYY-MM-DD format."

    description = data.get(
        "description",
        existing.description if existing else "",
    )

    if description is not None and not isinstance(description, str):
        return None, "Description must be text."

    if description and len(description) > 200:
        return None, "Description cannot exceed 200 characters."

    category_id = data.get(
        "category_id",
        existing.category_id if existing else None,
    )

    if category_id in ("", None):
        category_id = None
    else:
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            return None, "Invalid category ID."

        category = Category.query.filter_by(
            id=category_id,
            user_id=current_user.id,
        ).first()

        if not category:
            return None, "Category not found."

        if category.type != transaction_type:
            return None, "Category type must match transaction type."

    return {
        "type": transaction_type,
        "amount": amount,
        "date": transaction_date,
        "description": description.strip() if description else None,
        "category_id": category_id,
    }, None


@api_bp.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    """List the logged-in user's transactions or create one."""
    if request.method == "GET":
        query = Transaction.query.filter_by(user_id=current_user.id)

        transaction_type = request.args.get("type")
        if transaction_type:
            if transaction_type not in ("income", "expense"):
                return jsonify({"error": "Invalid transaction type."}), 400
            query = query.filter_by(type=transaction_type)

        results = query.order_by(
            Transaction.date.desc(),
            Transaction.id.desc(),
        ).all()

        return jsonify(
            {
                "transactions": [
                    transaction_to_dict(item) for item in results
                ],
                "count": len(results),
            }
        ), 200

    data = request.get_json(silent=True)
    validated, error = validate_transaction_data(data)
    if error:
        return jsonify({"error": error}), 400

    transaction = Transaction(
        user_id=current_user.id,
        **validated,
    )

    try:
        db.session.add(transaction)
        db.session.commit()
        return jsonify(
            {
                "message": "Transaction created successfully.",
                "transaction": transaction_to_dict(transaction),
            }
        ), 201
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to save transaction."}), 500


@api_bp.route(
    "/transactions/<int:transaction_id>",
    methods=["GET", "PUT", "PATCH", "DELETE"],
)
@login_required
def transaction_detail(transaction_id):
    """Read, update, or delete the logged-in user's transaction."""
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id,
    ).first()

    if not transaction:
        return jsonify({"error": "Transaction not found."}), 404

    if request.method == "GET":
        return jsonify({"transaction": transaction_to_dict(transaction)}), 200

    if request.method in ("PUT", "PATCH"):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(
                {"error": "Request body must be a JSON object."}
            ), 400

        if request.method == "PUT":
            required_fields = {"type", "amount", "date"}
            if not required_fields.issubset(data.keys()):
                return jsonify(
                    {"error": "PUT requires type, amount and date."}
                ), 400

        validated, error = validate_transaction_data(
            data,
            existing=transaction,
        )
        if error:
            return jsonify({"error": error}), 400

        for field, value in validated.items():
            setattr(transaction, field, value)

        try:
            db.session.commit()
            return jsonify(
                {
                    "message": "Transaction updated successfully.",
                    "transaction": transaction_to_dict(transaction),
                }
            ), 200
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Unable to update transaction."}), 500

    # DELETE
    try:
        db.session.delete(transaction)
        db.session.commit()
        return jsonify({"message": "Transaction deleted successfully."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to delete transaction."}), 500


def category_to_dict(category):
    """Convert a category model instance to a JSON-friendly dictionary."""
    return {
        "id": category.id,
        "user_id": category.user_id,
        "name": category.name,
        "type": category.type,
        "transaction_count": len(category.transactions),
    }


@api_bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    """List the logged-in user's categories or create one."""
    if request.method == "GET":
        query = Category.query.filter_by(user_id=current_user.id)
        cat_type = request.args.get("type")
        if cat_type:
            if cat_type not in ("income", "expense"):
                return jsonify({"error": "Invalid category type."}), 400
            query = query.filter_by(type=cat_type)

        results = query.order_by(Category.name.asc()).all()
        return jsonify(
            {
                "categories": [category_to_dict(item) for item in results],
                "count": len(results),
            }
        ), 200

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    name = data.get("name", "").strip()
    cat_type = data.get("type", "").strip().lower()

    if not name:
        return jsonify({"error": "Category name is required."}), 400
    if len(name) > 50:
        return jsonify({"error": "Category name cannot exceed 50 characters."}), 400
    if cat_type not in ("income", "expense"):
        return jsonify({"error": "Type must be 'income' or 'expense'."}), 400

    # Case-insensitive duplicate check for the current user and type
    existing = Category.query.filter(
        Category.user_id == current_user.id,
        Category.type == cat_type,
        db.func.lower(Category.name) == name.lower(),
    ).first()
    if existing:
        return jsonify(
            {"error": f"A {cat_type} category named '{name}' already exists."}
        ), 400

    category = Category(
        user_id=current_user.id,
        name=name,
        type=cat_type,
    )

    try:
        db.session.add(category)
        db.session.commit()
        return jsonify(
            {
                "message": "Category created successfully.",
                "category": category_to_dict(category),
            }
        ), 201
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to save category."}), 500


@api_bp.route(
    "/categories/<int:category_id>",
    methods=["GET", "PUT", "PATCH", "DELETE"],
)
@login_required
def category_detail(category_id):
    """Read, update, or delete the logged-in user's category."""
    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id,
    ).first()

    if not category:
        return jsonify({"error": "Category not found."}), 404

    if request.method == "GET":
        return jsonify({"category": category_to_dict(category)}), 200

    if request.method in ("PUT", "PATCH"):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        name = data.get("name", category.name).strip()
        cat_type = data.get("type", category.type).strip().lower()

        if not name:
            return jsonify({"error": "Category name cannot be empty."}), 400
        if len(name) > 50:
            return jsonify({"error": "Category name cannot exceed 50 characters."}), 400
        if cat_type not in ("income", "expense"):
            return jsonify({"error": "Type must be 'income' or 'expense'."}), 400

        if cat_type != category.type:
            tx_count = Transaction.query.filter_by(
                category_id=category.id,
                user_id=current_user.id,
            ).count()
            if tx_count > 0:
                return jsonify(
                    {
                        "error": f"Cannot change category type because it is currently assigned to {tx_count} transaction(s)."
                    }
                ), 400

        # Duplicate check
        duplicate = Category.query.filter(
            Category.user_id == current_user.id,
            Category.type == cat_type,
            Category.id != category.id,
            db.func.lower(Category.name) == name.lower(),
        ).first()
        if duplicate:
            return jsonify(
                {"error": f"A {cat_type} category named '{name}' already exists."}
            ), 400

        category.name = name
        category.type = cat_type

        try:
            db.session.commit()
            return jsonify(
                {
                    "message": "Category updated successfully.",
                    "category": category_to_dict(category),
                }
            ), 200
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Unable to update category."}), 500

    # DELETE: Check if assigned to any transactions
    tx_count = Transaction.query.filter_by(
        category_id=category.id,
        user_id=current_user.id,
    ).count()

    if tx_count > 0:
        return jsonify(
            {
                "error": f"Cannot delete category '{category.name}' because it is assigned to {tx_count} transaction(s)."
            }
        ), 400

    try:
        db.session.delete(category)
        db.session.commit()
        return jsonify({"message": "Category deleted successfully."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to delete category."}), 500


def calculate_budget_metrics(budget):
    """Calculate actual spending, remaining amount, usage percent and status."""
    start_date = date(budget.year, budget.month, 1)
    if budget.month == 12:
        next_month_start = date(budget.year + 1, 1, 1)
    else:
        next_month_start = date(budget.year, budget.month + 1, 1)

    query = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == budget.user_id,
        Transaction.type == "expense",
        Transaction.date >= start_date,
        Transaction.date < next_month_start,
    )

    if budget.category_id is not None:
        query = query.filter(Transaction.category_id == budget.category_id)

    spent = query.scalar()

    budget_amt = Decimal(str(budget.amount))
    spent_amt = Decimal(str(spent))
    remaining_amt = budget_amt - spent_amt

    if budget_amt > 0:
        percent = float((spent_amt / budget_amt) * Decimal("100"))
    else:
        percent = 0.0

    if percent > 100.0:
        status = "overspent"
    elif percent >= 80.0:
        status = "warning"
    else:
        status = "normal"

    return {
        "spent": spent_amt,
        "remaining": remaining_amt,
        "percent": round(percent, 1),
        "status": status,
    }


def budget_to_dict(budget):
    """Convert a budget model instance and its calculated metrics to a JSON dictionary."""
    metrics = calculate_budget_metrics(budget)
    return {
        "id": budget.id,
        "user_id": budget.user_id,
        "category_id": budget.category_id,
        "category_name": budget.category.name if budget.category else "All Categories",
        "amount": str(budget.amount),
        "month": budget.month,
        "year": budget.year,
        "spent": str(metrics["spent"]),
        "remaining": str(metrics["remaining"]),
        "percent": metrics["percent"],
        "status": metrics["status"],
        "created_at": (
            budget.created_at.isoformat() if budget.created_at else None
        ),
    }


@api_bp.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    """List the logged-in user's budgets or create one."""
    if request.method == "GET":
        query = Budget.query.filter_by(user_id=current_user.id)

        month_arg = request.args.get("month")
        year_arg = request.args.get("year")
        cat_id_arg = request.args.get("category_id")

        if month_arg:
            try:
                query = query.filter_by(month=int(month_arg))
            except ValueError:
                return jsonify({"error": "Invalid month."}), 400

        if year_arg:
            try:
                query = query.filter_by(year=int(year_arg))
            except ValueError:
                return jsonify({"error": "Invalid year."}), 400

        if cat_id_arg:
            try:
                query = query.filter_by(category_id=int(cat_id_arg))
            except ValueError:
                return jsonify({"error": "Invalid category ID."}), 400

        results = query.order_by(Budget.year.desc(), Budget.month.desc(), Budget.id.desc()).all()

        return jsonify(
            {
                "budgets": [budget_to_dict(b) for b in results],
                "count": len(results),
            }
        ), 200

    # POST: Create budget
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    category_id = data.get("category_id")
    raw_amount = data.get("amount")
    raw_month = data.get("month")
    raw_year = data.get("year")

    # Validate category_id (must be an expense category owned by the current user)
    if category_id in ("", None):
        return jsonify({"error": "Category is required for a budget."}), 400

    try:
        category_id = int(category_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid category ID."}), 400

    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id,
    ).first()

    if not category:
        return jsonify({"error": "Category not found."}), 404

    if category.type != "expense":
        return jsonify({"error": "Budgets can only be set for expense categories."}), 400

    # Validate amount
    try:
        amount = Decimal(str(raw_amount))
        if not amount.is_finite() or amount <= 0:
            return jsonify({"error": "Budget amount must be a positive number."}), 400
        if amount.as_tuple().exponent < -2:
            return jsonify({"error": "Budget amount can have at most 2 decimal places."}), 400
        if amount >= Decimal("10000000000"):
            return jsonify({"error": "Budget amount is too large."}), 400
        amount = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"error": "Enter a valid budget amount."}), 400

    # Validate month
    try:
        month = int(raw_month)
        if month < 1 or month > 12:
            return jsonify({"error": "Month must be between 1 and 12."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Enter a valid month (1-12)."}), 400

    # Validate year
    try:
        year = int(raw_year)
        if year < 2000 or year > 2100:
            return jsonify({"error": "Year must be between 2000 and 2100."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Enter a valid year."}), 400

    # Prevent duplicate budget for the same user, category, month, and year
    existing = Budget.query.filter_by(
        user_id=current_user.id,
        category_id=category_id,
        month=month,
        year=year,
    ).first()

    if existing:
        return jsonify(
            {"error": f"A budget for '{category.name}' in {month}/{year} already exists."}
        ), 400

    budget = Budget(
        user_id=current_user.id,
        category_id=category_id,
        amount=amount,
        month=month,
        year=year,
    )

    try:
        db.session.add(budget)
        db.session.commit()
        return jsonify(
            {
                "message": "Budget created successfully.",
                "budget": budget_to_dict(budget),
            }
        ), 201
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to save budget."}), 500


@api_bp.route(
    "/budgets/<int:budget_id>",
    methods=["GET", "PUT", "PATCH", "DELETE"],
)
@login_required
def budget_detail(budget_id):
    """Read, update, or delete the logged-in user's budget."""
    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id,
    ).first()

    if not budget:
        return jsonify({"error": "Budget not found."}), 404

    if request.method == "GET":
        return jsonify({"budget": budget_to_dict(budget)}), 200

    if request.method in ("PUT", "PATCH"):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        category_id = data.get("category_id", budget.category_id)
        raw_amount = data.get("amount", budget.amount)
        raw_month = data.get("month", budget.month)
        raw_year = data.get("year", budget.year)

        # Validate category_id if provided
        if category_id not in ("", None):
            try:
                category_id = int(category_id)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid category ID."}), 400

            category = Category.query.filter_by(
                id=category_id,
                user_id=current_user.id,
            ).first()

            if not category:
                return jsonify({"error": "Category not found."}), 404

            if category.type != "expense":
                return jsonify({"error": "Budgets can only be set for expense categories."}), 400
        else:
            return jsonify({"error": "Category is required."}), 400

        # Validate amount
        try:
            amount = Decimal(str(raw_amount))
            if not amount.is_finite() or amount <= 0:
                return jsonify({"error": "Budget amount must be a positive number."}), 400
            if amount.as_tuple().exponent < -2:
                return jsonify({"error": "Budget amount can have at most 2 decimal places."}), 400
            if amount >= Decimal("10000000000"):
                return jsonify({"error": "Budget amount is too large."}), 400
            amount = amount.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            return jsonify({"error": "Enter a valid budget amount."}), 400

        # Validate month
        try:
            month = int(raw_month)
            if month < 1 or month > 12:
                return jsonify({"error": "Month must be between 1 and 12."}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Enter a valid month (1-12)."}), 400

        # Validate year
        try:
            year = int(raw_year)
            if year < 2000 or year > 2100:
                return jsonify({"error": "Year must be between 2000 and 2100."}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Enter a valid year."}), 400

        # Duplicate check if category, month, or year changed
        duplicate = Budget.query.filter(
            Budget.user_id == current_user.id,
            Budget.category_id == category_id,
            Budget.month == month,
            Budget.year == year,
            Budget.id != budget.id,
        ).first()

        if duplicate:
            return jsonify(
                {"error": f"A budget for this category in {month}/{year} already exists."}
            ), 400

        budget.category_id = category_id
        budget.amount = amount
        budget.month = month
        budget.year = year

        try:
            db.session.commit()
            return jsonify(
                {
                    "message": "Budget updated successfully.",
                    "budget": budget_to_dict(budget),
                }
            ), 200
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Unable to update budget."}), 500

    # DELETE
    try:
        db.session.delete(budget)
        db.session.commit()
        return jsonify({"message": "Budget deleted successfully."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to delete budget."}), 500


# ========================================================
# AI ADVISOR & ML INTELLIGENCE ENDPOINTS
# ========================================================

@api_bp.route("/analytics", methods=["GET"])
@login_required
def analytics_data():
    """Return verified analytics, Scikit-learn ML predictions, and Gnani AI insights."""
    from ..services.ai_advisor import get_user_ai_financial_advisory
    advisory = get_user_ai_financial_advisory(current_user.id)
    return jsonify(advisory), 200


@api_bp.route("/ai/ask", methods=["POST"])
@login_required
def ask_ai_assistant():
    """Answer user financial questions using Gnani AI contextualized with user metrics."""
    from ..services.ai_advisor import handle_user_financial_question
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    result = handle_user_financial_question(current_user.id, question)
    return jsonify(result), 200


@api_bp.route("/ml/retrain", methods=["POST"])
@login_required
def retrain_ml():
    """Trigger Scikit-learn model retraining with latest transaction data."""
    from ml.pipeline import train_expense_forecaster
    try:
        metadata = train_expense_forecaster(user_id=current_user.id, force_retrain=True)
        return jsonify({
            "message": "Machine learning model retrained successfully.",
            "metadata": metadata
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrain ML model: {str(e)}"}), 500


# ========================================================
# GNANI VOICE SERVICES (PRISMA STT & TIMBRE TTS)
# ========================================================

ALLOWED_AUDIO_EXTENSIONS = {"wav", "mp3", "ogg", "webm", "m4a", "flac"}
MAX_AUDIO_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@api_bp.route("/ai/voice/transcribe", methods=["POST"])
@login_required
def transcribe_voice():
    """Transcribe user-recorded voice to text using Gnani Prisma STT.

    Accepts multipart/form-data with 'audio_file'.
    Returns: JSON {'transcript': str}
    """
    import os
    import tempfile
    from werkzeug.utils import secure_filename
    from ..services.prisma_service import PrismaSTTService, GnaniAPIError

    if "audio_file" not in request.files:
        return jsonify({"error": "No audio_file provided in request."}), 400

    file = request.files["audio_file"]
    if not file or not file.filename:
        return jsonify({"error": "Empty audio file uploaded."}), 400

    filename = secure_filename(file.filename) or "recording.webm"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext and ext not in ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({"error": f"Unsupported audio format: '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"}), 400

    # Read content to check file size limit (5MB)
    content = file.read()
    if not content:
        return jsonify({"error": "Uploaded audio file is empty."}), 400

    if len(content) > MAX_AUDIO_SIZE_BYTES:
        return jsonify({"error": "Audio file exceeds maximum size limit (5MB)."}), 400

    stt_service = PrismaSTTService()
    if not stt_service.is_configured():
        return jsonify({"error": "Voice STT service is not configured on the server."}), 503

    fd, temp_path = tempfile.mkstemp(suffix=f".{ext or 'webm'}")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        transcript = stt_service.transcribe(temp_path)
        return jsonify({"transcript": transcript}), 200
    except GnaniAPIError as e:
        return jsonify({"error": f"Speech transcription error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Failed to process audio: {str(e)}"}), 500
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@api_bp.route("/ai/voice/speak", methods=["POST"])
@login_required
def speak_ai_response():
    """Synthesize text into speech audio using Gnani Timbre TTS.

    Accepts JSON {'text': str}.
    Returns: audio/wav binary stream.
    """
    import logging
    from flask import Response
    from ..services.timbre_service import TimbreTTSService, GnaniAPIError

    logger = logging.getLogger(__name__)

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Text parameter is required."}), 400

    if len(text) > 2000:
        return jsonify({"error": "Text exceeds maximum character limit (2000 characters)."}), 400

    tts_service = TimbreTTSService()
    if not tts_service.is_configured():
        logger.warning("Timbre TTS requested but GNANI_API_KEY is not configured.")
        return jsonify({"error": "Voice TTS service is not configured on the server."}), 503

    try:
        audio_bytes = tts_service.synthesize(text)
        content_length = len(audio_bytes)
        logger.info("Serving synthesized audio response: %d bytes (audio/wav)", content_length)

        return Response(audio_bytes, mimetype="audio/wav", headers={
            "Content-Disposition": "inline; filename=response.wav",
            "Content-Length": str(content_length),
            "Cache-Control": "no-cache"
        })
    except GnaniAPIError as e:
        logger.error("Gnani Timbre API error during speech synthesis: %s", e)
        return jsonify({"error": f"Voice synthesis error: {str(e)}"}), 502
    except Exception as e:
        logger.error("Unexpected error during speech synthesis: %s", e)
        return jsonify({"error": f"Failed to synthesize voice: {str(e)}"}), 500


@api_bp.route("/ai/voice/ask", methods=["POST"])
@login_required
def unified_voice_assistant():
    """Unified voice workflow combining all three Gnani models:
    1. Prisma STT: Transcribe user's speech audio into text.
    2. Evon 30B: Multilingual reasoning over user's verified financial context and ML predictions.
    3. Timbre TTS: Synthesize Evon's response into spoken audio.

    Accepts: multipart/form-data with 'audio_file'.
    Returns: JSON {
        'status': 'success',
        'transcript': str,
        'answer': str,
        'source': str,
        'model': str,
        'audio_base64': str | None,
        'has_audio': bool
    }
    """
    import base64
    import os
    import tempfile
    from werkzeug.utils import secure_filename
    from ..services.prisma_service import PrismaSTTService, GnaniAPIError as PrismaError
    from ..services.timbre_service import TimbreTTSService, GnaniAPIError as TimbreError
    from ..services.ai_advisor import handle_user_financial_question

    if "audio_file" not in request.files:
        return jsonify({"error": "No audio_file provided in request."}), 400

    file = request.files["audio_file"]
    if not file or not file.filename:
        return jsonify({"error": "Empty audio file uploaded."}), 400

    filename = secure_filename(file.filename) or "recording.webm"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext and ext not in ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({"error": f"Unsupported audio format: '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"}), 400

    content = file.read()
    if not content:
        return jsonify({"error": "Uploaded audio file is empty."}), 400

    if len(content) > MAX_AUDIO_SIZE_BYTES:
        return jsonify({"error": "Audio file exceeds maximum size limit (5MB)."}), 400

    stt_service = PrismaSTTService()
    if not stt_service.is_configured():
        return jsonify({"error": "Voice STT service is not configured on the server."}), 503

    fd, temp_path = tempfile.mkstemp(suffix=f".{ext or 'webm'}")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        # 1. Prisma STT: Transcribe
        try:
            transcript = stt_service.transcribe(temp_path)
        except PrismaError as e:
            return jsonify({"error": f"Speech transcription error: {str(e)}"}), 502

        if not transcript or not transcript.strip():
            return jsonify({
                "status": "empty_transcript",
                "transcript": "",
                "answer": "No speech was detected in your recording. Please try speaking again.",
                "source": "Gnani Prisma STT",
                "model": "prisma-v3.0",
                "audio_base64": None,
                "has_audio": False
            }), 200

        # 2. Evon 30B: Multilingual Reasoning with verified user metrics
        evon_result = handle_user_financial_question(current_user.id, transcript.strip())
        answer_text = evon_result.get("answer", "")

        # 3. Timbre TTS: Synthesize speech
        audio_base64 = None
        tts_service = TimbreTTSService()
        if tts_service.is_configured() and answer_text:
            try:
                audio_bytes = tts_service.synthesize(answer_text)
                if audio_bytes:
                    audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
            except TimbreError:
                audio_base64 = None
            except Exception:
                audio_base64 = None

        return jsonify({
            "status": "success",
            "transcript": transcript.strip(),
            "answer": answer_text,
            "source": evon_result.get("source", "Gnani Evon 30B"),
            "model": evon_result.get("model", "gnani/gnani-evon-v3.3-30B-A3B"),
            "audio_base64": audio_base64,
            "has_audio": bool(audio_base64)
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to process voice assistant request: {str(e)}"}), 500
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
