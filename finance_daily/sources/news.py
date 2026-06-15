"""News collection from RSS feeds (no API key required)."""
from __future__ import annotations

import re
from datetime import date as _date, datetime
from time import mktime

import feedparser

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _published_iso(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        tm = entry.get(key)
        if tm:
            try:
                return datetime.fromtimestamp(mktime(tm)).isoformat(timespec="seconds")
            except Exception:
                continue
    return None


def collect_news(feeds: list[dict], today: str | None = None,
                 watchlist: list[str] | None = None) -> list[dict]:
    """Fetch all feeds, return deduped article rows ready for db.upsert_news."""
    today = today or _date.today().isoformat()
    watchlist = watchlist or []
    seen: set[str] = set()
    rows: list[dict] = []

    for feed in feeds:
        name, url = feed.get("name", "?"), feed.get("url")
        if not url:
            continue
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for e in parsed.entries:
            link = e.get("link")
            if not link or link in seen:
                continue
            seen.add(link)
            title = _clean(e.get("title"))
            summary = _clean(e.get("summary") or e.get("description"))
            blob = f"{title} {summary}".upper()
            mentioned = [s for s in watchlist
                         if re.search(rf"\b{re.escape(s.split('-')[0])}\b", blob)]
            rows.append({
                "url": link,
                "title": title,
                "summary": summary[:1000],
                "source": name,
                "published": _published_iso(e),
                "collected": today,
                "tickers": ",".join(mentioned) if mentioned else None,
            })
    return rows
