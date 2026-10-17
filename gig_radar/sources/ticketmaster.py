"""Ticketmaster Discovery API v2 — free key at https://developer.ticketmaster.com"""

from __future__ import annotations

import time
from datetime import datetime

import httpx

from gig_radar.models import Event, SaleWindow

BASE = "https://app.ticketmaster.com/discovery/v2"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_event(raw: dict, artist: str) -> Event:
    venue = (raw.get("_embedded", {}).get("venues") or [{}])[0]
    start = raw.get("dates", {}).get("start", {})
    sales_raw = raw.get("sales", {})

    sales: list[SaleWindow] = []
    for p in sales_raw.get("presales", []) or []:
        if at := _parse_dt(p.get("startDateTime")):
            sales.append(SaleWindow(p.get("name", "Presale"), at))
    if at := _parse_dt(sales_raw.get("public", {}).get("startDateTime")):
        sales.append(SaleWindow("General on-sale", at))
    sales.sort(key=lambda s: s.starts_at)

    return Event(
        id=raw["id"],
        artist=artist,
        name=raw.get("name", artist),
        url=raw.get("url", ""),
        venue=venue.get("name", "").strip(),
        city=venue.get("city", {}).get("name", "").strip(),
        country=venue.get("country", {}).get("countryCode", ""),
        starts_at=_parse_dt(start.get("dateTime")),
        local_date=start.get("localDate", "TBA"),
        sales=sales,
    )


class Ticketmaster:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client(base_url=BASE, timeout=20)

    def _get(self, path: str, **params) -> dict:
        params["apikey"] = self.api_key
        for attempt in range(3):
            r = self.client.get(path, params=params)
            if r.status_code == 429:  # 5 req/s limit
                time.sleep(1 + attempt)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()
        return {}

    def find_artist_id(self, artist: str) -> str | None:
        """Match the artist to a Ticketmaster attraction so 'Muse' doesn't return museum tours."""
        data = self._get("/attractions.json", keyword=artist, classificationName="music", size=10)
        attractions = data.get("_embedded", {}).get("attractions", [])
        for a in attractions:
            if a.get("name", "").casefold() == artist.casefold():
                return a["id"]
        return attractions[0]["id"] if attractions else None

    def events_for(self, artist: str, countries: list[str]) -> list[Event]:
        attraction_id = self.find_artist_id(artist)
        if not attraction_id:
            return []
        events: list[Event] = []
        for country in countries:
            data = self._get(
                "/events.json",
                attractionId=attraction_id,
                countryCode=country,
                size=100,
                sort="date,asc",
            )
            for raw in data.get("_embedded", {}).get("events", []):
                events.append(parse_event(raw, artist))
        return events
