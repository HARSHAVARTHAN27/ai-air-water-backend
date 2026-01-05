from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_NAME = "sensordata.db"

# ================= DATABASE INITIALIZATION =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pm25 REAL,
            co2 REAL,
            ph REAL,
            heartRate REAL,
            spo2 REAL,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= AI FUNCTIONS =================

def calculate_risk_score(pm25, co2, hr, spo2):
    score = 0
    if pm25 and pm25 > 80:
        score += 2
    if pm25 and pm25 > 150:
        score += 4
    if co2 and co2 > 1000:
        score += 2
    if hr and hr > 100:
        score += 2
    if spo2 and spo2 < 94:
        score += 3

    if score >= 6:
        return "HIGH"
    elif score >= 3:
        return "MEDIUM"
    else:
        return "LOW"


def detect_anomaly(current, history):
    if len(history) < 3:
        return False
    avg = sum(history) / len(history)
    return current > avg * 1.5


def predict_trend(values):
    if len(values) < 3:
        return "STABLE"
    if values[-1] > values[-2] > values[-3]:
        return "INCREASING"
    if values[-1] < values[-2] < values[-3]:
        return "DECREASING"
    return "STABLE"


def suggest_exit(pm25):
    zone_status = {
        "Zone A": "DANGER" if pm25 > 150 else "SAFE",
        "Zone B": "SAFE",
        "Zone C": "WARNING" if pm25 > 80 else "SAFE"
    }
    for zone, status in zone_status.items():
        if status == "SAFE":
            return f"Move towards {zone} Exit"
    return "Remain calm and wait for assistance"


def health_food_advisory(pm25, ph, hr, spo2):
    advice = []

    if pm25 and pm25 > 100:
        advice.append("Consume fruits rich in antioxidants")
        advice.append("Avoid oily and fried food")
        advice.append("Drink more water")

    if ph and (ph < 6.5 or ph > 8.5):
        advice.append("Use boiled or filtered water")

    if hr and hr > 100:
        advice.append("Take short rest breaks")

    if spo2 and spo2 < 94:
        advice.append("Avoid heavy physical activity today")

    if not advice:
        advice.append("Normal diet and activities recommended")

    return advice

# ================= API ROUTES =================

@app.route("/")
def home():
    return "AI Safety Backend Running"

# ---------- ESP32 SENDS DATA ----------
@app.route("/api/upload", methods=["POST"])
def upload_data():
    data = request.json

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sensor_data (pm25, co2, ph, heartRate, spo2, time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("pm25"),
        data.get("co2"),
        data.get("ph"),
        data.get("heartRate"),
        data.get("spo2"),
        datetime.now().strftime("%H:%M:%S")
    ))
    conn.commit()
    conn.close()

    return jsonify({"status": "Data stored successfully"}), 200

# ---------- DASHBOARD GET LATEST ----------
@app.route("/api/latest")
def latest_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()

    cursor.execute("SELECT pm25 FROM sensor_data ORDER BY id DESC LIMIT 5")
    pm_history = [r[0] for r in cursor.fetchall()]
    conn.close()

    if not row:
        return jsonify({"message": "No data available"})

    pm25 = row[1]
    co2 = row[2]
    ph = row[3]
    hr = row[4]
    spo2 = row[5]

    response = {
        "pm25": pm25,
        "co2": co2,
        "ph": ph,
        "heartRate": hr,
        "spo2": spo2,
        "time": row[6],
        "personal_risk": calculate_risk_score(pm25, co2, hr, spo2),
        "anomaly_detected": detect_anomaly(pm25, pm_history),
        "trend": predict_trend(pm_history),
        "exit_guidance": suggest_exit(pm25),
        "daily_advisory": health_food_advisory(pm25, ph, hr, spo2)
    }

    return jsonify(response)

# ---------- HISTORY FOR GRAPHS ----------
@app.route("/api/history")
def history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT pm25, ph, time FROM sensor_data ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {"pm25": r[0], "ph": r[1], "time": r[2]}
        for r in rows[::-1]
    ])

# ================= RUN SERVER =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
