import argparse
import sys
import logging

from src.utils import load_config, setup_logging, get_env_variable, validate_email, get_aqi_category, get_aqi_color
from src.collectors.aqi_collector import AQICollector
from src.storage.db_manager import DatabaseManager


class CLIContext:
    """Shared context for CLI commands"""

    def __init__(self, source: str):
        self.config = load_config()
        setup_logging(self.config)

        self.db = DatabaseManager(self.config['database']['url'])

        api_key = get_env_variable('AQI_API_KEY')
        url = self.config['aqi']['source'][source]['url']
        location = self.config['aqi']['source'][source]['location']
        self.collector = AQICollector(api_key, source=source, url=url, location=location)
        self.location = location
        self.logger = logging.getLogger(__name__)

    def cleanup(self):
        """Clean up resources"""
        if self.db:
            self.db.close()


def cmd_status(ctx: CLIContext, args):
    """Show current AQI status"""
    ctx.logger.info("Fetching current AQI...\n")

    aqi_data = ctx.collector.fetch_aqi()

    if aqi_data:
        for aqi in aqi_data:
            category = get_aqi_category(aqi['aqi'])
            color = get_aqi_color(aqi['aqi'])

            ctx.logger.info(f"AQI: {aqi['aqi']}")
            ctx.logger.info(f"Category: {category} ({color})")
            ctx.logger.info(f"Timestamp: {aqi['timestamp']}")
            ctx.logger.info(f"Source: {aqi['source']}")

            if 'components' in aqi and aqi['components']:
                for key, value in aqi['components'].items():
                    ctx.logger.info(f"{key.upper()}: {value}")
    else:
        ctx.logger.info("Failed to fetch AQI data")


def cmd_collect(ctx: CLIContext, args):
    """Manually collect and store AQI data"""
    ctx.logger.info("Collecting AQI data...")

    aqi_data = ctx.collector.fetch_aqi()

    if aqi_data:
        # Handle list of readings
        readings = aqi_data if isinstance(aqi_data, list) else [aqi_data]

        for reading in readings:
            reading['category'] = get_aqi_category(reading['aqi'])
            reading['color'] = get_aqi_color(reading['aqi'])

            if ctx.db.save_aqi_reading(reading):
                ctx.logger.info(f"Successfully stored AQI reading: {reading['aqi']}")
            else:
                ctx.logger.info("Failed to store AQI reading")
    else:
        ctx.logger.info("Failed to fetch AQI data")


def cmd_history(ctx: CLIContext, args):
    """Show AQI history"""
    days = args.days
    ctx.logger.info(f"AQI History (Last {days} days)")

    readings = ctx.db.get_readings_last_n_days(days)

    if readings:
        ctx.logger.info(f"{'Date':<20} {'AQI':<10} {'Category':<30}")
        ctx.logger.info("-" * 60)
        for reading in readings:
            ctx.logger.info(
                f"{reading.timestamp.strftime('%Y-%m-%d %H:%M'):<20} {reading.aqi:<10} {reading.category:<30}")

        # Show statistics
        avg_aqi = sum(r.aqi for r in readings) / len(readings)
        max_aqi = max(r.aqi for r in readings)
        min_aqi = min(r.aqi for r in readings)

        ctx.logger.info("\n" + "=" * 60)
        ctx.logger.info(f"Average AQI: {avg_aqi:.1f}")
        ctx.logger.info(f"Highest AQI: {max_aqi}")
        ctx.logger.info(f"Lowest AQI: {min_aqi}")
    else:
        ctx.logger.info("No data available for the specified period")


def cmd_add_subscriber(ctx: CLIContext, args):
    """Add a new subscriber"""
    email = args.email
    threshold = args.threshold

    if not validate_email(email):
        ctx.logger.info(f"Invalid email address: {email}")
        return

    ctx.logger.info(f"Adding subscriber: {email}")
    ctx.logger.info(f"Alert threshold: {threshold}")

    if ctx.db.add_subscriber(email, threshold):
        ctx.logger.info("Subscriber added successfully!")
    else:
        ctx.logger.info("Failed to add subscriber (may already exist)")


def cmd_list_subscribers(ctx: CLIContext, args):
    """List all subscribers"""
    ctx.logger.info("Active Subscribers")

    subscribers = ctx.db.get_active_subscribers()

    if subscribers:
        ctx.logger.info(f"{'Email':<35} {'Threshold':<15} {'Last Alert':<20}")
        ctx.logger.info("-" * 70)
        for sub in subscribers:
            last_alert = sub.last_alert_sent.strftime('%Y-%m-%d %H:%M') if sub.last_alert_sent else "Never"
            ctx.logger.info(f"{sub.email:<35} {sub.alert_threshold:<15} {last_alert:<20}")

        ctx.logger.info(f"Total subscribers: {len(subscribers)}")
    else:
        ctx.logger.info("No active subscribers")


def cmd_stats(ctx: CLIContext, args):
    """Show database statistics"""
    ctx.logger.info("Engine Statistics")

    stats = ctx.db.get_statistics()

    ctx.logger.info(f"Total Readings: {stats.get('total_readings', 0)}")
    ctx.logger.info(f"Active Subscribers: {stats.get('total_subscribers', 0)}")

    if stats.get('latest_aqi'):
        ctx.logger.info(f"\nLatest Reading:")
        ctx.logger.info(f"  AQI: {stats['latest_aqi']}")
        ctx.logger.info(f"  Time: {stats['latest_timestamp']}")


def main():
    parser = argparse.ArgumentParser(
        description="India AQI Alert Engine - Command Line Interface"
    )

    # Global argument - applies to all subcommands
    parser.add_argument(
        '--source',
        type=str,
        default='openweather',
        help='AQI collector source application (default: openweather)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Status command
    subparsers.add_parser('status', help='Show current AQI status')

    # Collect command
    subparsers.add_parser('collect', help='Manually collect and store AQI data')

    # History command
    history_parser = subparsers.add_parser('history', help='Show AQI history')
    history_parser.add_argument('--days', type=int, default=7, help='Number of days (default: 7)')

    # Add subscriber command
    add_sub_parser = subparsers.add_parser('add-subscriber', help='Add a new subscriber')
    add_sub_parser.add_argument('email', help='Email address')
    add_sub_parser.add_argument('--threshold', type=int, default=100, help='Alert threshold (default: 100)')

    # List subscribers command
    subparsers.add_parser('list-subscribers', help='List all active subscribers')

    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to appropriate command handler
    commands = {
        'status': cmd_status,
        'collect': cmd_collect,
        'history': cmd_history,
        'add-subscriber': cmd_add_subscriber,
        'list-subscribers': cmd_list_subscribers,
        'stats': cmd_stats
    }

    ctx = None
    try:
        # Initialize context once with the source
        ctx = CLIContext(args.source)

        # Execute the command with context
        commands[args.command](ctx, args)

    except Exception as e:
        logging.error(f"Error: {e}")
        logging.error(f"Command failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up resources
        if ctx:
            ctx.cleanup()


if __name__ == '__main__':
    main()
