from __future__ import annotations

import html
import time

import httpx

from gig_radar.models import Digest
from gig_radar.notify import body_lines, title


def html_link(text: str, url: str) -> str:
    return f'<a href="{html.escape(url)}">{text}</a>' if url else text


class Telegram:
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def text(self, d: Digest) -> str:
        lines = [f"<b>{html.escape(title(d))}</b>", *body_lines(d, link=html_link, esc=html.escape)]
        return "\n".join(lines)

    def send(self, digests: list[Digest]) -> None:
        for d in digests:
            r = httpx.post(
                self.url,
                json={
                    "chat_id": self.chat_id,
                    "text": self.text(d),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            r.raise_for_status()
            time.sleep(0.5)
