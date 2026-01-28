# src/collectors/aqi_collector.py
import requests
import logging
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class AQICollector:
    """Collects AQI data from various sources"""

    def __init__(self, api_key: str, source: str, url: str, location: list):
        self.api_key = api_key
        self.source = source
        self.url = url
        self.location = location

    def fetch_aqi(self) -> Optional[Dict]:
        """
        Fetch current AQI data for the location
        Returns dict with aqi, components, and timestamp
        """
        try:
            if self.source == "openweather":
                return self._fetch_from_openweather(self.location)
            else:
                logger.error(f"Unknown source: {self.source}")
                return None
        except Exception as e:
            logger.error(f"Error fetching AQI data: {e}")
            raise

    def _fetch_from_openweather(self, location) -> Optional[List]:
        """Fetch from OpenWeatherMap Air Pollution API"""
        aqi_data = []
        if location:
            for loc_dict in location:
                logger.info(f"Fetching AQI data for location: {loc_dict} from openweather")
                lat = loc_dict.get("latitude")
                lon = loc_dict.get("longitude")
                try:
                    url = self.url
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

                        aqi_data.append({
                            "aqi": aqi_value,
                            "aqi_scale": aqi_scale,
                            "components": pollution_data.get("components", {}),
                            "timestamp": datetime.fromtimestamp(pollution_data["dt"]),
                            "location": loc_dict,
                            "source": "openweather"
                        })
                        logger.info(f"Successfully fetched AQI data for location: {loc_dict} from openweather")

                except Exception as e:
                    logger.error(f"Error fetching AQI data from openweather "
                                 f"for co-ordinates: {loc_dict}. ERROR: {e}")
        return aqi_data

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
