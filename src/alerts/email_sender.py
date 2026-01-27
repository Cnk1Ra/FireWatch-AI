"""
FireWatch AI - Email Sender
Sends fire alert emails using SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.core.config import settings


@dataclass
class EmailConfig:
    """Email server configuration."""
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_address: str
    from_name: str = "FireWatch AI"
    use_tls: bool = True


class EmailSender:
    """Sends emails via SMTP."""

    def __init__(self, config: Optional[EmailConfig] = None):
        """
        Initialize email sender.

        Args:
            config: Email configuration (uses settings if not provided)
        """
        if config:
            self.config = config
        else:
            self.config = EmailConfig(
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                username=settings.smtp_user or "",
                password=settings.smtp_password or "",
                from_address=settings.smtp_user or "noreply@firewatch.ai",
            )

    def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email.

        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body

        Returns:
            Dictionary with send results
        """
        if not self.config.username or not self.config.password:
            return {
                "success": False,
                "error": "Email credentials not configured",
                "sent_to": [],
            }

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_address}>"
            msg["To"] = ", ".join(to_addresses)

            # Add text part
            text_part = MIMEText(body_text, "plain", "utf-8")
            msg.attach(text_part)

            # Add HTML part if provided
            if body_html:
                html_part = MIMEText(body_html, "html", "utf-8")
                msg.attach(html_part)

            # Connect and send
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.username, self.config.password)
                server.sendmail(
                    self.config.from_address,
                    to_addresses,
                    msg.as_string()
                )

            return {
                "success": True,
                "sent_to": to_addresses,
                "subject": subject,
            }

        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "SMTP authentication failed",
                "sent_to": [],
            }
        except smtplib.SMTPException as e:
            return {
                "success": False,
                "error": f"SMTP error: {str(e)}",
                "sent_to": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to send email: {str(e)}",
                "sent_to": [],
            }


def generate_alert_email_html(
    alert_title: str,
    alert_message: str,
    fire_lat: float,
    fire_lon: float,
    fire_area: float,
    region: str,
    evacuation: bool = False
) -> str:
    """
    Generate HTML email for fire alert.

    Args:
        alert_title: Alert title
        alert_message: Alert message
        fire_lat: Fire latitude
        fire_lon: Fire longitude
        fire_area: Burned area in hectares
        region: Affected region
        evacuation: Whether evacuation is recommended

    Returns:
        HTML email content
    """
    evac_banner = ""
    if evacuation:
        evac_banner = """
        <div style="background-color: #dc3545; color: white; padding: 15px;
                    text-align: center; font-size: 18px; font-weight: bold;">
            🚨 EVACUAÇÃO RECOMENDADA - SIGA AS ORIENTAÇÕES DAS AUTORIDADES
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
        {evac_banner}

        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #ff6b35; color: white; padding: 20px;
                        text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">🔥 FireWatch AI</h1>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Sistema de Alerta de Incêndios</p>
            </div>

            <div style="background-color: #f8f9fa; padding: 20px; border: 1px solid #ddd;">
                <h2 style="color: #333; margin-top: 0;">{alert_title}</h2>

                <div style="background-color: white; padding: 15px; border-radius: 8px;
                            margin: 15px 0; border-left: 4px solid #ff6b35;">
                    <p style="margin: 0; white-space: pre-line;">{alert_message}</p>
                </div>

                <h3 style="color: #333;">📍 Informações do Incêndio</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Região:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{region}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Área afetada:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{fire_area:.1f} hectares</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Coordenadas:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{fire_lat:.4f}, {fire_lon:.4f}</td>
                    </tr>
                </table>

                <div style="margin-top: 20px; text-align: center;">
                    <a href="https://www.google.com/maps?q={fire_lat},{fire_lon}"
                       style="display: inline-block; background-color: #ff6b35; color: white;
                              padding: 12px 24px; text-decoration: none; border-radius: 4px;
                              font-weight: bold;">
                        📍 Ver no Mapa
                    </a>
                </div>
            </div>

            <div style="background-color: #333; color: white; padding: 15px;
                        text-align: center; border-radius: 0 0 8px 8px; font-size: 12px;">
                <p style="margin: 0;">
                    <strong>Contatos de Emergência:</strong><br>
                    Bombeiros: 193 | Defesa Civil: 199 | SAMU: 192
                </p>
                <p style="margin: 10px 0 0 0; color: #aaa;">
                    FireWatch AI - Sistema de Monitoramento de Incêndios<br>
                    <a href="https://firewatch.ai" style="color: #ff6b35;">firewatch.ai</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def send_fire_alert_email(
    to_addresses: List[str],
    alert_title: str,
    alert_message: str,
    fire_lat: float,
    fire_lon: float,
    fire_area: float,
    region: str,
    evacuation: bool = False
) -> Dict[str, Any]:
    """
    Send a fire alert email.

    Args:
        to_addresses: List of recipient emails
        alert_title: Alert title
        alert_message: Alert message
        fire_lat: Fire latitude
        fire_lon: Fire longitude
        fire_area: Burned area
        region: Affected region
        evacuation: Whether evacuation is recommended

    Returns:
        Send results
    """
    sender = EmailSender()

    subject = f"🔥 FireWatch Alerta: {alert_title}"

    body_html = generate_alert_email_html(
        alert_title, alert_message,
        fire_lat, fire_lon, fire_area, region, evacuation
    )

    return sender.send_email(
        to_addresses=to_addresses,
        subject=subject,
        body_text=alert_message,
        body_html=body_html,
    )
