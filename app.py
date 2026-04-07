import os
import json
import base64
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

DB_FILE = "licenses.db"
PRIVATE_KEY_FILE = "private_key.pem"
PUBLIC_KEY_FILE = "public_key.pem"
SETTINGS_FILE = "panel_settings.json"

app = Flask(__name__)


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso(dt=None):
    dt = dt or utc_now()
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


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
    conn.commit()
    conn.close()


def ensure_settings_file():
    if not os.path.exists(SETTINGS_FILE):
        save_settings({
            "banner_text": "RA DEVELOPER Exclusive License --- Hapi Automation Board",
            "developer_name": "DR.MASUM",
            "contact_number": "01799523472"
        })


def load_settings():
    ensure_settings_file()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "banner_text": "RA DEVELOPER Exclusive License --- Hapi Automation Board",
            "developer_name": "DR.MASUM",
            "contact_number": "01799523472"
        }


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
    return {
        "user": row["user"],
        "machine_id": row["machine_id"],
        "issued_at": row["created_at"],
        "expiry": row["expiry"],
        "lifetime": bool(row["lifetime"]),
        "sync_days": int(row["sync_days"]),
        "server_url": row["server_url"] or "",
    }


@app.route("/")
def home():
    return "HAPI SERVER RUNNING"


@app.route("/api/public_settings", methods=["GET"])
def public_settings():
    return jsonify(load_settings())


@app.route("/api/update_settings", methods=["POST"])
def update_settings():
    data = request.get_json(silent=True) or {}
    current = load_settings()

    current["banner_text"] = str(
        data.get("banner_text", current.get("banner_text", ""))
    ).strip()
    current["developer_name"] = str(
        data.get("developer_name", current.get("developer_name", ""))
    ).strip()
    current["contact_number"] = str(
        data.get("contact_number", current.get("contact_number", ""))
    ).strip()

    save_settings(current)
    return jsonify({"success": True, "settings": current})


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

    token_machine_id = str(payload.get("machine_id", "")).strip().upper()
    if token_machine_id != machine_id:
        return jsonify({"ok": False, "message": "Wrong PC"}), 403

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM licenses WHERE machine_id = ?",
        (machine_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "License not found"}), 404

    row = dict(row)

    conn.execute(
        "UPDATE licenses SET last_seen = ? WHERE machine_id = ?",
        (utc_iso(), machine_id)
    )
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
            return jsonify({
                "ok": False,
                "message": "License expiry invalid"
            }), 500

    refreshed_row = conn.execute(
        "SELECT * FROM licenses WHERE machine_id = ?",
        (machine_id,)
    ).fetchone()
    conn.close()

    new_token = sign_payload(build_payload_from_row(refreshed_row))

    return jsonify({
        "ok": True,
        "message": "Sync success",
        "server_time": utc_iso(),
        "sync_days": int(refreshed_row["sync_days"]),
        "token": new_token
    })


if __name__ == "__main__":
    if not os.path.exists(PRIVATE_KEY_FILE) or not os.path.exists(PUBLIC_KEY_FILE):
        print("private_key.pem or public_key.pem not found.")
        raise SystemExit(1)

    init_db()
    ensure_settings_file()

    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
