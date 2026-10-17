from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class Watchlist(BaseModel):
    artists: list[str] = Field(min_length=1)
    countries: list[str] = Field(default_factory=lambda: ["AU"])
    cities: list[str] = Field(default_factory=list)
    remind_hours_before: int = Field(default=24, ge=1, le=168)

    @field_validator("artists")
    @classmethod
    def strip_artists(cls, v: list[str]) -> list[str]:
        return [a.strip() for a in v if a.strip()]

    @field_validator("countries")
    @classmethod
    def upper_countries(cls, v: list[str]) -> list[str]:
        return [c.strip().upper() for c in v]

    def wants_place(self, city: str, state: str) -> bool:
        """Match a city/suburb or a state code, so 'VIC' catches Docklands and Melbourne."""
        if not self.cities:
            return True
        wanted = {c.casefold() for c in self.cities}
        return city.casefold() in wanted or state.casefold() in wanted


def load_watchlist(path: str | Path = "watchlist.yml") -> Watchlist:
    with open(path, encoding="utf-8") as f:
        return Watchlist.model_validate(yaml.safe_load(f) or {})
