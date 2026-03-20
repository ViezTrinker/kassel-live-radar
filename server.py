from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

data_bundle = None

def load_gtfs_lazy():
    global data_bundle
    if data_bundle is not None: return data_bundle
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        def p(f): return os.path.join(base_path, f)
        
        stops = pd.read_csv(p('stops.txt'), dtype=str)[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']]
        stops['stop_lat'] = pd.to_numeric(stops['stop_lat'])
        stops['stop_lon'] = pd.to_numeric(stops['stop_lon'])
        
        stops_display = stops.groupby('stop_name').agg({'stop_lat': 'mean', 'stop_lon': 'mean'}).reset_index()
        routes = pd.read_csv(p('routes.txt'), dtype=str)[['route_id', 'route_short_name', 'route_type']]
        trips = pd.read_csv(p('trips.txt'), dtype=str)[['trip_id', 'route_id', 'service_id', 'trip_headsign']]
        stimes = pd.read_csv(p('stop_times.txt'), dtype=str)[['trip_id', 'departure_time', 'stop_id']]
        calendar = pd.read_csv(p('calendar.txt'), dtype=str)
        cal_dates = pd.read_csv(p('calendar_dates.txt'), dtype=str) if os.path.exists(p('calendar_dates.txt')) else pd.DataFrame()

        df_live = stimes.merge(stops, on='stop_id').merge(trips, on='trip_id').merge(routes, on='route_id')
        df_live['seconds'] = df_live['departure_time'].apply(lambda x: int(x.split(':')[0])*3600 + int(x.split(':')[1])*60 + int(x.split(':')[2]))
        
        data_bundle = (df_live, stops_display, calendar, cal_dates, stimes, trips, routes, stops)
        return data_bundle
    except Exception as e:
        return None

def get_active_services(calendar, cal_dates, v_date_str):
    target_dt = datetime.strptime(v_date_str, "%Y%m%d")
    day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][target_dt.weekday()]
    active = calendar[calendar[day_name] == '1']['service_id'].tolist()
    if not cal_dates.empty:
        ex = cal_dates[cal_dates['date'] == v_date_str]
        active = [s for s in active if s not in ex[ex['exception_type'] == '2']['service_id'].tolist()] + ex[ex['exception_type'] == '1']['service_id'].tolist()
    return active

@app.route('/')
def index(): return app.send_static_file('index.html')

@app.route('/stops')
def get_stops():
    data = load_gtfs_lazy()
    return jsonify(data[1].to_dict(orient='records') if data else [])

@app.route('/stop_schedule/<stop_name>')
def get_stop_schedule(stop_name):
    data = load_gtfs_lazy()
    df_live, _, _, _, _, _, _, _ = data
    v_time = request.args.get('time', datetime.now().strftime("%H:%M:%S"))
    h, m, s = map(int, v_time.split(':')); sec = h * 3600 + m * 60 + s
    
    sched = df_live[df_live['stop_name'] == stop_name]
    sched = sched[(sched['seconds'] >= sec) & (sched['seconds'] <= sec + 3600)]
    return jsonify(sched.sort_values('seconds').head(10)[['departure_time', 'route_short_name', 'trip_headsign']].to_dict(orient='records'))

@app.route('/vehicles')
def get_vehicles():
    data = load_gtfs_lazy()
    if not data: return jsonify([])
    df_live, _, calendar, cal_dates, _, _, _, _ = data
    v_time = request.args.get('time', datetime.now().strftime("%H:%M:%S"))
    v_date = request.args.get('date', datetime.now().strftime("%Y%m%d"))
    h, m, s = map(int, v_time.split(':')); sec = h * 3600 + m * 60 + s
    active_services = get_active_services(calendar, cal_dates, v_date)
    active_now = df_live[(df_live['seconds'] >= sec - 600) & (df_live['seconds'] <= sec + 600) & (df_live['service_id'].isin(active_services))]
    
    vehicles = []
    for tid, group in active_now.groupby('trip_id'):
        group = group.sort_values('seconds')
        before, after = group[group['seconds'] <= sec].tail(1), group[group['seconds'] >= sec].head(1)
        if not before.empty and not after.empty and before.index[0] != after.index[0]:
            b, a = before.iloc[0], after.iloc[0]
            frac = (sec - b['seconds']) / (a['seconds'] - b['seconds'])
            vehicles.append({'id': str(tid), 'lat': b['stop_lat'] + (a['stop_lat'] - b['stop_lat']) * frac, 'lon': b['stop_lon'] + (a['stop_lon'] - b['stop_lon']) * frac, 'line': str(b['route_short_name']), 'type': int(b['route_type'])})
    return jsonify(vehicles)

@app.route('/vehicle_details/<trip_id>')
def get_details(trip_id):
    data = load_gtfs_lazy()
    df_stimes, df_stops = data[4], data[7]
    v_time = request.args.get('time', "12:00:00")
    h, m, s = map(int, v_time.split(':')); sec = h * 3600 + m * 60 + s
    trip = df_stimes[df_stimes['trip_id'] == trip_id].merge(df_stops, on='stop_id')
    trip['sec'] = trip['departure_time'].apply(lambda x: int(x.split(':')[0])*3600 + int(x.split(':')[1])*60 + int(x.split(':')[2]))
    trip = trip.sort_values('sec')
    return jsonify({'destination': trip.iloc[-1]['stop_name'], 'full_route': trip[['stop_lat', 'stop_lon']].values.tolist(), 'previous': trip[trip['sec'] < sec].tail(3)[['departure_time', 'stop_name']].to_dict(orient='records'), 'next': trip[trip['sec'] >= sec].head(5)[['departure_time', 'stop_name']].to_dict(orient='records')})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
