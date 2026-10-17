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
    starts_at: datetime | None
    local_date: str
    sales: list[SaleWindow] = field(default_factory=list)

    @property
    def where(self) -> str:
        return ", ".join(p for p in (self.venue, self.city, self.country) if p)


@dataclass
class Alert:
    kind: str  # "announced" | "onsale_soon"
    event: Event
    sale: SaleWindow | None = None
