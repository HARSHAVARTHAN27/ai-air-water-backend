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
            pm25 REAL, mq135 REAL, ph REAL, turbidity REAL,
            heartRate REAL, spo2 REAL, temperature REAL, humidity REAL,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= SMART AI ENGINE =================

def analyze_trends(history_values):
    """Predicts if levels are Increasing, Decreasing, or Stable."""
    if len(history_values) < 3: return "STABLE"
    if history_values[-1] > history_values[-2] > history_values[-3]:
        return "INCREASING"
    if values[-1] < values[-2] < values[-3]:
        return "DECREASING"
    return "STABLE"

def detect_anomaly(current, history):
    """Detects a sudden 50% spike compared to the moving average."""
    if len(history) < 3 or current is None: return False
    avg = sum(history) / len(history)
    return current > (avg * 1.5)

def get_ai_guidance(risk_level, insights):
    """Generates actionable safety protocols based on calculated risk."""
    guidance = {
        "DANGER": "EVACUATE AREA. Use industrial-grade masks and strictly avoid water source.",
        "WARNING": "CAUTION. Increase ventilation and boil/filter water before use.",
        "SAFE": "Normal conditions. No special action required."
    }
    return guidance.get(risk_level, "Monitor system closely.")

def ai_risk_engine(sensor, history_pm, history_turb):
    # Safe Extraction
    pm25 = sensor.get("pm25", 0) or 0.0
    mq135 = sensor.get("mq135", 0) or 0.0
    ph = sensor.get("ph", 7.0) or 7.0
    turb = sensor.get("turbidity", 0) or 0.0
    temp = sensor.get("temperature", 25) or 25.0

    risk_score = 0
    insights = []

    # --- Air AI Analysis ---
    if pm25 > 150: 
        risk_score += 2
        insights.append("Hazardous Air: PM2.5 levels pose immediate health risk.")
    elif pm25 > 80: 
        risk_score += 1
        insights.append("Air Quality: Poor. Sensitive groups should stay indoors.")

    # --- Water AI Analysis ---
    if ph < 6.5 or ph > 8.5:
        risk_score += 1
        insights.append(f"Water pH ({ph}) is corrosive/alkaline. Do not drink.")
    
    if turb > 1000:
        risk_score += 2
        insights.append("Severe Water Turbidity: High bacterial contamination risk.")
    
    # --- Determine Global Risk ---
    risk_level = "SAFE"
    if risk_score >= 3: risk_level = "DANGER"
    elif risk_score >= 1: risk_level = "WARNING"

    return {
        "risk_level": risk_level,
        "insights": insights,
        "trends": {
            "air_trend": analyze_trends(history_pm),
            "water_trend": analyze_trends(history_turb)
        },
        "anomalies": {
            "air_spike": detect_anomaly(pm25, history_pm),
            "water_spike": detect_anomaly(turb, history_turb)
        },
        "action_plan": get_ai_guidance(risk_level, insights)
    }

# ================= API ROUTES =================

@app.route("/api/upload", methods=["POST"])
def upload_data():
    try:
        data = request.json
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sensor_data (pm25, mq135, ph, turbidity, temperature, humidity, time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data.get("pm25"), data.get("mq135"), data.get("ph"), 
              data.get("turbidity"), data.get("temperature"), data.get("humidity"),
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return jsonify({"status": "Success"}), 200
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

@app.route("/api/latest", methods=["GET"])
def get_latest():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get Current Data
    cursor.execute("SELECT pm25, mq135, ph, turbidity, temperature, humidity, time FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()

    # Get Historical Data for AI Analysis (Last 5 records)
    cursor.execute("SELECT pm25, turbidity FROM sensor_data ORDER BY id DESC LIMIT 5")
    history = cursor.fetchall()
    conn.close()

    if not row: return jsonify({"message": "No data"})

    s_data = {"pm25": row[0], "mq135": row[1], "ph": row[2], "turbidity": row[3], "temperature": row[4]}
    
    # Process through AI Engine
    pm_history = [r[0] for r in history if r[0] is not None][::-1]
    turb_history = [r[1] for r in history if r[1] is not None][::-1]
    
    ai_report = ai_risk_engine(s_data, pm_history, turb_history)

    return jsonify({
        "sensor_data": s_data,
        "timestamp": row[6],
        "ai_analysis": ai_report
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
