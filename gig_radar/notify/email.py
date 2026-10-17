from __future__ import annotations

import smtplib
from email.message import EmailMessage

from gig_radar.models import Alert
from gig_radar.notify import body_lines, title


class Email:
    """One digest email per run, so a big first run doesn't flood your inbox."""

    name = "email"

    def __init__(self, host: str, port: int, user: str, password: str, to: str):
        self.host, self.port, self.user, self.password, self.to = host, port, user, password, to

    def build(self, alerts: list[Alert]) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = title(alerts[0]) if len(alerts) == 1 else f"🎶 gig-radar: {len(alerts)} updates"
        msg["From"] = self.user
        msg["To"] = self.to
        sections = ["\n".join([title(a), *body_lines(a)]) for a in alerts]
        msg.set_content("\n\n".join(sections) + "\n\n— gig-radar")
        return msg

    def send(self, alerts: list[Alert]) -> None:
        with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as smtp:
            smtp.login(self.user, self.password)
            smtp.send_message(self.build(alerts))
