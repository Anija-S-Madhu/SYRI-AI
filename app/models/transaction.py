from datetime import datetime, timezone
from ..extensions import db


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )

    category_id = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['category_id', 'user_id'],
            ['categories.id', 'categories.user_id'],
            name='fk_transaction_category_owner'
        ),
    )

    def __repr__(self):
        return f'<Transaction {self.type} {self.amount}>'