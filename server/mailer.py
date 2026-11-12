"""Pluggable sign-in mail. SMTP when configured. No vendor signup.

Tests install a capture mailer. Production with no sender returns no mailer,
and the auth route fails without issuing a session.
"""
import os
import smtplib
from email.message import EmailMessage

_installed = None


class CaptureMailer:
    def __init__(self):
        self.outbox = []

    def send(self, to, subject, text):
        self.outbox.append({"to": to, "subject": subject, "text": text})


class SmtpMailer:
    def __init__(self, host, port, username, password, from_addr, use_tls):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.use_tls = use_tls

    def send(self, to, subject, text):
        message = EmailMessage()
        message["From"] = self.from_addr
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            smtp.ehlo()
            if self.use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


def install(mailer):
    global _installed
    _installed = mailer


def reset():
    global _installed
    _installed = None


def get_mailer():
    if _installed is not None:
        return _installed
    host = os.environ.get("SMTP_HOST", "").strip()
    from_addr = os.environ.get("SMTP_FROM", "").strip()
    if not host or not from_addr:
        return None
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        return None
    return SmtpMailer(
        host=host,
        port=port,
        username=os.environ.get("SMTP_USERNAME", "").strip(),
        password=os.environ.get("SMTP_PASSWORD", ""),
        from_addr=from_addr,
        use_tls=os.environ.get("SMTP_TLS", "1").strip() != "0",
    )
