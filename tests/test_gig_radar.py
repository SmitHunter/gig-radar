import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from gig_radar.config import Watchlist
from gig_radar.diff import State, find_alerts
from gig_radar.models import SaleWindow, group_alerts
from gig_radar.notify import body_lines, fmt_date, fmt_dates, title
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
    assert sydney.where == "Qudos Bank Arena, Sydney NSW"
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
    w = Watchlist(artists=[" Fred again.. ", ""], cities=["sydney", "VIC"])
    assert w.artists == ["Fred again.."]
    assert w.countries == ["AU"]
    assert w.wants_place("Sydney", "NSW") and not w.wants_place("Perth", "WA")
    assert w.wants_place("Docklands", "VIC")  # Ticketmaster names the suburb, the state catches it


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


def test_one_message_per_artist_with_linked_shows(events):
    digests = group_alerts(find_alerts(events, State(), remind_hours=24, now=NOW))
    assert len(digests) == 1 and len(digests[0].events) == 2

    embed = Discord("https://discord.test").embed(digests[0])
    assert embed["title"] == "🎤 Fred again..: 2 new shows in NSW, VIC"
    assert "[Sun 14 Feb 2027 · Qudos Bank Arena, Sydney NSW](https://www.ticketmaster.com.au/event/Z7r9jZ1A7jYvA)" in embed["description"]
    assert embed["url"] is None  # several shows: each line carries its own link

    msg = Email("smtp.test", 465, "me@test", "pw", "you@test").build(digests)
    assert msg["Subject"] == "🎤 Fred again..: 2 new shows in NSW, VIC"
    assert "Rod Laver Arena, Melbourne VIC" in msg.get_content()


def test_reminders_group_by_sale_across_shows(events):
    state = State(seen={e.id: e.local_date for e in events})
    twin = parse_event({**FIXTURE["_embedded"]["events"][0], "id": "other-night"}, "Fred again..")
    state.seen[twin.id] = twin.local_date
    digests = group_alerts(find_alerts([events[0], twin], state, remind_hours=24, now=NOW))
    assert len(digests) == 1 and digests[0].kind == "onsale_soon" and len(digests[0].events) == 2
    assert title(digests[0]).startswith("⏰ Fred again..: Artist Presale opens")
    lines = body_lines(digests[0])
    assert len([l for l in lines if l.startswith("📍")]) == 1  # same night + venue shown once


def test_announcement_hides_past_sales_and_says_on_sale_now(events):
    [digest] = group_alerts(find_alerts(events[:1], State(), remind_hours=24, now=NOW))
    mid = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)  # presale passed, public on-sale still ahead
    tickets = [l for l in body_lines(digest, now=mid) if l.startswith("🎟️")]
    assert len(tickets) == 1 and "General on-sale" in tickets[0]
    after = datetime(2026, 11, 1, tzinfo=timezone.utc)
    assert "🎟️ On sale now" in body_lines(digest, now=after)


def test_dates_read_like_people_write_them():
    from datetime import date
    assert fmt_date("2026-12-10", today=date(2026, 10, 18)) == "Thu 10 Dec"
    assert fmt_date("2027-02-19", today=date(2026, 10, 18)) == "Fri 19 Feb 2027"
    assert fmt_date("TBA") == "TBA"
    today = date(2026, 10, 18)
    assert fmt_dates(["2027-09-03", "2027-09-04", "2027-09-06"], today) == "3, 4, 6 Sep 2027"
    assert fmt_dates(["2026-10-29", "2026-10-30", "2026-11-01"], today) == "29, 30 Oct, 1 Nov"
    assert fmt_dates(["2026-12-10", "TBA"], today) == "10 Dec, TBA"


def test_one_line_per_venue_and_sale_times_say_which_state(events):
    sydney, melbourne = events
    second = parse_event({**FIXTURE["_embedded"]["events"][0], "id": "syd-2"}, "Fred again..")
    second.local_date = "2027-02-15"
    # Melbourne opens an hour earlier than Sydney, as split-state on-sales often do
    melbourne.sales = [SaleWindow("General on-sale", sydney.sales[-1].starts_at.replace(hour=22))]
    [digest] = group_alerts(find_alerts([sydney, second, melbourne], State(), remind_hours=24, now=NOW))
    lines = body_lines(digest, now=NOW)
    assert any(l.startswith("📍 14, 15 Feb 2027 · Qudos Bank Arena, Sydney NSW") for l in lines)
    assert [l.split(":")[0] for l in lines if l.startswith("🎟️")] == [
        "🎟️ Artist Presale (NSW)", "🎟️ General on-sale (VIC)", "🎟️ General on-sale (NSW)",
    ]
