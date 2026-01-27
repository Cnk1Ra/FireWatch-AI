"""
FireWatch AI - Alert Manager
Centralized alert creation and distribution system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"           # Informational, no action required
    WARNING = "warning"     # Potential threat, monitor situation
    ALERT = "alert"         # Active threat, prepare for action
    CRITICAL = "critical"   # Immediate danger, take action now
    EMERGENCY = "emergency" # Life-threatening, evacuate


class AlertChannel(str, Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"


@dataclass
class AlertRecipient:
    """Alert recipient information."""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    push_token: Optional[str] = None
    preferred_channel: AlertChannel = AlertChannel.EMAIL
    language: str = "pt-BR"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "preferred_channel": self.preferred_channel.value,
            "language": self.language,
        }


@dataclass
class Alert:
    """Fire alert object."""
    alert_id: str
    fire_id: str
    level: AlertLevel
    title: str
    message: str
    created_at: datetime
    expires_at: Optional[datetime]

    # Fire information
    fire_latitude: float
    fire_longitude: float
    fire_area_hectares: float

    # Alert metadata
    affected_region: str
    affected_population: int
    evacuation_recommended: bool

    # Distribution status
    channels_sent: List[str] = field(default_factory=list)
    recipients_count: int = 0
    delivery_status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "fire_id": self.fire_id,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "fire_info": {
                "latitude": self.fire_latitude,
                "longitude": self.fire_longitude,
                "area_hectares": self.fire_area_hectares,
            },
            "affected_region": self.affected_region,
            "affected_population": self.affected_population,
            "evacuation_recommended": self.evacuation_recommended,
            "distribution": {
                "channels": self.channels_sent,
                "recipients_count": self.recipients_count,
                "status": self.delivery_status,
            },
        }

    def get_sms_message(self) -> str:
        """Get shortened message for SMS."""
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ALERT: "🔥",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.EMERGENCY: "🆘",
        }
        emoji = level_emoji.get(self.level, "🔥")

        msg = f"{emoji} FIREWATCH: {self.title}\n"
        msg += f"Região: {self.affected_region}\n"

        if self.evacuation_recommended:
            msg += "⚠️ EVACUAÇÃO RECOMENDADA\n"

        msg += f"Info: firewatch.ai/alert/{self.alert_id}"

        return msg[:160]  # SMS limit


class AlertManager:
    """Manages alert creation and distribution."""

    def __init__(self):
        """Initialize the alert manager."""
        self.alerts: Dict[str, Alert] = {}
        self.recipients: List[AlertRecipient] = []
        self.alert_history: List[Alert] = []

    def add_recipient(self, recipient: AlertRecipient) -> None:
        """Add a recipient to receive alerts."""
        self.recipients.append(recipient)

    def create_alert(
        self,
        fire_id: str,
        level: AlertLevel,
        fire_lat: float,
        fire_lon: float,
        fire_area: float,
        region: str,
        population: int = 0,
        evacuation: bool = False,
        custom_message: Optional[str] = None
    ) -> Alert:
        """
        Create a new fire alert.

        Args:
            fire_id: Fire identifier
            level: Alert severity level
            fire_lat: Fire latitude
            fire_lon: Fire longitude
            fire_area: Burned area in hectares
            region: Affected region name
            population: Affected population
            evacuation: Whether evacuation is recommended
            custom_message: Optional custom alert message

        Returns:
            Alert object
        """
        alert_id = f"ALERT-{uuid.uuid4().hex[:8].upper()}"

        title = self._generate_title(level, region, fire_area)
        message = custom_message or self._generate_message(
            level, region, fire_area, population, evacuation
        )

        alert = Alert(
            alert_id=alert_id,
            fire_id=fire_id,
            level=level,
            title=title,
            message=message,
            created_at=datetime.now(),
            expires_at=None,
            fire_latitude=fire_lat,
            fire_longitude=fire_lon,
            fire_area_hectares=fire_area,
            affected_region=region,
            affected_population=population,
            evacuation_recommended=evacuation,
        )

        self.alerts[alert_id] = alert
        self.alert_history.append(alert)

        return alert

    def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[AlertChannel]] = None
    ) -> Dict[str, Any]:
        """
        Send alert through specified channels.

        Args:
            alert: Alert to send
            channels: List of channels to use (default: all)

        Returns:
            Dictionary with delivery results
        """
        if channels is None:
            channels = [AlertChannel.EMAIL, AlertChannel.DASHBOARD]

        results = {
            "alert_id": alert.alert_id,
            "channels": {},
            "total_sent": 0,
            "total_failed": 0,
        }

        for channel in channels:
            channel_result = self._send_to_channel(alert, channel)
            results["channels"][channel.value] = channel_result
            results["total_sent"] += channel_result.get("sent", 0)
            results["total_failed"] += channel_result.get("failed", 0)

        alert.channels_sent = [c.value for c in channels]
        alert.recipients_count = results["total_sent"]
        alert.delivery_status = "sent" if results["total_sent"] > 0 else "failed"

        return results

    def _send_to_channel(
        self,
        alert: Alert,
        channel: AlertChannel
    ) -> Dict[str, Any]:
        """Send alert to a specific channel."""
        # Filter recipients for this channel
        recipients = [
            r for r in self.recipients
            if r.preferred_channel == channel
        ]

        # In production, this would actually send the alerts
        # For now, we simulate the sending
        return {
            "channel": channel.value,
            "recipients": len(recipients),
            "sent": len(recipients),
            "failed": 0,
            "status": "simulated",
        }

    def _generate_title(
        self,
        level: AlertLevel,
        region: str,
        area: float
    ) -> str:
        """Generate alert title based on level and fire size."""
        level_titles = {
            AlertLevel.INFO: f"Foco de incêndio detectado em {region}",
            AlertLevel.WARNING: f"Alerta de incêndio em {region}",
            AlertLevel.ALERT: f"Incêndio ativo em {region} - {area:.0f} ha",
            AlertLevel.CRITICAL: f"CRÍTICO: Incêndio em {region} - {area:.0f} ha",
            AlertLevel.EMERGENCY: f"EMERGÊNCIA: Evacuação em {region}",
        }
        return level_titles.get(level, f"Alerta de incêndio em {region}")

    def _generate_message(
        self,
        level: AlertLevel,
        region: str,
        area: float,
        population: int,
        evacuation: bool
    ) -> str:
        """Generate alert message."""
        msg = f"Um incêndio foi detectado na região de {region}.\n\n"
        msg += f"Área afetada: {area:.1f} hectares\n"

        if population > 0:
            msg += f"População na área: {population:,} pessoas\n"

        if level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
            msg += "\n⚠️ ATENÇÃO: Esta é uma situação de risco elevado.\n"

        if evacuation:
            msg += "\n🚨 EVACUAÇÃO RECOMENDADA\n"
            msg += "Siga as orientações das autoridades locais.\n"
            msg += "Dirija-se ao abrigo mais próximo.\n"

        msg += "\nPara mais informações, acesse: firewatch.ai\n"
        msg += "Em caso de emergência, ligue: 193 (Bombeiros)"

        return msg

    def get_active_alerts(self) -> List[Alert]:
        """Get all active (non-expired) alerts."""
        now = datetime.now()
        return [
            a for a in self.alerts.values()
            if a.expires_at is None or a.expires_at > now
        ]

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get a specific alert by ID."""
        return self.alerts.get(alert_id)


