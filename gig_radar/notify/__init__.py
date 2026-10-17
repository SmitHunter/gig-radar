"""Each notifier turns on only when its secrets are set, so you pick channels by adding secrets."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Protocol

from gig_radar.models import Alert


class Notifier(Protocol):
    name: str

    def send(self, alerts: list[Alert]) -> None: ...


def fmt_time(dt: datetime) -> str:
    # Sale times come back in UTC; show them in the runner's TZ (set TZ in the workflow).
    return dt.astimezone().strftime("%a %d %b, %I:%M %p %Z").replace(" 0", " ")


def title(alert: Alert) -> str:
    e = alert.event
    if alert.kind == "announced":
        return f"🎤 New show: {e.artist} — {e.city or e.country} ({e.local_date})"
    return f"⏰ Tickets soon: {e.artist} — {alert.sale.name} {fmt_time(alert.sale.starts_at)}"


def body_lines(alert: Alert) -> list[str]:
    e = alert.event
    lines = [f"{e.name}", f"📍 {e.where}", f"📅 {e.local_date}"]
    upcoming = e.sales if alert.kind == "announced" else [alert.sale]
    for s in upcoming:
        lines.append(f"🎟️ {s.name}: {fmt_time(s.starts_at)}")
    if e.url:
        lines.append(e.url)
    return lines


def enabled_notifiers() -> list[Notifier]:
    from gig_radar.notify.discord import Discord
    from gig_radar.notify.email import Email
    from gig_radar.notify.telegram import Telegram

    env = os.environ
    found: list[Notifier] = []
    if url := env.get("DISCORD_WEBHOOK_URL"):
        found.append(Discord(url))
    if (token := env.get("TELEGRAM_BOT_TOKEN")) and (chat := env.get("TELEGRAM_CHAT_ID")):
        found.append(Telegram(token, chat))
    if all(env.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO")):
        found.append(
            Email(
                host=env["SMTP_HOST"],
                port=int(env.get("SMTP_PORT") or 465),
                user=env["SMTP_USER"],
                password=env["SMTP_PASSWORD"],
                to=env["EMAIL_TO"],
            )
        )
    return found
