"""Category model — user-specific income/expense categories."""

from ..extensions import db


class Category(db.Model):
    """Spending or income category owned by a single user."""

    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(10), nullable=False)

    # Relationships
    transactions = db.relationship(
        'Transaction',
        backref=db.backref('category', overlaps='transactions,user'),
        lazy=True,
        overlaps='user,transactions'
    )

    budgets = db.relationship(
        'Budget',
        backref=db.backref('category', overlaps='budgets,user'),
        lazy=True,
        overlaps='user,budgets'
    )

    __table_args__ = (
        db.UniqueConstraint(
            'user_id',
            'name',
            'type',
            name='uq_user_category'
        ),
        db.UniqueConstraint(
            'id',
            'user_id',
            name='uq_category_id_user'
        ),
    )

    def __repr__(self):
        return f'<Category {self.name} ({self.type})>'