from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

# Globale Variable für die Daten
data_bundle = None

def load_gtfs():
    global data_bundle
    if data_bundle is not None:
        return data_bundle
    
    try:
        print("Lade GTFS-Daten (Lazy Loading)...")
        # Hier laden wir nur die absolut notwendigen Spalten, um RAM zu sparen
        stops = pd.read_csv('stops.txt', dtype=str)[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        stops['stop_lat'] = pd.to_numeric(stops['stop_lat'])
        stops['stop_lon'] = pd.to_numeric(stops['stop_lon'])
        
        stops_display = stops.groupby('stop_name').agg({
            'stop_lat': 'mean', 'stop_lon': 'mean', 'stop_id': 'first'
        }).reset_index()

        routes = pd.read_csv('routes.txt', dtype=str)[['route_id', 'route_short_name', 'route_type']]
        trips = pd.read_csv('trips.txt', dtype=str)[['trip_id', 'route_id', 'service_id', 'trip_headsign']]
        stimes = pd.read_csv('stop_times.txt', dtype=str)[['trip_id', 'departure_time', 'stop_id']]
        calendar = pd.read_csv('calendar.txt', dtype=str)
        cal_dates = pd.read_csv('calendar_dates.txt', dtype=str) if os.path.exists('calendar_dates.txt') else pd.DataFrame()

        df_live = stimes.merge(stops, on='stop_id').merge(trips, on='trip_id').merge(routes, on='route_id')
        df_live['seconds'] = df_live['departure_time'].apply(lambda x: int(x.split(':')[0])*3600 + int(x.split(':')[1])*60 + int(x.split(':')[2]))
        
        data_bundle = (df_live, stops_display, calendar, cal_dates, stimes, trips, routes, stops)
        print("GTFS-Daten erfolgreich geladen!")
        return data_bundle
    except Exception as e:
        print(f"Fehler beim Laden: {e}")
        return None

# Hilfsfunktion, um sicherzustellen, dass Daten da sind
def get_data():
    data = load_gtfs()
    if data is None:
        return None, None, None, None, None, None, None, None
    return data

def get_active_services(calendar, cal_dates):
    now = datetime.now()
    day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][now.weekday()]
    today = now.strftime("%Y%m%d")
    active = calendar[calendar[day_name] == '1']['service_id'].tolist()
    if not cal_dates.empty:
        removed = cal_dates[(cal_dates['date'] == today) & (cal_dates['exception_type'] == '2')]['service_id'].tolist()
        added = cal_dates[(cal_dates['date'] == today) & (cal_dates['exception_type'] == '1')]['service_id'].tolist()
        active = [s for s in active if s not in removed]
        active.extend(added)
    return active

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/stops')
def get_stops():
    _, stops_display, _, _, _, _, _, _ = get_data()
    return jsonify(stops_display.to_dict(orient='records') if stops_display is not None else [])

@app.route('/vehicles')
def get_vehicles():
    df_main, _, calendar, cal_dates, _, _, _, _ = get_data()
    if df_main is None: return jsonify([])
    
    sec = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second
    active_services = get_active_services(calendar, cal_dates)
    active_now = df_main[(df_main['seconds'] >= sec - 600) & (df_main['seconds'] <= sec + 600) & (df_main['service_id'].isin(active_services))]
    
    vehicles = []
    for tid, group in active_now.groupby('trip_id'):
        group = group.sort_values('seconds')
        before, after = group[group['seconds'] <= sec].tail(1), group[group['seconds'] >= sec].head(1)
        if not before.empty and not after.empty and before.index[0] != after.index[0]:
            r_a, r_b = before.iloc[0], after.iloc[0]
            frac = (sec - r_a['seconds']) / (r_b['seconds'] - r_a['seconds'])
            vehicles.append({
                'id': str(tid), 'lat': r_a['stop_lat'] + (r_b['stop_lat'] - r_a['stop_lat']) * frac,
                'lon': r_a['stop_lon'] + (r_b['stop_lon'] - r_a['stop_lon']) * frac,
                'line': str(r_a['route_short_name']), 'type': int(r_a['route_type'])
            })
    return jsonify(vehicles)

# ... (Restliche Routen wie stop_schedule und vehicle_details nutzen auch get_data())
# Damit es kurz bleibt, hier nur die Anpassung für diese Routen:
# In jeder Route am Anfang: df_main, df_stops_display, calendar, cal_dates, df_stimes, df_trips, df_routes, df_all_stops = get_data()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)