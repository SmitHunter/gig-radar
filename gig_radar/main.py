from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from gig_radar.config import load_watchlist
from gig_radar.diff import State, find_alerts
from gig_radar.notify import body_lines, enabled_notifiers, title
from gig_radar.sources.ticketmaster import Ticketmaster


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gig-radar", description="Get told about gigs before tickets drop.")
    ap.add_argument("--watchlist", default="watchlist.yml")
    ap.add_argument("--state", default="state.json")
    ap.add_argument("--dry-run", action="store_true", help="print alerts, don't send or save")
    args = ap.parse_args(argv)
    # Windows consoles default to cp1252, which can't print the emoji in alerts.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        print("Set TICKETMASTER_API_KEY (free at https://developer.ticketmaster.com)", file=sys.stderr)
        return 2

    watchlist = load_watchlist(args.watchlist)
    state = State.load(args.state)
    state.prune(date.today().isoformat())
    tm = Ticketmaster(api_key)

    events = []
    for artist in watchlist.artists:
        found = [e for e in tm.events_for(artist, watchlist.countries) if watchlist.wants_city(e.city)]
        print(f"{artist}: {len(found)} upcoming show(s)")
        events += found

    alerts = find_alerts(events, state, watchlist.remind_hours_before)
    print(f"{len(alerts)} alert(s)")

    if args.dry_run:
        for a in alerts:
            print("\n" + "\n  ".join([title(a), *body_lines(a)]))
        return 0

    notifiers = enabled_notifiers()
    if alerts and not notifiers:
        print("No notifier configured — add DISCORD_WEBHOOK_URL, TELEGRAM_* or SMTP_* secrets.", file=sys.stderr)
        return 1

    sent, failed = 0, 0
    for n in notifiers if alerts else []:
        try:
            n.send(alerts)
            sent += 1
            print(f"sent via {n.name}")
        except Exception as exc:  # one broken channel shouldn't block the others
            failed += 1
            print(f"{n.name} failed: {exc}", file=sys.stderr)

    # Only remember alerts once at least one channel got them through, so nothing is lost.
    if not alerts or sent:
        state.save(args.state)
    return 1 if failed else 0
