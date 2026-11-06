from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models.user import User
from ..models.transaction import Transaction
from ..models.category import Category
from ..models.budget import Budget


main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('main.register'))

        if len(password) < 8:
            flash('Password must contain at least 8 characters.', 'error')
            return redirect(url_for('main.register'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('main.register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('main.register'))

        user = User(username=username, email=email)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully. Please log in.', 'success')
            return redirect(url_for('main.login'))

        except Exception:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('main.register'))

    return render_template('register.html')


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)

            next_page = request.args.get('next')

            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)

            return redirect(url_for('main.dashboard'))

        flash('Invalid email or password.', 'error')

    return render_template('login.html')


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/dashboard')
@login_required
def dashboard():

    user_id = current_user.id

    total_income = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter_by(
        user_id=user_id,
        type='income'
    ).scalar()

    total_expenses = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter_by(
        user_id=user_id,
        type='expense'
    ).scalar()

    today = date.today()
    first_day = today.replace(day=1)

    monthly_income = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income',
        Transaction.date >= first_day
    ).scalar()

    monthly_expenses = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= first_day
    ).scalar()

    available_balance = total_income - total_expenses
    monthly_savings = monthly_income - monthly_expenses

    recent_transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    ).limit(5).all()

    from ..services.ai_advisor import get_user_ai_financial_advisory
    advisory = get_user_ai_financial_advisory(user_id)

    return render_template(
        'dashboard.html',
        total_income=total_income,
        total_expenses=total_expenses,
        available_balance=available_balance,
        monthly_savings=monthly_savings,
        recent_transactions=recent_transactions,
        advisory=advisory
    )


# =========================================================
# TRANSACTIONS
# =========================================================

@main_bp.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():

    if request.method == 'POST':

        transaction_type = request.form.get('type', '').strip().lower()
        amount_text = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        transaction_date = request.form.get('date', '').strip()
        category_id_text = request.form.get('category_id', '').strip()

        # Validate transaction type
        if transaction_type not in ['income', 'expense']:
            flash('Please select a valid transaction type.', 'error')
            return redirect(url_for('main.transactions'))

        # Validate description
        if len(description) > 200:
            flash('Description must be 200 characters or less.', 'error')
            return redirect(url_for('main.transactions'))

        # Validate amount and date
        try:
            amount = Decimal(amount_text)

            if (
                not amount.is_finite()
                or amount <= 0
                or amount >= Decimal('10000000000')
            ):
                raise ValueError

            if amount.as_tuple().exponent < -2:
                raise ValueError

            selected_date = date.fromisoformat(transaction_date)

        except (InvalidOperation, ValueError, TypeError):
            flash('Please enter a valid amount and date.', 'error')
            return redirect(url_for('main.transactions'))

        # Validate category ID
        try:
            category_id = int(category_id_text)
        except (ValueError, TypeError):
            flash('Please select a valid category.', 'error')
            return redirect(url_for('main.transactions'))

        # Ensure category belongs to the logged-in user
        # and matches the transaction type
        selected_category = Category.query.filter_by(
            id=category_id,
            user_id=current_user.id,
            type=transaction_type
        ).first()

        if not selected_category:
            flash(
                'Please select a valid category for this transaction.',
                'error'
            )
            return redirect(url_for('main.transactions'))

        # Create transaction with selected category
        transaction = Transaction(
            user_id=current_user.id,
            category_id=selected_category.id,
            type=transaction_type,
            amount=amount,
            description=description or None,
            date=selected_date
        )

        try:
            db.session.add(transaction)
            db.session.commit()

            flash('Transaction added successfully!', 'success')

        except Exception:
            db.session.rollback()
            flash('Could not save transaction. Please try again.', 'error')

        return redirect(url_for('main.transactions'))

    # GET: Fetch only the logged-in user's transactions
    all_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    ).all()

    # Fetch only the logged-in user's categories
    user_categories = Category.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Category.name.asc()
    ).all()

    return render_template(
        'transactions.html',
        transactions=all_transactions,
        categories=user_categories,
        today=date.today().isoformat()
    )


# =========================================================
# CATEGORIES
# =========================================================

