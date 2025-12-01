# src/collectors/aqi_collector.py
import requests
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AQICollector:
    """Collects AQI data from various sources"""

    def __init__(self, api_key: str, source: str = "openweather"):
        self.api_key = api_key
        self.source = source

    def fetch_aqi(self, location) -> Optional[Dict]:
        """
        Fetch current AQI data for the location
        Returns dict with aqi, components, and timestamp
        """
        try:
            if self.source == "openweather":
                return self._fetch_from_openweather(**location("openweather"))
            elif self.source == "iqair":
                return self._fetch_from_iqair(**location("iqair"))
            else:
                logger.error(f"Unknown source: {self.source}")
                return None
        except Exception as e:
            logger.error(f"Error fetching AQI data: {e}")
            raise

    def _fetch_from_openweather(self, lat=12.9716, lon=77.5946) -> Optional[Dict]:
        """Fetch from OpenWeatherMap Air Pollution API"""
        try:
            url = f"http://api.openweathermap.org/data/2.5/air_pollution"
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "list" in data and len(data["list"]) > 0:
                pollution_data = data["list"][0]

                # OpenWeather uses 1-5 scale, convert to standard AQI
                aqi_scale = pollution_data["main"]["aqi"]
                aqi_value = self._convert_openweather_to_aqi(aqi_scale)

                return {
                    "aqi": aqi_value,
                    "aqi_scale": aqi_scale,
                    "components": pollution_data.get("components", {}),
                    "timestamp": datetime.fromtimestamp(pollution_data["dt"]),
                    "location": "Bangalore",
                    "source": "openweather"
                }

            return None
        except Exception as e:
            logger.error(f"Error fetching AQI data from OpenWeather: {e}")
            raise

    def _fetch_from_iqair(self, city="Bangalore", state="Karnataka") -> Optional[Dict]:
        """Fetch from IQAir API"""
        try:
            url = "http://api.airvisual.com/v2/city"
            params = {
                "city": city,
                "state": state,
                "country": "India",
                "key": self.api_key
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data["status"] == "success":
                pollution = data["data"]["current"]["pollution"]

                return {
                    "aqi": pollution["aqius"],  # US AQI standard
                    "main_pollutant": pollution["mainus"],
                    "timestamp": datetime.fromisoformat(pollution["ts"].replace("Z", "+00:00")),
                    "location": "Bangalore",
                    "source": "iqair"
                }

            return None
        except Exception as e:
            logger.error(f"Error fetching AQI data from IQAir: {e}")
            raise

    @staticmethod
    def _convert_openweather_to_aqi(scale: int) -> int:
        """
        Convert OpenWeather's 1-5 scale to approximate US AQI
        1 = Good (0-50)
        2 = Fair (51-100)
        3 = Moderate (101-150)
        4 = Poor (151-200)
        5 = Very Poor (201-300)
        """
        conversion = {
            1: 25,  # Good
            2: 75,  # Fair
            3: 125,  # Moderate
            4: 175,  # Poor
            5: 250  # Very Poor
        }
        return conversion.get(scale, 0)

    @staticmethod
    def get_aqi_category(aqi: int) -> str:
        """Get AQI category from value"""
        if aqi <= 50:
            return "Good"
        elif aqi <= 100:
            return "Moderate"
        elif aqi <= 150:
            return "Unhealthy for Sensitive Groups"
        elif aqi <= 200:
            return "Unhealthy"
        elif aqi <= 300:
            return "Very Unhealthy"
        else:
            return "Hazardous"

    @staticmethod
    def get_aqi_color(aqi: int) -> str:
        """Get color code for AQI value"""
        if aqi <= 50:
            return "Green"
        elif aqi <= 100:
            return "Yellow"
        elif aqi <= 150:
            return "Orange"
        elif aqi <= 200:
            return "Red"
        elif aqi <= 300:
            return "Purple"
        else:
            return "Maroon"
