"""Tests for transaction API endpoints (PUT and DELETE) and data isolation."""

import unittest
from datetime import date
from decimal import Decimal

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models.user import User
from app.models.transaction import Transaction


class TestTransactionsAPI(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create User 1
        self.user1 = User(username="alice", email="alice@example.com")
        self.user1.set_password("Password123")
        db.session.add(self.user1)

        # Create User 2
        self.user2 = User(username="bob", email="bob@example.com")
        self.user2.set_password("Password123")
        db.session.add(self.user2)

        db.session.commit()

        # Create a transaction for User 1
        self.tx1 = Transaction(
            user_id=self.user1.id,
            type="expense",
            amount=Decimal("250.00"),
            description="Grocery shopping",
            date=date(2026, 11, 1),
        )
        db.session.add(self.tx1)
        db.session.commit()
        self.tx1_id = self.tx1.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    # ----------------------------------------------------
    # EDIT (PUT) TESTS
    # ----------------------------------------------------
    def test_user_can_edit_own_transaction(self):
        """User 1 should be able to edit their own transaction via PUT."""
        self.login("alice@example.com", "Password123")

        update_payload = {
            "type": "income",
            "amount": "1200.50",
            "description": "Freelance payout",
            "date": "2026-11-03",
        }

        response = self.client.put(
            f"/api/transactions/{self.tx1_id}",
            json=update_payload,
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("message", data)
        self.assertEqual(data["transaction"]["type"], "income")
        self.assertEqual(data["transaction"]["amount"], "1200.50")
        self.assertEqual(data["transaction"]["description"], "Freelance payout")
        self.assertEqual(data["transaction"]["date"], "2026-11-03")

        # Verify database record
        updated_tx = db.session.get(Transaction, self.tx1_id)
        self.assertEqual(updated_tx.type, "income")
        self.assertEqual(Decimal(str(updated_tx.amount)), Decimal("1200.50"))
        self.assertEqual(updated_tx.description, "Freelance payout")
        self.assertEqual(updated_tx.date, date(2026, 11, 3))

    def test_edit_validation_errors(self):
        """Invalid PUT payloads must be rejected with 400 Bad Request."""
        self.login("alice@example.com", "Password123")

        # Negative amount
        res = self.client.put(
            f"/api/transactions/{self.tx1_id}",
            json={"type": "expense", "amount": "-50.00", "date": "2026-11-03"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

        # Invalid type
        res = self.client.put(
            f"/api/transactions/{self.tx1_id}",
            json={"type": "invalid_type", "amount": "50.00", "date": "2026-11-03"},
        )
        self.assertEqual(res.status_code, 400)

        # Missing required field
        res = self.client.put(
            f"/api/transactions/{self.tx1_id}",
            json={"type": "expense", "amount": "50.00"},  # missing date
        )
        self.assertEqual(res.status_code, 400)

    # ----------------------------------------------------
    # DELETE TESTS
    # ----------------------------------------------------
    def test_user_can_delete_own_transaction(self):
        """User 1 should be able to delete their own transaction via DELETE."""
        self.login("alice@example.com", "Password123")

        response = self.client.delete(f"/api/transactions/{self.tx1_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("message", data)

        # Verify removed from database
        deleted_tx = db.session.get(Transaction, self.tx1_id)
        self.assertIsNone(deleted_tx)

    # ----------------------------------------------------
    # SECURITY & MULTI-USER ISOLATION TESTS
    # ----------------------------------------------------
    def test_user_cannot_edit_other_users_transaction(self):
        """User 2 must NOT be able to edit User 1's transaction (returns 404)."""
        self.login("bob@example.com", "Password123")

        response = self.client.put(
            f"/api/transactions/{self.tx1_id}",
            json={
                "type": "income",
                "amount": "9999.00",
                "description": "Hacked",
                "date": "2026-11-03",
            },
        )

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data.get("error"), "Transaction not found.")

        # Ensure User 1's transaction was NOT altered
        tx = db.session.get(Transaction, self.tx1_id)
        self.assertEqual(tx.description, "Grocery shopping")
        self.assertEqual(tx.type, "expense")

    def test_user_cannot_delete_other_users_transaction(self):
        """User 2 must NOT be able to delete User 1's transaction (returns 404)."""
        self.login("bob@example.com", "Password123")

        response = self.client.delete(f"/api/transactions/{self.tx1_id}")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data.get("error"), "Transaction not found.")

        # Ensure User 1's transaction is still intact
        tx = db.session.get(Transaction, self.tx1_id)
        self.assertIsNotNone(tx)

    def test_unauthenticated_cannot_edit_or_delete(self):
        """Unauthenticated requests must be blocked by login_required."""
        # PUT
        res_put = self.client.put(
            f"/api/transactions/{self.tx1_id}",
            json={
                "type": "income",
                "amount": "100.00",
                "date": "2026-11-03",
            },
        )
        self.assertEqual(res_put.status_code, 302)  # Redirects to login

        # DELETE
        res_del = self.client.delete(f"/api/transactions/{self.tx1_id}")
        self.assertEqual(res_del.status_code, 302)  # Redirects to login


if __name__ == "__main__":
    unittest.main()
