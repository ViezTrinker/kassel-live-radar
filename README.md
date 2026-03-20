# Kassel Live Transit Radar 🛰️🚌

A real-time transit visualization dashboard for Kassel, Germany. This application interpolates GTFS schedule data to simulate live vehicle positions on a high-performance interactive map.

**🌍 Live Demo:** [https://kassel-live-radar.onrender.com/](https://kassel-live-radar.onrender.com/)

![Project Preview](kassel_live_radar.png)

## 🌟 Features

- **Live Vehicle Tracking:** Trams and buses move in real-time based on GTFS stop-time interpolation.
- **Route Visualization:** Click on any vehicle to see its full intended path, including the last 5 and next 5 stops with arrival times.
- **Stop Schedules:** Click on any station to see a live departure board for the next 60 minutes.
- **Smart Search:** Quickly find and zoom to any transit stop in the network.
- **Modern UI:** Clean "Google Maps" style interface with a discrete system clock for synchronization.

## 🛠️ Tech Stack

- **Backend:** Python (Flask, Pandas)
- **Frontend:** JavaScript (Leaflet.js)
- **Deployment:** Render.com (Gunicorn WSGI)
- **Data Format:** GTFS (General Transit Feed Specification)