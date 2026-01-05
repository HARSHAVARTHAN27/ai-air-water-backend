from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_NAME = "sensordata.db"

# ================= DATABASE INITIALIZATION =================
def init_db():
    conn = sqlite3.connect("sensordata.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pm25 REAL,
            mq135 REAL,
            ph REAL,
            heartRate REAL,
            spo2 REAL,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= SMART AI LOGIC =================

def ai_risk_analysis(data):
    mq135 = data.get("mq135")
    ph = data.get("ph")
    ph = sensor.get("ph", 7)

    risk = "SAFE"
    insights = []

    if pm25 > 150:
        risk = "DANGER"
        insights.append(
            "PM2.5 has reached a critical level. Prolonged exposure can cause breathing stress and eye irritation."
        )
    elif pm25 > 80:
        risk = "WARNING"
        insights.append(
            "PM2.5 level is elevated. Long exposure may lead to fatigue or mild respiratory discomfort."
        )

   if mq135 is not None and mq135 > 1.2:
    # do something
        risk = "WARNING"
        insights.append(
            "Toxic gas concentration detected. Ventilation is recommended."
        )

    if ph is not None and (ph < 6.5 or ph > 8.5):
        risk = "WARNING"
        insights.append(
            "Water quality is outside the safe pH range. Consumption without treatment is not advised."
        )

    return risk, insights


def detect_anomaly(current, history):
    if len(history) < 3 or current is None:
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


def ai_exit_guidance(risk):
    if risk == "DANGER":
        return {
            "message": "Evacuate immediately via Exit-B (upwind side). Avoid enclosed and low-ventilation zones.",
            "priority": "HIGH"
        }
    elif risk == "WARNING":
        return {
            "message": "Reduce exposure. Move to well-ventilated areas and avoid emission zones.",
            "priority": "MEDIUM"
        }
    else:
        return {
            "message": "No evacuation required. Environment is stable.",
            "priority": "LOW"
        }


def ai_health_and_food_advice(risk):
    if risk == "DANGER":
        return {
            "workers": [
                "Drink warm water frequently",
                "Consume Vitamin-C rich fruits",
                "Avoid heavy physical work",
                "Wear N95 or industrial masks"
            ],
            "nearby_homes": [
                "Keep doors and windows closed",
                "Avoid outdoor activities",
                "Use boiled or filtered water"
            ],
            "officers": [
                "Activate ventilation systems",
                "Restrict access to high-risk zones",
                "Initiate shift rotation if needed"
            ]
        }

    elif risk == "WARNING":
        return {
            "workers": [
                "Increase fluid intake",
                "Prefer light meals",
                "Limit exposure duration"
            ],
            "nearby_homes": [
                "Limit outdoor exposure",
                "Ensure clean drinking water"
            ],
            "officers": [
                "Monitor pollution trends",
                "Prepare emergency response"
            ]
        }

    else:
        return {
            "workers": [
                "Maintain balanced diet",
                "Stay hydrated",
                "Follow safety norms"
            ],
            "nearby_homes": [
                "Normal activities can continue"
            ],
            "officers": [
                "Continue routine monitoring"
            ]
        }

# ================= API ROUTES =================

@app.route("/")
def home():
    return "AI Safety Backend Running"


# ---------- ESP / NODEMCU UPLOAD ----------
@app.route("/api/upload", methods=["POST"])
def upload_data():
    data = request.json

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sensor_data (pm25, mq135, ph, heartRate, spo2, time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("pm25"),
        data.get("mq135"),
        data.get("ph"),
        data.get("heartRate"),
        data.get("spo2"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

    return jsonify({"status": "Data stored successfully"}), 200


# ---------- LATEST DATA FOR DASHBOARD ----------
@app.route("/api/latest", methods=["GET"])
def get_latest():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()

    cursor.execute("SELECT pm25 FROM sensor_data ORDER BY id DESC LIMIT 5")
    pm_history = [r[0] for r in cursor.fetchall() if r[0] is not None]
    conn.close()

    if not row:
        return jsonify({"message": "No data available"})

    pm25, mq135, ph, hr, spo2 = row[1], row[2], row[3], row[4], row[5]

    risk, insights = ai_risk_analysis({
        "pm25": pm25,
        "mq135": mq135,
        "ph": ph
    })

    response = {
        "timestamp": row[6],
        "sensor_data": {
            "pm25": pm25,
            "mq135": mq135,
            "ph": ph,
            "heartRate": hr,
            "spo2": spo2
        },
        "ai": {
            "risk_level": risk,
            "ai_insights": insights,
            "anomaly_detected": detect_anomaly(pm25, pm_history),
            "trend": predict_trend(pm_history),
            "exit_guidance": ai_exit_guidance(risk),
            "health_and_food_advice": ai_health_and_food_advice(risk)
        }
    }

    return jsonify(response)


# ---------- HISTORY FOR GRAPHS ----------
@app.route("/api/history", methods=["GET"])
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
    app.run(host="0.0.0.0", port=5000)
