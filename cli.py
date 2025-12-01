# cli.py
import argparse
import sys
import logging
from datetime import datetime, timedelta

from src.utils import load_config, setup_logging, get_env_variable, validate_email
from src.collectors.aqi_collector import AQICollector
from src.storage.db_manager import DatabaseManager


def init_components():
    """Initialize configuration and components"""
    config = load_config()
    setup_logging(config)

    db = DatabaseManager(config['database']['url'])

    api_key = get_env_variable('AQI_API_KEY')
    collector = AQICollector(api_key, source=config['aqi']['source'])

    return config, db, collector


def cmd_status(args):
    """Show current AQI status"""
    config, db, collector = init_components()

    print("\n🔍 Fetching current AQI for Bangalore...\n")

    aqi_data = collector.fetch_aqi()

    if aqi_data:
        category = collector.get_aqi_category(aqi_data['aqi'])
        color = collector.get_aqi_color(aqi_data['aqi'])

        print(f"AQI: {aqi_data['aqi']}")
        print(f"Category: {category} ({color})")
        print(f"Timestamp: {aqi_data['timestamp']}")
        print(f"Source: {aqi_data['source']}")

        if 'components' in aqi_data and aqi_data['components']:
            print("\nPollutant Components:")
            for key, value in aqi_data['components'].items():
                print(f"  {key.upper()}: {value}")
    else:
        print("❌ Failed to fetch AQI data")

    db.close()


def cmd_collect(args):
    """Manually collect and store AQI data"""
    config, db, collector = init_components()

    print("\n📊 Collecting AQI data...\n")

    aqi_data = collector.fetch_aqi()

    if aqi_data:
        aqi_data['category'] = collector.get_aqi_category(aqi_data['aqi'])
        aqi_data['color'] = collector.get_aqi_color(aqi_data['aqi'])

        if db.save_aqi_reading(aqi_data):
            print(f"✅ Successfully stored AQI reading: {aqi_data['aqi']}")
        else:
            print("❌ Failed to store AQI reading")
    else:
        print("❌ Failed to fetch AQI data")

    db.close()


def cmd_history(args):
    """Show AQI history"""
    config, db, collector = init_components()

    days = args.days
    print(f"\n📈 AQI History (Last {days} days)\n")

    readings = db.get_readings_last_n_days(days)

    if readings:
        print(f"{'Date':<20} {'AQI':<10} {'Category':<30}")
        print("-" * 60)
        for reading in readings:
            print(f"{reading.timestamp.strftime('%Y-%m-%d %H:%M'):<20} {reading.aqi:<10} {reading.category:<30}")

        # Show statistics
        avg_aqi = sum(r.aqi for r in readings) / len(readings)
        max_aqi = max(r.aqi for r in readings)
        min_aqi = min(r.aqi for r in readings)

        print("\n" + "=" * 60)
        print(f"Average AQI: {avg_aqi:.1f}")
        print(f"Highest AQI: {max_aqi}")
        print(f"Lowest AQI: {min_aqi}")
    else:
        print("No data available for the specified period")

    db.close()


def cmd_add_subscriber(args):
    """Add a new subscriber"""
    config, db, collector = init_components()

    email = args.email
    threshold = args.threshold

    if not validate_email(email):
        print(f"❌ Invalid email address: {email}")
        db.close()
        return

    print(f"\n➕ Adding subscriber: {email}")
    print(f"   Alert threshold: {threshold}")

    if db.add_subscriber(email, threshold):
        print("✅ Subscriber added successfully!")
    else:
        print("❌ Failed to add subscriber (may already exist)")

    db.close()


def cmd_list_subscribers(args):
    """List all subscribers"""
    config, db, collector = init_components()

    print("\n📋 Active Subscribers\n")

    subscribers = db.get_active_subscribers()

    if subscribers:
        print(f"{'Email':<35} {'Threshold':<15} {'Last Alert':<20}")
        print("-" * 70)
        for sub in subscribers:
            last_alert = sub.last_alert_sent.strftime('%Y-%m-%d %H:%M') if sub.last_alert_sent else "Never"
            print(f"{sub.email:<35} {sub.alert_threshold:<15} {last_alert:<20}")

        print(f"\nTotal subscribers: {len(subscribers)}")
    else:
        print("No active subscribers")

    db.close()


def cmd_stats(args):
    """Show database statistics"""
    config, db, collector = init_components()

    print("\n📊 Engine Statistics\n")

    stats = db.get_statistics()

    print(f"Total Readings: {stats.get('total_readings', 0)}")
    print(f"Active Subscribers: {stats.get('total_subscribers', 0)}")

    if stats.get('latest_aqi'):
        print(f"\nLatest Reading:")
        print(f"  AQI: {stats['latest_aqi']}")
        print(f"  Time: {stats['latest_timestamp']}")

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Bangalore AQI Alert Engine - Command Line Interface"
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

    try:
        commands[args.command](args)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logging.error(f"Command failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()