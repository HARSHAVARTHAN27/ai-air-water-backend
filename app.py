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

# ================= AI LOGIC HELPERS =================

def analyze_trend(values):
    """Checks if the last 3 readings are increasing or decreasing."""
    if len(values) < 3: return "STABLE"
    if values[-1] > values[-2] > values[-3]: return "INCREASING"
    if values[-1] < values[-2] < values[-3]: return "DECREASING"
    return "STABLE"

def detect_anomaly(current, history):
    """Detects a sudden 50% spike compared to recent average."""
    if len(history) < 3 or current is None: return False
    avg = sum(history) / len(history)
    return current > (avg * 1.5)

# ================= MAIN AI RISK ENGINE =================

def ai_risk_engine(sensor, history_pm, history_turb):
    # Safe data extraction with defaults
    pm25 = sensor.get("pm25") if sensor.get("pm25") is not None else 0.0
    turb = sensor.get("turbidity") if sensor.get("turbidity") is not None else 0.0
    ph = sensor.get("ph") if sensor.get("ph") is not None else 7.0
    temp = sensor.get("temperature") if sensor.get("temperature") is not None else 25.0

    risk_level = "SAFE"
    insights = []
    
    # 1. Air Risk
    if pm25 > 150:
        risk_level = "DANGER"
        insights.append("CRITICAL: Hazardous PM2.5 levels. Evacuate or use N95 masks.")
    elif pm25 > 80:
        risk_level = "WARNING"
        insights.append("Warning: Air quality is poor. Limit outdoor activity.")

    # 2. Water Risk
    if ph < 6.5 or ph > 8.5:
        if risk_level != "DANGER": risk_level = "WARNING"
        insights.append(f"Water pH ({ph}) is outside safe limits (6.5-8.5).")
    
    if turb > 1000:
        risk_level = "DANGER"
        insights.append("Water is highly turbid. High risk of contamination.")
    
    # 3. Trends & Anomalies
    air_trend = analyze_trend(history_pm)
    water_trend = analyze_trend(history_turb)
    
    return {
        "overall_risk": risk_level,
        "insights": insights,
        "analysis": {
            "air_trend": air_trend,
            "water_trend": water_trend,
            "air_anomaly": detect_anomaly(pm25, history_pm),
            "water_anomaly": detect_anomaly(turb, history_turb)
        },
        "guidance": "Boil water and use air purifiers." if risk_level != "SAFE" else "Conditions are optimal."
    }

# ================= API ROUTES =================

@app.route("/")
def home():
    return jsonify({"message": "AI Air & Water Backend is Live", "status": "Ready"})

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
    
    # Get Current
    cursor.execute("SELECT pm25, mq135, ph, turbidity, temperature, humidity, time FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()

    # Get Last 5 for AI History
    cursor.execute("SELECT pm25, turbidity FROM sensor_data ORDER BY id DESC LIMIT 5")
    hist_rows = cursor.fetchall()
    conn.close()

    if not row: return jsonify({"message": "No data yet"})

    # Prepare data for AI
    current_sensor = {"pm25": row[0], "mq135": row[1], "ph": row[2], "turbidity": row[3], "temperature": row[4], "humidity": row[5]}
    pm_history = [r[0] for r in hist_rows if r[0] is not None][::-1]
    turb_history = [r[1] for r in hist_rows if r[1] is not None][::-1]

    # Run AI Risk Engine
    ai_results = ai_risk_engine(current_sensor, pm_history, turb_history)

    return jsonify({
        "timestamp": row[6],
        "sensor_data": current_sensor,
        "ai_report": ai_results
    })

@app.route("/api/history", methods=["GET"])
def get_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT pm25, ph, turbidity, time FROM sensor_data ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{"pm25": r[0], "ph": r[1], "turb": r[2], "time": r[3]} for r in rows[::-1]])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
