# src/utils.py
import yaml
import logging
from pathlib import Path
from typing import Dict
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_config(config_path: str = "config/config.yaml") -> Dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML configuration: {e}")


def setup_logging(config: Dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})

    # Create logs directory if it doesn't exist
    log_file = log_config.get('file', 'logs/aqi_engine.log')
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_config.get('level', 'INFO')),
        format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )

    # Set up rotating file handler if size limits specified
    if 'max_bytes' in log_config:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            log_file,
            maxBytes=log_config.get('max_bytes', 10485760),
            backupCount=log_config.get('backup_count', 5)
        )
        handler.setFormatter(logging.Formatter(log_config.get('format')))
        logging.getLogger().addHandler(handler)


def get_env_variable(key: str, default: str = None) -> str:
    """Get environment variable with optional default"""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value


def format_aqi_message(aqi: int, category: str, color: str, timestamp) -> str:
    """Format AQI data into a readable message"""
    return f"""
🌍 Bangalore Air Quality Update

AQI: {aqi} ({category})
Status: {color}
Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

"""


def get_health_recommendation(aqi: int) -> str:
    """Get health recommendations based on AQI level"""
    if aqi <= 50:
        return "Air quality is good. Great day for outdoor activities! 🌞"
    elif aqi <= 100:
        return "Air quality is acceptable. Sensitive individuals should consider limiting prolonged outdoor exertion."
    elif aqi <= 150:
        return "Sensitive groups should reduce prolonged outdoor activities. Everyone else can continue normal activities with awareness."
    elif aqi <= 200:
        return "Everyone should limit prolonged outdoor exertion. Keep windows closed and use air purifiers if available."
    elif aqi <= 300:
        return "Avoid all outdoor activities. Keep windows closed and use air purifiers. Wear N95 masks if going outside is necessary."
    else:
        return "HAZARDOUS! Stay indoors. Close all windows and use air purifiers. Avoid all outdoor exposure."


def validate_email(email: str) -> bool:
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def create_data_directories():
    """Create necessary data directories if they don't exist"""
    directories = ['data', 'logs', 'config']
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


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