@main_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():

    if request.method == 'POST':

        name = request.form.get('name', '').strip()
        cat_type = request.form.get('type', '').strip().lower()

        if not name:
            flash('Category name is required.', 'error')
            return redirect(url_for('main.categories'))

        if len(name) > 50:
            flash('Category name must be 50 characters or less.', 'error')
            return redirect(url_for('main.categories'))

        if cat_type not in ['income', 'expense']:
            flash('Please select a valid category type.', 'error')
            return redirect(url_for('main.categories'))

        existing = Category.query.filter(
            Category.user_id == current_user.id,
            Category.type == cat_type,
            db.func.lower(Category.name) == name.lower()
        ).first()

        if existing:
            flash(
                f"A {cat_type} category named '{name}' already exists.",
                'error'
            )
            return redirect(url_for('main.categories'))

        category = Category(
            user_id=current_user.id,
            name=name,
            type=cat_type
        )

        try:
            db.session.add(category)
            db.session.commit()
            flash(f"'{name}' category added successfully!", 'success')

        except Exception:
            db.session.rollback()
            flash('Could not save category. Please try again.', 'error')

        return redirect(url_for('main.categories'))

    income_categories = Category.query.filter_by(
        user_id=current_user.id,
        type='income'
    ).order_by(Category.name.asc()).all()

    expense_categories = Category.query.filter_by(
        user_id=current_user.id,
        type='expense'
    ).order_by(Category.name.asc()).all()

    return render_template(
        'categories.html',
        income_categories=income_categories,
        expense_categories=expense_categories
    )


@main_bp.route('/categories/<int:category_id>/edit', methods=['POST'])
@login_required
def edit_category(category_id):

    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id
    ).first_or_404()

    name = request.form.get('name', '').strip()
    cat_type = request.form.get('type', '').strip().lower()

    if not name:
        flash('Category name cannot be empty.', 'error')
        return redirect(url_for('main.categories'))

    if len(name) > 50:
        flash('Category name must be 50 characters or less.', 'error')
        return redirect(url_for('main.categories'))

    if cat_type not in ['income', 'expense']:
        flash('Please select a valid category type.', 'error')
        return redirect(url_for('main.categories'))

    if cat_type != category.type:

        tx_count = Transaction.query.filter_by(
            category_id=category.id,
            user_id=current_user.id
        ).count()

        if tx_count > 0:
            flash(
                f"Cannot change category type because it is currently assigned to {tx_count} transaction(s).",
                'error'
            )
            return redirect(url_for('main.categories'))

    duplicate = Category.query.filter(
        Category.user_id == current_user.id,
        Category.type == cat_type,
        Category.id != category.id,
        db.func.lower(Category.name) == name.lower()
    ).first()

    if duplicate:
        flash(f"A {cat_type} category named '{name}' already exists.", 'error')
        return redirect(url_for('main.categories'))

    category.name = name
    category.type = cat_type

    try:
        db.session.commit()
        flash('Category updated successfully!', 'success')

    except Exception:
        db.session.rollback()
        flash('Could not update category.', 'error')

    return redirect(url_for('main.categories'))


@main_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):

    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id
    ).first_or_404()

    tx_count = Transaction.query.filter_by(
        category_id=category.id,
        user_id=current_user.id
    ).count()

    if tx_count > 0:
        flash(
            f"Cannot delete category '{category.name}' because it is assigned to {tx_count} transaction(s).",
            'error'
        )
        return redirect(url_for('main.categories'))

    try:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully.', 'success')

    except Exception:
        db.session.rollback()
        flash('Could not delete category.', 'error')

    return redirect(url_for('main.categories'))


# =========================================================
# BUDGETS
# =========================================================

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def get_budget_metrics_main(budget):

    """Calculate actual spending, remaining, percent and status."""

    start_date = date(budget.year, budget.month, 1)

    if budget.month == 12:
        next_month_start = date(budget.year + 1, 1, 1)
    else:
        next_month_start = date(budget.year, budget.month + 1, 1)

    query = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == budget.user_id,
        Transaction.type == 'expense',
        Transaction.date >= start_date,
        Transaction.date < next_month_start,
    )

    if budget.category_id is not None:
        query = query.filter(
            Transaction.category_id == budget.category_id
        )

    spent = query.scalar()

    budget_amt = Decimal(str(budget.amount))
    spent_amt = Decimal(str(spent))
    remaining_amt = budget_amt - spent_amt

    if budget_amt > 0:
        percent = float(
            (spent_amt / budget_amt) * Decimal("100")
        )
    else:
        percent = 0.0

    if percent > 100.0:
        status = "overspent"
    elif percent >= 80.0:
        status = "warning"
    else:
        status = "normal"

    month_name = (
        MONTH_NAMES[budget.month]
        if 1 <= budget.month <= 12
        else str(budget.month)
    )

    return {
        "budget": budget,
        "spent": spent_amt,
        "remaining": remaining_amt,
        "percent": round(percent, 1),
        "status": status,
        "progress_width": min(percent, 100.0),
        "month_name": month_name,
    }


