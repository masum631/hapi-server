import os
import json
import base64
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, request, redirect, url_for, session, render_template_string, jsonify
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

DB_FILE = "licenses.db"
PRIVATE_KEY_FILE = "private_key.pem"
PUBLIC_KEY_FILE = "public_key.pem"
SETTINGS_FILE = "panel_settings.json"

APP_DEBUG = False

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "MasumHabiba2026!ChangeThis")
FLASK_SECRET = os.environ.get("FLASK_SECRET", "MASUM_HABIBA_PANEL_SECRET_CHANGE_THIS_2026")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

app = Flask(__name__)
app.secret_key = FLASK_SECRET


LOGIN_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Admin Login</title>
    <style>
        body { font-family: Arial, sans-serif; background:#10151c; color:#fff; padding:40px; }
        .box { max-width:420px; margin:auto; background:#18212b; padding:24px; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,0.3); }
        input, button { width:100%; padding:12px; margin:8px 0; box-sizing:border-box; border-radius:8px; border:none; }
        input { background:#0f141b; color:#fff; border:1px solid #2f3f52; }
        button { background:#4da3ff; color:#fff; font-weight:bold; cursor:pointer; }
        .bad { color:#ff7b7b; }
    </style>
</head>
<body>
    <div class="box">
        <h2>HAPI BOT Admin Login</h2>
        <form method="post">
            <input name="username" placeholder="Username" required>
            <input name="password" type="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        {% if error %}
            <p class="bad">{{ error }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

HTML_PAGE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>HAPI BOT Admin Panel</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #10151c; color: #fff; }
        .card { background: #18212b; padding: 18px; border-radius: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.25); margin-bottom: 18px; }
        h1, h2, h3 { margin-top: 0; }
        input, textarea, button, select {
            padding: 10px; margin: 6px 0; width: 100%; box-sizing: border-box;
            border-radius: 8px; border: 1px solid #2f3f52; background:#0f141b; color:#fff;
        }
        textarea { min-height: 130px; }
        table { width: 100%; border-collapse: collapse; background: #18212b; }
        th, td { padding: 10px; border-bottom: 1px solid #2b3948; text-align: left; vertical-align: top; }
        th { background: #111923; }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .small { font-size: 12px; color: #a8b3bf; }
        .ok { color: #62d26f; font-weight: bold; }
        .bad { color: #ff6b6b; font-weight: bold; }
        .warn { color: #ffbf4d; font-weight: bold; }
        .topbar { display:flex; justify-content:space-between; align-items:center; gap:16px; }
        .btn { display:inline-block; padding:8px 12px; background:#4da3ff; color:#fff; text-decoration:none; border-radius:8px; border:none; cursor:pointer; width:auto; }
        .btn-red { background:#b30000; }
        .btn-green { background:#006b1b; }
        .btn-orange { background:#b36b00; }
        .inline-form { display:inline; }
        .mono { font-family: Consolas, monospace; word-break: break-all; }
        .urlbox { background:#0f141b; border:1px solid #2f3f52; padding:10px; border-radius:8px; }
    </style>
</head>
<body>
    <div class="topbar">
        <h1>HAPI BOT Admin Panel</h1>
        <div><a class="btn" href="{{ url_for('logout') }}">Logout</a></div>
    </div>

    <div class="card">
        <h2>Server Info</h2>
        <div class="urlbox"><b>Server URL:</b> {{ default_server_url }}</div>
    </div>

    <div class="card">
        <h2>Public Banner / Info Control</h2>
        <form method="post" action="{{ url_for('save_public_settings') }}">
            <label>Banner Text</label>
            <input name="banner_text" value="{{ public_settings.banner_text }}">
            <div class="row">
                <div>
                    <label>Developer Name</label>
                    <input name="developer_name" value="{{ public_settings.developer_name }}">
                </div>
                <div>
                    <label>Contact Number</label>
                    <input name="contact_number" value="{{ public_settings.contact_number }}">
                </div>
            </div>
            <button type="submit" class="btn">Save Public Settings</button>
        </form>
    </div>

    <div class="card">
        <h2>Dashboard</h2>
        <p>Total Devices: <b>{{ stats.total }}</b></p>
        <p>Blocked: <b>{{ stats.blocked }}</b></p>
        <p>Lifetime: <b>{{ stats.lifetime }}</b></p>
        <p>Expired: <b>{{ stats.expired }}</b></p>
        <p>Recently Seen (24h): <b>{{ stats.recent }}</b></p>
    </div>

    <div class="card">
        <h2>Create / Update License</h2>
        <form method="post" action="{{ url_for('create_license') }}">
            <div class="row">
                <div>
                    <label>User Name</label>
                    <input name="user" required>
                </div>
                <div>
                    <label>Machine ID</label>
                    <input name="machine_id" required>
                </div>
            </div>

            <div class="row">
                <div>
                    <label>License Days (ignored if Lifetime checked)</label>
                    <input name="days" type="number" min="1" value="30">
                </div>
                <div>
                    <label>Sync Every X Days</label>
                    <input name="sync_days" type="number" min="1" value="7">
                </div>
            </div>

            <div class="row">
                <div>
                    <label>Server URL</label>
                    <input name="server_url" value="{{ default_server_url }}">
                </div>
                <div>
                    <label>Note</label>
                    <input name="note">
                </div>
            </div>

            <label><input type="checkbox" name="lifetime" value="1" style="width:auto;"> Lifetime License</label>
            <br>
            <button type="submit" class="btn">Create / Update License</button>
        </form>

        {% if generated_token %}
            <hr>
            <h3>Generated License Key</h3>
            <textarea readonly>{{ generated_token }}</textarea>
            <p class="small">Copy this full key and send it to the client.</p>
        {% endif %}
    </div>

    <div class="card">
        <h2>Device List</h2>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Machine ID</th>
                    <th>Status</th>
                    <th>Expiry</th>
                    <th>Sync Days</th>
                    <th>Last Seen</th>
                    <th>Note</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for row in devices %}
                    <tr>
                        <td>{{ row['user'] }}</td>
                        <td class="mono">{{ row['machine_id'] }}</td>
                        <td>
                            {% if row['blocked'] %}
                                <span class="bad">BLOCKED</span>
                            {% elif row['is_expired'] %}
                                <span class="warn">EXPIRED</span>
                            {% else %}
                                <span class="ok">ACTIVE</span>
                            {% endif %}
                        </td>
                        <td>{{ row['expiry'] }}</td>
                        <td>{{ row['sync_days'] }}</td>
                        <td>{{ row['last_seen'] or '-' }}</td>
                        <td>{{ row['note'] or '-' }}</td>
                        <td>
                            <form class="inline-form" method="post" action="{{ url_for('toggle_block', machine_id=row['machine_id']) }}">
                                {% if row['blocked'] %}
                                    <button class="btn btn-green" type="submit">Unblock</button>
                                {% else %}
                                    <button class="btn btn-red" type="submit">Block</button>
                                {% endif %}
                            </form>
                            <form class="inline-form" method="post" action="{{ url_for('reissue_license', machine_id=row['machine_id']) }}">
                                <button class="btn btn-orange" type="submit">Reissue Key</button>
                            </form>
                        </td>
                    </tr>
                    {% if reissued_for == row['machine_id'] and generated_token %}
                    <tr>
                        <td colspan="8">
                            <div class="card" style="margin:0;">
                                <h3>Reissued License for {{ row['machine_id'] }}</h3>
                                <textarea readonly>{{ generated_token }}</textarea>
                            </div>
                        </td>
                    </tr>
                    {% endif %}
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso(dt=None):
    dt = dt or utc_now()
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def get_default_server_url():
    if RENDER_EXTERNAL_URL:
        return RENDER_EXTERNAL_URL.rstrip("/")
    return request.host_url.rstrip("/")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            machine_id TEXT PRIMARY KEY,
            user TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expiry TEXT NOT NULL,
            lifetime INTEGER NOT NULL DEFAULT 0,
            sync_days INTEGER NOT NULL DEFAULT 7,
            blocked INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT,
            note TEXT,
            server_url TEXT
        )
    """)
    conn.commit()
    conn.close()

    if not os.path.exists(SETTINGS_FILE):
        save_public_settings_file({
            "banner_text": "RA DEVELOPER Exclusive License --- Hapi Automation Board",
            "developer_name": "DR.MASUM",
            "contact_number": "01799523472"
        })


def load_private_key():
    with open(PRIVATE_KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key():
    with open(PUBLIC_KEY_FILE, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def sign_payload(payload: dict) -> str:
    private_key = load_private_key()
    payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = private_key.sign(
        payload_str.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    license_data = {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("utf-8"),
    }
    return base64.b64encode(json.dumps(license_data, separators=(",", ":")).encode("utf-8")).decode("utf-8")


def verify_token(token: str):
    try:
        decoded = base64.b64decode(token).decode("utf-8")
        data = json.loads(decoded)
        payload = data["payload"]
        signature = base64.b64decode(data["signature"])
        payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

        public_key = load_public_key()
        public_key.verify(
            signature,
            payload_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True, payload
    except Exception:
        return False, None


def build_payload_from_row(row):
    return {
        "user": row["user"],
        "machine_id": row["machine_id"],
        "issued_at": row["created_at"],
        "expiry": row["expiry"],
        "lifetime": bool(row["lifetime"]),
        "sync_days": int(row["sync_days"]),
        "server_url": row["server_url"] or "",
    }


def load_public_settings_file():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "banner_text": "",
            "developer_name": "DR.MASUM",
            "contact_number": "01799523472"
        }
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_public_settings_file(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def render_panel(generated_token="", reissued_for=""):
    conn = get_db()
    rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    conn.close()

    now = utc_now().date()
    devices = []
    blocked = 0
    lifetime = 0
    expired = 0
    recent = 0

    for row in rows:
        row_dict = dict(row)
        is_expired = False
        if row_dict["lifetime"]:
            lifetime += 1
        else:
            try:
                expiry_date = datetime.strptime(row_dict["expiry"], "%Y-%m-%d").date()
                is_expired = now > expiry_date
            except Exception:
                is_expired = True

        if row_dict["blocked"]:
            blocked += 1
        if is_expired:
            expired += 1

        if row_dict["last_seen"]:
            try:
                seen_dt = datetime.fromisoformat(row_dict["last_seen"])
                if (utc_now() - seen_dt).total_seconds() <= 86400:
                    recent += 1
            except Exception:
                pass

        row_dict["is_expired"] = is_expired
        devices.append(row_dict)

    stats = {
        "total": len(devices),
        "blocked": blocked,
        "lifetime": lifetime,
        "expired": expired,
        "recent": recent,
    }

    return render_template_string(
        HTML_PAGE,
        devices=devices,
        stats=stats,
        generated_token=generated_token,
        reissued_for=reissued_for,
        default_server_url=get_default_server_url(),
        public_settings=load_public_settings_file(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Invalid credentials"
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_panel()


@app.route("/save_public_settings", methods=["POST"])
@login_required
def save_public_settings():
    save_public_settings_file({
        "banner_text": request.form.get("banner_text", "").strip(),
        "developer_name": request.form.get("developer_name", "DR.MASUM").strip() or "DR.MASUM",
        "contact_number": request.form.get("contact_number", "01799523472").strip() or "01799523472",
    })
    return redirect(url_for("index"))


@app.route("/create_license", methods=["POST"])
@login_required
def create_license():
    user = request.form.get("user", "").strip()
    machine_id = request.form.get("machine_id", "").strip().upper()
    note = request.form.get("note", "").strip()
    server_url = request.form.get("server_url", "").strip()
    lifetime = 1 if request.form.get("lifetime") == "1" else 0

    try:
        days = int(request.form.get("days", "30"))
    except ValueError:
        days = 30

    try:
        sync_days = int(request.form.get("sync_days", "7"))
    except ValueError:
        sync_days = 7

    if not user or not machine_id:
        return "User and Machine ID are required", 400

    sync_days = max(1, sync_days)
    created_at = utc_iso()
    expiry = "2099-12-31" if lifetime else (utc_now() + timedelta(days=max(1, days))).date().isoformat()

    if not server_url:
        server_url = get_default_server_url()

    conn = get_db()
    conn.execute("""
        INSERT INTO licenses (machine_id, user, created_at, expiry, lifetime, sync_days, blocked, last_seen, note, server_url)
        VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
        ON CONFLICT(machine_id) DO UPDATE SET
            user=excluded.user,
            created_at=excluded.created_at,
            expiry=excluded.expiry,
            lifetime=excluded.lifetime,
            sync_days=excluded.sync_days,
            note=excluded.note,
            server_url=excluded.server_url
    """, (machine_id, user, created_at, expiry, lifetime, sync_days, note, server_url))
    conn.commit()

    row = conn.execute("SELECT * FROM licenses WHERE machine_id = ?", (machine_id,)).fetchone()
    conn.close()

    token = sign_payload(build_payload_from_row(row))
    return render_panel(generated_token=token)


@app.route("/toggle_block/<machine_id>", methods=["POST"])
@login_required
def toggle_block(machine_id):
    machine_id = machine_id.upper()
    conn = get_db()
    row = conn.execute("SELECT blocked FROM licenses WHERE machine_id = ?", (machine_id,)).fetchone()
    if row:
        new_value = 0 if row["blocked"] else 1
        conn.execute("UPDATE licenses SET blocked = ? WHERE machine_id = ?", (new_value, machine_id))
        conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/reissue_license/<machine_id>", methods=["POST"])
@login_required
def reissue_license(machine_id):
    machine_id = machine_id.upper()
    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE machine_id = ?", (machine_id,)).fetchone()
    conn.close()

    if not row:
        return redirect(url_for("index"))

    token = sign_payload(build_payload_from_row(row))
    return render_panel(generated_token=token, reissued_for=machine_id)


@app.route("/api/public_settings", methods=["GET"])
def api_public_settings():
    return jsonify(load_public_settings_file())


@app.route("/api/sync", methods=["POST"])
def api_sync():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    machine_id = str(data.get("machine_id", "")).strip().upper()

    if not token or not machine_id:
        return jsonify({"ok": False, "message": "Missing token or machine_id"}), 400

    ok, payload = verify_token(token)
    if not ok or not payload:
        return jsonify({"ok": False, "message": "Invalid token"}), 400

    if str(payload.get("machine_id", "")).strip().upper() != machine_id:
        return jsonify({"ok": False, "message": "Wrong PC"}), 403

    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE machine_id = ?", (machine_id,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "License not found"}), 404

    row = dict(row)

    if row["blocked"]:
        conn.execute("UPDATE licenses SET last_seen = ? WHERE machine_id = ?", (utc_iso(), machine_id))
        conn.commit()
        conn.close()
        return jsonify({
            "ok": False,
            "blocked": True,
            "message": "Blocked by admin",
            "server_time": utc_iso()
        }), 403

    if not row["lifetime"]:
        try:
            expiry_date = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
            if utc_now().date() > expiry_date:
                conn.execute("UPDATE licenses SET last_seen = ? WHERE machine_id = ?", (utc_iso(), machine_id))
                conn.commit()
                conn.close()
                return jsonify({
                    "ok": False,
                    "message": "License expired",
                    "server_time": utc_iso()
                }), 403
        except Exception:
            conn.close()
            return jsonify({"ok": False, "message": "License expiry invalid"}), 500

    conn.execute("UPDATE licenses SET last_seen = ? WHERE machine_id = ?", (utc_iso(), machine_id))
    conn.commit()

    refreshed_row = conn.execute("SELECT * FROM licenses WHERE machine_id = ?", (machine_id,)).fetchone()
    conn.close()

    new_token = sign_payload(build_payload_from_row(refreshed_row))

    return jsonify({
        "ok": True,
        "message": "Sync success",
        "server_time": utc_iso(),
        "sync_days": int(refreshed_row["sync_days"]),
        "token": new_token,
    })


@app.route("/health", methods=["GET"])
def health():
    return "OK"


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=APP_DEBUG)
