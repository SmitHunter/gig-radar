from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SaleWindow:
    """A moment tickets become available: a presale or the public on-sale."""

    name: str
    starts_at: datetime

    @property
    def key(self) -> str:
        return f"{self.name}@{self.starts_at.isoformat()}"


@dataclass
class Event:
    id: str
    artist: str
    name: str
    url: str
    venue: str
    city: str
    country: str
    state: str
    starts_at: datetime | None
    local_date: str
    sales: list[SaleWindow] = field(default_factory=list)

    @property
    def place(self) -> str:
        """'Docklands VIC': Ticketmaster names suburbs, so the state says where that is."""
        return " ".join(p for p in (self.city, self.state) if p) or self.country

    @property
    def where(self) -> str:
        return ", ".join(p for p in (self.venue, self.place) if p)


@dataclass
class Alert:
    kind: str  # "announced" | "onsale_soon"
    event: Event
    sale: SaleWindow | None = None


@dataclass
class Digest:
    """What one message says: an artist's new shows, or the ticket releases coming up for them."""

    kind: str
    artist: str
    events: list[Event] = field(default_factory=list)
    releases: list[tuple[SaleWindow, Event]] = field(default_factory=list)  # reminders only


def group_alerts(alerts: list[Alert]) -> list[Digest]:
    digests: dict[tuple, Digest] = {}
    for a in alerts:
        d = digests.setdefault((a.kind, a.event.artist), Digest(a.kind, a.event.artist))
        if a.event not in d.events:
            d.events.append(a.event)
        if a.sale:
            d.releases.append((a.sale, a.event))
    return list(digests.values())
