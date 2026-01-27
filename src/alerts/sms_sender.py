"""
SMS notification sender using Twilio
Sends fire alerts via SMS to registered users
"""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SMSMessage:
    """SMS message data structure."""
    to: str
    body: str
    alert_level: str
    location: Optional[str] = None
    sent_at: Optional[datetime] = None
    message_sid: Optional[str] = None
    status: str = "pending"


class TwilioSMSSender:
    """
    SMS sender using Twilio API.

    Sends fire alert notifications via SMS.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None
    ):
        """
        Initialize Twilio SMS sender.

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
            from_number: Twilio phone number to send from
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")

        self._client = None
        self._initialized = False

        if self.account_sid and self.auth_token:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Twilio client."""
        try:
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
            self._initialized = True
            logger.info("Twilio SMS client initialized")
        except ImportError:
            logger.warning("Twilio package not installed. SMS sending disabled.")
            self._initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            self._initialized = False

    @property
    def is_configured(self) -> bool:
        """Check if SMS sender is properly configured."""
        return bool(
            self.account_sid and
            self.auth_token and
            self.from_number and
            self._initialized
        )

    def send_alert(
        self,
        phone_number: str,
        alert_level: str,
        location: str,
        message: str
    ) -> SMSMessage:
        """
        Send a fire alert SMS.

        Args:
            phone_number: Recipient phone number (E.164 format)
            alert_level: Alert severity level
            location: Fire location description
            message: Alert message

        Returns:
            SMSMessage with send status
        """
        # Format phone number
        formatted_number = self._format_phone_number(phone_number)

        # Build SMS body
        body = self._build_alert_body(alert_level, location, message)

        sms = SMSMessage(
            to=formatted_number,
            body=body,
            alert_level=alert_level,
            location=location
        )

        if not self.is_configured:
            logger.warning(f"SMS not configured. Would send to {formatted_number}: {body}")
            sms.status = "not_configured"
            return sms

        try:
            twilio_message = self._client.messages.create(
                body=body,
                from_=self.from_number,
                to=formatted_number
            )

            sms.message_sid = twilio_message.sid
            sms.status = twilio_message.status
            sms.sent_at = datetime.utcnow()

            logger.info(f"SMS sent to {formatted_number}: {twilio_message.sid}")

        except Exception as e:
            logger.error(f"Failed to send SMS to {formatted_number}: {e}")
            sms.status = "failed"

        return sms

    def send_bulk_alert(
        self,
        phone_numbers: List[str],
        alert_level: str,
        location: str,
        message: str
    ) -> List[SMSMessage]:
        """
        Send alert to multiple phone numbers.

        Args:
            phone_numbers: List of recipient phone numbers
            alert_level: Alert severity level
            location: Fire location description
            message: Alert message

        Returns:
            List of SMSMessage with send statuses
        """
        results = []

        for phone in phone_numbers:
            result = self.send_alert(phone, alert_level, location, message)
            results.append(result)

        # Log summary
        sent = sum(1 for r in results if r.status in ["queued", "sent", "delivered"])
        failed = sum(1 for r in results if r.status == "failed")
        logger.info(f"Bulk SMS: {sent} sent, {failed} failed out of {len(phone_numbers)}")

        return results

    def send_evacuation_alert(
        self,
        phone_number: str,
        community: str,
        direction: str,
        time_minutes: int
    ) -> SMSMessage:
        """
        Send evacuation alert with route information.

        Args:
            phone_number: Recipient phone number
            community: Community/area name
            direction: Evacuation direction
            time_minutes: Estimated time to safety

        Returns:
            SMSMessage with send status
        """
        body = (
            f"🚨 ALERTA DE EVACUACAO - FireWatch AI\n\n"
            f"Area: {community}\n"
            f"Rota: Siga para {direction}\n"
            f"Tempo estimado: {time_minutes} min\n\n"
            f"EMERGENCIA: 193 (Bombeiros)\n"
            f"Nao entre em panico. Siga as orientacoes."
        )

        return self._send_message(phone_number, body, "CRITICO", community)

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number to E.164 format.

        Args:
            phone: Input phone number

        Returns:
            Formatted phone number
        """
        # Remove non-numeric characters
        cleaned = ''.join(filter(str.isdigit, phone))

        # Add Brazil country code if not present
        if len(cleaned) == 11:  # Brazilian mobile: DDD + 9 digits
            return f"+55{cleaned}"
        elif len(cleaned) == 10:  # Brazilian landline: DDD + 8 digits
            return f"+55{cleaned}"
        elif len(cleaned) == 13 and cleaned.startswith("55"):
            return f"+{cleaned}"
        elif cleaned.startswith("+"):
            return phone

        return f"+{cleaned}"

    def _build_alert_body(
        self,
        alert_level: str,
        location: str,
        message: str
    ) -> str:
        """
        Build SMS body for fire alert.

        Args:
            alert_level: Alert severity
            location: Fire location
            message: Custom message

        Returns:
            Formatted SMS body
        """
        emoji = self._get_level_emoji(alert_level)

        return (
            f"{emoji} ALERTA {alert_level} - FireWatch AI\n\n"
            f"Local: {location}\n"
            f"{message}\n\n"
            f"Bombeiros: 193 | Def. Civil: 199"
        )

    def _get_level_emoji(self, level: str) -> str:
        """Get emoji for alert level."""
        emojis = {
            "BAIXO": "🟢",
            "MODERADO": "🟡",
            "ALTO": "🟠",
            "MUITO ALTO": "🔴",
            "CRITICO": "🚨"
        }
        return emojis.get(level.upper(), "⚠️")

    def _send_message(
        self,
        phone: str,
        body: str,
        level: str,
        location: str
    ) -> SMSMessage:
        """Internal method to send SMS message."""
        formatted_number = self._format_phone_number(phone)

        sms = SMSMessage(
            to=formatted_number,
            body=body,
            alert_level=level,
            location=location
        )

        if not self.is_configured:
            sms.status = "not_configured"
            return sms

        try:
            twilio_message = self._client.messages.create(
                body=body,
                from_=self.from_number,
                to=formatted_number
            )
            sms.message_sid = twilio_message.sid
            sms.status = twilio_message.status
            sms.sent_at = datetime.utcnow()
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            sms.status = "failed"

        return sms

    def get_message_status(self, message_sid: str) -> Optional[str]:
        """
        Check status of a sent message.

        Args:
            message_sid: Twilio message SID

        Returns:
            Message status or None if not found
        """
        if not self.is_configured:
            return None

        try:
            message = self._client.messages(message_sid).fetch()
            return message.status
        except Exception as e:
            logger.error(f"Failed to get message status: {e}")
            return None


