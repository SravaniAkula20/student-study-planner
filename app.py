
import calendar
import sqlite3
import os

from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "studyflow-development-key-change-before-deployment"
)

DATABASE = "studyflow.db"


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ==========================================
# CREATE DATABASE TABLES
# ==========================================

def create_table():

    conn = get_db()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    # Existing tasks table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            deadline TEXT NOT NULL,
            priority TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    # NEW: Daily plans table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            plan_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            notes TEXT,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ==========================================
# LOGIN REQUIRED DECORATOR
# ==========================================

def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper


# ==========================================
# REGISTER
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
            """, (username, email, hashed_password))

            conn.commit()

            user = conn.execute("""
                SELECT id, username FROM users WHERE email = ?
            """, (email,)).fetchone()

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash("Account created successfully!")

            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            flash("This email is already registered.")
            return redirect(url_for("register"))

        finally:
            conn.close()

    return render_template("register.html")


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
@login_required
def logout():

    session.clear()
    flash("You have been logged out.")

    return redirect(url_for("login"))


# ==========================================
# DASHBOARD
# ==========================================

@app.route("/")
@login_required
def dashboard():

    user_id = session["user_id"]

    search = request.args.get("search", "").strip()
    priority = request.args.get("priority", "")
    status = request.args.get("status", "")

    conn = get_db()

    # Personal statistics
    all_tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ?
    """, (user_id,)).fetchall()

    total = len(all_tasks)

    completed = sum(task["completed"] for task in all_tasks)

    pending = total - completed

    progress = round((completed / total) * 100) if total else 0

    # Filter tasks
    query = "SELECT * FROM tasks WHERE user_id = ?"
    values = [user_id]

    if search:
        query += " AND (title LIKE ? OR subject LIKE ?)"
        values.extend([f"%{search}%", f"%{search}%"])

    if priority in ["Low", "Medium", "High"]:
        query += " AND priority = ?"
        values.append(priority)

    if status == "Pending":
        query += " AND completed = 0"

    elif status == "Completed":
        query += " AND completed = 1"

    query += " ORDER BY deadline ASC"

    tasks = conn.execute(query, values).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        tasks=tasks,
        total=total,
        completed=completed,
        pending=pending,
        progress=progress,
        search=search,
        priority=priority,
        status=status,
        username=session["username"]
    )


# ==========================================
# ADD TASK
# ==========================================

@app.route("/add", methods=["POST"])
@login_required
def add_task():

    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    deadline = request.form.get("deadline", "")
    priority = request.form.get("priority", "")

    if not title or not subject or not deadline:
        flash("Please fill in all task fields.")
        return redirect(url_for("dashboard"))

    if priority not in ["Low", "Medium", "High"]:
        flash("Please select a valid priority.")
        return redirect(url_for("dashboard"))

    try:
        date.fromisoformat(deadline)
    except ValueError:
        flash("Please enter a valid deadline.")
        return redirect(url_for("dashboard"))

    conn = get_db()

    conn.execute("""
        INSERT INTO tasks
        (user_id, title, subject, deadline, priority)
        VALUES (?, ?, ?, ?, ?)
    """, (
        session["user_id"],
        title,
        subject,
        deadline,
        priority
    ))

    conn.commit()
    conn.close()

    flash("Task added successfully!")

    return redirect(url_for("dashboard"))


