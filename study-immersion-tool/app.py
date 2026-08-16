#!/usr/bin/python3
"""나만의 공부 몰입 툴 - Flask 백엔드.

뽀모도로 세션, 할 일 체크리스트, 오늘의 목표/피드백/연습장을
SQLite에 저장하고 통계를 계산해 프론트엔드(단일 페이지)에 제공한다.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "study.db"

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            duration_minutes REAL NOT NULL,
            completed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_notes (
            date TEXT PRIMARY KEY,
            goal TEXT NOT NULL DEFAULT '',
            feedback TEXT NOT NULL DEFAULT '',
            notepad TEXT NOT NULL DEFAULT ''
        );
        """
    )
    db.commit()
    db.close()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return today_str()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return today_str()
    return value


@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------- tasks --
@app.route("/api/tasks", methods=["GET", "POST"])
def tasks():
    db = get_db()
    if request.method == "GET":
        date = parse_date(request.args.get("date"))
        rows = db.execute(
            "SELECT id, text, done FROM tasks WHERE date = ? ORDER BY id",
            (date,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    date = parse_date(payload.get("date"))
    if not text:
        return jsonify({"error": "text is required"}), 400
    cur = db.execute(
        "INSERT INTO tasks (date, text, done, created_at) VALUES (?, ?, 0, ?)",
        (date, text, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "text": text, "done": 0}), 201


@app.route("/api/tasks/<int:task_id>", methods=["PATCH", "DELETE"])
def task_detail(task_id):
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return "", 204

    payload = request.get_json(silent=True) or {}
    row = db.execute("SELECT done FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    done = payload.get("done")
    done = (not row["done"]) if done is None else bool(done)
    db.execute("UPDATE tasks SET done = ? WHERE id = ?", (int(done), task_id))
    db.commit()
    return jsonify({"id": task_id, "done": int(done)})


# ------------------------------------------------------------ daily note --
@app.route("/api/note", methods=["GET", "PUT"])
def note():
    db = get_db()
    if request.method == "GET":
        date = parse_date(request.args.get("date"))
        row = db.execute(
            "SELECT goal, feedback, notepad FROM daily_notes WHERE date = ?",
            (date,),
        ).fetchone()
        if row is None:
            return jsonify({"goal": "", "feedback": "", "notepad": ""})
        return jsonify(dict(row))

    payload = request.get_json(silent=True) or {}
    date = parse_date(payload.get("date"))
    existing = db.execute(
        "SELECT goal, feedback, notepad FROM daily_notes WHERE date = ?", (date,)
    ).fetchone()
    goal = payload.get("goal", existing["goal"] if existing else "")
    feedback = payload.get("feedback", existing["feedback"] if existing else "")
    notepad = payload.get("notepad", existing["notepad"] if existing else "")
    db.execute(
        """
        INSERT INTO daily_notes (date, goal, feedback, notepad) VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET goal = excluded.goal,
                                         feedback = excluded.feedback,
                                         notepad = excluded.notepad
        """,
        (date, goal, feedback, notepad),
    )
    db.commit()
    return jsonify({"date": date, "goal": goal, "feedback": feedback, "notepad": notepad})


# --------------------------------------------------------------- sessions --
@app.route("/api/sessions", methods=["POST"])
def create_session():
    db = get_db()
    payload = request.get_json(silent=True) or {}
    session_type = payload.get("type")
    duration = payload.get("duration_minutes")
    date = parse_date(payload.get("date"))
    if session_type not in ("focus", "break") or not isinstance(duration, (int, float)):
        return jsonify({"error": "invalid payload"}), 400
    db.execute(
        "INSERT INTO sessions (date, type, duration_minutes, completed_at) VALUES (?, ?, ?, ?)",
        (date, session_type, duration, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return jsonify(_today_summary(db, date)), 201


def _today_summary(db, date):
    row = db.execute(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS minutes, COUNT(*) AS count
        FROM sessions WHERE date = ? AND type = 'focus'
        """,
        (date,),
    ).fetchone()
    return {"date": date, "focus_minutes": row["minutes"], "focus_count": row["count"]}


@app.route("/api/summary")
def summary():
    date = parse_date(request.args.get("date"))
    return jsonify(_today_summary(get_db(), date))


@app.route("/api/stats")
def stats():
    days = request.args.get("days", 7, type=int)
    days = max(1, min(days, 90))
    db = get_db()
    rows = db.execute(
        """
        SELECT date, COALESCE(SUM(duration_minutes), 0) AS minutes
        FROM sessions WHERE type = 'focus'
        GROUP BY date
        """
    ).fetchall()
    by_date = {r["date"]: r["minutes"] for r in rows}
    today = datetime.now().date()
    result = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        result.append({"date": d, "minutes": by_date.get(d, 0)})
    return jsonify(result)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
