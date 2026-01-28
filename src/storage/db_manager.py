# src/storage/db_manager.py
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from typing import List, Optional
import logging
import json

logger = logging.getLogger(__name__)

Base = declarative_base()


class AQIReading(Base):
    """Model for storing AQI readings"""
    __tablename__ = 'aqi_readings'

    id = Column(Integer, primary_key=True)
    aqi = Column(Integer, nullable=False)
    category = Column(String(50))
    color = Column(String(20))
    location = Column(String(100), default="Bangalore")
    components = Column(JSON)  # Store pollutant components
    source = Column(String(50))
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AQIReading(aqi={self.aqi}, category={self.category}, timestamp={self.timestamp})>"


class Subscriber(Base):
    """Model for storing alert subscribers"""
    __tablename__ = 'subscribers'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    telegram_id = Column(String(100), unique=True)
    alert_threshold = Column(Integer, default=100)  # Alert when AQI exceeds this
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_alert_sent = Column(DateTime)

    def __repr__(self):
        return f"<Subscriber(email={self.email}, threshold={self.alert_threshold})>"


class DatabaseManager:
    """Manages all database operations"""

    def __init__(self, database_url: str = "sqlite:///data/aqi_data.db"):
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        logger.info(f"Database initialized: {database_url}")

    def save_aqi_reading(self, aqi_data: dict) -> bool:
        """Save an AQI reading to database"""
        try:
            reading = AQIReading(
                aqi=aqi_data['aqi'],
                category=aqi_data.get('category'),
                color=aqi_data.get('color'),
                location=json.dumps(aqi_data.get('location')),
                components=aqi_data.get('components'),
                source=aqi_data.get('source'),
                timestamp=aqi_data['timestamp']
            )
            self.session.add(reading)
            self.session.commit()
            logger.info(f"Saved AQI reading: {aqi_data['aqi']} at {aqi_data['timestamp']}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving AQI reading: {e}")
            raise

    def get_latest_reading(self) -> Optional[AQIReading]:
        """Get the most recent AQI reading"""
        try:
            return self.session.query(AQIReading).order_by(
                AQIReading.timestamp.desc()
            ).first()
        except Exception as e:
            logger.error(f"Error fetching latest reading: {e}")
            raise

    def get_readings_by_date_range(self, start_date: datetime, end_date: datetime) -> List[AQIReading]:
        """Get all readings within a date range"""
        try:
            return self.session.query(AQIReading).filter(
                AQIReading.timestamp >= start_date,
                AQIReading.timestamp <= end_date
            ).order_by(AQIReading.timestamp).all()
        except Exception as e:
            logger.error(f"Error fetching readings by date range: {e}")
            raise

    def get_readings_last_n_days(self, days: int = 7) -> List[AQIReading]:
        """Get readings from the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_readings_by_date_range(start_date, end_date)

    def add_subscriber(self, email: str, threshold: int = 100, telegram_id: str = None) -> bool:
        """Add a new subscriber"""
        try:
            subscriber = Subscriber(
                email=email,
                alert_threshold=threshold,
                telegram_id=telegram_id
            )
            self.session.add(subscriber)
            self.session.commit()
            logger.info(f"Added subscriber: {email}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding subscriber: {e}")
            raise

    def get_active_subscribers(self) -> List[Subscriber]:
        """Get all active subscribers"""
        try:
            return self.session.query(Subscriber).filter(
                Subscriber.is_active == 1
            ).all()
        except Exception as e:
            logger.error(f"Error fetching subscribers: {e}")
            raise

    def update_last_alert_time(self, subscriber_id: int):
        """Update the last alert sent time for a subscriber"""
        try:
            subscriber = self.session.query(Subscriber).filter(
                Subscriber.id == subscriber_id
            ).first()
            if subscriber:
                subscriber.last_alert_sent = datetime.utcnow()
                self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating last alert time: {e}")
            raise

    def get_statistics(self) -> dict:
        """Get basic statistics about stored data"""
        try:
            total_readings = self.session.query(AQIReading).count()
            total_subscribers = self.session.query(Subscriber).filter(
                Subscriber.is_active == 1
            ).count()

            latest = self.get_latest_reading()

            return {
                "total_readings": total_readings,
                "total_subscribers": total_subscribers,
                "latest_aqi": latest.aqi if latest else None,
                "latest_timestamp": latest.timestamp if latest else None
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise

    def close(self):
        """Close database connection"""
        self.session.close()
