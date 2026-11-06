"""Utility functions for authorization and data isolation."""

from flask import abort
from flask_login import current_user


def get_user_record_or_404(model, record_id):
    """Fetch a record by ID, ensuring it belongs to the current user.

    Returns the record if ownership is confirmed.
    Raises 404 if the record does not exist.
    Raises 403 if the record belongs to another user.
    """
    record = model.query.get_or_404(record_id)
    if record.user_id != current_user.id:
        abort(403)
    return record
