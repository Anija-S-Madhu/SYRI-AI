"""Budget model — monthly spending limits per category."""

from datetime import datetime, timezone

from ..extensions import db


class Budget(db.Model):
    """Monthly budget limit owned by a user."""

    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )

    category_id = db.Column(
        db.Integer,
        nullable=True
    )

    # Accurate financial storage
    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['category_id', 'user_id'],
            ['categories.id', 'categories.user_id'],
            name='fk_budget_category_owner'
        ),
        db.UniqueConstraint(
            'user_id',
            'category_id',
            'month',
            'year',
            name='uq_user_budget_period'
        ),
    )

    def __repr__(self):
        return f'<Budget {self.amount} for {self.month}/{self.year}>'