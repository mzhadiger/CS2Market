"""
auth.py — Flask-Login integration.

Passwords are hashed with Werkzeug's pbkdf2:sha256. Plaintext passwords
never touch the database.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

import db

# --- Flask-Login plumbing ---------------------------------------------------

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "You need to sign in first."


class User(UserMixin):
    """Wraps a row from the Users table. Flask-Login requires .get_id()."""
    def __init__(self, row):
        self.id             = row["user_id"]   # required by Flask-Login
        self.username       = row["username"]
        self.email          = row["email"]
        self.wallet_balance = row["wallet_balance"]
        self.reputation     = row["reputation"]


@login_manager.user_loader
def load_user(user_id):
    row = db.query_one(
        "SELECT user_id, username, email, wallet_balance, reputation "
        "  FROM Users WHERE user_id = %s",
        (user_id,),
    )
    return User(row) if row else None


# --- Routes -----------------------------------------------------------------

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not (username and email and password):
            flash("All fields are required.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        # Check for duplicates using a single OR'd lookup.
        dup = db.query_one(
            "SELECT user_id FROM Users WHERE username = %s OR email = %s",
            (username, email),
        )
        if dup:
            flash("That username or email is already taken.", "error")
            return render_template("register.html")

        db.execute(
            "INSERT INTO Users (username, email, password_hash, wallet_balance) "
            "VALUES (%s, %s, %s, %s)",
            (username, email, generate_password_hash(password), 500.00),
        )
        flash("Account created — please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        row = db.query_one(
            "SELECT user_id, username, email, password_hash, wallet_balance, reputation "
            "  FROM Users WHERE username = %s",
            (username,),
        )
        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row), remember=True)
            flash(f"Welcome back, {row['username']}.", "success")
            return redirect(request.args.get("next") or url_for("home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "success")
    return redirect(url_for("home"))