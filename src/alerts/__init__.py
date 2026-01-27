"""
FireWatch AI - Alert System
Manages fire alerts via email, SMS, and push notifications.
"""

from src.alerts.alert_manager import (
    Alert,
    AlertManager,
    AlertLevel,
    create_fire_alert,
    send_alert,
)
from src.alerts.email_sender import (
    EmailSender,
    send_fire_alert_email,
)
from src.alerts.sms_sender import (
    TwilioSMSSender,
    SMSMessage,
    MockSMSSender,
    get_sms_sender,
)
from src.alerts.push_notification import (
    FirebasePushService,
    WebPushService,
    PushNotification,
    MockPushService,
    get_push_service,
)

__all__ = [
    # Alert Manager
    "Alert",
    "AlertManager",
    "AlertLevel",
    "create_fire_alert",
    "send_alert",
    # Email
    "EmailSender",
    "send_fire_alert_email",
    # SMS
    "TwilioSMSSender",
    "SMSMessage",
    "MockSMSSender",
    "get_sms_sender",
    # Push Notifications
    "FirebasePushService",
    "WebPushService",
    "PushNotification",
    "MockPushService",
    "get_push_service",
]
