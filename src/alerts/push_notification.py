"""
Push notification service for FireWatch AI
Supports Firebase Cloud Messaging (FCM) and Web Push
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PushNotification:
    """Push notification data structure."""
    title: str
    body: str
    token: str
    data: Dict[str, Any] = field(default_factory=dict)
    image_url: Optional[str] = None
    click_action: Optional[str] = None
    sent_at: Optional[datetime] = None
    message_id: Optional[str] = None
    status: str = "pending"


@dataclass
class NotificationTopic:
    """Topic for broadcast notifications."""
    name: str
    description: str
    subscriber_count: int = 0


class FirebasePushService:
    """
    Push notification service using Firebase Cloud Messaging.

    Sends fire alerts to mobile and web clients.
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        """
        Initialize Firebase push service.

        Args:
            credentials_path: Path to Firebase service account JSON
            project_id: Firebase project ID
        """
        self.credentials_path = credentials_path or os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID")

        self._app = None
        self._initialized = False

        if self.credentials_path:
            self._initialize_firebase()

    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK."""
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            cred = credentials.Certificate(self.credentials_path)
            self._app = firebase_admin.initialize_app(cred)
            self._initialized = True
            logger.info("Firebase push service initialized")

        except ImportError:
            logger.warning("firebase-admin not installed. Push notifications disabled.")
        except FileNotFoundError:
            logger.warning(f"Firebase credentials not found: {self.credentials_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")

    @property
    def is_configured(self) -> bool:
        """Check if push service is configured."""
        return self._initialized

    def send_to_device(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> PushNotification:
        """
        Send notification to a specific device.

        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Image URL for rich notification

        Returns:
            PushNotification with send status
        """
        notification = PushNotification(
            title=title,
            body=body,
            token=token,
            data=data or {},
            image_url=image_url
        )

        if not self.is_configured:
            logger.warning(f"Push not configured. Would send: {title}")
            notification.status = "not_configured"
            return notification

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url
                ),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token
            )

            response = messaging.send(message)

            notification.message_id = response
            notification.status = "sent"
            notification.sent_at = datetime.utcnow()

            logger.info(f"Push sent to device: {response}")

        except Exception as e:
            logger.error(f"Push send failed: {e}")
            notification.status = "failed"

        return notification

    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send notification to a topic (broadcast).

        Args:
            topic: Topic name (e.g., "fire_alerts_sp")
            title: Notification title
            body: Notification body
            data: Additional data payload

        Returns:
            Send result
        """
        if not self.is_configured:
            logger.warning(f"Push not configured. Would broadcast to {topic}: {title}")
            return {"status": "not_configured"}

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data={k: str(v) for k, v in (data or {}).items()},
                topic=topic
            )

            response = messaging.send(message)

            logger.info(f"Push sent to topic {topic}: {response}")
            return {"status": "sent", "message_id": response}

        except Exception as e:
            logger.error(f"Topic push failed: {e}")
            return {"status": "failed", "error": str(e)}

    def send_fire_alert(
        self,
        token: str,
        alert_level: str,
        location: str,
        lat: float,
        lon: float,
        fire_id: Optional[int] = None
    ) -> PushNotification:
        """
        Send a fire alert notification.

        Args:
            token: Device token
            alert_level: Alert severity level
            location: Fire location description
            lat: Latitude
            lon: Longitude
            fire_id: Optional fire cluster ID

        Returns:
            PushNotification result
        """
        emoji = self._get_alert_emoji(alert_level)

        title = f"{emoji} Alerta de Incendio - {alert_level}"
        body = f"Foco de incendio detectado em {location}. Verifique as orientacoes."

        data = {
            "type": "fire_alert",
            "alert_level": alert_level,
            "location": location,
            "latitude": str(lat),
            "longitude": str(lon),
            "timestamp": datetime.utcnow().isoformat()
        }

        if fire_id:
            data["fire_id"] = str(fire_id)

        return self.send_to_device(
            token=token,
            title=title,
            body=body,
            data=data
        )

    def send_evacuation_alert(
        self,
        token: str,
        community: str,
        route_direction: str,
        time_to_safety_min: int
    ) -> PushNotification:
        """
        Send evacuation alert notification.

        Args:
            token: Device token
            community: Community name
            route_direction: Direction to evacuate
            time_to_safety_min: Time to safe zone

        Returns:
            PushNotification result
        """
        title = "🚨 EVACUACAO IMEDIATA"
        body = f"Evacue {community} agora! Siga para {route_direction}. Tempo: {time_to_safety_min} min."

        data = {
            "type": "evacuation",
            "community": community,
            "direction": route_direction,
            "time_minutes": str(time_to_safety_min),
            "priority": "critical"
        }

        return self.send_to_device(
            token=token,
            title=title,
            body=body,
            data=data
        )

    def broadcast_to_region(
        self,
        state: str,
        alert_level: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Broadcast alert to all subscribers in a region.

        Args:
            state: State/region code
            alert_level: Alert severity
            message: Alert message

        Returns:
            Broadcast result
        """
        topic = f"fire_alerts_{state.lower().replace(' ', '_')}"

        emoji = self._get_alert_emoji(alert_level)
        title = f"{emoji} Alerta {alert_level} - {state}"

        return self.send_to_topic(
            topic=topic,
            title=title,
            body=message,
            data={
                "type": "regional_alert",
                "state": state,
                "alert_level": alert_level
            }
        )

    def subscribe_to_region(self, token: str, state: str) -> bool:
        """
        Subscribe device to regional alerts.

        Args:
            token: Device token
            state: State/region to subscribe

        Returns:
            True if subscription successful
        """
        if not self.is_configured:
            return False

        try:
            from firebase_admin import messaging

            topic = f"fire_alerts_{state.lower().replace(' ', '_')}"
            response = messaging.subscribe_to_topic([token], topic)

            if response.success_count > 0:
                logger.info(f"Device subscribed to {topic}")
                return True

            return False

        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            return False

    def unsubscribe_from_region(self, token: str, state: str) -> bool:
        """
        Unsubscribe device from regional alerts.

        Args:
            token: Device token
            state: State/region to unsubscribe

        Returns:
            True if unsubscription successful
        """
        if not self.is_configured:
            return False

        try:
            from firebase_admin import messaging

            topic = f"fire_alerts_{state.lower().replace(' ', '_')}"
            response = messaging.unsubscribe_from_topic([token], topic)

            return response.success_count > 0

        except Exception as e:
            logger.error(f"Unsubscription failed: {e}")
            return False

    def _get_alert_emoji(self, level: str) -> str:
        """Get emoji for alert level."""
        emojis = {
            "BAIXO": "🟢",
            "MODERADO": "🟡",
            "ALTO": "🟠",
            "MUITO ALTO": "🔴",
            "CRITICO": "🚨"
        }
        return emojis.get(level.upper(), "⚠️")


class WebPushService:
    """
    Web Push notification service.

    Sends notifications to web browsers using VAPID.
    """

    def __init__(
        self,
        vapid_public_key: Optional[str] = None,
        vapid_private_key: Optional[str] = None,
        vapid_email: Optional[str] = None
    ):
        """
        Initialize Web Push service.

        Args:
            vapid_public_key: VAPID public key
            vapid_private_key: VAPID private key
            vapid_email: Contact email for VAPID
        """
        self.vapid_public_key = vapid_public_key or os.getenv("VAPID_PUBLIC_KEY")
        self.vapid_private_key = vapid_private_key or os.getenv("VAPID_PRIVATE_KEY")
        self.vapid_email = vapid_email or os.getenv("VAPID_EMAIL")

        self._initialized = bool(
            self.vapid_public_key and
            self.vapid_private_key
        )

    @property
    def is_configured(self) -> bool:
        return self._initialized

    def send(
        self,
        subscription_info: Dict[str, Any],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send Web Push notification.

        Args:
            subscription_info: Browser push subscription
            title: Notification title
            body: Notification body
            data: Additional data

        Returns:
            True if sent successfully
        """
        if not self.is_configured:
            logger.warning("Web Push not configured")
            return False

        try:
            from pywebpush import webpush, WebPushException

            payload = json.dumps({
                "title": title,
                "body": body,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            })

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims={"sub": f"mailto:{self.vapid_email}"}
            )

            logger.info("Web push sent successfully")
            return True

        except ImportError:
            logger.warning("pywebpush not installed")
            return False
        except Exception as e:
            logger.error(f"Web push failed: {e}")
            return False


class MockPushService:
    """Mock push service for testing."""

    def __init__(self):
        self.sent_notifications: List[PushNotification] = []

    @property
    def is_configured(self) -> bool:
        return True

    def send_to_device(
        self,
        token: str,
        title: str,
        body: str,
        **kwargs
    ) -> PushNotification:
        """Mock send to device."""
        notification = PushNotification(
            title=title,
            body=body,
            token=token,
            status="mock_sent",
            message_id=f"MOCK_{len(self.sent_notifications)}",
            sent_at=datetime.utcnow()
        )
        self.sent_notifications.append(notification)
        logger.info(f"[MOCK PUSH] {title}: {body}")
        return notification


def get_push_service() -> FirebasePushService:
    """Get push notification service instance."""
    service = FirebasePushService()

    if not service.is_configured:
        logger.warning("Firebase not configured, using mock push service")
        return MockPushService()

    return service
