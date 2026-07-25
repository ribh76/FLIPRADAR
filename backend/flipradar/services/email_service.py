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


@dataclass(frozen=True)
class EmailTemplate:
    subject: str
    text_body: str
    html_body: str


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


def verification_email_template(
    *, username: str, verification_url: str
) -> EmailTemplate:
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
    return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)


def registration_email_template(*, username: str) -> EmailTemplate:
    subject = "Welcome to FlipRadar"
    text_body = (
        f"Hi {username},\n\n"
        "Your FlipRadar account is ready. Once your email is verified, you can "
        "track your LEGO portfolio, analyze buys, and keep your session secure."
    )
    html_body = f"""
    <p>Hi {username},</p>
    <p>Your FlipRadar account is ready.</p>
    <p>Once your email is verified, you can track your LEGO portfolio, analyze buys, and keep your session secure.</p>
    """
    return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)


def password_reset_email_template(*, username: str, reset_url: str) -> EmailTemplate:
    subject = "Reset your FlipRadar password"
    text_body = (
        f"Hi {username},\n\n"
        "Use this link to reset your FlipRadar password:\n"
        f"{reset_url}\n\n"
        "This link expires soon. If you did not request a password reset, "
        "you can ignore this email."
    )
    html_body = f"""
    <p>Hi {username},</p>
    <p>Use this link to reset your FlipRadar password:</p>
    <p><a href="{reset_url}">Reset your password</a></p>
    <p>This link expires soon. If you did not request a password reset, you can ignore this email.</p>
    """
    return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)


def email_change_confirmation_template(
    *, username: str, new_email: str, confirmation_url: str
) -> EmailTemplate:
    subject = "Confirm your new FlipRadar email"
    text_body = (
        f"Hi {username},\n\n"
        f"Confirm {new_email} as your FlipRadar account email with this link:\n"
        f"{confirmation_url}\n\n"
        "Your current account email stays active until this link is verified. "
        "If you did not request this change, you can ignore this email."
    )
    html_body = f"""
    <p>Hi {username},</p>
    <p>Confirm <strong>{new_email}</strong> as your FlipRadar account email with this link:</p>
    <p><a href="{confirmation_url}">Confirm new email</a></p>
    <p>Your current account email stays active until this link is verified. If you did not request this change, you can ignore this email.</p>
    """
    return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)


def account_deletion_confirmation_template(
    *, username: str, deletion_scheduled_at: str
) -> EmailTemplate:
    subject = "FlipRadar account deletion scheduled"
    text_body = (
        f"Hi {username},\n\n"
        "Your FlipRadar account deletion was confirmed. Your user data is "
        f"scheduled to be removed after {deletion_scheduled_at}.\n\n"
        "If you did not request this, contact FlipRadar support immediately."
    )
    html_body = f"""
    <p>Hi {username},</p>
    <p>Your FlipRadar account deletion was confirmed.</p>
    <p>Your user data is scheduled to be removed after <strong>{deletion_scheduled_at}</strong>.</p>
    <p>If you did not request this, contact FlipRadar support immediately.</p>
    """
    return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)


def security_email_template(*, username: str, event_label: str) -> EmailTemplate:
    subject = f"Security alert: {event_label}"
    text_body = (
        f"Hi {username},\n\n"
        f"Security event: {event_label}.\n\n"
        "If this was you, no action is needed. If this was not you, reset your "
        "password and contact FlipRadar support."
    )
    html_body = f"""
    <p>Hi {username},</p>
    <p><strong>Security event:</strong> {event_label}.</p>
    <p>If this was you, no action is needed. If this was not you, reset your password and contact FlipRadar support.</p>
    """
    return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)


async def _send_template(
    *,
    to_address: str,
    template: EmailTemplate,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    service = email_service or get_email_service()
    return await service.send(
        to_address=to_address,
        subject=template.subject,
        text_body=template.text_body,
        html_body=template.html_body,
    )


async def send_verification_email(
    *,
    to_address: str,
    username: str,
    verification_url: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    return await _send_template(
        to_address=to_address,
        template=verification_email_template(
            username=username, verification_url=verification_url
        ),
        email_service=email_service,
    )


async def send_registration_email(
    *,
    to_address: str,
    username: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    return await _send_template(
        to_address=to_address,
        template=registration_email_template(username=username),
        email_service=email_service,
    )


async def send_password_reset_email(
    *,
    to_address: str,
    username: str,
    reset_url: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    return await _send_template(
        to_address=to_address,
        template=password_reset_email_template(username=username, reset_url=reset_url),
        email_service=email_service,
    )


async def send_email_change_confirmation_email(
    *,
    to_address: str,
    username: str,
    new_email: str,
    confirmation_url: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    return await _send_template(
        to_address=to_address,
        template=email_change_confirmation_template(
            username=username,
            new_email=new_email,
            confirmation_url=confirmation_url,
        ),
        email_service=email_service,
    )


async def send_account_deletion_confirmation_email(
    *,
    to_address: str,
    username: str,
    deletion_scheduled_at: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    return await _send_template(
        to_address=to_address,
        template=account_deletion_confirmation_template(
            username=username,
            deletion_scheduled_at=deletion_scheduled_at,
        ),
        email_service=email_service,
    )


async def send_security_email(
    *,
    to_address: str,
    username: str,
    event_label: str,
    email_service: EmailService | None = None,
) -> EmailSendResult:
    return await _send_template(
        to_address=to_address,
        template=security_email_template(username=username, event_label=event_label),
        email_service=email_service,
    )