@main_bp.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():

    if request.method == 'POST':

        category_id_val = request.form.get('category_id')
        amount_text = request.form.get('amount', '').strip()
        month_val = request.form.get('month', '').strip()
        year_val = request.form.get('year', '').strip()

        if not category_id_val:
            flash('Please select an expense category.', 'error')
            return redirect(url_for('main.budgets'))

        try:
            category_id = int(category_id_val)
        except (ValueError, TypeError):
            flash('Invalid category selection.', 'error')
            return redirect(url_for('main.budgets'))

        category = Category.query.filter_by(
            id=category_id,
            user_id=current_user.id
        ).first()

        if not category or category.type != 'expense':
            flash(
                'Budgets can only be set for your expense categories.',
                'error'
            )
            return redirect(url_for('main.budgets'))

        try:
            amount = Decimal(amount_text)

            if (
                not amount.is_finite()
                or amount <= 0
                or amount >= Decimal('10000000000')
            ):
                raise ValueError

            if amount.as_tuple().exponent < -2:
                raise ValueError

            amount = amount.quantize(Decimal('0.01'))

        except (InvalidOperation, ValueError, TypeError):
            flash('Please enter a valid positive budget amount.', 'error')
            return redirect(url_for('main.budgets'))

        try:
            month = int(month_val)

            if month < 1 or month > 12:
                raise ValueError

        except (ValueError, TypeError):
            flash('Please select a valid month (1-12).', 'error')
            return redirect(url_for('main.budgets'))

        try:
            year = int(year_val)

            if year < 2000 or year > 2100:
                raise ValueError

        except (ValueError, TypeError):
            flash('Please enter a valid year between 2000 and 2100.', 'error')
            return redirect(url_for('main.budgets'))

        existing = Budget.query.filter_by(
            user_id=current_user.id,
            category_id=category_id,
            month=month,
            year=year
        ).first()

        if existing:
            flash(
                f"A budget for '{category.name}' in {MONTH_NAMES[month]} {year} already exists.",
                'error'
            )
            return redirect(url_for('main.budgets'))

        budget = Budget(
            user_id=current_user.id,
            category_id=category_id,
            amount=amount,
            month=month,
            year=year
        )

        try:
            db.session.add(budget)
            db.session.commit()

            flash(
                f"Budget for '{category.name}' ({MONTH_NAMES[month]} {year}) set to ₹{amount:.2f} successfully!",
                'success'
            )

        except Exception:
            db.session.rollback()
            flash('Could not save budget. Please try again.', 'error')

        return redirect(url_for('main.budgets'))

    today = date.today()

    selected_month = request.args.get('month', type=int) or today.month
    selected_year = request.args.get('year', type=int) or today.year

    expense_categories = Category.query.filter_by(
        user_id=current_user.id,
        type='expense'
    ).order_by(Category.name.asc()).all()

    user_budgets = Budget.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Budget.year.desc(),
        Budget.month.desc(),
        Budget.id.desc()
    ).all()

    budgets_with_metrics = [
        get_budget_metrics_main(b)
        for b in user_budgets
    ]

    total_budgeted = sum(
        (b["budget"].amount for b in budgets_with_metrics),
        Decimal("0")
    )

    total_spent = sum(
        (b["spent"] for b in budgets_with_metrics),
        Decimal("0")
    )

    total_remaining = total_budgeted - total_spent

    overall_percent = (
        round(float((total_spent / total_budgeted * 100)), 1)
        if total_budgeted > 0
        else 0.0
    )

    return render_template(
        'budgets.html',
        budgets_with_metrics=budgets_with_metrics,
        expense_categories=expense_categories,
        current_month=today.month,
        current_year=today.year,
        selected_month=selected_month,
        selected_year=selected_year,
        month_names=MONTH_NAMES,
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        total_remaining=total_remaining,
        overall_percent=overall_percent,
    )