# ==========================================
# EDIT TASK
# ==========================================

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):

    user_id = session["user_id"]

    conn = get_db()

    task = conn.execute("""
        SELECT * FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id)).fetchone()

    if task is None:
        conn.close()
        flash("Task not found.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        deadline = request.form.get("deadline", "")
        priority = request.form.get("priority", "")

        try:
            date.fromisoformat(deadline)
            valid_date = True
        except ValueError:
            valid_date = False

        if (
            not title or not subject or not valid_date
            or priority not in ["Low", "Medium", "High"]
        ):
            conn.close()
            flash("Please enter valid task details.")
            return redirect(url_for("edit_task", task_id=task_id))

        conn.execute("""
            UPDATE tasks
            SET title = ?, subject = ?, deadline = ?, priority = ?
            WHERE id = ? AND user_id = ?
        """, (
            title,
            subject,
            deadline,
            priority,
            task_id,
            user_id
        ))

        conn.commit()
        conn.close()

        flash("Task updated successfully!")

        return redirect(url_for("dashboard"))

    conn.close()

    return render_template("edit_task.html", task=task)


# ==========================================
# COMPLETE / UNDO TASK
# ==========================================

@app.route("/toggle/<int:task_id>")
@login_required
def toggle_task(task_id):

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        UPDATE tasks
        SET completed = CASE
            WHEN completed = 0 THEN 1
            ELSE 0
        END
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ==========================================
# DELETE TASK
# ==========================================

@app.route("/delete/<int:task_id>")
@login_required
def delete_task(task_id):

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        DELETE FROM tasks
        WHERE id = ? AND user_id = ?
    """, (task_id, user_id))

    conn.commit()
    conn.close()

    flash("Task deleted.")

    return redirect(url_for("dashboard"))


# ==========================================
# CALENDAR
# ==========================================

@app.route("/calendar")
@login_required
def study_calendar():

    user_id = session["user_id"]

    today = date.today()
    today_str = today.isoformat()

    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)

    if month < 1 or month > 12:
        month = today.month

    conn = get_db()

    tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND deadline LIKE ?
        ORDER BY deadline
    """, (user_id, f"{year}-{month:02d}-%")).fetchall()

    upcoming_tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND deadline >= ? AND completed = 0
        ORDER BY deadline ASC
    """, (user_id, today_str)).fetchall()

    overdue_tasks = conn.execute("""
        SELECT * FROM tasks
        WHERE user_id = ? AND deadline < ? AND completed = 0
        ORDER BY deadline ASC
    """, (user_id, today_str)).fetchall()

    conn.close()

    tasks_by_date = {}

    for task in tasks:
        day = int(task["deadline"].split("-")[2])
        tasks_by_date.setdefault(day, []).append(task)

    cal = calendar.Calendar(
        firstweekday=6
    ).monthdayscalendar(year, month)

    return render_template(
        "calendar.html",
        cal=cal,
        month_name=calendar.month_name[month],
        month=month,
        year=year,
        tasks_by_date=tasks_by_date,
        upcoming_tasks=upcoming_tasks,
        overdue_tasks=overdue_tasks,
        today=today
    )


# ==========================================
# DAILY PLANNER
# ==========================================

