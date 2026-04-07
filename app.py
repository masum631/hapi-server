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
PRIVATE_KEY_FILE = "/etc/secrets/private_key.pem"
PUBLIC_KEY_FILE = "/etc/secrets/public_key.pem"

APP_SECRET = os.environ.get("FLASK_SECRET", "fallback_secret_123")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.secret_key = APP_SECRET


LOGIN_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>DR. Developer Admin Login</title>
    <style>
        body { font-family: Arial, sans-serif; background:#10151c; color:#fff; padding:40px; }
        .box { max-width:420px; margin:auto; background:#18212b; padding:24px; border-radius:12px; }
        input, button { width:100%; padding:12px; margin:8px 0; box-sizing:border-box; border-radius:8px; border:none; }
        input { background:#0f141b; color:#fff; border:1px solid #2f3f52; }
        button { background:#4da3ff; color:#fff; font-weight:bold; cursor:pointer; }
        .bad { color:#ff7b7b; }
    </style>
</head>
<body>
    <div class="box">
        <h2>DR. Developer Admin Login</h2>
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

PANEL_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>DR. Developer Admin Panel</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #10151c; color: #fff; }
        .card { background: #18212b; padding: 18px; border-radius: 14px; margin-bottom: 18px; }
        h1, h2, h3 { margin-top: 0; }
        input, textarea, button {
            padding: 10px; margin: 6px 0; width: 100%; box-sizing: border-box;
            border-radius: 8px; border: 1px solid #2f3f52; background:#0f141b; color:#fff;
        }
        textarea { min-height: 120px; }
        table { width: 100%; border-collapse: collapse; background: #18212b; }
        th, td { padding: 10px; border-bottom: 1px solid #2b3948; text-align: left; vertical-align: top; }
        th { background: #111923; }
        .row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .row3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }
        .topbar { display:flex; justify-content:space-between; align-items:center; gap:16px; }
        .btn { display:inline-block; padding:8px 12px; background:#4da3ff; color:#fff; text-decoration:none; border-radius:8px; border:none; cursor:pointer; width:auto; }
        .btn-red { background:#b30000; }
        .btn-green { background:#006b1b; }
        .btn-orange { background:#b36b00; }
        .btn-purple { background:#6c63ff; }
        .btn-gray { background:#555; }
        .inline-form { display:inline; }
        .mono { font-family: Consolas, monospace; word-break: break-all; }
        .ok { color:#62d26f; font-weight:bold; }
        .bad { color:#ff6b6b; font-weight:bold; }
        .warn { color:#ffbf4d; font-weight:bold; }
        .small { color:#a8b3bf; font-size:12px; }
        .pill { display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; }
        .on { background:#0d5f1c; }
        .off { background:#6a1515; }
    </style>
</head>
<body>
    <div class="topbar">
        <h1>DR. Developer Admin Panel</h1>
        <div>
            <span class="pill {{ 'on' if maintenance_mode else 'off' }}">
                Maintenance: {{ 'ON' if maintenance_mode else 'OFF' }}
            </span>
            <a class="btn" href="{{ url_for('logout') }}">Logout</a>
        </div>
    </div>

    <div class="card">
        <h2>Dashboard</h2>
        <div class="row3">
            <div>Total Devices: <b>{{ stats.total }}</b></div>
            <div>Blocked: <b>{{ stats.blocked }}</b></div>
            <div>Expired: <b>{{ stats.expired }}</b></div>
            <div>Online (2 min): <b>{{ stats.online }}</b></div>
            <div>Lifetime: <b>{{ stats.lifetime }}</b></div>
            <div>Maintenance: <b>{{ 'ON' if maintenance_mode else 'OFF' }}</b></div>
        </div>
    </div>

    <div class="card">
        <h2>Global Live Banner</h2>
        <form method="post" action="{{ url_for('save_global_banner') }}">
            <label>Global Banner Text</label>
            <input name="banner_text" value="{{ global_banner }}">
            <button type="submit" class="btn">Save Global Banner</button>
        </form>
    </div>

    <div class="card">
        <h2>Maintenance Mode</h2>
        <form method="post" action="{{ url_for('toggle_maintenance') }}">
            <button type="submit" class="btn btn-orange">
                Turn {{ 'OFF' if maintenance_mode else 'ON' }} Maintenance
            </button>
        </form>
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

            <div class="row3">
                <div>
                    <label>License Days</label>
                    <input name="days" type="number" min="1" value="30">
                </div>
                <div>
                    <label>Sync Every X Days</label>
                    <input name="sync_days" type="number" min="1" value="7">
                </div>
                <div>
                    <label>Machine Rename</label>
                    <input name="machine_alias">
                </div>
            </div>

            <div class="row">
                <div>
                    <label>Per-user Custom Banner</label>
                    <input name="custom_banner">
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
        {% endif %}
    </div>

    <div class="card">
        <h2>Search</h2>
        <form method="get" action="{{ url_for('index') }}">
            <input name="q" placeholder="Search by user / machine id / alias" value="{{ q }}">
            <button type="submit" class="btn">Search</button>
        </form>
    </div>

    <div class="card">
        <h2>Device List</h2>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Machine / Alias</th>
                    <th>Status</th>
                    <th>Expiry</th>
                    <th>Last Seen</th>
                    <th>Custom Banner</th>
                    <th>Note</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for row in devices %}
                <tr>
                    <td>{{ row['user'] }}</td>
                    <td class="mono">
                        {{ row['machine_id'] }}<br>
                        <span class="small">{{ row['machine_alias'] or '' }}</span>
                    </td>
                    <td>
                        {% if row['blocked'] %}
                            <span class="bad">BLOCKED</span>
                        {% elif row['is_expired'] %}
                            <span class="warn">EXPIRED</span>
                        {% elif row['is_online'] %}
                            <span class="ok">ONLINE</span>
                        {% else %}
                            <span>ACTIVE</span>
                        {% endif %}
                    </td>
                    <td>{{ row['expiry'] }}</td>
                    <td>{{ row['last_seen'] or '-' }}</td>
                    <td>{{ row['custom_banner'] or '-' }}</td>
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
                            <button class="btn btn-orange" type="submit">Reissue</button>
                        </form>

                        <form class="inline-form" method="post" action="{{ url_for('extend_license', machine_id=row['machine_id']) }}">
                            <input type="hidden" name="days" value="30">
                            <button class="btn btn-purple" type="submit">+30 Days</button>
                        </form>

                        <form class="inline-form" method="post" action="{{ url_for('delete_license', machine_id=row['machine_id']) }}" onsubmit="return confirm('Delete this license?')">
                            <button class="btn btn-gray" type="submit">Delete</button>
                        </form>
                    </td>
                </tr>
                {% if reissued_for == row['machine_id'] and generated_token %}
                <tr>
                    <td colspan="8">
                        <div class="card" style="margin:0;">
                            <h3>Reissued License</h3>
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


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table, column, column_def):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        conn.commit()


def get_meta(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_meta(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO app_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    conn.commit()
    conn.close()


def init_db():
    conn = get_db()
    conn.execute("""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()

    ensure_column(conn, "licenses", "machine_alias", "TEXT")
    ensure_column(conn, "licenses", "custom_banner", "TEXT")

    conn.close()

    if not get_meta("global_banner"):
        set_meta("global_banner", "DR. Developer Exclusive License --- Hapi Automation Board")
    if not get_meta("maintenance_mode"):
        set_meta("maintenance_mode", "0")


def get_maintenance_mode():
    return get_meta("maintenance_mode", "0") == "1"


def set_maintenance_mode(enabled: bool):
    set_meta("maintenance_mode", "1" if enabled else "0")


def get_global_banner():
    return get_meta("global_banner", "DR. Developer Exclusive License --- Hapi Automation Board")


def set_global_banner(text):
    set_meta("global_banner", text or "DR. Developer Exclusive License --- Hapi Automation Board")


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
    return base64.b64encode(
        json.dumps(license_data, separators=(",", ":")).encode("utf-8")
    ).decode("utf-8")


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
    host_url = request.host_url.rstrip("/")
    return {
        "user": row["user"],
        "machine_id": row["machine_id"],
        "issued_at": row["created_at"],
        "expiry": row["expiry"],
        "lifetime": bool(row["lifetime"]),
        "sync_days": int(row["sync_days"]),
        "server_url": host_url,
    }


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def device_stats(rows):
    today = utc_now().date()
    total = len(rows)
    blocked = 0
    expired = 0
    lifetime = 0
    online = 0

    out = []
    for row in rows:
        row = dict(row)
        is_expired = False
        is_online = False

        if row["lifetime"]:
            lifetime += 1
        else:
            try:
                expiry_date = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
                is_expired = today > expiry_date
            except Exception:
                is_expired = True

        if row["blocked"]:
            blocked += 1
        if is_expired:
            expired += 1

        if row["last_seen"]:
            try:
                seen = datetime.fromisoformat(row["last_seen"])
                if (utc_now() - seen).total_seconds() <= 120:
                    is_online = True
                    online += 1
            except Exception:
                pass

        row["is_expired"] = is_expired
        row["is_online"] = is_online
        out.append(row)

    return out, {
        "total": total,
        "blocked": blocked,
        "expired": expired,
        "lifetime": lifetime,
        "online": online,
    }


def render_panel(generated_token="", reissued_for="", q=""):
    conn = get_db()
    if q:
        search = f"%{q}%"
        rows = conn.execute("""
            SELECT * FROM licenses
            WHERE user LIKE ? OR machine_id LIKE ? OR IFNULL(machine_alias, '') LIKE ?
            ORDER BY created_at DESC
        """, (search, search, search)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    conn.close()

    devices, stats = device_stats(rows)

    return render_template_string(
        PANEL_HTML,
        devices=devices,
        stats=stats,
        generated_token=generated_token,
        reissued_for=reissued_for,
        q=q,
        global_banner=get_global_banner(),
        maintenance_mode=get_maintenance_mode(),
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
    q = request.args.get("q", "").strip()
    return render_panel(q=q)


@app.route("/save_global_banner", methods=["POST"])
@login_required
def save_global_banner():
    set_global_banner(request.form.get("banner_text", "").strip())
    return redirect(url_for("index"))


@app.route("/toggle_maintenance", methods=["POST"])
@login_required
def toggle_maintenance():
    set_maintenance_mode(not get_maintenance_mode())
    return redirect(url_for("index"))


@app.route("/create_license", methods=["POST"])
@login_required
def create_license():
    user = request.form.get("user", "").strip()
    machine_id = request.form.get("machine_id", "").strip().upper()
    note = request.form.get("note", "").strip()
    custom_banner = request.form.get("custom_banner", "").strip()
    machine_alias = request.form.get("machine_alias", "").strip()
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

    created_at = utc_iso()
    expiry = "2099-12-31" if lifetime else (utc_now() + timedelta(days=max(1, days))).date().isoformat()

    conn = get_db()
    conn.execute("""
        INSERT INTO licenses
        (machine_id, user, created_at, expiry, lifetime, sync_days, blocked, last_seen, note, server_url, machine_alias, custom_banner)
        VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?, ?)
        ON CONFLICT(machine_id) DO UPDATE SET
            user=excluded.user,
            created_at=excluded.created_at,
            expiry=excluded.expiry,
            lifetime=excluded.lifetime,
            sync_days=excluded.sync_days,
            note=excluded.note,
            server_url=excluded.server_url,
            machine_alias=excluded.machine_alias,
            custom_banner=excluded.custom_banner
    """, (
        machine_id, user, created_at, expiry, lifetime, max(1, sync_days),
        note, request.host_url.rstrip("/"), machine_alias, custom_banner
    ))
    conn.commit()

    row = conn.execute("SELECT * FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()
    conn.close()

    token = sign_payload(build_payload_from_row(row))
    return render_panel(generated_token=token)


@app.route("/toggle_block/<machine_id>", methods=["POST"])
@login_required
def toggle_block(machine_id):
    machine_id = machine_id.upper()
    conn = get_db()
    row = conn.execute("SELECT blocked FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()
    if row:
        new_value = 0 if int(row["blocked"]) else 1
        conn.execute("UPDATE licenses SET blocked=? WHERE machine_id=?", (new_value, machine_id))
        conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/extend_license/<machine_id>", methods=["POST"])
@login_required
def extend_license(machine_id):
    machine_id = machine_id.upper()
    try:
        days = int(request.form.get("days", "30"))
    except ValueError:
        days = 30

    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()
    if row:
        if int(row["lifetime"]) == 1:
            conn.close()
            return redirect(url_for("index"))

        try:
            current_expiry = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
        except Exception:
            current_expiry = utc_now().date()

        base_date = max(current_expiry, utc_now().date())
        new_expiry = (base_date + timedelta(days=max(1, days))).isoformat()

        conn.execute("UPDATE licenses SET expiry=? WHERE machine_id=?", (new_expiry, machine_id))
        conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete_license/<machine_id>", methods=["POST"])
@login_required
def delete_license(machine_id):
    machine_id = machine_id.upper()
    conn = get_db()
    conn.execute("DELETE FROM licenses WHERE machine_id=?", (machine_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/reissue_license/<machine_id>", methods=["POST"])
@login_required
def reissue_license(machine_id):
    machine_id = machine_id.upper()
    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()
    conn.close()

    if not row:
        return redirect(url_for("index"))

    token = sign_payload(build_payload_from_row(row))
    return render_panel(generated_token=token, reissued_for=machine_id)


@app.route("/api/public_settings", methods=["GET"])
def api_public_settings():
    machine_id = request.args.get("machine_id", "").strip().upper()
    result = {"banner_text": get_global_banner()}

    if machine_id:
        conn = get_db()
        row = conn.execute("SELECT custom_banner FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()
        conn.close()
        if row and row["custom_banner"]:
            result["banner_text"] = row["custom_banner"]

    return jsonify(result)


@app.route("/api/sync", methods=["POST"])
def api_sync():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    machine_id = str(data.get("machine_id", "")).strip().upper()

    if not token or not machine_id:
        return jsonify({"ok": False, "message": "Missing token or machine_id"}), 400

    if get_maintenance_mode():
        return jsonify({"ok": False, "message": "Maintenance mode"}), 403

    ok, payload = verify_token(token)
    if not ok or not payload:
        return jsonify({"ok": False, "message": "Invalid token"}), 400

    if str(payload.get("machine_id", "")).strip().upper() != machine_id:
        return jsonify({"ok": False, "message": "Wrong PC"}), 403

    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "License not found"}), 404

    row = dict(row)

    conn.execute("UPDATE licenses SET last_seen=? WHERE machine_id=?", (utc_iso(), machine_id))
    conn.commit()

    if int(row["blocked"]) == 1:
        conn.close()
        return jsonify({
            "ok": False,
            "blocked": True,
            "message": "Blocked by admin",
            "server_time": utc_iso()
        }), 403

    if not bool(row["lifetime"]):
        try:
            expiry_date = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
            if utc_now().date() > expiry_date:
                conn.close()
                return jsonify({
                    "ok": False,
                    "message": "License expired",
                    "server_time": utc_iso()
                }), 403
        except Exception:
            conn.close()
            return jsonify({"ok": False, "message": "License expiry invalid"}), 500

    refreshed_row = conn.execute("SELECT * FROM licenses WHERE machine_id=?", (machine_id,)).fetchone()
    conn.close()

    new_token = sign_payload(build_payload_from_row(refreshed_row))

    return jsonify({
        "ok": True,
        "message": "Sync success",
        "server_time": utc_iso(),
        "sync_days": int(refreshed_row["sync_days"]),
        "token": new_token
    })


@app.route("/health", methods=["GET"])
def health():
    return "OK"


if __name__ == "__main__":
    if not os.path.exists(PRIVATE_KEY_FILE) or not os.path.exists(PUBLIC_KEY_FILE):
        print("private_key.pem or public_key.pem not found.")
        raise SystemExit(1)

    init_db()

    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
