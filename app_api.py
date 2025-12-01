import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB = 'shine28.db'
ADMIN_PASSWORD = os.environ.get('SHINE28_ADMIN_PW', 'shine28@1986')
SECRET = os.environ.get('SHINE28_SECRET', 'change-this-secret')

def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        balance INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount INTEGER,
        note TEXT,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    conn.close()

app = Flask(__name__, template_folder='templates')
app.secret_key = SECRET
CORS(app)

with app.app_context():
    init_db()

# --- API routes ---
@app.route("/")
def index():
    return jsonify({"ok": True, "message": "Shine28 API running"})

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error":"username and password required"}),400
    pw_hash = generate_password_hash(password)
    conn = get_db()
    try:
        conn.execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (username, pw_hash))
        conn.commit()
    except Exception:
        return jsonify({"error":"username taken"}),409
    return jsonify({"ok": True}),201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = get_db()
    user = conn.execute("SELECT id,username,balance,password_hash FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error":"invalid credentials"}),401
    return jsonify({"ok": True, "username": user["username"], "balance": user["balance"]})

@app.route("/api/user", methods=["GET"])
def api_user():
    username = request.args.get("username")
    if not username:
        return jsonify({"error":"username required"}),400
    conn = get_db()
    user = conn.execute("SELECT id,username,balance FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not user:
        return jsonify({"error":"user not found"}),404
    return jsonify({"username": user["username"], "balance": user["balance"]})

@app.route("/api/request", methods=["POST"])
def api_request():
    data = request.get_json() or request.form
    username = (data.get("username") or "").strip()
    ttype = data.get("type")
    try:
        amount = int(data.get("amount") or 0)
    except:
        amount = 0
    note = data.get("note") or ""
    if not username or ttype not in ("deposit","withdraw") or amount <= 0:
        return jsonify({"error":"invalid request"}),400
    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error":"user not found"}),404
    conn.execute("INSERT INTO transactions(user_id,type,amount,note,status) VALUES(?,?,?,?,?)",
                 (user["id"], ttype, amount, note, "pending"))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "request created"})

# --- Admin web panel (black & gold) ---
@app.route("/admin", methods=["GET","POST"])
def admin_panel():
    if request.method == "POST":
        pw = request.form.get("admin_pw","")
        if pw != ADMIN_PASSWORD:
            flash("Wrong admin password","error")
            return redirect(url_for("admin_panel"))
        conn = get_db()
        txs = conn.execute(
            "SELECT t.id,t.type,t.amount,t.note,t.status,t.created_at,u.username "
            "FROM transactions t LEFT JOIN users u ON u.id=t.user_id ORDER BY t.created_at DESC"
        ).fetchall()
        conn.close()
        return render_template("admin_panel.html", txs=txs, admin=True)
    return render_template("admin_login.html")

@app.route("/admin/process/<int:tx_id>/<action>", methods=["GET","POST"])
def admin_process(tx_id, action):
    if action not in ("approve","reject"):
        flash("Invalid action","error")
        return redirect(url_for("admin_panel"))
    pw = request.args.get("pw") or request.form.get("admin_pw")
    if pw != ADMIN_PASSWORD:
        flash("Admin password required","error")
        return redirect(url_for("admin_panel"))
    conn = get_db()
    tx = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if not tx:
        flash("Transaction not found","error")
        conn.close()
        return redirect(url_for("admin_panel"))
    if action == "approve":
        if tx["type"] == "deposit":
            conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (tx["amount"], tx["user_id"]))
        elif tx["type"] == "withdraw":
            cur = conn.execute("SELECT balance FROM users WHERE id=?", (tx["user_id"],)).fetchone()
            if not cur or cur["balance"] < tx["amount"]:
                flash("Insufficient balance","error")
                conn.close()
                return redirect(url_for("admin_panel"))
            conn.execute("UPDATE users SET balance = balance - ? WHERE id=?", (tx["amount"], tx["user_id"]))
        conn.execute("UPDATE transactions SET status='approved' WHERE id=?", (tx_id,))
        conn.commit()
        conn.close()
        flash("Approved and applied","success")
    else:
        conn.execute("UPDATE transactions SET status='rejected' WHERE id=?", (tx_id,))
        conn.commit()
        conn.close()
        flash("Rejected","info")
    return redirect(url_for("admin_panel"))

@app.route("/ui")
def ui():
    return render_template("ui_index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