@app.route("/daily-planner", methods=["GET", "POST"])
@login_required
def daily_planner():

    user_id = session["user_id"]

    selected_date = request.args.get(
        "date",
        date.today().isoformat()
    )

    # Validate selected date
    try:
        date.fromisoformat(selected_date)
    except ValueError:
        selected_date = date.today().isoformat()

    conn = get_db()

    # Add a new daily plan
    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        plan_date = request.form.get("plan_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        notes = request.form.get("notes", "").strip()

        # Validate date and time
        try:
            date.fromisoformat(plan_date)

            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")

            if end <= start:
                raise ValueError

        except ValueError:
            conn.close()
            flash("Please enter a valid date and time range.")
            return redirect(url_for(
                "daily_planner",
                date=selected_date
            ))

        if not title or not subject:
            conn.close()
            flash("Please enter a task title and subject.")
            return redirect(url_for(
                "daily_planner",
                date=plan_date
            ))

        conn.execute("""
            INSERT INTO daily_plans
            (
                user_id, title, subject, plan_date,
                start_time, end_time, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            title,
            subject,
            plan_date,
            start_time,
            end_time,
            notes
        ))

        conn.commit()
        conn.close()

        flash("Daily plan added successfully!")

        return redirect(url_for(
            "daily_planner",
            date=plan_date
        ))

    # Get plans for the selected date
    plans = conn.execute("""
        SELECT * FROM daily_plans
        WHERE user_id = ? AND plan_date = ?
        ORDER BY start_time ASC
    """, (
        user_id,
        selected_date
    )).fetchall()

    total = len(plans)

    completed = sum(plan["completed"] for plan in plans)

    pending = total - completed

    progress = round((completed / total) * 100) if total else 0

    conn.close()

    return render_template(
        "daily_planner.html",
        plans=plans,
        selected_date=selected_date,
        total=total,
        completed=completed,
        pending=pending,
        progress=progress,
        username=session.get("username")
    )


# ==========================================
# EDIT DAILY PLAN
# ==========================================

@app.route("/daily-plan/edit/<int:plan_id>", methods=["GET", "POST"])
@login_required
def edit_daily_plan(plan_id):

    user_id = session["user_id"]

    conn = get_db()

    plan = conn.execute("""
        SELECT * FROM daily_plans
        WHERE id = ? AND user_id = ?
    """, (
        plan_id,
        user_id
    )).fetchone()

    if plan is None:
        conn.close()
        flash("Daily plan not found.")
        return redirect(url_for("daily_planner"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        plan_date = request.form.get("plan_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        notes = request.form.get("notes", "").strip()

        try:
            date.fromisoformat(plan_date)

            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")

            if end <= start:
                raise ValueError

        except ValueError:
            conn.close()
            flash("Please enter a valid date and time range.")
            return redirect(url_for(
                "edit_daily_plan",
                plan_id=plan_id
            ))

        if not title or not subject:
            conn.close()
            flash("Title and subject are required.")
            return redirect(url_for(
                "edit_daily_plan",
                plan_id=plan_id
            ))

        conn.execute("""
            UPDATE daily_plans
            SET
                title = ?,
                subject = ?,
                plan_date = ?,
                start_time = ?,
                end_time = ?,
                notes = ?
            WHERE id = ? AND user_id = ?
        """, (
            title,
            subject,
            plan_date,
            start_time,
            end_time,
            notes,
            plan_id,
            user_id
        ))

        conn.commit()
        conn.close()

        flash("Daily plan updated successfully!")

        return redirect(url_for(
            "daily_planner",
            date=plan_date
        ))

    conn.close()

    return render_template(
        "edit_daily_plan.html",
        plan=plan
    )


# ==========================================
# COMPLETE / UNDO DAILY PLAN
# ==========================================

@app.route("/daily-plan/toggle/<int:plan_id>", methods=["POST"])
@login_required
def toggle_daily_plan(plan_id):

    user_id = session["user_id"]

    conn = get_db()

    # Find the plan belonging to this user
    plan = conn.execute("""
        SELECT plan_date FROM daily_plans
        WHERE id = ? AND user_id = ?
    """, (
        plan_id,
        user_id
    )).fetchone()

    if plan is None:
        conn.close()
        flash("Daily plan not found.")
        return redirect(url_for("daily_planner"))

    selected_date = plan["plan_date"]

    conn.execute("""
        UPDATE daily_plans
        SET completed = CASE
            WHEN completed = 0 THEN 1
            ELSE 0
        END
        WHERE id = ? AND user_id = ?
    """, (
        plan_id,
        user_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for(
        "daily_planner",
        date=selected_date
    ))


# ==========================================
# DELETE DAILY PLAN
# ==========================================

@app.route("/daily-plan/delete/<int:plan_id>", methods=["POST"])
@login_required
def delete_daily_plan(plan_id):

    user_id = session["user_id"]

    conn = get_db()

    # Get the plan date before deleting
    plan = conn.execute("""
        SELECT plan_date FROM daily_plans
        WHERE id = ? AND user_id = ?
    """, (
        plan_id,
        user_id
    )).fetchone()

    if plan is None:
        conn.close()
        flash("Daily plan not found.")
        return redirect(url_for("daily_planner"))

    selected_date = plan["plan_date"]

    conn.execute("""
        DELETE FROM daily_plans
        WHERE id = ? AND user_id = ?
    """, (
        plan_id,
        user_id
    ))

    conn.commit()
    conn.close()

    flash("Daily plan deleted.")

    return redirect(url_for(
        "daily_planner",
        date=selected_date
    ))


# ==========================================
# START APPLICATION
# ==========================================

if __name__ == "__main__":

    create_table()

    app.run(debug=True)
