from flask_login import current_user
import requests
from datetime import datetime, timedelta, date as dt
from flask import session

# Weather API Call Workings
def get_weather(c:str,cn:str):
    print(f"COUNTRY: {cn}")
    latitude, longitude = 40.7128, -74.0060
    url_geo = "https://geocoding-api.open-meteo.com/v1/search"
    param = {
        "name": c,
    }

    try:
        response = requests.get(url_geo, params=param, timeout=5)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
    except Exception as e:
        print("Geo API error:", e)
        latitude, longitude = 40.7128, -74.0060
        results = []
         
    for res in results:
        if c.lower() in res["name"].lower() and res["country"].lower() == cn.lower():
                print("HERE")
                selected_city = res
                latitude = selected_city["latitude"]
                longitude = selected_city["longitude"]
                break
    
    today = dt.today().strftime('%Y-%m-%d')

    # API endpoint
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "rain",
            "snowfall",
            "uv_index",
            "relative_humidity_2m",
            "wind_speed_10m"
        ]),
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto"
    }

    # Make the request
    response = requests.get(url, params=params)
    data = response.json()

    # Extract current weather
    current = data.get("current", {})
    daily = data.get("daily", {})

    weather_data = {}

    weather_data['temp'] = current.get('temperature_2m', None)
    weather_data['feels_like'] = current.get('apparent_temperature', None)
    weather_data['rain'] = current.get('rain', None)
    weather_data['snow'] = current.get('snowfall', None)
    weather_data['uv'] = current.get('uv_index', None)
    weather_data['humidity'] = current.get('relative_humidity_2m', None)
    weather_data['wind_speed'] = current.get('wind_speed_10m', None)

    # Extract only today's max/min
    if "time" in daily and today in daily["time"]:
        index = daily["time"].index(today)
        weather_data['max_temp'] = daily['temperature_2m_max'][index]
        weather_data['min_temp'] = daily['temperature_2m_min'][index]
    else:
        weather_data['max_temp'], weather_data['min_temp'] = None,None
    
    return weather_data

def update_weather_if_needed(user_data):
    last_fetch_str = session.get("weather_last_fetched", "")
    now = datetime.now()

    if last_fetch_str:
        try:
            last_fetch = datetime.fromisoformat(last_fetch_str)
            if now - last_fetch < timedelta(minutes=30):  # only if <30 mins passed
                print("OLD")
                return session.get("weather_data", {})
        except:
            pass

    weather_data = get_weather(user_data['city'], user_data['country'])
    session["weather_data"] = weather_data
    session["weather_last_fetched"] = now.isoformat()
    print("NEW")
    return weather_data


def is_admin():
    try:
        admin = current_user.is_authenticated and current_user.role == "admin"
    except:
        admin = False
    return admin
