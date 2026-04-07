from flask import Flask, request, jsonify

app = Flask(__name__)

# simple memory storage
devices = {}

@app.route("/")
def home():
    return "HAPI SERVER RUNNING"

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    device_id = data.get("device_id")
    
    devices[device_id] = {
        "status": "online",
        "blocked": False
    }
    
    return jsonify({"message": "registered"})

@app.route("/get_status/<device_id>")
def get_status(device_id):
    if device_id in devices:
        return jsonify(devices[device_id])
    return jsonify({"error": "not found"})

@app.route("/block/<device_id>", methods=["POST"])
def block(device_id):
    if device_id in devices:
        devices[device_id]["blocked"] = True
        return jsonify({"message": "blocked"})
    return jsonify({"error": "not found"})

@app.route("/unblock/<device_id>", methods=["POST"])
def unblock(device_id):
    if device_id in devices:
        devices[device_id]["blocked"] = False
        return jsonify({"message": "unblocked"})
    return jsonify({"error": "not found"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)