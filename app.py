from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_NAME = "sensordata.db"

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

def ai_risk_analysis(sensor):
    ph = sensor.get("ph", 7)
    turbidity = sensor.get("turbidity", 0)
    temp = sensor.get("temperature", 25)
    hum = sensor.get("humidity", 50)

    risk = "SAFE"
    insights = []

    # Water Quality Logic
    if ph < 6.5 or ph > 8.5:
        risk = "WARNING"
        insights.append(f"Unsafe pH level: {ph}. Neutral range is 6.5-8.5.")
    
    if turbidity > 1000:
        risk = "DANGER"
        insights.append("High Turbidity! Water contains heavy suspended solids.")

    # Temp & Humidity Logic
    if temp > 45:
        risk = "WARNING"
        insights.append(f"High Temp detected ({temp}°C). May affect oxygen levels in water.")
    
    if hum > 90:
        insights.append("High Humidity: Risk of condensation on electronic components.")

    return risk, insights

@app.route("/api/upload", methods=["POST"])
def upload_data():
    try:
        data = request.json
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
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
        return jsonify({"status": "Success"}), 200
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

@app.route("/api/latest", methods=["GET"])
def get_latest():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT ph, turbidity, temperature, humidity, time FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row: return jsonify({"message": "No data"})

    s_data = {"ph": row[0], "turbidity": row[1], "temperature": row[2], "humidity": row[3]}
    risk, insights = ai_risk_analysis(s_data)
    
    return jsonify({"sensor_data": s_data, "time": row[4], "ai_risk": risk, "insights": insights})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
