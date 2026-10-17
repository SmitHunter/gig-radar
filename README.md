<div align="center">

# 📡 gig-radar

**A self-hosted gig alert bot for your Discord, Telegram or inbox.**<br>
New shows from your artists, plus a reminder before every presale. Runs free on GitHub Actions.

[![tests](https://github.com/SmitHunter/gig-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/SmitHunter/gig-radar/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![cost](https://img.shields.io/badge/hosting-%240-22c55e)
![setup](https://img.shields.io/badge/setup-~5%20min-8B5CF6)

<img src="docs/alert-preview.svg" alt="Example gig-radar alerts in Discord: a new show announcement and a presale reminder" width="680">

<sub>Example alerts, shown in Discord. Telegram and email get the same info.</sub>

</div>

---

## The problem

Spotify told me about a gig **after** it had sold out. Good gig apps exist, but they all live inside *their* app or *their* emails, and they get lost among every other notification. I wanted alerts in the places my mates and I already talk, on a schedule I control, from code I can read.

## The fix

You list your artists in one file. A free GitHub Action checks Ticketmaster every 6 hours, and you get **two pings per show**:

| When | Alert |
|---|---|
| 🎤 Show is announced | Artist, venue, city, date, **every presale + on-sale time**, ticket link |
| ⏰ ~24h before tickets open | "Artist Presale opens Thu 5 Nov, 9:00 AM. Set an alarm." |

No server, no app, no database. You're never told twice about the same thing.

## Setup (about 5 minutes)

**1. Fork this repo**, then open the **Actions** tab and click *"I understand my workflows, go ahead and enable them"*.

**2. Edit [`watchlist.yml`](watchlist.yml)**, right on GitHub:

```yaml
artists:
  - Fred again..
  - Tame Impala
countries: [AU]        # or NZ, GB, US, ... as many as you like
cities: []             # optional, e.g. [Sydney, Melbourne]
remind_hours_before: 24
```

**3. Add secrets** in *Settings → Secrets and variables → Actions*:

| Secret | Where to get it |
|---|---|
| `TICKETMASTER_API_KEY` | **Required.** Free at [developer.ticketmaster.com](https://developer.ticketmaster.com/): sign up, then copy the *Consumer Key* |
| `DISCORD_WEBHOOK_URL` | Discord channel → *Edit Channel → Integrations → Webhooks → New Webhook → Copy URL* |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Make a bot with [@BotFather](https://t.me/BotFather), message it once, then read your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates` |
| `SMTP_HOST` `SMTP_USER` `SMTP_PASSWORD` `EMAIL_TO` | Gmail: `smtp.gmail.com` + an [app password](https://myaccount.google.com/apppasswords). `SMTP_PORT` is optional (default 465) |

Add only the channels you want; each one turns on when its secrets are set.

**Test it:** Actions → **watch** → **Run workflow**. Your first alerts land within a minute.

> 🕐 Alert times default to Sydney time. Change it under *Variables*: add `TIMEZONE`, e.g. `Pacific/Auckland` or `Europe/London`.

## How it works

```mermaid
flowchart LR
    A[⏱ GitHub Action<br/>every 6h] --> B[watchlist.yml]
    B --> C[Ticketmaster<br/>Discovery API]
    C --> D{New show?<br/>Sale opening soon?}
    S[(state.json<br/>on the state branch)] <--> D
    D -->|yes| E[Discord]
    D -->|yes| F[Telegram]
    D -->|yes| G[Email digest]
```

1. **Find the artist, not the keyword.** Each name is matched to a Ticketmaster *attraction* first, so a search for "Muse" doesn't return museum tours.
2. **Normalise.** Every presale and the public on-sale become a sorted list of `SaleWindow`s.
3. **Diff against memory.** `state.json` records the shows and reminders already sent. It lives on a separate `state` branch, so `main` stays clean and forks start fresh.
4. **Notify, then remember.** State is saved only once at least one channel delivered, so a Discord outage never loses an alert.

```
gig_radar/
├── config.py               # watchlist.yml → validated settings (pydantic)
├── sources/ticketmaster.py # API client: artist match, events, sale windows
├── diff.py                 # what's new / what's opening soon + state
├── notify/                 # discord · telegram · email (auto-enabled by secrets)
└── main.py                 # fetch → diff → notify → save
```

## Why not just use an existing app?

Honestly, for most people one of these is enough:

- **[Whatslively](https://whatslively.com/)** (Australia): reads your Spotify/Apple Music, covers Ticketek, Ticketmaster, Moshtix and Oztix, and pings you before on-sales. If you're in Australia and want an app, start there.
- **Bandsintown / Songkick**: follow artists, get alerted when they announce shows near you.
- **Ticketmaster Favourites**: alerts for new shows and on-sales, Ticketmaster events only.

gig-radar is for when you want something different:

| | gig-radar | Gig apps |
|---|:-:|:-:|
| Alerts land in **your Discord server or Telegram group**, so mates see them together | ✅ | ❌ |
| You own it: open source, self-hosted, no account, no tracking, $0 | ✅ | ❌ |
| Set your own rules: countries, cities, how early to remind | ✅ | partly |
| Hackable: add a source or channel in one small Python file | ✅ | ❌ |
| Covers every Australian ticket site | ❌ Ticketmaster only (see Limits) | ✅ Whatslively |

## Run it locally

```bash
git clone https://github.com/SmitHunter/gig-radar && cd gig-radar
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

pytest                                   # 10 tests, no network needed
TICKETMASTER_API_KEY=xxx python -m gig_radar --dry-run   # print alerts, send nothing
```

## Limits (honest ones)

- **Ticketmaster only.** Ticketek and Oztix only give API access to approved partners, and I found no public Moshtix API. gig-radar uses official APIs only and doesn't scrape, so shows sold only through those sites won't appear. If you get partner access, adding a source is one file in `gig_radar/sources/`.
- **Presale codes aren't in the API.** You get the presale *time*; the code still comes from the artist's mailing list. Sign up there too.
- Free API key: 5,000 calls/day. 20 artists checked every 6h uses about 160.
- GitHub pauses scheduled workflows in repos with no activity for 60 days. It emails you first, and one click turns them back on.

## Roadmap

- [ ] More sources, where an official API allows it
- [ ] `.ics` calendar feed of every on-sale time
- [ ] "Similar artists touring near you" from your Spotify top artists

## License

MIT. Fork it, break it, catch the gig.
