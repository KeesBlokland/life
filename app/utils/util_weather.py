"""
util_weather.py - Weather data fetching for Life app
Version: 1.0.01
Purpose: OpenWeatherMap API integration with caching for Elten, DE weather
Created: 2025-06-16
"""

import requests
import json
import os
from datetime import datetime, timedelta
from flask import current_app

def get_weather_data():
    """Get weather data with caching - updates only during active hours"""
    try:
        # Check if we should update (only 06:00-18:00)
        current_hour = datetime.now().hour
        if not (6 <= current_hour <= 18):
            return get_cached_weather()
        
        # Check cache age
        cache_path = os.path.join(current_app.config['DATA_DIR'], 'weather_cache.json')
        
        if os.path.exists(cache_path):
            cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
            if cache_age < timedelta(hours=1):  # Use cache if less than 1 hour old
                return get_cached_weather()
        
        # Fetch fresh data
        return fetch_fresh_weather()
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Weather fetch error: {str(e)}")
        return None

def fetch_fresh_weather():
    """Fetch fresh weather data from OpenWeatherMap"""
    try:
        api_key = current_app.config.get('OPENWEATHER_API_KEY')
        city_id = current_app.config.get('WEATHER_CITY_ID', '2930665')  # Elten, DE
        
        if not api_key:
            if current_app.config['DEBUG']:
                current_app.logger.debug("No OpenWeatherMap API key configured")
            return None
        
        # Current weather + 5-day forecast (includes 3-hour intervals)
        url = f"https://api.openweathermap.org/data/2.5/forecast?id={city_id}&appid={api_key}&units=metric"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Process and cache the data
        weather_info = process_weather_data(data)
        cache_weather_data(weather_info)
        
        if current_app.config['DEBUG']:
            current_app.logger.debug("Fresh weather data fetched and cached")
        
        return weather_info
        
    except requests.exceptions.RequestException as e:
        if current_app:
            current_app.logger.error(f"Weather API request failed: {str(e)}")
        return get_cached_weather()
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Weather processing error: {str(e)}")
        return None

def process_weather_data(api_data):
    """Process OpenWeatherMap API response into our format"""
    try:
        current_time = datetime.now()
        
        # Get current conditions (first forecast entry)
        current = api_data['list'][0]
        
        # Get next 6 hours of forecasts (2 more 3-hour intervals)
        forecast = []
        for item in api_data['list'][1:3]:  # Next 6 hours
            forecast_time = datetime.fromtimestamp(item['dt'])
            
            forecast.append({
                'time': forecast_time.strftime('%H:%M'),
                'temp': round(item['main']['temp']),
                'description': item['weather'][0]['description'].title(),
                'wind_speed': round(item['wind']['speed'] * 3.6),  # Convert m/s to km/h
                'wind_direction': get_wind_direction(item['wind'].get('deg', 0)),
                'rain': get_rain_info(item)
            })
        
        weather_info = {
            'location': api_data['city']['name'],
            'current': {
                'temp': round(current['main']['temp']),
                'description': current['weather'][0]['description'].title(),
                'wind_speed': round(current['wind']['speed'] * 3.6),
                'wind_direction': get_wind_direction(current['wind'].get('deg', 0)),
                'rain': get_rain_info(current)
            },
            'forecast': forecast,
            'updated': current_time.strftime('%H:%M')
        }
        
        return weather_info
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Weather data processing error: {str(e)}")
        return None

def get_wind_direction(degrees):
    """Convert wind degrees to compass direction"""
    if degrees is None:
        return "N"
    
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(degrees / 45) % 8
    return directions[index]

def get_rain_info(weather_item):
    """Extract rain information from weather item"""
    if 'rain' in weather_item and '3h' in weather_item['rain']:
        rain_mm = weather_item['rain']['3h']
        if rain_mm > 0.1:
            return f"{rain_mm:.1f}mm"
    return "No rain"

def cache_weather_data(weather_data):
    """Save weather data to cache file"""
    try:
        cache_path = os.path.join(current_app.config['DATA_DIR'], 'weather_cache.json')
        
        with open(cache_path, 'w') as f:
            json.dump(weather_data, f)
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Weather data cached to {cache_path}")
            
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to cache weather data: {str(e)}")

def get_cached_weather():
    """Load weather data from cache"""
    try:
        cache_path = os.path.join(current_app.config['DATA_DIR'], 'weather_cache.json')
        
        if not os.path.exists(cache_path):
            return None
        
        with open(cache_path, 'r') as f:
            data = json.load(f)
        
        # Add cache age info
        cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
        hours_old = int(cache_age.total_seconds() / 3600)
        
        if hours_old > 0:
            data['cache_note'] = f"Updated {hours_old}h ago"
        
        return data
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to load cached weather: {str(e)}")
        return None

def is_weather_update_time():
    """Check if it's time to update weather (06:00-18:00)"""
    current_hour = datetime.now().hour
    return 6 <= current_hour <= 18