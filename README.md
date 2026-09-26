# Metacritic RSS

Unofficial RSS feeds generated from Metacritic's front pages — the same idea as a "webpage to RSS" service, but self-hosted and free.

| Feed | Source |
|------|--------|
| [games.xml](https://infinitty35.github.io/metacritic-rss-muse/games.xml) 🎮 | https://www.metacritic.com/game/ |
| [tv.xml](https://infinitty35.github.io/metacritic-rss-muse/tv.xml) 📺 | https://www.metacritic.com/tv/ |

Paste either URL into any RSS reader (Feedly, Inoreader, NetNewsWire, etc.) to subscribe.

## How it works

1. `scraper.py` fetches both Metacritic front pages and turns every product card into an RSS `<item>`, tagged with its section ("New Releases", "Upcoming Games", …) and Metascore.
2. A GitHub Actions workflow (`.github/workflows/update-feeds.yml`) runs the scraper every 6 hours and commits the fresh feeds to `docs/`.
3. GitHub Pages serves `docs/` — that's the feed URL.

No servers, no API keys, no cost.

## Run it locally

```bash
pip install -r requirements.txt
python scraper.py   # writes docs/games.xml, docs/tv.xml, docs/index.html
```

## Enable Pages (one-time, done at setup)

Repo Settings → Pages → Deploy from a branch → `main`, folder `/docs`.

## Notes

- Not affiliated with Metacritic. For personal use; be kind to their servers (the scraper already pauses between requests).
- If Metacritic changes their page markup, the CSS-class selectors in `scraper.py` (`front-door-game__*`, `product-card`) are the first place to look.
