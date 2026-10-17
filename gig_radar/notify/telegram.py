from __future__ import annotations

import html
import time

import httpx

from gig_radar.models import Alert
from gig_radar.notify import body_lines, title


class Telegram:
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def text(self, alert: Alert) -> str:
        lines = [f"<b>{html.escape(title(alert))}</b>"]
        lines += [html.escape(l) for l in body_lines(alert)]
        return "\n".join(lines)

    def send(self, alerts: list[Alert]) -> None:
        for alert in alerts:
            r = httpx.post(
                self.url,
                json={"chat_id": self.chat_id, "text": self.text(alert), "parse_mode": "HTML"},
                timeout=20,
            )
            r.raise_for_status()
            time.sleep(0.5)
