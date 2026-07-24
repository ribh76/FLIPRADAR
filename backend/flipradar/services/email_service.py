import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from flipradar.core.settings import EmailSettings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailSendResult:
    attempted: bool
    sent: bool
    reason: str | None = None


class EmailService(Protocol):
    async def send(
        self, *, to_address: str, subject: str, text_body: str, html_body: str
    ) -> EmailSendResult:
        """Send one email message."""


class SmtpEmailService:
    def __init__(self, settings: EmailSettings | None = None) -> None:
        self.settings = settings or get_settings().email

    async def send(
        self, *, to_address: str, subject: str, text_body: str, html_body: str
    ) -> EmailSendResult:
        if not self.settings.configured:
            logger.info("email skipped reason=not_configured to=%s", to_address)
            return EmailSendResult(
                attempted=False, sent=False, reason="email_not_configured"
            )

        message = EmailMessage()
        message["From"] = self.settings.from_address
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        try:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.timeout_seconds,
            ) as smtp:
                smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.password or "")
                smtp.send_message(message)
        except OSError, smtplib.SMTPException:
            logger.exception("email send failed to=%s", to_address)
            return EmailSendResult(attempted=True, sent=False, reason="send_failed")

        logger.info("email sent to=%s subject=%s", to_address, subject)
        return EmailSendResult(attempted=True, sent=True)


def get_email_service() -> EmailService:
    return SmtpEmailService()


async def send_verification_email(
    *,
    to_address: str,
    username: str,
    verification_url: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    service = email_service or get_email_service()
    subject = "Verify your FlipRadar account"
    text_body = (
        f"Hi {username},\n\n"
        "Verify your FlipRadar account with this link:\n"
        f"{verification_url}\n\n"
        "This link expires soon. If you did not create a FlipRadar account, "
        "you can ignore this email."
    )
    html_body = f"""
    <p>Hi {username},</p>
    <p>Verify your FlipRadar account with this link:</p>
    <p><a href="{verification_url}">Verify your email</a></p>
    <p>This link expires soon. If you did not create a FlipRadar account, you can ignore this email.</p>
    """
    return await service.send(
        to_address=to_address,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
