from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta

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
            temperature REAL, humidity REAL, time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= ENHANCED AI FEATURE LOGIC =================

def detect_anomaly(current, history):
    if len(history) < 3 or not current: return False
    avg = sum(history) / len(history)
    return current > (avg * 1.5)

def predict_trend(history):
    if len(history) < 3: return "STABLE"
    if history[-1] > history[-2] > history[-3]: return "INCREASING (Worsening)"
    if history[-1] < history[-2] < history[-3]: return "DECREASING (Improving)"
    return "STABLE"

def get_detailed_ai_logic(risk, data, is_online):
    # If the system is offline, override advice to show connection error
    if not is_online:
        return {
            "health_advisory": "STALE DATA: System is offline. Do not rely on these readings.",
            "food_safety": "System Connection Lost.",
            "worker_monitoring": "SYSTEM ERROR: Check ESP32 Power/WiFi.",
            "exit_guidance": "Check Network Status."
        }
    
    if risk == "DANGER":
        return {
            "health_advisory": "CRITICAL: High respiratory risk. Drink 3L+ water. Eat Vitamin C rich foods.",
            "food_safety": "STOP consumption of local water. Use only sealed/bottled water.",
            "worker_monitoring": "MANDATORY: Workers must wear N95 masks. Max 15-min outdoor shifts.",
            "exit_guidance": "EVACUATE to Zone B (Clean Air Zone) immediately."
        }
    elif risk == "WARNING":
        return {
            "health_advisory": "MODERATE: Wear surgical masks. Avoid heavy exercise. Use antioxidants.",
            "food_safety": "Filter/Boil all drinking water. Keep food containers sealed.",
            "worker_monitoring": "CAUTION: Rotate staff every 2 hours. Ensure hydration stations.",
            "exit_guidance": "Stay indoors. Close windows and use air purifiers."
        }
    return {
        "health_advisory": "OPTIMAL: Safe conditions. Maintain balanced diet.",
        "food_safety": "Standard safety applies. Water and food are safe.",
        "worker_monitoring": "STABLE: Standard protocols. No extra PPE required.",
        "exit_guidance": "No evacuation required. All zones safe."
    }

def calculate_risk(data):
    pm, ph, turb = data.get("pm25", 0), data.get("ph", 7.0), data.get("turbidity", 0)
    score, insights = 0, []

    if pm > 150: score += 3; insights.append("Hazardous Air (PM2.5).")
    elif pm > 80: score += 1; insights.append("Elevated Air Pollution.")
    if ph < 6.5 or ph > 8.5: score += 1; insights.append("Water pH imbalance.")
    if turb > 500: score += 2; insights.append("High water turbidity.")

    risk_level = "DANGER" if score >= 3 else "WARNING" if score >= 1 else "SAFE"
    return risk_level, insights

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
        """, (data.get("pm25"), data.get("mq135"), data.get("ph"), data.get("turbidity"), 
              data.get("temperature"), data.get("humidity"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/latest", methods=["GET"])
def get_latest():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # FETCH LAST VALID DATA (Holding Logic)
    cursor.execute("SELECT ph, turbidity, temperature, humidity, time FROM sensor_data WHERE ph IS NOT NULL ORDER BY id DESC LIMIT 5")
    w_hist = cursor.fetchall()
    cursor.execute("SELECT pm25, mq135 FROM sensor_data WHERE pm25 IS NOT NULL ORDER BY id DESC LIMIT 5")
    a_hist = cursor.fetchall()
    conn.close()

    if not w_hist or not a_hist: return jsonify({"status": "OFFLINE", "message": "No data in database"})

    # Check for Heartbeat (Connection Status)
    last_time_str = w_hist[0][4]
    last_time_obj = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
    time_diff = (datetime.now() - last_time_obj).total_seconds()
    
    # If data is older than 60 seconds, consider it DISCONNECTED
    is_online = time_diff < 60 

    ph_history = [row[0] for row in w_hist][::-1]
    pm_history = [row[0] for row in a_hist][::-1]

    combined = {
        "ph": w_hist[0][0], "turbidity": w_hist[0][1],
        "temp": w_hist[0][2], "hum": w_hist[0][3],
        "pm25": a_hist[0][0], "mq135": a_hist[0][1],
        "time": w_hist[0][4]
    }

    risk_level, insights = calculate_risk(combined)
    # If offline, force risk to "UNKNOWN/DISCONNECTED"
    final_risk = risk_level if is_online else "DISCONNECTED"
    
    advisory = get_detailed_ai_logic(final_risk, combined, is_online)

    return jsonify({
        "system_status": "ONLINE" if is_online else "OFFLINE",
        "sensor_data": combined,
        "ai_risk_assessment": final_risk,
        "insights": insights if is_online else ["Check Device Connection"],
        "predictions": {
            "air_trend": predict_trend(pm_history) if is_online else "N/A",
            "water_trend": predict_trend(ph_history) if is_online else "N/A",
            "anomaly_detected": detect_anomaly(combined["pm25"], pm_history) if is_online else False
        },
        "daily_advisory": {
            "health_food": advisory["health_advisory"],
            "food_safety": advisory["food_safety"]
        },
        "worker_health": advisory["worker_monitoring"],
        "exit_guidance": advisory["exit_guidance"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
