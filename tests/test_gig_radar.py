import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from gig_radar.config import Watchlist
from gig_radar.diff import State, find_alerts
from gig_radar.notify import body_lines
from gig_radar.notify.discord import Discord
from gig_radar.notify.email import Email
from gig_radar.sources.ticketmaster import Ticketmaster, parse_event

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "events_sample.json").read_text())
NOW = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def events():
    return [parse_event(raw, "Fred again..") for raw in FIXTURE["_embedded"]["events"]]


def test_parse_event_reads_venue_and_sorted_sales(events):
    sydney = events[0]
    assert sydney.where == "Qudos Bank Arena, Sydney, AU"
    assert [s.name for s in sydney.sales] == ["Artist Presale", "General on-sale"]


def test_missing_sale_dates_are_fine(events):
    melbourne = events[1]
    assert melbourne.sales == []
    assert melbourne.starts_at is None
    assert melbourne.local_date == "2027-02-18"


def test_new_shows_are_announced_once(events):
    state = State()
    first = find_alerts(events, state, remind_hours=24, now=NOW)
    assert [a.kind for a in first] == ["announced", "announced"]
    assert find_alerts(events, state, remind_hours=24, now=NOW) == []


def test_reminder_fires_before_presale_for_known_show(events):
    # Show was announced days ago; presale starts in 23h.
    state = State(seen={e.id: e.local_date for e in events})
    alerts = find_alerts(events, state, remind_hours=24, now=NOW)
    assert len(alerts) == 1
    assert alerts[0].kind == "onsale_soon"
    assert alerts[0].sale.name == "Artist Presale"
    # ...and never twice.
    assert find_alerts(events, state, remind_hours=24, now=NOW) == []


def test_public_onsale_reminder_comes_later(events):
    state = State(seen={e.id: e.local_date for e in events})
    later = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)
    alerts = find_alerts(events, state, remind_hours=24, now=later)
    assert [a.sale.name for a in alerts] == ["General on-sale"]


def test_brand_new_show_with_imminent_presale_is_not_double_pinged(events):
    state = State()
    alerts = find_alerts(events[:1], state, remind_hours=24, now=NOW)
    assert [a.kind for a in alerts] == ["announced"]
    assert find_alerts(events[:1], state, remind_hours=24, now=NOW) == []


def test_state_round_trip_and_prune(tmp_path, events):
    state = State()
    find_alerts(events, state, remind_hours=24, now=NOW)
    path = tmp_path / "state.json"
    state.save(path)
    loaded = State.load(path)
    assert loaded.seen == state.seen
    loaded.prune(today="2027-02-16")  # Sydney show has happened, Melbourne hasn't
    assert list(loaded.seen) == ["Z7r9jZ1A7jYvB"]


def test_watchlist_defaults_and_city_filter():
    w = Watchlist(artists=[" Fred again.. ", ""], cities=["sydney"])
    assert w.artists == ["Fred again.."]
    assert w.countries == ["AU"]
    assert w.wants_city("Sydney") and not w.wants_city("Perth")


def test_ticketmaster_matches_exact_artist_name():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/attractions.json"):
            return httpx.Response(200, json={"_embedded": {"attractions": [
                {"id": "wrong", "name": "Muse Tribute Band"},
                {"id": "right", "name": "Muse"},
            ]}})
        assert request.url.params["attractionId"] == "right"
        assert request.url.params["countryCode"] == "AU"
        return httpx.Response(200, json=FIXTURE)

    client = httpx.Client(base_url="https://tm.test", transport=httpx.MockTransport(handler))
    events = Ticketmaster("key", client).events_for("Muse", ["AU"])
    assert len(events) == 2 and events[0].artist == "Muse"


def test_discord_embed_and_email_digest(events):
    alerts = find_alerts(events, State(), remind_hours=24, now=NOW)
    embed = Discord("https://discord.test").embed(alerts[0])
    assert embed["title"].startswith("🎤 New show: Fred again.. — Sydney")
    assert "Artist Presale" in embed["description"]
    assert embed["url"] == events[0].url

    msg = Email("smtp.test", 465, "me@test", "pw", "you@test").build(alerts)
    assert msg["Subject"] == "🎶 gig-radar: 2 updates"
    assert "Rod Laver Arena" in msg.get_content()


def test_announcement_hides_past_sales_and_says_on_sale_now(events):
    alert = find_alerts(events[:1], State(), remind_hours=24, now=NOW)[0]
    mid = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)  # presale passed, public on-sale still ahead
    assert [l for l in body_lines(alert, now=mid) if "🎟️" in l] == [l for l in body_lines(alert, now=mid) if "General" in l]
    after = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert "🎟️ On sale now" in body_lines(alert, now=after)
