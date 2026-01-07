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
            mq135 REAL,
            ph REAL,
            turbidity REAL,
            temperature REAL,
            humidity REAL,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= AI RISK ANALYSIS =================
def ai_risk_analysis(data):
    risk = "SAFE"
    insights = []

    # Water Logic (Using .get with defaults for safety)
    ph = data.get("ph", 7.0)
    turb = data.get("turbidity", 0.0)
    if ph < 6.5 or ph > 8.5:
        risk = "WARNING"
        insights.append(f"Abnormal pH level: {ph}")
    if turb > 1000:
        risk = "DANGER"
        insights.append("High water turbidity detected.")

    # Air Logic
    pm = data.get("pm25", 0.0)
    if pm > 150:
        risk = "DANGER"
        insights.append("Hazardous Air Quality (PM2.5)")
    elif pm > 80:
        if risk != "DANGER": risk = "WARNING"
        insights.append("Poor Air Quality.")

    return risk, insights

# ================= API ROUTES =================

@app.route("/")
def home():
    return "AI Sensor Backend - Status: Online (Holding Values Enabled)"

# ---------- UPLOAD ROUTE (ESP32 Calls This) ----------
@app.route("/api/upload", methods=["POST"])
def upload_data():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400
            
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sensor_data (pm25, mq135, ph, turbidity, temperature, humidity, time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("pm25"), data.get("mq135"), 
            data.get("ph"), data.get("turbidity"),
            data.get("temperature"), data.get("humidity"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "Data Recorded"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- LATEST ROUTE (Dashboard Calls This) ----------
@app.route("/api/latest", methods=["GET"])
def get_latest():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # FETCH LAST WATER DATA (Holds value if current packet only has air)
        cursor.execute("""
            SELECT ph, turbidity, temperature, humidity, time 
            FROM sensor_data 
            WHERE ph IS NOT NULL 
            ORDER BY id DESC LIMIT 1
        """)
        w_row = cursor.fetchone()

        # FETCH LAST AIR DATA (Holds value if current packet only has water)
        cursor.execute("""
            SELECT pm25, mq135 
            FROM sensor_data 
            WHERE pm25 IS NOT NULL 
            ORDER BY id DESC LIMIT 1
        """)
        a_row = cursor.fetchone()
        
        conn.close()

        # Build combined data (Memory logic)
        combined_data = {
            "ph": w_row[0] if w_row else 7.0,
            "turbidity": w_row[1] if w_row else 0.0,
            "temperature": w_row[2] if w_row else 25.0,
            "humidity": w_row[3] if w_row else 50.0,
            "pm25": a_row[0] if a_row else 0.0,
            "mq135": a_row[1] if a_row else 0.0,
            "timestamp": w_row[4] if w_row else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Run AI analysis on the merged "held" data
        risk, insights = ai_risk_analysis(combined_data)

        return jsonify({
            "sensor_data": combined_data,
            "ai_report": {
                "risk_level": risk,
                "insights": insights
            },
            "status": "values_held"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- HISTORY ROUTE (For Charts) ----------
@app.route("/api/history", methods=["GET"])
def get_history():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT ph, turbidity, pm25, time FROM sensor_data ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        return jsonify([{"ph": r[0], "turb": r[1], "pm25": r[2], "time": r[3]} for r in rows[::-1]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
