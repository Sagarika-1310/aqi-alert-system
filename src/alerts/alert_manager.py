# src/alerts/alert_manager.py
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.storage.db_manager import DatabaseManager, Subscriber
from src.utils import get_aqi_category, get_aqi_color, setup_logging


class AlertManager:
    """Manages AQI alerts and threshold checking"""

    def __init__(self, config: dict, db: DatabaseManager):
        self.config = config
        self.db = db
        self.alert_config = config.get('alerts', {})
        self.thresholds = self.alert_config.get('thresholds', [])
        self.cooldown_hours = self.alert_config.get('cooldown_hours', 6)

        setup_logging(self.config)

        # Sort thresholds by level for efficient checking
        self.thresholds.sort(key=lambda x: x['level'])

        logger.info(f"Alert Manager initialized with {len(self.thresholds)} thresholds")

    def check_and_generate_alerts(self, current_aqi: int, aqi_data: dict) -> List[Dict]:
        """
        Check current AQI against thresholds and generate alerts for subscribers
        Returns list of alerts to be sent
        """
        if not self.alert_config.get('enabled', True):
            logger.info("Alerts are disabled in configuration")
            return []

        alerts_to_send = []

        # Get all active subscribers
        subscribers = self.db.get_active_subscribers()

        if not subscribers:
            logger.info("No active subscribers to send alerts to")
            return []

        for subscriber in subscribers:
            alert = self._check_subscriber_alert(subscriber, current_aqi, aqi_data)
            if alert:
                alerts_to_send.append(alert)

        logger.info(f"Generated {len(alerts_to_send)} alerts for current AQI: {current_aqi}")
        return alerts_to_send

    def _check_subscriber_alert(self, subscriber: Subscriber, current_aqi: int, aqi_data: dict) -> Optional[Dict]:
        """Check if a specific subscriber should receive an alert"""

        # Check if AQI exceeds subscriber's threshold
        if current_aqi < subscriber.alert_threshold:
            return None

        # Check cooldown period
        if not self._is_cooldown_expired(subscriber):
            logger.debug(f"Cooldown active for subscriber {subscriber.email}")
            return None

        # Find the appropriate threshold message
        threshold_info = self._get_threshold_info(current_aqi)

        # Create alert
        alert = {
            'subscriber_id': subscriber.id,
            'email': subscriber.email,
            'telegram_id': subscriber.telegram_id,
            'aqi': current_aqi,
            'category': aqi_data.get('category', 'Unknown'),
            'color': aqi_data.get('color', 'Unknown'),
            'timestamp': aqi_data.get('timestamp', datetime.now()),
            'threshold_level': threshold_info['level'],
            'threshold_category': threshold_info['category'],
            'message': threshold_info['message'],
            'health_recommendation': self._get_health_recommendation(current_aqi),
            'location': aqi_data.get('location', 'Bangalore')
        }

        return alert

    def _is_cooldown_expired(self, subscriber: Subscriber) -> bool:
        """Check if cooldown period has expired for a subscriber"""
        if not subscriber.last_alert_sent:
            return True

        cooldown_delta = timedelta(hours=self.cooldown_hours)
        time_since_last = datetime.utcnow() - subscriber.last_alert_sent

        return time_since_last >= cooldown_delta

    def _get_threshold_info(self, aqi: int) -> Dict:
        """Get threshold information for given AQI value"""
        # Find the highest threshold that applies
        applicable_threshold = None

        for threshold in self.thresholds:
            if aqi >= threshold['level']:
                applicable_threshold = threshold
            else:
                break

        if applicable_threshold:
            return applicable_threshold

        # Default threshold info if none configured
        return {
            'level': 100,
            'category': 'Moderate',
            'message': 'Air quality is degrading. Consider limiting outdoor activities.'
        }

    @staticmethod
    def _get_health_recommendation(aqi: int) -> str:
        """Get health recommendations based on AQI level"""
        if aqi <= 50:
            return "Air quality is good. Enjoy outdoor activities! 🌞"
        elif aqi <= 100:
            return "Air quality is acceptable. Unusually sensitive people should consider limiting prolonged outdoor exertion."
        elif aqi <= 150:
            return "🟠 Sensitive groups (children, elderly, people with respiratory conditions) should reduce prolonged outdoor activities."
        elif aqi <= 200:
            return "🔴 Everyone should limit prolonged outdoor exertion. Keep windows closed and use air purifiers if available."
        elif aqi <= 300:
            return "🟣 Avoid all outdoor activities. Keep windows closed. Use air purifiers. Wear N95 masks if you must go outside."
        else:
            return "🟤 HAZARDOUS! Remain indoors. Close all windows. Use air purifiers. Avoid all outdoor exposure. Health emergency conditions."

    def get_alert_statistics(self) -> Dict:
        """Get statistics about alerts sent"""
        subscribers = self.db.get_active_subscribers()

        total_subscribers = len(subscribers)
        subscribers_with_alerts = sum(1 for s in subscribers if s.last_alert_sent is not None)

        # Get recent alerts count (last 24 hours)
        recent_threshold = datetime.utcnow() - timedelta(hours=24)
        recent_alerts = sum(1 for s in subscribers
                            if s.last_alert_sent and s.last_alert_sent >= recent_threshold)

        return {
            'total_subscribers': total_subscribers,
            'subscribers_with_alerts': subscribers_with_alerts,
            'alerts_last_24h': recent_alerts,
            'configured_thresholds': len(self.thresholds),
            'cooldown_hours': self.cooldown_hours
        }

    def test_alert_for_subscriber(self, email: str, test_aqi: int = 200) -> Optional[Dict]:
        """
        Test alert generation for a specific subscriber
        Useful for debugging and verification
        """
        subscribers = [s for s in self.db.get_active_subscribers() if s.email == email]

        if not subscribers:
            logger.error(f"Subscriber not found: {email}")
            return None

        subscriber = subscribers[0]

        test_data = {
            'aqi': test_aqi,
            'category': get_aqi_category(test_aqi),
            'color': get_aqi_color(test_aqi),
            'timestamp': datetime.now(),
            'location': 'Bangalore'
        }

        # Temporarily bypass cooldown for testing
        original_last_alert = subscriber.last_alert_sent
        subscriber.last_alert_sent = None

        alert = self._check_subscriber_alert(subscriber, test_aqi, test_data)

        # Restore original last alert time
        subscriber.last_alert_sent = original_last_alert

        return alert
