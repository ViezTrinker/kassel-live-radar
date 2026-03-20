from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

# Globaler Speicher für die Daten
data_bundle = None

def load_gtfs_lazy():
    global data_bundle
    if data_bundle is not None:
        return data_bundle
    
    try:
        # Absoluter Pfad für Linux/Render sicherstellen
        base_path = os.path.dirname(os.path.abspath(__file__))
        def p(f): return os.path.join(base_path, f)

        print(f"Lade GTFS-Daten aus: {base_path}")
        
        # Nur notwendige Spalten laden, um RAM zu sparen
        stops = pd.read_csv(p('stops.txt'), dtype=str)[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        stops['stop_lat'] = pd.to_numeric(stops['stop_lat'])
        stops['stop_lon'] = pd.to_numeric(stops['stop_lon'])
        
        stops_display = stops.groupby('stop_name').agg({
            'stop_lat': 'mean', 'stop_lon': 'mean', 'stop_id': 'first'
        }).reset_index()

        routes = pd.read_csv(p('routes.txt'), dtype=str)[['route_id', 'route_short_name', 'route_type']]
        trips = pd.read_csv(p('trips.txt'), dtype=str)[['trip_id', 'route_id', 'service_id', 'trip_headsign']]
        stimes = pd.read_csv(p('stop_times.txt'), dtype=str)[['trip_id', 'departure_time', 'stop_id']]
        calendar = pd.read_csv(p('calendar.txt'), dtype=str)
        
        c_dates_path = p('calendar_dates.txt')
        cal_dates = pd.read_csv(c_dates_path, dtype=str) if os.path.exists(c_dates_path) else pd.DataFrame()

        # Haupt-Merge für die Live-Positionen
        df_live = stimes.merge(stops, on='stop_id').merge(trips, on='trip_id').merge(routes, on='route_id')
        df_live['seconds'] = df_live['departure_time'].apply(lambda x: int(x.split(':')[0])*3600 + int(x.split(':')[1])*60 + int(x.split(':')[2]))
        
        data_bundle = (df_live, stops_display, calendar, cal_dates, stimes, trips, routes, stops)
        print("GTFS erfolgreich initialisiert!")
        return data_bundle
    except Exception as e:
        print(f"Fehler beim Laden: {e}")
        return None

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
    data = load_gtfs_lazy()
    return jsonify(data[1].to_dict(orient='records') if data else [])

@app.route('/vehicles')
def get_vehicles():
    data = load_gtfs_lazy()
    if not data: return jsonify([])
    df_live, _, calendar, cal_dates, _, _, _, _ = data
    sec = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second
    active_services = get_active_services(calendar, cal_dates)
    active_now = df_live[(df_live['seconds'] >= sec - 600) & (df_live['seconds'] <= sec + 600) & (df_live['service_id'].isin(active_services))]
    
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

@app.route('/stop_schedule/<stop_name>')
def get_stop_schedule(stop_name):
    data = load_gtfs_lazy()
    if not data: return jsonify([])
    _, _, calendar, cal_dates, df_stimes, df_trips, df_routes, df_all_stops = data
    now = datetime.now()
    sec = now.hour * 3600 + now.minute * 60 + now.second
    active_services = get_active_services(calendar, cal_dates)
    relevant_ids = df_all_stops[df_all_stops['stop_name'] == stop_name]['stop_id'].tolist()
    schedule = df_stimes[df_stimes['stop_id'].isin(relevant_ids)].copy()
    schedule['sec'] = schedule['departure_time'].apply(lambda x: int(x.split(':')[0])*3600 + int(x.split(':')[1])*60 + int(x.split(':')[2]))
    upcoming = schedule[(schedule['sec'] >= sec) & (schedule['sec'] <= sec + 3600)]
    upcoming = upcoming.merge(df_trips, on='trip_id').merge(df_routes, on='route_id')
    upcoming = upcoming[upcoming['service_id'].isin(active_services)]
    res = upcoming.sort_values('sec').drop_duplicates(subset=['departure_time', 'route_short_name', 'trip_headsign']).head(15)
    return jsonify(res[['departure_time', 'route_short_name', 'trip_headsign']].to_dict(orient='records'))

@app.route('/vehicle_details/<trip_id>')
def get_vehicle_details(trip_id):
    data = load_gtfs_lazy()
    if not data: return jsonify({})
    _, _, _, _, df_stimes, _, _, df_all_stops = data
    sec = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second
    trip_stops = df_stimes[df_stimes['trip_id'] == trip_id].copy()
    trip_stops = trip_stops.merge(df_all_stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']], on='stop_id')
    trip_stops['sec'] = trip_stops['departure_time'].apply(lambda x: int(x.split(':')[0])*3600 + int(x.split(':')[1])*60 + int(x.split(':')[2]))
    trip_stops = trip_stops.sort_values('sec')
    return jsonify({
        'previous': trip_stops[trip_stops['sec'] < sec].tail(5)[['departure_time', 'stop_name']].to_dict(orient='records'),
        'next': trip_stops[trip_stops['sec'] >= sec].head(5)[['departure_time', 'stop_name']].to_dict(orient='records'),
        'destination': trip_stops.iloc[-1]['stop_name'],
        'full_route': trip_stops[['stop_lat', 'stop_lon']].values.tolist()
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
