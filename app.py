from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# settings file
SETTINGS_FILE = "panel_settings.json"

# =========================
# PUBLIC SETTINGS API (IMPORTANT)
# =========================
@app.route("/api/public_settings")
def public_settings():
    try:
        if not os.path.exists(SETTINGS_FILE):
            return jsonify({"error": "settings file not found"})

        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)

        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})

# =========================
# HOME (optional)
# =========================
@app.route("/")
def home():
    return "HAPI SERVER RUNNING"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
