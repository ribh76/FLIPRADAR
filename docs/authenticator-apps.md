# MFA authenticator support

FlipRadar currently supports email-based MFA: an 8-digit one-time code is sent through the configured SMTP provider, then paired with one of the user's configured security questions.

No third-party authenticator applications are supported in this release. Google Authenticator, Microsoft Authenticator, Authy, 1Password, and similar TOTP apps cannot be enrolled yet; do not present them as supported in product UI.

If access to the email factor is lost, use the MFA reset flow. It sends a one-time reset link to the verified account email, disables MFA, invalidates pending MFA challenges and active refresh sessions, and notifies the account holder.
