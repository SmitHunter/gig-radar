from __future__ import annotations

import time

import httpx

from gig_radar.models import Alert
from gig_radar.notify import body_lines, title

PURPLE, ORANGE = 0x8B5CF6, 0xF59E0B


class Discord:
    name = "discord"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def embed(self, alert: Alert) -> dict:
        lines = body_lines(alert)
        url = alert.event.url or None
        return {
            "title": title(alert)[:256],
            "url": url,
            "description": "\n".join(l for l in lines if l != url),
            "color": PURPLE if alert.kind == "announced" else ORANGE,
        }

    def send(self, alerts: list[Alert]) -> None:
        # Discord allows 10 embeds per message.
        for i in range(0, len(alerts), 10):
            chunk = alerts[i : i + 10]
            r = httpx.post(
                self.webhook_url,
                json={"username": "gig-radar", "embeds": [self.embed(a) for a in chunk]},
                timeout=20,
            )
            r.raise_for_status()
            time.sleep(1)
