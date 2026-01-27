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

__all__ = [
    "Alert",
    "AlertManager",
    "AlertLevel",
    "create_fire_alert",
    "send_alert",
    "EmailSender",
    "send_fire_alert_email",
]
