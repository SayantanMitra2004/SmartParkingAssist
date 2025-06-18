import os
import uuid
import sqlite3
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for,session
from werkzeug.utils import secure_filename

app = Flask(__name__)
DATABASE = 'parking.db'
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        vehicle_number TEXT,
        vehicle_type TEXT,
        location TEXT,
        entry_time TEXT,
        exit_time TEXT,
        submitted_at TEXT

        )
    ''')

def create_station_file(station_id, data):
    monthly_rate_value = data.get('monthlyRate')
    if monthly_rate_value is not None:
        try:
            monthly_rate_str = f"${float(monthly_rate_value):.2f}"
        except:
            monthly_rate_str = "Invalid"
    else:
        monthly_rate_str = "Not set"

    content = f"""
🚗 Parking Station Registration Confirmation

Station ID: {station_id}
Station Name: {data.get('stationName', '')}
Manager Name: {data.get('managerName', '')}
Address: {data.get('address', '')}
Contact: {data.get('contactNumber', 'N/A')}

Total Capacity: {data.get('totalCapacity', '')}
Hourly Rate: ${float(data.get('hourlyRate', 0)):.2f}
Daily Rate: ${float(data.get('dailyRate', 0)):.2f}
Monthly Rate: {monthly_rate_str}

✅ Registration completed successfully!
"""

    filename = f"{station_id}_confirmation.txt"
    filepath = os.path.join(DOWNLOAD_FOLDER, secure_filename(filename))

    # ✅ Use utf-8 encoding to support emojis
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip())

    return filename


def fetch_parking_stations():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT station_name, address, hourly_rate, total_capacity FROM stations')
        stations = cursor.fetchall()

    # Convert rows to dictionary format
    result = []
    for row in stations:
        name, address, rate, capacity = row
        result.append({
            'name': name,
            'address': address,
            'rate': f'₹{int(rate)}/hour',
            'distance': f'{round(0.5 + (capacity % 15) * 0.1, 1)} km',
            'availability': 'available' if capacity > 20 else ('limited' if 0 < capacity <= 20 else 'full'),
            'spots': capacity,
            'category': 'premium' if rate > 40 else 'budget'
        })
    return result

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/find_parking')
def parking_info():
    return render_template('find_parking.html')

@app.route('/station_manager')
def station_manager():
    return render_template('station_manager.html')


@app.route('/parking_info', methods=['GET','POST'])
def receive_parking_info():
   
    try:
        data = request.json

        name = data.get('name')
        phone = data.get('phone')
        vehicle_number = data.get('vehicleNumber')
        vehicle_type = data.get('vehicleType')
        location = data.get('currentLocation')
        entry_time = data.get('entryTime')
        exit_time = data.get('exitTime')
        timestamp = data.get('timestamp')

        if isinstance(location, dict):
            location_str = f"{location.get('latitude')}, {location.get('longitude')}"
        else:
            location_str = str(location)  # fallback if it's already a string


        # Log data for debugging
        print(f"Received parking info: {data}")

        # Optional: validate fields here

        # Save to SQLite (you must create the table beforehand)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO parking_requests 
            (name, phone, vehicle_number, vehicle_type, location, entry_time, exit_time, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, phone, vehicle_number, vehicle_type, location_str, entry_time, exit_time, timestamp))
        conn.commit()
        conn.close()

        # Redirect to get_parking and pass location in query string
        return redirect(url_for('get_parking', location=location_str))

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Something went wrong"}), 500
    

@app.route('/stations')
def get_stations():
    stations = fetch_parking_stations()
    return jsonify(stations)

@app.route('/get_parking')
def get_parking():
    location = request.args.get('location', 'Unknown Location')
    print(location)
    return render_template('parking_info.html', location=location)

# Route: Register new parking station
@app.route('/register_station', methods=['GET','POST'])
def register_station():
    if request.method == "POST":
        try:
            data = request.get_json() if request.is_json else request.form.to_dict()
            print("Received data:", data)  # Debug log

            # Required fields validation
            required_fields = ['stationName', 'managerName', 'address', 'totalCapacity', 'hourlyRate', 'dailyRate']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400

            # Assigning values safely
            station_id = str(uuid.uuid4())[:8]
            name = data.get('stationName', '').strip()
            manager = data.get('managerName', '').strip()
            address = data.get('address', '').strip()
            total_capacity = int(data.get('totalCapacity', 0))
            contact = data.get('contactNumber', '').strip()
            hourly_rate = float(data.get('hourlyRate', 0))
            daily_rate = float(data.get('dailyRate', 0))
            monthly_rate = data.get('monthlyRate')
            monthly_rate = float(monthly_rate) if monthly_rate else None

            # Save to database
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stations (
                        station_id TEXT PRIMARY KEY,
                        station_name TEXT,
                        manager_name TEXT,
                        address TEXT,
                        total_capacity INTEGER,
                        contact_number TEXT,
                        hourly_rate REAL,
                        daily_rate REAL,
                        monthly_rate REAL
                    )
                ''')
                cursor.execute('''
                    INSERT INTO stations (station_id, station_name, manager_name, address, total_capacity, contact_number, hourly_rate, daily_rate, monthly_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (station_id, name, manager, address, total_capacity, contact, hourly_rate, daily_rate, monthly_rate))
                conn.commit()

            # Generate station file
            file_name = create_station_file(station_id, data)

            return jsonify({
                "status": "success",
                "station_id": station_id,
                "download_file": file_name
            })

        except Exception as e:
            print("Error:", str(e))
            return jsonify({"status": "error", "message": str(e)}), 500


    
    return render_template('register_station.html')

# Route to serve download file
@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found"}), 404


if __name__ == "__main__":
    app.run(debug = True)