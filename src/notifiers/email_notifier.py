# src/notifiers/email_notifier.py
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Handles sending email notifications"""

    def __init__(self, config: dict, smtp_username: str, smtp_password: str):
        self.config = config.get('notifications', {}).get('email', {})
        self.enabled = self.config.get('enabled', False)

        self.smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.from_email = self.config.get('from_email')
        self.from_name = self.config.get('from_name', 'Bangalore AQI Alerts')

        self.smtp_username = smtp_username
        self.smtp_password = smtp_password

        if not self.enabled:
            logger.warning("Email notifications are disabled in configuration")

        if self.enabled and (not smtp_username or not smtp_password):
            logger.error("Email enabled but credentials not provided")
            self.enabled = False

    def send_alert(self, alert: Dict) -> bool:
        """Send an alert email to a subscriber"""
        if not self.enabled:
            logger.info("Email notifications disabled, skipping alert")
            return False

        try:
            subject = self._create_subject(alert)
            body = self._create_alert_body(alert)

            success = self._send_email(
                to_email=alert['email'],
                subject=subject,
                body=body
            )

            if success:
                logger.info(f"Alert email sent to {alert['email']}")
            else:
                logger.error(f"Failed to send alert email to {alert['email']}")

            return success

        except Exception as e:
            logger.error(f"Error sending alert email: {e}")
            return False

    def send_batch_alerts(self, alerts: List[Dict]) -> Dict:
        """Send multiple alerts and return statistics"""
        results = {
            'total': len(alerts),
            'sent': 0,
            'failed': 0
        }

        for alert in alerts:
            if self.send_alert(alert):
                results['sent'] += 1
            else:
                results['failed'] += 1

        logger.info(f"Batch alert results: {results['sent']}/{results['total']} sent successfully")
        return results

    def send_daily_report(self, report_data: Dict, recipients: List[str]) -> bool:
        """Send daily AQI report to subscribers"""
        if not self.enabled:
            return False

        try:
            subject = f"Daily AQI Report - Bangalore - {datetime.now().strftime('%B %d, %Y')}"
            body = self._create_report_body(report_data)

            success_count = 0
            for recipient in recipients:
                if self._send_email(recipient, subject, body):
                    success_count += 1

            logger.info(f"Daily report sent to {success_count}/{len(recipients)} recipients")
            return success_count > 0

        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False

    def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Core email sending function"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Attach both plain text and HTML versions
            text_part = MIMEText(body, 'plain')
            html_part = MIMEText(self._text_to_html(body), 'html')

            msg.attach(text_part)
            msg.attach(html_part)

            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed - check credentials")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    def _create_subject(self, alert: Dict) -> str:
        """Create email subject line"""
        aqi = alert['aqi']
        category = alert['category']

        emoji_map = {
            'Good': '🟢',
            'Moderate': '🟡',
            'Unhealthy for Sensitive Groups': '🟠',
            'Unhealthy': '🔴',
            'Very Unhealthy': '🟣',
            'Hazardous': '🟤'
        }

        emoji = emoji_map.get(category, '⚠️')

        return f"{emoji} AQI Alert: {aqi} - {category} in Bangalore"

    def _create_alert_body(self, alert: Dict) -> str:
        """Create alert email body"""
        body = f"""
                Air Quality Alert for Bangalore
                {'=' * 50}
                
                ⚠️ ALERT: Air Quality Index has exceeded your threshold!
                
                Current AQI: {alert['aqi']}
                Category: {alert['category']} ({alert['color']})
                Your Threshold: {alert.get('threshold_level', 'N/A')}
                Time: {alert['timestamp'].strftime('%B %d, %Y at %I:%M %p')}
                Location: {alert['location']}
                
                {'=' * 50}
                
                HEALTH RECOMMENDATION:
                {alert['health_recommendation']}
                
                {'=' * 50}
                
                What you should do:
                {alert['message']}
                
                {'=' * 50}
                
                Stay safe and monitor air quality regularly!
                
                This is an automated alert from Bangalore AQI Engine.
                You can update your alert preferences by contacting the administrator.
                
                ---
                Powered by Bangalore AQI Alert Engine
                """
        return body.strip()

    def _create_report_body(self, report_data: Dict) -> str:
        """Create daily report email body"""
        stats = report_data.get('statistics', {})
        readings = report_data.get('recent_readings', [])

        body = f"""
                Daily Air Quality Report - Bangalore
                {'=' * 50}
                
                Report Date: {datetime.now().strftime('%B %d, %Y')}
                
                SUMMARY
                -------
                Average AQI (24h): {stats.get('avg_aqi', 'N/A')}
                Highest AQI: {stats.get('max_aqi', 'N/A')}
                Lowest AQI: {stats.get('min_aqi', 'N/A')}
                Total Readings: {stats.get('total_readings', 'N/A')}
                
                CURRENT STATUS
                --------------
                Current AQI: {stats.get('current_aqi', 'N/A')}
                Category: {stats.get('current_category', 'N/A')}
                """

        if readings:
            body += "\nRECENT READINGS (Last 24 Hours)\n"
            body += "-" * 50 + "\n"
            for reading in readings[:10]:  # Show last 10 readings
                body += f"{reading['time']}: AQI {reading['aqi']} ({reading['category']})\n"

        body += f"""
            {'=' * 50}
            
            HEALTH RECOMMENDATIONS
            {stats.get('health_recommendation', 'Monitor air quality regularly.')}
            
            {'=' * 50}
            
            Stay informed and breathe easy!
            
            ---
            Powered by Bangalore AQI Alert Engine
            """
        return body.strip()

    def _text_to_html(self, text: str) -> str:
        """Convert plain text to simple HTML"""
        # Simple conversion - wrap in HTML tags and convert newlines to <br>
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text = text.replace('\n', '<br>\n')

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #f4f4f4; padding: 10px; margin-bottom: 20px; }}
                .alert {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 10px 0; }}
                .info {{ background-color: #d1ecf1; border-left: 4px solid #17a2b8; padding: 15px; margin: 10px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 0.9em; color: #666; }}
            </style>
        </head>
        <body>
            <div class="content">
                {text}
            </div>
        </body>
        </html>
        """
        return html

    def test_connection(self) -> bool:
        """Test SMTP connection and credentials"""
        if not self.enabled:
            logger.warning("Email is disabled, cannot test connection")
            return False

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)

            logger.info("Email connection test successful")
            return True

        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return False
