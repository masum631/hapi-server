from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

SETTINGS_FILE = "panel_settings.json"

# demo in-memory sync ok response
# later চাইলে DB/signature logic add করবে

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "banner_text": "RA DEVELOPER Exclusive License --- Hapi Automation Board",
            "developer_name": "DR.MASUM",
            "contact_number": "01799523472"
        }
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
    current["banner_text"] = data.get("banner_text", current.get("banner_text", ""))
    current["developer_name"] = data.get("developer_name", current.get("developer_name", ""))
    current["contact_number"] = data.get("contact_number", current.get("contact_number", ""))
    save_settings(current)
    return jsonify({"success": True})


@app.route("/api/sync", methods=["POST"])
def api_sync():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    machine_id = str(data.get("machine_id", "")).strip()

    if not token or not machine_id:
        return jsonify({"ok": False, "message": "Missing token or machine_id"}), 400

    # temporary success response so customer bot shows ONLINE
    return jsonify({
        "ok": True,
        "message": "Sync success",
        "server_time": "2026-04-08T00:00:00+00:00",
        "token": token
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
