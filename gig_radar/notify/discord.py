from __future__ import annotations

import time

import httpx

from gig_radar.models import Digest
from gig_radar.notify import body_lines, title

PURPLE, ORANGE = 0x8B5CF6, 0xF59E0B


def md_link(text: str, url: str) -> str:
    return f"[{text}]({url})" if url else text


class Discord:
    name = "discord"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def embed(self, d: Digest) -> dict:
        return {
            "title": title(d)[:256],
            "url": d.events[0].url if len(d.events) == 1 and d.events[0].url else None,
            "description": "\n".join(body_lines(d, link=md_link))[:4096],
            "color": PURPLE if d.kind == "announced" else ORANGE,
        }

    def send(self, digests: list[Digest]) -> None:
        # Discord allows 10 embeds per message.
        for i in range(0, len(digests), 10):
            chunk = digests[i : i + 10]
            r = httpx.post(
                self.webhook_url,
                json={"username": "gig-radar", "embeds": [self.embed(d) for d in chunk]},
                timeout=20,
            )
            r.raise_for_status()
            time.sleep(1)
