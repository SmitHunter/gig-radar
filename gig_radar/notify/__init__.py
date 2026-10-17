"""Each notifier turns on only when its secrets are set, so you pick channels by adding secrets."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Protocol

from gig_radar.models import Digest, SaleWindow


class Notifier(Protocol):
    name: str

    def send(self, digests: list[Digest]) -> None: ...


def fmt_time(dt: datetime) -> str:
    # Sale times come back in UTC; show them in the runner's TZ (set TZ in the workflow).
    local = dt.astimezone()
    tz = local.strftime("%Z")
    if " " in tz:  # Windows spells zones out ("AUS Eastern Daylight Time"); Linux says "AEDT"
        tz = "".join(w[0] for w in tz.split())
    return local.strftime(f"%a %d %b, %I:%M %p {tz}").replace(" 0", " ").replace(":00 ", " ")


def _year(d: date, today: date) -> str:
    return "" if d.year == today.year else f" {d.year}"


def fmt_date(local_date: str, today: date | None = None) -> str:
    try:
        d = date.fromisoformat(local_date)
    except ValueError:
        return local_date  # "TBA"
    today = today or date.today()
    return d.strftime("%a %d %b").replace(" 0", " ") + _year(d, today)


def fmt_dates(local_dates: list[str], today: date | None = None) -> str:
    """One date reads 'Fri 19 Feb'; a run reads '3, 4, 6 Sep' or '29, 30 Oct, 1 Nov'."""
    if len(local_dates) == 1:
        return fmt_date(local_dates[0], today)
    today = today or date.today()
    known = sorted(date.fromisoformat(x) for x in local_dates if x != "TBA")
    parts: list[str] = []
    for i, d in enumerate(known):
        last_of_month = i + 1 == len(known) or (known[i + 1].year, known[i + 1].month) != (d.year, d.month)
        parts.append(f"{d.day} {d.strftime('%b')}" if last_of_month else str(d.day))
    out = ", ".join(parts) + (_year(known[-1], today) if known else "")
    return out + (", TBA" if len(known) < len(local_dates) else "")


def _states(events) -> str:
    states = list(dict.fromkeys(e.state or e.country for e in events))
    return ", ".join(s for s in states if s)


def title(d: Digest) -> str:
    if d.kind == "onsale_soon":
        sales = _by_sale(d.releases)
        if len(sales) == 1:
            s = sales[0][0]
            return f"⏰ {d.artist}: {s.name} opens {fmt_time(s.starts_at)}"
        return f"⏰ {d.artist}: tickets open soon"
    if len(d.events) == 1:
        return f"🎤 {d.artist}: new show in {d.events[0].place}"
    return f"🎤 {d.artist}: {len(d.events)} new shows in {_states(d.events)}"


def _by_sale(pairs) -> list[tuple[SaleWindow, list]]:
    """Each sale with the shows it covers (on-sale times often differ by state)."""
    found: dict[tuple, tuple[SaleWindow, list]] = {}
    for s, e in pairs:
        found.setdefault((s.name, s.starts_at), (s, []))[1].append(e)
    return sorted(found.values(), key=lambda x: x[0].starts_at)


def plain_link(text: str, url: str) -> str:
    return f"{text}  {url}" if url else text


def body_lines(
    d: Digest,
    now: datetime | None = None,
    link: Callable[[str, str], str] = plain_link,
    esc: Callable[[str], str] = str,
) -> list[str]:
    """Tour name, one line per venue with its dates (linked), then when tickets open."""
    now = now or datetime.now(timezone.utc)
    lines = [esc(d.events[0].name)]

    venues: dict[str, list] = {}
    for e in d.events:
        venues.setdefault(e.where, []).append(e)
    for where, evs in venues.items():
        dates = list(dict.fromkeys(e.local_date for e in evs))  # a "Two Show Pass" shares a night
        lines.append("📍 " + link(esc(f"{fmt_dates(dates)} · {where}"), evs[0].url))

    if d.kind == "onsale_soon":
        upcoming = _by_sale(d.releases)
    else:
        upcoming = _by_sale((s, e) for e in d.events for s in e.sales if s.starts_at > now)
    split = len({_states(evs) for _, evs in upcoming}) > 1
    for s, evs in upcoming:
        where = f" ({_states(evs)})" if split else ""
        lines.append(esc(f"🎟️ {s.name}{where}: {fmt_time(s.starts_at)}"))
    if d.kind == "onsale_soon":
        lines.append("Set an alarm. ⏰")
    elif not upcoming and any(e.sales for e in d.events):
        lines.append("🎟️ On sale now")
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
