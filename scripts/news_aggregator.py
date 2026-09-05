#!/usr/bin/env python3
"""
news_aggregator.py
Recolecta noticias financieras vía RSS (Google News + fuentes generales de mercado)
sin necesidad de API keys. Cubre: mercado general, sectores GICS, cripto y tickers
específicos que se agreguen en config.py.
"""
import feedparser
import requests
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text):
    return _TAG_RE.sub("", text or "").replace("&nbsp;", " ").strip()

HEADERS = {"User-Agent": "Mozilla/5.0 (InvestNewsBot research tool)"}

# Feeds generales de mercado (no requieren query, ya son financieros)
GENERAL_FEEDS = {
    "market_general": [
        "https://news.google.com/rss/search?q=stock+market+OR+wall+street+OR+federal+reserve&hl=en-US&gl=US&ceid=US:en",
        "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",  # MarketWatch top stories
        "https://www.marketwatch.com/rss/topstories",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # WSJ Markets
        "https://www.investing.com/rss/news_25.rss",  # Investing.com stock market news
    ],
}

EU_MARKET_QUERY = "European stock market OR Euro Stoxx OR DAX OR CAC 40 OR IBEX 35"

SECTOR_QUERIES = {
    "tecnologia": "technology stocks OR tech sector earnings",
    "energia": "energy stocks OR oil prices OR renewable energy market",
    "salud": "healthcare stocks OR pharma sector",
    "financiero": "banking sector stocks OR financial sector earnings",
    "consumo": "consumer stocks OR retail sector earnings",
    "industrial": "industrial stocks OR manufacturing sector",
    "materiales": "materials sector stocks OR mining sector",
    "inmobiliario": "real estate sector stocks OR REIT market",
    "utilities": "utilities sector stocks",
    "comunicaciones": "communication services sector stocks OR telecom sector",
    "cripto": "cryptocurrency market OR bitcoin OR ethereum price",
}


def _google_news_rss(query, lang="en-US", country="US"):
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={country}&ceid={country}:{lang.split('-')[0]}"
    return url


def fetch_feed(url, retries=2, timeout=15):
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return feedparser.parse(resp.content)
        except Exception as e:
            if attempt == retries:
                print(f"  [warn] fallo al obtener {url[:80]}: {e}")
        time.sleep(1)
    return None


def _entry_to_item(entry, category, source_label=None):
    published = None
    if getattr(entry, "published_parsed", None):
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    source = source_label
    if not source and getattr(entry, "source", None):
        source = getattr(entry.source, "title", None)
    return {
        "title": entry.get("title", "").strip(),
        "link": entry.get("link", ""),
        "summary": _strip_html(entry.get("summary", ""))[:500],
        "published": published,
        "source": source or "unknown",
        "category": category,
    }


def collect_general_market_news():
    items = []
    for url in GENERAL_FEEDS["market_general"]:
        feed = fetch_feed(url)
        if not feed:
            continue
        for entry in feed.entries[:20]:
            items.append(_entry_to_item(entry, "market_general"))
    # EU market coverage
    feed = fetch_feed(_google_news_rss(EU_MARKET_QUERY))
    if feed:
        for entry in feed.entries[:20]:
            items.append(_entry_to_item(entry, "market_general_eu"))
    return items


def collect_sector_news(sectors=None, max_per_sector=12):
    sectors = sectors or list(SECTOR_QUERIES.keys())
    items = []
    for sector in sectors:
        query = SECTOR_QUERIES.get(sector)
        if not query:
            continue
        feed = fetch_feed(_google_news_rss(query))
        if not feed:
            continue
        for entry in feed.entries[:max_per_sector]:
            items.append(_entry_to_item(entry, f"sector:{sector}"))
    return items


_PLACEHOLDER_TITLE_RE = re.compile(r"(?i)^symbol_*\b")


def _looks_like_placeholder_title(title):
    """Algunas fuentes (visto con páginas de CNN tipo '{symbol} Stock Quote...')
    sirven una plantilla sin interpolar cuando el ticker es poco común, dejando
    literalmente la palabra 'symbol'/'symbol__' en el título en vez del ticker
    real. Se descartan esos casos en vez de mostrarlos tal cual al usuario."""
    t = (title or "").strip()
    return bool(_PLACEHOLDER_TITLE_RE.match(t))


def collect_ticker_news(tickers, max_per_ticker=8):
    items = []
    for ticker in tickers:
        query = f"{ticker} stock"
        feed = fetch_feed(_google_news_rss(query))
        if not feed:
            continue
        for entry in feed.entries[:max_per_ticker]:
            item = _entry_to_item(entry, f"ticker:{ticker}")
            if _looks_like_placeholder_title(item.get("title")):
                continue
            item["ticker"] = ticker
            items.append(item)
    return items


def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = it["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


if __name__ == "__main__":
    print("Probando agregador de noticias...")
    general = collect_general_market_news()
    print(f"Noticias generales de mercado: {len(general)}")
    for it in general[:3]:
        print("  -", it["title"], "|", it["source"])

    sectors = collect_sector_news(["tecnologia", "cripto"], max_per_sector=5)
    print(f"\nNoticias de sectores (tecnologia, cripto): {len(sectors)}")
    for it in sectors[:3]:
        print("  -", it["title"], "|", it["category"])

    tickers = collect_ticker_news(["AAPL"], max_per_ticker=5)
    print(f"\nNoticias de AAPL: {len(tickers)}")
    for it in tickers[:3]:
        print("  -", it["title"])