class MockSMSSender:
    """
    Mock SMS sender for testing.

    Logs messages instead of sending them.
    """

    def __init__(self):
        self.sent_messages: List[SMSMessage] = []
        logger.info("Mock SMS sender initialized")

    @property
    def is_configured(self) -> bool:
        return True

    def send_alert(
        self,
        phone_number: str,
        alert_level: str,
        location: str,
        message: str
    ) -> SMSMessage:
        """Log alert instead of sending."""
        sms = SMSMessage(
            to=phone_number,
            body=f"[{alert_level}] {location}: {message}",
            alert_level=alert_level,
            location=location,
            status="mock_sent",
            sent_at=datetime.utcnow(),
            message_sid=f"MOCK_{len(self.sent_messages)}"
        )

        self.sent_messages.append(sms)
        logger.info(f"[MOCK SMS] To: {phone_number}, Level: {alert_level}, Location: {location}")

        return sms

    def send_bulk_alert(
        self,
        phone_numbers: List[str],
        alert_level: str,
        location: str,
        message: str
    ) -> List[SMSMessage]:
        """Send mock alerts to multiple numbers."""
        return [
            self.send_alert(phone, alert_level, location, message)
            for phone in phone_numbers
        ]


def get_sms_sender() -> TwilioSMSSender:
    """
    Get SMS sender instance.

    Returns mock sender if Twilio is not configured.
    """
    sender = TwilioSMSSender()

    if not sender.is_configured:
        logger.warning("Twilio not configured, using mock SMS sender")
        return MockSMSSender()

    return sender
