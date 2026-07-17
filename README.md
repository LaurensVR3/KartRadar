# KartRadar

Karting availability — own-kart and rental — scanned across every venue we can reach.

KartRadar auto-discovers karting venues that run on the [Apex Timing](https://www.apex-timing.com/)
booking platform, works out which of their products are genuine karting sessions
(as opposed to laser tag, bowling, mini golf, or motorcycle track days sold
through the same system), classifies them into own-kart vs. rental and by
racing class, and checks live day-by-day availability for the next few weeks
— so you can scan many tracks at once instead of checking each one's site by
hand.

## How it works

- **Catalog discovery** (`catalog/build_catalog.py`) probes Apex Timing center
  IDs, keeps only centers that show a genuine karting signal, and classifies
  every product (own-kart vs. rental, racing class, price, duration) using a
  set of keyword rules tuned against real venue data. Some venues also run a
  separate calendar-based booking system alongside (or instead of) their
  product catalog — that gets discovered too, and only surfaces as its own
  listing when it actually fills a gap the product catalog doesn't cover.
- **Live availability** (`app/scheduler.py`) refreshes once a day, checking
  every discovered venue's real booking calendar. Visitors to the site read
  from a shared cache — nobody's page load triggers a live upstream request.
- **The site** (`app/`) is a small FastAPI app: one table, filterable by
  country, own-kart vs. rental, and racing class/rental type, with per-venue
  favorites saved in your browser only (no cookies, no tracking).

## Quick start (Docker)

```bash
git clone https://github.com/LaurensVR3/KartRadar.git
cd KartRadar
docker compose up -d --build
```

The `app` service publishes no ports by default — see `docker-compose.override.yml`
for a local-testing override that maps it to `localhost:8090`, or put it
behind your own reverse proxy / tunnel for real deployment (a
[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
setup is what this project is built around — see `.env.example` for the
`cloudflared` steps).

On first run it does a full catalog probe, which takes a few minutes; after
that it refreshes once daily (configurable via `DAILY_REFRESH_HOUR`).

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Default | Meaning |
|---|---|---|
| `DAILY_REFRESH_HOUR` | `0` | Hour (0-23, local time) for the daily catalog rebuild + availability check |
| `DAYS_AHEAD` | `28` | How many days ahead to check availability for |
| `TUNNEL_TOKEN` | — | Cloudflare Tunnel token, only needed if using `cloudflared` |

## Running locally without Docker

```bash
pip install -r requirements.txt
python -m catalog.build_catalog   # first-time catalog build
uvicorn app.main:app --reload
```

## Adding a track that isn't on Apex Timing

`app/providers/` defines a `Provider` interface with `manual` (link-out
placeholder) and `ical` (generic ICS feed) implementations ready to use —
add an entry to `tracks.yaml` following the examples in that file, or write
a new provider for a booking system that needs bespoke scraping.

## Issues

Found a venue that's misclassified, missing, or showing the wrong
availability? Please [open an issue](https://github.com/LaurensVR3/KartRadar/issues)
— include the venue name and what you'd expect to see.

## License

[GPL-3.0](LICENSE)
