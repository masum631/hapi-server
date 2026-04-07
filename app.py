from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

SETTINGS_FILE = "panel_settings.json"


# -----------------------------
# Load settings
# -----------------------------
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


# -----------------------------
# Save settings
# -----------------------------
def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)


# -----------------------------
# PUBLIC API (IMPORTANT)
# -----------------------------
@app.route("/api/public_settings", methods=["GET"])
def public_settings():
    settings = load_settings()
    return jsonify(settings)


# -----------------------------
# ADMIN LOGIN
# -----------------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    if data.get("username") == "admin" and data.get("password") == "admin":
        return jsonify({"success": True})
    return jsonify({"success": False}), 401


# -----------------------------
# UPDATE SETTINGS
# -----------------------------
@app.route("/api/update_settings", methods=["POST"])
def update_settings():
    data = request.json
    save_settings(data)
    return jsonify({"success": True})


# -----------------------------
# ROOT CHECK
# -----------------------------
@app.route("/")
def home():
    return "HAPI SERVER RUNNING"


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
