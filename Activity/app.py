import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, flash, g, redirect, render_template, request,
    send_from_directory, session, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = INSTANCE_DIR / "acc_portal.db"

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE = 5 * 1024 * 1024

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "acc-portal-dev-secret-change-me"),
    DATABASE=str(DB_PATH),
    UPLOAD_FOLDER=str(UPLOAD_DIR),
    MAX_CONTENT_LENGTH=MAX_FILE_SIZE,
)

INSTANCE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            course TEXT NOT NULL,
            year_level TEXT NOT NULL,
            valid_id_filename TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scholarship_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scholarship_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            household_income TEXT NOT NULL,
            guardian_name TEXT NOT NULL,
            guardian_contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()


@app.before_request
def before_request():
    init_db()
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)


@app.context_processor
def inject_globals():
    return {
        "current_user": g.get("current_user"),
        "csrf_token": session.get("csrf_token"),
    }


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.current_user = None
    else:
        g.current_user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.current_user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def valid_csrf():
    return request.form.get("csrf_token") == session.get("csrf_token")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def unique_upload_name(original):
    safe = secure_filename(original)
    stem = Path(safe).stem or "valid_id"
    ext = Path(safe).suffix.lower()
    return f"{secrets.token_hex(12)}_{stem}{ext}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.current_user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Invalid form token. Please try again.", "danger")
            return redirect(url_for("register"))

        student_id = request.form.get("student_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        course = request.form.get("course", "").strip()
        year_level = request.form.get("year_level", "").strip()
        valid_id = request.files.get("valid_id")

        errors = []
        if not all([student_id, full_name, email, username, password, course, year_level]):
            errors.append("Please complete all required fields.")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if not valid_id or not valid_id.filename:
            errors.append("A valid ID file is required.")
        elif not allowed_file(valid_id.filename):
            errors.append("Valid ID must be PDF, JPG, JPEG, or PNG.")

        db = get_db()
        if not errors:
            existing = db.execute(
                "SELECT student_id, email, username FROM users WHERE student_id = ? OR email = ? OR username = ?",
                (student_id, email, username),
            ).fetchone()
            if existing:
                if existing["student_id"] == student_id:
                    errors.append("Student ID is already registered.")
                if existing["email"] == email:
                    errors.append("Email is already registered.")
                if existing["username"] == username:
                    errors.append("Username is already taken.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("register.html", form=request.form)

        filename = unique_upload_name(valid_id.filename)
        valid_id.save(UPLOAD_DIR / filename)

        try:
            db.execute(
                """
                INSERT INTO users
                (student_id, full_name, email, username, password_hash, course, year_level, valid_id_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id, full_name, email, username,
                    generate_password_hash(password), course, year_level, filename,
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            (UPLOAD_DIR / filename).unlink(missing_ok=True)
            flash("Registration could not be completed because the account already exists.", "danger")
            return render_template("register.html", form=request.form)

        flash("Registration successful. You can now log in and apply for a scholarship.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not valid_csrf():
            flash("Invalid form token. Please try again.", "danger")
            return redirect(url_for("login"))

        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier.lower()),
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            flash("Welcome back, " + user["full_name"] + "!", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    application = get_db().execute(
        "SELECT * FROM scholarship_applications WHERE user_id = ? ORDER BY applied_at DESC LIMIT 1",
        (g.current_user["id"],),
    ).fetchone()
    return render_template("dashboard.html", application=application)


@app.route("/scholarship", methods=["GET", "POST"])
@login_required
def scholarship():
    db = get_db()
    existing = db.execute(
        "SELECT * FROM scholarship_applications WHERE user_id = ? ORDER BY applied_at DESC LIMIT 1",
        (g.current_user["id"],),
    ).fetchone()

    if request.method == "POST":
        if not valid_csrf():
            flash("Invalid form token. Please try again.", "danger")
            return redirect(url_for("scholarship"))
        if existing:
            flash("You already have a scholarship application on record.", "warning")
            return redirect(url_for("dashboard"))

        scholarship_type = request.form.get("scholarship_type", "").strip()
        reason = request.form.get("reason", "").strip()
        household_income = request.form.get("household_income", "").strip()
        guardian_name = request.form.get("guardian_name", "").strip()
        guardian_contact = request.form.get("guardian_contact", "").strip()

        if not all([scholarship_type, reason, household_income, guardian_name, guardian_contact]):
            flash("Please complete all scholarship fields.", "danger")
            return render_template("scholarship.html", form=request.form)

        db.execute(
            """
            INSERT INTO scholarship_applications
            (user_id, scholarship_type, reason, household_income, guardian_name, guardian_contact, status, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
            """,
            (
                g.current_user["id"], scholarship_type, reason,
                household_income, guardian_name, guardian_contact,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        db.commit()
        flash("Scholarship application submitted successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("scholarship.html", form={})


@app.route("/uploads/<path:filename>")
@login_required
def protected_upload(filename):
    # Only the owner can access their uploaded valid ID.
    if filename != g.current_user["valid_id_filename"]:
        return "Forbidden", 403
    return send_from_directory(UPLOAD_DIR, filename)


@app.errorhandler(413)
def too_large(error):
    flash("The uploaded file is too large. Maximum size is 5 MB.", "danger")
    return redirect(url_for("register"))


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database initialized.")


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
