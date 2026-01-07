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
    # Table includes all potential sensors but allows them to be NULL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pm25 REAL,
            mq135 REAL,
            ph REAL,
            turbidity REAL,
            heartRate REAL,
            spo2 REAL,
            temperature REAL,
            humidity REAL,
            time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= AI RISK ANALYSIS (With NoneType Protection) =================
def ai_risk_analysis(sensor):
    # Safety check: if the value is None from the DB, use a neutral default
    ph = sensor.get("ph") if sensor.get("ph") is not None else 7.0
    turb = sensor.get("turbidity") if sensor.get("turbidity") is not None else 0.0
    temp = sensor.get("temperature") if sensor.get("temperature") is not None else 25.0
    hum = sensor.get("humidity") if sensor.get("humidity") is not None else 50.0

    risk = "SAFE"
    insights = []

    # Water Quality AI Logic
    if ph < 6.5 or ph > 8.5:
        risk = "WARNING"
        insights.append(f"Water pH ({ph}) is outside safe drinking limits.")
    
    if turb > 1000:
        risk = "DANGER"
        insights.append("High turbidity detected! The water is very cloudy.")
    elif turb > 400:
        if risk != "DANGER": risk = "WARNING"
        insights.append("Moderate turbidity. Filtration recommended.")

    # Temp & Humidity Logic
    if temp > 45:
        risk = "WARNING"
        insights.append(f"High Temperature ({temp}°C) may affect water oxygen levels.")
    
    if hum > 90:
        insights.append("Extremely high humidity detected.")

    return risk, insights

# ================= API ROUTES =================

@app.route("/")
def home():
    return "Water Monitoring AI Backend is Online"

# ---------- ESP32 UPLOAD ROUTE ----------
@app.route("/api/upload", methods=["POST"])
def upload_data():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON payload received"}), 400

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Insert data using .get() to avoid KeyErrors if a sensor is missing
        cursor.execute("""
            INSERT INTO sensor_data (ph, turbidity, temperature, humidity, time)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("ph"),
            data.get("turbidity"),
            data.get("temperature"),
            data.get("humidity"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()
        
        print(f"Successfully stored: {data}")
        return jsonify({"status": "Success", "data_received": data}), 200

    except Exception as e:
        print(f"Upload Error: {e}")
        return jsonify({"status": "Error", "message": str(e)}), 500

# ---------- DASHBOARD LATEST DATA ----------
@app.route("/api/latest", methods=["GET"])
def get_latest():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Fetch the most recent row
        cursor.execute("SELECT ph, turbidity, temperature, humidity, time FROM sensor_data ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"message": "Database is currently empty"}), 200

        # Map DB row to dictionary for AI processing
        s_data = {
            "ph": row[0],
            "turbidity": row[1],
            "temperature": row[2],
            "humidity": row[3]
        }
        
        risk, insights = ai_risk_analysis(s_data)
        
        return jsonify({
            "sensor_data": s_data,
            "timestamp": row[4],
            "ai_analysis": {
                "risk_level": risk,
                "insights": insights
            }
        })

    except Exception as e:
        print(f"Latest Route Error: {e}")
        return jsonify({"error": str(e)}), 500

# ---------- DATA HISTORY (For Graphs) ----------
@app.route("/api/history", methods=["GET"])
def get_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT ph, turbidity, time FROM sensor_data ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {"ph": r[0], "turbidity": r[1], "time": r[2]}
        for r in rows[::-1] # Reverse to show oldest to newest on graph
    ])

# ================= RUN SERVER =================
if __name__ == "__main__":
    # Port 5000 for local; Render will override this automatically
    app.run(host="0.0.0.0", port=5000)
