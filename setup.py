# # Setup script
# import os
#
#
# def create_project_structure():
#     dirs = [
#         'config',
#         'data',
#         'logs',
#         'src/collectors',
#         'src/storage',
#         'src/alerts',
#         'src/notifiers',
#         'src/reports',
#         'tests'
#     ]
#
#     for dir in dirs:
#         os.makedirs(dir, exist_ok=True)
#         if dir.startswith('src/'):
#             open(f'{dir}/__init__.py', 'a').close()
#
#     # Create placeholder files
#     open('data/.gitkeep', 'a').close()
#     open('logs/.gitkeep', 'a').close()
#
#     print("Project structure created successfully!")
#
#
# if __name__ == '__main__':
#     create_project_structure()

import requests

"""Fetch from OpenWeatherMap Air Pollution API"""
# Bangalore coordinates
lat, lon = 12.9716, 77.5946

url = f"http://api.openweathermap.org/data/2.5/air_pollution"
params = {
    "lat": lat,
    "lon": lon,
    "appid": "663e47d987f9c47db1dfcd5ecc8ba0c0"
}

response = requests.get(url, params=params, timeout=10)
response.raise_for_status()

data = response.json()

print(data)

if "list" in data and len(data["list"]) > 0:
    pollution_data = data["list"][0]

