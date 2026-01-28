# src/scheduler.py
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import signal
import sys

from datashader.composite import source
from docutils.nodes import option

from src.utils import load_config, setup_logging, get_env_variable, get_aqi_category, get_aqi_color
from src.collectors.aqi_collector import AQICollector
from src.storage.db_manager import DatabaseManager
from src.alerts.alert_manager import AlertManager
from src.notifiers.email_notifier import EmailNotifier

logger = logging.getLogger(__name__)


class AQIEngine:
    """Main AQI Alert Engine - orchestrates all components"""

    def __init__(self, aqi_source: str, config_path: str = "config/config.yaml"):
        logger.info("Initializing AQI Alert Engine...")

        # Load configuration
        self.config = load_config(config_path)
        setup_logging(self.config)

        self.source = aqi_source

        # Initialize components
        self._init_components()

        # Initialize scheduler
        self.scheduler = BlockingScheduler()
        self._setup_jobs()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        logger.info("AQI Alert Engine initialized successfully")

    def _init_components(self):
        """Initialize all engine components"""
        # Database
        db_url = self.config['database']['url']
        self.db = DatabaseManager(db_url)
        logger.info(f"Database initialized: {db_url}")

        # AQI Collector
        api_key = get_env_variable('AQI_API_KEY')
        url = self.config['aqi']['source'][self.source]['url']
        location = self.config['aqi']['source'][self.source]['location']
        self.collector = AQICollector(api_key, self.source, url, location)
        logger.info(f"AQI Collector initialized (source: {source})")

        # Alert Manager
        self.alert_manager = AlertManager(self.config, self.db)
        logger.info("Alert Manager initialized")

        # Email Notifier
        try:
            smtp_user = get_env_variable('SMTP_USERNAME')
            smtp_pass = get_env_variable('SMTP_PASSWORD')
            self.email_notifier = EmailNotifier(self.config, smtp_user, smtp_pass)
            logger.info("Email Notifier initialized")
        except ValueError as e:
            logger.warning(f"Email Notifier not initialized: {e}")
            self.email_notifier = None

    def _setup_jobs(self):
        """Setup scheduled jobs"""
        aqi_config = self.config['aqi']
        interval_seconds = aqi_config.get('check_interval', 3600)

        # Job 1: Collect AQI data periodically
        self.scheduler.add_job(
            func=self.collect_and_process,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id='collect_aqi',
            name='Collect AQI Data',
            replace_existing=True
        )
        logger.info(f"Scheduled AQI collection every {interval_seconds} seconds")

        # Job 2: Daily reports (if enabled)
        if self.config.get('reports', {}).get('enabled', False):
            report_time = self.config['reports'].get('time', '08:00')
            hour, minute = map(int, report_time.split(':'))

            self.scheduler.add_job(
                func=self.generate_daily_report,
                trigger=CronTrigger(hour=hour, minute=minute),
                id='daily_report',
                name='Generate Daily Report',
                replace_existing=True
            )
            logger.info(f"Scheduled daily report at {report_time}")

        # Job 3: Cleanup old data (optional)
        retention_days = self.config.get('general', {}).get('data_retention_days', 90)
        if retention_days:
            self.scheduler.add_job(
                func=self.cleanup_old_data,
                trigger=CronTrigger(hour=2, minute=0),  # Run at 2 AM daily
                id='cleanup_data',
                name='Cleanup Old Data',
                replace_existing=True
            )
            logger.info(f"Scheduled data cleanup (retention: {retention_days} days)")

    def collect_and_process(self):
        """Main job: Collect AQI data, store it, and send alerts if needed"""
        try:
            logger.info("Starting AQI collection and processing...")

            # Fetch AQI data
            aqi_data = self.collector.fetch_aqi()

            if not aqi_data:
                logger.error("Failed to fetch AQI data")
                return

            # Add category and color
            aqi_data['category'] = get_aqi_category(aqi_data['aqi'])
            aqi_data['color'] = get_aqi_color(aqi_data['aqi'])

            logger.info(f"Collected AQI: {aqi_data['aqi']} ({aqi_data['category']})")

            # Store in database
            if not self.db.save_aqi_reading(aqi_data):
                logger.error("Failed to store AQI reading")
                return

            # Check for alerts
            alerts = self.alert_manager.check_and_generate_alerts(
                aqi_data['aqi'],
                aqi_data
            )

            if alerts:
                logger.info(f"Generated {len(alerts)} alerts")
                self._send_alerts(alerts)
            else:
                logger.info("No alerts triggered")

            logger.info("AQI collection and processing completed")

        except Exception as e:
            logger.error(f"Error in collect_and_process: {e}", exc_info=True)

    def _send_alerts(self, alerts: list):
        """Send alerts via all configured channels"""
        # Send email alerts
        if self.email_notifier and self.email_notifier.enabled:
            email_results = self.email_notifier.send_batch_alerts(alerts)
            logger.info(f"Email alerts: {email_results}")

        # Update last alert time for subscribers
        for alert in alerts:
            self.db.update_last_alert_time(alert['subscriber_id'])

    def generate_daily_report(self):
        """Generate and send daily AQI report"""
        try:
            logger.info("Generating daily report...")

            # Get statistics for the report
            latest_reading = self.db.get_latest_reading()
            readings_24h = self.db.get_readings_last_n_days(1)

            if not readings_24h:
                logger.warning("No data available for daily report")
                return

            # Calculate statistics
            aqi_values = [r.aqi for r in readings_24h]
            stats = {
                'current_aqi': latest_reading.aqi if latest_reading else 'N/A',
                'current_category': latest_reading.category if latest_reading else 'N/A',
                'avg_aqi': round(sum(aqi_values) / len(aqi_values), 1),
                'max_aqi': max(aqi_values),
                'min_aqi': min(aqi_values),
                'total_readings': len(readings_24h),
                'health_recommendation': self._get_health_recommendation(
                    latest_reading.aqi if latest_reading else 0
                )
            }

            recent_readings = [
                {
                    'time': r.timestamp.strftime('%I:%M %p'),
                    'aqi': r.aqi,
                    'category': r.category
                }
                for r in readings_24h[-10:]  # Last 10 readings
            ]

            report_data = {
                'date': datetime.now().strftime('%B %d, %Y'),
                'statistics': stats,
                'recent_readings': recent_readings
            }

            # Get subscribers who want reports
            subscribers = self.db.get_active_subscribers()

            if subscribers:
                # Send email reports
                if self.email_notifier and self.email_notifier.enabled:
                    emails = [s.email for s in subscribers]
                    self.email_notifier.send_daily_report(report_data, emails)

                logger.info(f"Daily report sent to {len(subscribers)} subscribers")
            else:
                logger.info("No subscribers for daily report")

        except Exception as e:
            logger.error(f"Error generating daily report: {e}", exc_info=True)

    def cleanup_old_data(self):
        """Cleanup old data based on retention policy"""
        try:
            retention_days = self.config.get('general', {}).get('data_retention_days', 90)
            logger.info(f"Cleaning up data older than {retention_days} days...")

            # This would need to be implemented in db_manager
            # For now, just log
            logger.info("Data cleanup completed")

        except Exception as e:
            logger.error(f"Error during data cleanup: {e}", exc_info=True)

    def _get_health_recommendation(self, aqi: int) -> str:
        """Get health recommendation based on AQI"""
        if aqi <= 50:
            return "Air quality is good. Enjoy outdoor activities!"
        elif aqi <= 100:
            return "Air quality is acceptable."
        elif aqi <= 150:
            return "Sensitive groups should reduce prolonged outdoor exposure."
        elif aqi <= 200:
            return "Everyone should limit prolonged outdoor exertion."
        elif aqi <= 300:
            return "Avoid all outdoor activities. Use air purifiers indoors."
        else:
            return "Hazardous conditions. Stay indoors with air purifiers."

    def start(self):
        """Start the engine"""
        logger.info("=" * 70)
        logger.info("Starting Bangalore AQI Alert Engine")
        logger.info("=" * 70)

        # Run initial collection
        logger.info("Running initial AQI collection...")
        self.collect_and_process()

        # Start scheduler
        logger.info("Starting scheduler...")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutdown signal received")
            self.shutdown()

    def shutdown(self):
        """Gracefully shutdown the engine"""
        logger.info("Shutting down AQI Alert Engine...")

        if self.scheduler.running:
            self.scheduler.shutdown()

        if self.db:
            self.db.close()

        logger.info("AQI Alert Engine stopped")

    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self.shutdown()
        sys.exit(0)


def aqi_source_handler(option):
    match option:
        case 1:
            return "openweather"


def main(option):
    """Main entry point"""
    try:
        engine = AQIEngine(aqi_source_handler(option))
        engine.start()
    except Exception as e:
        logger.critical(f"Failed to start engine: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main(option=option)
