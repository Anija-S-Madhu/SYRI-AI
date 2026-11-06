"""Comprehensive test suite for Budget Management module.
Covers authentication, CRUD, validation, actual transaction spending calculation,
warning and overspending alerts, duplicate prevention, and strict multi-user isolation.
"""

import unittest
from datetime import date
from decimal import Decimal

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models.user import User
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.budget import Budget


class TestBudgetManagement(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create User 1 (Alice)
        self.user1 = User(username="alice", email="alice@example.com")
        self.user1.set_password("Password123")
        db.session.add(self.user1)

        # Create User 2 (Bob)
        self.user2 = User(username="bob", email="bob@example.com")
        self.user2.set_password("Password123")
        db.session.add(self.user2)

        db.session.commit()

        # Alice's categories
        self.cat_food = Category(user_id=self.user1.id, name="Groceries", type="expense")
        self.cat_salary = Category(user_id=self.user1.id, name="Salary", type="income")
        db.session.add_all([self.cat_food, self.cat_salary])

        # Bob's category
        self.cat_bob = Category(user_id=self.user2.id, name="Bob Groceries", type="expense")
        db.session.add(self.cat_bob)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)

    def login(self, email="alice@example.com", password="Password123"):
        self.logout()
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    # ----------------------------------------------------
    # 1. AUTHENTICATION & ACCESS CONTROL
    # ----------------------------------------------------
    def test_unauthenticated_access_is_blocked(self):
        """Unauthenticated requests must redirect to /login."""
        res_page = self.client.get("/budgets")
        self.assertEqual(res_page.status_code, 302)
        self.assertIn("/login", res_page.headers.get("Location", ""))

        res_api = self.client.get("/api/budgets")
        self.assertEqual(res_api.status_code, 302)

        res_post = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_food.id, "amount": "1000", "month": 11, "year": 2026},
        )
        self.assertEqual(res_post.status_code, 302)

    def test_authenticated_user_can_access_budgets_page(self):
        """Logged-in user can access /budgets successfully."""
        self.login("alice@example.com", "Password123")
        res = self.client.get("/budgets")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Budget Management", res.data)
        self.assertIn(b"Create Monthly Budget", res.data)
        self.assertIn(b"Total Budgeted", res.data)

    # ----------------------------------------------------
    # 2. CRUD OPERATIONS (PAGE AND API)
    # ----------------------------------------------------
    def test_create_budget_via_form_and_api(self):
        """User can create budgets via web form and API."""
        self.login("alice@example.com", "Password123")

        # Via form
        res_form = self.client.post(
            "/budgets",
            data={
                "category_id": str(self.cat_food.id),
                "amount": "5000.00",
                "month": "11",
                "year": "2026",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b"Groceries", res_form.data)
        self.assertIn(b"5000.00", res_form.data)

        # Check DB
        b1 = Budget.query.filter_by(
            user_id=self.user1.id, category_id=self.cat_food.id, month=11, year=2026
        ).first()
        self.assertIsNotNone(b1)
        self.assertEqual(Decimal(str(b1.amount)), Decimal("5000.00"))

        # Via API (different month)
        res_api = self.client.post(
            "/api/budgets",
            json={
                "category_id": self.cat_food.id,
                "amount": "6000.00",
                "month": 12,
                "year": 2026,
            },
        )
        self.assertEqual(res_api.status_code, 201)
        data = res_api.get_json()
        self.assertEqual(data["budget"]["amount"], "6000.00")
        self.assertEqual(data["budget"]["month"], 12)

    def test_edit_budget(self):
        """User can edit an existing budget."""
        self.login("alice@example.com", "Password123")

        budget = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("4000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget)
        db.session.commit()

        # Update via API
        res = self.client.put(
            f"/api/budgets/{budget.id}",
            json={
                "category_id": self.cat_food.id,
                "amount": "4500.00",
                "month": 11,
                "year": 2026,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["budget"]["amount"], "4500.00")

        updated = db.session.get(Budget, budget.id)
        self.assertEqual(Decimal(str(updated.amount)), Decimal("4500.00"))

    def test_delete_budget(self):
        """User can delete their own budget."""
        self.login("alice@example.com", "Password123")

        budget = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("3000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget)
        db.session.commit()
        b_id = budget.id

        res = self.client.delete(f"/api/budgets/{b_id}")
        self.assertEqual(res.status_code, 200)

        # Verify deletion
        self.assertIsNone(db.session.get(Budget, b_id))

    # ----------------------------------------------------
    # 3. SPENDING CALCULATIONS & ALERTS (NORMAL, WARNING, OVERSPENT)
    # ----------------------------------------------------
    def test_budget_spending_calculation_normal(self):
        """Budget with < 80% spent is in 'normal' status with accurate remaining amount."""
        self.login("alice@example.com", "Password123")

        budget = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("1000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget)

        # Add 500 expense in Nov 2026
        tx = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="expense",
            amount=Decimal("500.00"),
            date=date(2026, 11, 15),
        )
        db.session.add(tx)
        db.session.commit()

        res = self.client.get(f"/api/budgets/{budget.id}")
        self.assertEqual(res.status_code, 200)
        b = res.get_json()["budget"]

        self.assertEqual(b["spent"], "500.00")
        self.assertEqual(b["remaining"], "500.00")
        self.assertEqual(b["percent"], 50.0)
        self.assertEqual(b["status"], "normal")

    def test_budget_warning_at_80_percent(self):
        """Budget with >= 80% and <= 100% spent triggers warning status."""
        self.login("alice@example.com", "Password123")

        budget = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("1000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget)

        # Add 850 expense in Nov 2026 (85%)
        tx = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="expense",
            amount=Decimal("850.00"),
            date=date(2026, 11, 10),
        )
        db.session.add(tx)
        db.session.commit()

        res = self.client.get(f"/api/budgets/{budget.id}")
        b = res.get_json()["budget"]

        self.assertEqual(b["spent"], "850.00")
        self.assertEqual(b["remaining"], "150.00")
        self.assertEqual(b["percent"], 85.0)
        self.assertEqual(b["status"], "warning")

        # Web page should show warning
        res_page = self.client.get("/budgets")
        self.assertIn(b"Caution", res_page.data)

    def test_budget_overspent_at_over_100_percent(self):
        """Budget exceeding 100% triggers overspent status and negative remaining."""
        self.login("alice@example.com", "Password123")

        budget = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("1000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget)

        # Add 1250 expense in Nov 2026 (125%)
        tx = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="expense",
            amount=Decimal("1250.00"),
            date=date(2026, 11, 20),
        )
        db.session.add(tx)
        db.session.commit()

        res = self.client.get(f"/api/budgets/{budget.id}")
        b = res.get_json()["budget"]

        self.assertEqual(b["spent"], "1250.00")
        self.assertEqual(b["remaining"], "-250.00")
        self.assertEqual(b["percent"], 125.0)
        self.assertEqual(b["status"], "overspent")

        # Web page should show over budget banner
        res_page = self.client.get("/budgets")
        self.assertIn(b"Over Budget", res_page.data)

    def test_only_matching_month_and_category_transactions_count(self):
        """Transactions in other months or other categories must NOT count towards the budget."""
        self.login("alice@example.com", "Password123")

        cat2 = Category(user_id=self.user1.id, name="Electronics", type="expense")
        db.session.add(cat2)
        db.session.commit()

        budget = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("1000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget)

        # 1. Matching transaction: 300
        tx1 = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="expense",
            amount=Decimal("300.00"),
            date=date(2026, 11, 5),
        )
        # 2. Different month (October): 400
        tx2 = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="expense",
            amount=Decimal("400.00"),
            date=date(2026, 10, 25),
        )
        # 3. Different category (Electronics in Nov): 600
        tx3 = Transaction(
            user_id=self.user1.id,
            category_id=cat2.id,
            type="expense",
            amount=Decimal("600.00"),
            date=date(2026, 11, 8),
        )
        # 4. Income transaction in Nov for same category: 2000
        tx4 = Transaction(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            type="income",
            amount=Decimal("2000.00"),
            date=date(2026, 11, 1),
        )
        db.session.add_all([tx1, tx2, tx3, tx4])
        db.session.commit()

        res = self.client.get(f"/api/budgets/{budget.id}")
        b = res.get_json()["budget"]

        # Only tx1 (300.00) should be counted!
        self.assertEqual(b["spent"], "300.00")
        self.assertEqual(b["remaining"], "700.00")
        self.assertEqual(b["percent"], 30.0)

    # ----------------------------------------------------
    # 4. VALIDATION & DUPLICATE PREVENTION
    # ----------------------------------------------------
    def test_prevent_duplicate_budget_for_same_category_and_period(self):
        """Cannot create two budgets for the same category, month, and year."""
        self.login("alice@example.com", "Password123")

        # Create first
        res1 = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_food.id, "amount": "1000", "month": 11, "year": 2026},
        )
        self.assertEqual(res1.status_code, 201)

        # Duplicate attempt
        res2 = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_food.id, "amount": "2000", "month": 11, "year": 2026},
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already exists", res2.get_json()["error"])

    def test_invalid_amounts_and_dates_rejected(self):
        """Reject non-positive amounts, invalid months, and non-expense categories."""
        self.login("alice@example.com", "Password123")

        # Negative amount
        res1 = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_food.id, "amount": "-100", "month": 11, "year": 2026},
        )
        self.assertEqual(res1.status_code, 400)

        # Invalid month
        res2 = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_food.id, "amount": "100", "month": 13, "year": 2026},
        )
        self.assertEqual(res2.status_code, 400)

        # Non-expense category (Salary is income)
        res3 = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_salary.id, "amount": "100", "month": 11, "year": 2026},
        )
        self.assertEqual(res3.status_code, 400)
        self.assertIn("expense categories", res3.get_json()["error"])

    # ----------------------------------------------------
    # 5. STRICT MULTI-USER ISOLATION
    # ----------------------------------------------------
    def test_other_users_transactions_do_not_affect_budget_spending(self):
        """Bob's expenses must NEVER count towards Alice's budget."""
        self.login("alice@example.com", "Password123")

        # Alice creates budget
        budget_alice = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("1000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget_alice)

        # Bob records an expense in Nov 2026
        tx_bob = Transaction(
            user_id=self.user2.id,
            category_id=self.cat_bob.id,
            type="expense",
            amount=Decimal("950.00"),
            date=date(2026, 11, 10),
        )
        db.session.add(tx_bob)
        db.session.commit()

        # Alice checks her budget: spent must be 0, not 950!
        res = self.client.get(f"/api/budgets/{budget_alice.id}")
        b = res.get_json()["budget"]
        self.assertEqual(b["spent"], "0.00")
        self.assertEqual(b["remaining"], "1000.00")
        self.assertEqual(b["percent"], 0.0)

    def test_user_cannot_access_or_modify_other_users_budget(self):
        """Bob cannot view, edit, or delete Alice's budget."""
        # Alice creates a budget
        budget_alice = Budget(
            user_id=self.user1.id,
            category_id=self.cat_food.id,
            amount=Decimal("1000.00"),
            month=11,
            year=2026,
        )
        db.session.add(budget_alice)
        db.session.commit()
        alice_b_id = budget_alice.id

        # Bob logs in
        self.login("bob@example.com", "Password123")

        # Bob lists budgets: Alice's budget must NOT appear
        res_list = self.client.get("/api/budgets")
        self.assertEqual(res_list.status_code, 200)
        self.assertEqual(len(res_list.get_json()["budgets"]), 0)

        # Bob tries to GET Alice's budget
        res_get = self.client.get(f"/api/budgets/{alice_b_id}")
        self.assertEqual(res_get.status_code, 404)

        # Bob tries to PUT Alice's budget
        res_put = self.client.put(
            f"/api/budgets/{alice_b_id}",
            json={"category_id": self.cat_bob.id, "amount": "9999", "month": 11, "year": 2026},
        )
        self.assertEqual(res_put.status_code, 404)

        # Bob tries to DELETE Alice's budget
        res_del = self.client.delete(f"/api/budgets/{alice_b_id}")
        self.assertEqual(res_del.status_code, 404)

        # Alice's budget remains intact
        self.assertIsNotNone(db.session.get(Budget, alice_b_id))

    def test_user_cannot_link_budget_to_other_users_category(self):
        """Bob cannot create a budget using Alice's category ID."""
        self.login("bob@example.com", "Password123")

        res = self.client.post(
            "/api/budgets",
            json={"category_id": self.cat_food.id, "amount": "1000", "month": 11, "year": 2026},
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
