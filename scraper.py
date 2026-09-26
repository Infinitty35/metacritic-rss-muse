#!/usr/bin/env python3
"""Scrape Metacritic's Games and TV front pages and publish them as RSS 2.0 feeds.

Mimics what a "webpage to RSS" service does: each product card on the page
becomes one <item> in the feed, tagged with the section it appeared in
(e.g. "New Releases", "Upcoming Games").

Outputs (written under docs/ so GitHub Pages can serve them):
    docs/games.xml   - feed for https://www.metacritic.com/game/
    docs/tv.xml      - feed for https://www.metacritic.com/tv/
    docs/index.html  - landing page linking both feeds

On a fetch or parse failure the existing files are left untouched, so a
failed run never publishes an empty feed.
"""

import re
import sys
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import requests
from bs4 import BeautifulSoup

BASE = "https://www.metacritic.com"
PAGES = {
    "games": f"{BASE}/game/",
    "tv": f"{BASE}/tv/",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 30

# Metacritic score sentiments, used to disambiguate titles ending in numbers
# (e.g. "EA Sports FC 27" with a score of 77).
SENTIMENTS = (
    "Universal Acclaim",
    "Generally Favorable",
    "Mixed or Average",
    "Generally Unfavorable",
    "Overwhelming Dislike",
)
SENTIMENT_RE = re.compile(
    r"^(.*?)\s+(\d+|tbd)\s+(%s)\s*$" % "|".join(SENTIMENTS)
)
TBD_RE = re.compile(r"^(.*?)\s+tbd\s*$", re.IGNORECASE)
CARD_LINK_RE = re.compile(r"^/(game|tv)/[^/]+(/season-[^/]+)?/$")

OUT_DIR = Path(__file__).resolve().parent / "docs"


def parse_card_text(text):
    """Split 'Title 77 Generally Favorable' -> (title, score, sentiment)."""
    text = " ".join(text.split())
    m = SENTIMENT_RE.match(text)
    if m:
        return m.group(1).strip(), m.group(2), m.group(3)
    m = TBD_RE.match(text)
    if m:
        return m.group(1).strip(), "tbd", ""
    return text, "tbd", ""


def scrape(page_key, url):
    """Return (feed_title, [items]); each item is a dict."""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    kind = "game" if page_key == "games" else "tv"
    feed_title = "Metacritic - New Games" if kind == "game" else "Metacritic - New TV Shows"

    items = []
    seen = set()
    section_divs = soup.find_all(
        "div", class_=re.compile(rf"front-door-{kind}__")
    )
    for div in section_divs:
        cards = div.find_all("div", class_="product-card")
        if not cards:
            continue
        heading = div.find(["h2", "h3"])
        section = heading.get_text(" ", strip=True) if heading else "Featured"
        # Strip trailing "See All" link text that lives inside the heading.
        section = re.sub(r"\s*See All\s*$", "", section)
        for card in cards:
            a = card.find("a", href=re.compile(CARD_LINK_RE))
            if not a:
                continue
            href = a["href"]
            if href in seen:
                continue
            seen.add(href)
            title, score, sentiment = parse_card_text(a.get_text(" ", strip=True))
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "link": BASE + href,
                    "score": score,
                    "sentiment": sentiment,
                    "section": section,
                }
            )
    if not items:
        raise RuntimeError(f"no items parsed from {url}")
    return feed_title, items


def build_rss(feed_title, page_url, items):
    now = format_datetime(datetime.now(timezone.utc))
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = feed_title
    SubElement(channel, "link").text = page_url
    SubElement(channel, "description").text = (
        f"Unofficial RSS feed generated from {page_url}"
    )
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = now

    for it in items:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = it["title"]
        SubElement(item, "link").text = it["link"]
        SubElement(item, "guid").text = it["link"]
        SubElement(item, "pubDate").text = now
        SubElement(item, "category").text = it["section"]
        if it["score"] == "tbd":
            desc = f"Metascore: TBD · {it['section']}"
        else:
            desc = f"Metascore: {it['score']}"
            if it["sentiment"]:
                desc += f" — {it['sentiment']}"
            desc += f" · {it['section']}"
        SubElement(item, "description").text = desc

    xml = minidom.parseString(tostring(rss, encoding="unicode")).toprettyxml(
        indent="  ", encoding="UTF-8"
    )
    return xml


def build_index(feeds):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Metacritic RSS Feeds</title>
<link rel="alternate" type="application/rss+xml" title="Metacritic - New Games" href="games.xml">
<link rel="alternate" type="application/rss+xml" title="Metacritic - New TV Shows" href="tv.xml">
<style>
body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 3rem auto; padding: 0 1rem; }}
li {{ margin: 0.75rem 0; }}
small {{ color: #666; }}
</style>
</head>
<body>
<h1>Metacritic RSS Feeds</h1>
<p>Unofficial RSS feeds generated from Metacritic's front pages. Updated every 6 hours.</p>
<ul>
<li><a href="games.xml">🎮 New Games</a> <small>(metacritic.com/game/)</small></li>
<li><a href="tv.xml">📺 New TV Shows</a> <small>(metacritic.com/tv/)</small></li>
</ul>
<p><small>Not affiliated with Metacritic. For personal use.</small></p>
</body>
</html>
"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for key, url in PAGES.items():
        print(f"Scraping {url} ...", flush=True)
        time.sleep(2)  # be polite between requests
        feed_title, items = scrape(key, url)
        print(f"  -> {len(items)} items")
        results[key] = (feed_title, url, items)

    for key, (feed_title, url, items) in results.items():
        (OUT_DIR / f"{key}.xml").write_bytes(build_rss(feed_title, url, items))
        print(f"Wrote docs/{key}.xml")
    (OUT_DIR / "index.html").write_text(
        build_index(results), encoding="utf-8"
    )
    print("Wrote docs/index.html")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never publish a half-built feed
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