def create_fire_alert(
    fire_id: str,
    latitude: float,
    longitude: float,
    area_hectares: float,
    region: str,
    risk_level: str = "high",
    population: int = 0
) -> Alert:
    """
    Convenience function to create a fire alert.

    Args:
        fire_id: Fire identifier
        latitude: Fire latitude
        longitude: Fire longitude
        area_hectares: Burned area
        region: Region name
        risk_level: Risk level string
        population: Affected population

    Returns:
        Alert object
    """
    level_map = {
        "low": AlertLevel.INFO,
        "moderate": AlertLevel.WARNING,
        "high": AlertLevel.ALERT,
        "very_high": AlertLevel.CRITICAL,
        "extreme": AlertLevel.EMERGENCY,
    }
    level = level_map.get(risk_level, AlertLevel.ALERT)

    evacuation = level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]

    manager = AlertManager()
    return manager.create_alert(
        fire_id=fire_id,
        level=level,
        fire_lat=latitude,
        fire_lon=longitude,
        fire_area=area_hectares,
        region=region,
        population=population,
        evacuation=evacuation,
    )


def send_alert(alert: Alert, channels: List[str] = None) -> Dict[str, Any]:
    """
    Convenience function to send an alert.

    Args:
        alert: Alert to send
        channels: List of channel names

    Returns:
        Delivery results
    """
    manager = AlertManager()

    if channels:
        channel_enums = [AlertChannel(c) for c in channels]
    else:
        channel_enums = None

    return manager.send_alert(alert, channel_enums)