@main_bp.route('/budgets/<int:budget_id>/edit', methods=['POST'])
@login_required
def edit_budget(budget_id):

    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id
    ).first_or_404()

    category_id_val = request.form.get('category_id')
    amount_text = request.form.get('amount', '').strip()
    month_val = request.form.get('month', '').strip()
    year_val = request.form.get('year', '').strip()

    if not category_id_val:
        flash('Please select an expense category.', 'error')
        return redirect(url_for('main.budgets'))

    try:
        category_id = int(category_id_val)
    except (ValueError, TypeError):
        flash('Invalid category selection.', 'error')
        return redirect(url_for('main.budgets'))

    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id
    ).first()

    if not category or category.type != 'expense':
        flash(
            'Budgets can only be set for your expense categories.',
            'error'
        )
        return redirect(url_for('main.budgets'))

    try:
        amount = Decimal(amount_text)

        if (
            not amount.is_finite()
            or amount <= 0
            or amount >= Decimal('10000000000')
        ):
            raise ValueError

        if amount.as_tuple().exponent < -2:
            raise ValueError

        amount = amount.quantize(Decimal('0.01'))

    except (InvalidOperation, ValueError, TypeError):
        flash('Please enter a valid positive budget amount.', 'error')
        return redirect(url_for('main.budgets'))

    try:
        month = int(month_val)

        if month < 1 or month > 12:
            raise ValueError

    except (ValueError, TypeError):
        flash('Please select a valid month (1-12).', 'error')
        return redirect(url_for('main.budgets'))

    try:
        year = int(year_val)

        if year < 2000 or year > 2100:
            raise ValueError

    except (ValueError, TypeError):
        flash('Please enter a valid year between 2000 and 2100.', 'error')
        return redirect(url_for('main.budgets'))

    duplicate = Budget.query.filter(
        Budget.user_id == current_user.id,
        Budget.category_id == category_id,
        Budget.month == month,
        Budget.year == year,
        Budget.id != budget.id
    ).first()

    if duplicate:
        flash(
            f"A budget for '{category.name}' in {MONTH_NAMES[month]} {year} already exists.",
            'error'
        )
        return redirect(url_for('main.budgets'))

    budget.category_id = category_id
    budget.amount = amount
    budget.month = month
    budget.year = year

    try:
        db.session.commit()
        flash('Budget updated successfully!', 'success')

    except Exception:
        db.session.rollback()
        flash('Could not update budget.', 'error')

    return redirect(url_for('main.budgets'))


@main_bp.route('/budgets/<int:budget_id>/delete', methods=['POST'])
@login_required
def delete_budget(budget_id):

    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id
    ).first_or_404()

    try:
        db.session.delete(budget)
        db.session.commit()
        flash('Budget deleted successfully.', 'success')

    except Exception:
        db.session.rollback()
        flash('Could not delete budget.', 'error')

    return redirect(url_for('main.budgets'))


# =========================================================
# ANALYTICS & REPORTS
# =========================================================

@main_bp.route('/analytics')
@login_required
def analytics():
    from ..services.ai_advisor import get_user_ai_financial_advisory
    advisory = get_user_ai_financial_advisory(current_user.id)

    expense_txs = Transaction.query.filter_by(
        user_id=current_user.id,
        type='expense'
    ).all()

    category_data = {}
    for t in expense_txs:
        c_name = t.category.name if t.category else 'Uncategorized'
        category_data[c_name] = category_data.get(c_name, 0.0) + float(t.amount)

    return render_template(
        'analytics.html',
        advisory=advisory,
        category_labels=list(category_data.keys()),
        category_values=list(category_data.values())
    )


@main_bp.route('/reports')
@login_required
def reports():
    from ..services.ai_advisor import get_user_ai_financial_advisory
    advisory = get_user_ai_financial_advisory(current_user.id)

    txs = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc(), Transaction.id.desc()).all()

    return render_template(
        'reports.html',
        advisory=advisory,
        transactions=txs
    )


@main_bp.route('/reports/export-csv')
@login_required
def export_csv():
    import csv
    from io import StringIO
    from flask import Response

    txs = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.date.desc(), Transaction.id.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Date', 'Type', 'Category', 'Amount', 'Description'])
    for t in txs:
        cat_name = t.category.name if t.category else 'Uncategorized'
        cw.writerow([
            t.id,
            t.date.isoformat(),
            t.type,
            cat_name,
            f"{float(t.amount):.2f}",
            t.description or ''
        ])

    output = si.getvalue()
    filename = f"syri_financial_report_{date.today().isoformat()}.csv"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
