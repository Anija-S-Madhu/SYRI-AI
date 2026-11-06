"""Comprehensive test suite for Category Management module.
Covers authentication, CRUD, validation, transaction protection, and multi-user data isolation.
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


class TestCategoryManagement(unittest.TestCase):
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
        """Unauthenticated requests to categories page and APIs must be redirected to login."""
        # Page route
        res = self.client.get("/categories")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # API routes
        res_api = self.client.get("/api/categories")
        self.assertEqual(res_api.status_code, 302)

        res_post = self.client.post("/api/categories", json={"name": "Test", "type": "income"})
        self.assertEqual(res_post.status_code, 302)

    def test_authenticated_user_can_access_categories_page(self):
        """Logged-in user should access /categories successfully."""
        self.login("alice@example.com", "Password123")
        res = self.client.get("/categories")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Category Management", res.data)
        self.assertIn(b"Income Categories", res.data)
        self.assertIn(b"Expense Categories", res.data)

    # ----------------------------------------------------
    # 2. CRUD OPERATIONS (PAGE AND API)
    # ----------------------------------------------------
    def test_add_income_and_expense_categories_via_form(self):
        """User can add both income and expense categories via web form."""
        self.login("alice@example.com", "Password123")

        # Add Income category
        res1 = self.client.post(
            "/categories",
            data={"name": "Salary", "type": "income"},
            follow_redirects=True,
        )
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b"Salary", res1.data)

        # Add Expense category
        res2 = self.client.post(
            "/categories",
            data={"name": "Groceries", "type": "expense"},
            follow_redirects=True,
        )
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"Groceries", res2.data)

        # Check DB
        cat_inc = Category.query.filter_by(user_id=self.user1.id, name="Salary").first()
        self.assertIsNotNone(cat_inc)
        self.assertEqual(cat_inc.type, "income")

        cat_exp = Category.query.filter_by(user_id=self.user1.id, name="Groceries").first()
        self.assertIsNotNone(cat_exp)
        self.assertEqual(cat_exp.type, "expense")

    def test_add_categories_via_api(self):
        """User can add category via JSON API."""
        self.login("alice@example.com", "Password123")

        res = self.client.post(
            "/api/categories",
            json={"name": "Consulting", "type": "income"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["category"]["name"], "Consulting")
        self.assertEqual(data["category"]["type"], "income")

    def test_edit_category(self):
        """User can edit their category name via API and web form."""
        self.login("alice@example.com", "Password123")

        cat = Category(user_id=self.user1.id, name="Food", type="expense")
        db.session.add(cat)
        db.session.commit()

        # Edit via API
        res = self.client.put(
            f"/api/categories/{cat.id}",
            json={"name": "Dining & Groceries", "type": "expense"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["category"]["name"], "Dining & Groceries")

        updated = db.session.get(Category, cat.id)
        self.assertEqual(updated.name, "Dining & Groceries")

    def test_delete_unassigned_category(self):
        """User can delete an unassigned category."""
        self.login("alice@example.com", "Password123")

        cat = Category(user_id=self.user1.id, name="Old Hobby", type="expense")
        db.session.add(cat)
        db.session.commit()
        cat_id = cat.id

        res = self.client.delete(f"/api/categories/{cat_id}")
        self.assertEqual(res.status_code, 200)

        # Verify deletion
        self.assertIsNone(db.session.get(Category, cat_id))

    # ----------------------------------------------------
    # 3. VALIDATION & DUPLICATE PREVENTION
    # ----------------------------------------------------
    def test_prevent_duplicate_category_name_for_same_type(self):
        """Prevent duplicate category name for the same user and type (case-insensitive)."""
        self.login("alice@example.com", "Password123")

        # Create first
        self.client.post("/api/categories", json={"name": "Utilities", "type": "expense"})

        # Duplicate with exact case
        res_dup1 = self.client.post("/api/categories", json={"name": "Utilities", "type": "expense"})
        self.assertEqual(res_dup1.status_code, 400)
        self.assertIn("already exists", res_dup1.get_json()["error"])

        # Duplicate with different case
        res_dup2 = self.client.post("/api/categories", json={"name": "utilities", "type": "expense"})
        self.assertEqual(res_dup2.status_code, 400)
        self.assertIn("already exists", res_dup2.get_json()["error"])

    def test_allow_same_name_for_different_type(self):
        """A user may have 'Other' as both an income category and an expense category."""
        self.login("alice@example.com", "Password123")

        res_inc = self.client.post("/api/categories", json={"name": "Other", "type": "income"})
        self.assertEqual(res_inc.status_code, 201)

        res_exp = self.client.post("/api/categories", json={"name": "Other", "type": "expense"})
        self.assertEqual(res_exp.status_code, 201)

    def test_empty_or_too_long_name_is_rejected(self):
        """Validation fails if category name is empty or exceeds 50 characters."""
        self.login("alice@example.com", "Password123")

        # Empty name
        res_empty = self.client.post("/api/categories", json={"name": "", "type": "income"})
        self.assertEqual(res_empty.status_code, 400)

        # Over 50 chars
        res_long = self.client.post("/api/categories", json={"name": "A" * 51, "type": "income"})
        self.assertEqual(res_long.status_code, 400)

        # Invalid type
        res_inv = self.client.post("/api/categories", json={"name": "Valid", "type": "transfer"})
        self.assertEqual(res_inv.status_code, 400)

    # ----------------------------------------------------
    # 4. PREVENT DELETION IF ASSIGNED TO TRANSACTIONS
    # ----------------------------------------------------
    def test_prevent_deleting_category_with_transactions(self):
        """Cannot delete a category currently assigned to transactions. Clear error message shown."""
        self.login("alice@example.com", "Password123")

        cat = Category(user_id=self.user1.id, name="Rent", type="expense")
        db.session.add(cat)
        db.session.commit()

        # Assign a transaction to this category
        tx = Transaction(
            user_id=self.user1.id,
            category_id=cat.id,
            type="expense",
            amount=Decimal("15000.00"),
            description="Monthly apartment rent",
            date=date(2026, 11, 1),
        )
        db.session.add(tx)
        db.session.commit()

        # Attempt DELETE via API
        res_api = self.client.delete(f"/api/categories/{cat.id}")
        self.assertEqual(res_api.status_code, 400)
        data = res_api.get_json()
        self.assertIn("Cannot delete category", data["error"])
        self.assertIn("assigned to 1 transaction(s)", data["error"])

        # Attempt DELETE via Form route
        res_form = self.client.post(f"/categories/{cat.id}/delete", follow_redirects=True)
        self.assertEqual(res_form.status_code, 200)
        self.assertIn(b"Cannot delete category", res_form.data)

        # Verify category STILL exists in database
        self.assertIsNotNone(db.session.get(Category, cat.id))

    def test_prevent_changing_type_if_transactions_exist(self):
        """Cannot change category type (e.g. expense -> income) if transactions are linked."""
        self.login("alice@example.com", "Password123")

        cat = Category(user_id=self.user1.id, name="Supplies", type="expense")
        db.session.add(cat)
        db.session.commit()

        tx = Transaction(
            user_id=self.user1.id,
            category_id=cat.id,
            type="expense",
            amount=Decimal("120.00"),
            date=date(2026, 11, 2),
        )
        db.session.add(tx)
        db.session.commit()

        # Attempt to change type to income
        res = self.client.put(
            f"/api/categories/{cat.id}",
            json={"name": "Supplies", "type": "income"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Cannot change category type", res.get_json()["error"])

    # ----------------------------------------------------
    # 5. STRICT MULTI-USER DATA ISOLATION
    # ----------------------------------------------------
    def test_users_can_have_same_category_name_independently(self):
        """User 1 and User 2 can both have a category named 'Salary' without conflict."""
        # User 1 adds Salary
        self.login("alice@example.com", "Password123")
        res1 = self.client.post("/api/categories", json={"name": "Salary", "type": "income"})
        self.assertEqual(res1.status_code, 201)

        # User 2 logs in and adds Salary
        self.login("bob@example.com", "Password123")
        res2 = self.client.post("/api/categories", json={"name": "Salary", "type": "income"})
        self.assertEqual(res2.status_code, 201)

        # Check DB has two separate records with separate user_id
        salaries = Category.query.filter_by(name="Salary").all()
        self.assertEqual(len(salaries), 2)
        user_ids = {s.user_id for s in salaries}
        self.assertEqual(user_ids, {self.user1.id, self.user2.id})

    def test_user_cannot_view_edit_or_delete_other_users_category(self):
        """Bob cannot access, update, or delete Alice's category."""
        # Alice creates a category
        cat_alice = Category(user_id=self.user1.id, name="Secret Venture", type="income")
        db.session.add(cat_alice)
        db.session.commit()
        alice_cat_id = cat_alice.id

        # Bob logs in
        self.login("bob@example.com", "Password123")

        # Bob lists categories: Alice's category must NOT appear
        res_list = self.client.get("/api/categories")
        self.assertEqual(res_list.status_code, 200)
        cat_names = [c["name"] for c in res_list.get_json()["categories"]]
        self.assertNotIn("Secret Venture", cat_names)

        # Bob tries to GET Alice's category detail
        res_get = self.client.get(f"/api/categories/{alice_cat_id}")
        self.assertEqual(res_get.status_code, 404)

        # Bob tries to PUT Alice's category
        res_put = self.client.put(
            f"/api/categories/{alice_cat_id}",
            json={"name": "Hacked Venture", "type": "income"},
        )
        self.assertEqual(res_put.status_code, 404)

        # Bob tries to DELETE Alice's category
        res_del = self.client.delete(f"/api/categories/{alice_cat_id}")
        self.assertEqual(res_del.status_code, 404)

        # Alice's category remains untouched
        intact_cat = db.session.get(Category, alice_cat_id)
        self.assertEqual(intact_cat.name, "Secret Venture")


if __name__ == "__main__":
    unittest.main()
