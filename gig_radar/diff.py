"""Decide what's worth telling you about, and remember it so you're only told once."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gig_radar.models import Alert, Event


class State:
    def __init__(self, seen: dict[str, str] | None = None, reminded: set[str] | None = None):
        self.seen = seen or {}  # event id -> event date (for pruning)
        self.reminded = reminded or set()  # "event_id|sale_key"

    @classmethod
    def load(cls, path: str | Path) -> State:
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(data.get("seen", {}), set(data.get("reminded", [])))

    def save(self, path: str | Path) -> None:
        data = {"seen": dict(sorted(self.seen.items())), "reminded": sorted(self.reminded)}
        Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def prune(self, today: str) -> None:
        """Forget shows that have already happened so the file doesn't grow forever."""
        gone = {eid for eid, date in self.seen.items() if date != "TBA" and date < today}
        self.seen = {k: v for k, v in self.seen.items() if k not in gone}
        self.reminded = {r for r in self.reminded if r.split("|", 1)[0] not in gone}


def find_alerts(
    events: list[Event],
    state: State,
    remind_hours: int,
    now: datetime | None = None,
) -> list[Alert]:
    now = now or datetime.now(timezone.utc)
    window_end = now + timedelta(hours=remind_hours)
    alerts: list[Alert] = []

    for event in events:
        is_new = event.id not in state.seen
        if is_new:
            alerts.append(Alert("announced", event))
            state.seen[event.id] = event.local_date

        for sale in event.sales:
            reminder_key = f"{event.id}|{sale.key}"
            if reminder_key in state.reminded or not (now < sale.starts_at <= window_end):
                continue
            state.reminded.add(reminder_key)
            # A brand-new show already lists its sale times, so skip the duplicate ping.
            if not is_new:
                alerts.append(Alert("onsale_soon", event, sale))

    return alerts
