"""SQLite storage + full-text search. All history lives here, forever.

Tables
------
prices   : one row per (symbol, date) snapshot — price, % change, volume, stats.
news     : one row per article (deduped by URL), with published date.
digests  : one row per day — the narrative summary + raw market JSON blob.
news_fts : FTS5 virtual table mirroring news(title, summary) for fast search.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,            -- YYYY-MM-DD (collection date)
    label       TEXT,                     -- friendly name (macro) or NULL
    kind        TEXT,                     -- 'watchlist' | 'macro'
    price       REAL,
    prev_close  REAL,
    change_pct  REAL,
    volume      INTEGER,
    day_high    REAL,
    day_low     REAL,
    market_cap  REAL,
    extra_json  TEXT,                     -- arbitrary extra stats
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS news (
    url          TEXT PRIMARY KEY,
    title        TEXT,
    summary      TEXT,
    source       TEXT,
    published    TEXT,                    -- ISO timestamp if known
    collected    TEXT NOT NULL,           -- YYYY-MM-DD we first saw it
    tickers      TEXT                     -- comma-joined symbols mentioned
);

CREATE TABLE IF NOT EXISTS digests (
    date        TEXT PRIMARY KEY,         -- YYYY-MM-DD
    summary_md  TEXT,                     -- the narrative (markdown)
    market_json TEXT,                     -- snapshot of prices/macro that day
    headlines_n INTEGER,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS calendar (
    date        TEXT NOT NULL,            -- event date YYYY-MM-DD
    symbol      TEXT,
    kind        TEXT,                     -- 'earnings' | 'economic'
    title       TEXT,
    detail      TEXT,
    collected   TEXT NOT NULL,
    PRIMARY KEY (date, symbol, title)
);

CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
    title, summary, source UNINDEXED, url UNINDEXED, published UNINDEXED,
    content='news', content_rowid='rowid'
);

-- Keep the FTS index in sync with the news table.
CREATE TRIGGER IF NOT EXISTS news_ai AFTER INSERT ON news BEGIN
    INSERT INTO news_fts(rowid, title, summary, source, url, published)
    VALUES (new.rowid, new.title, new.summary, new.source, new.url, new.published);
END;
CREATE TRIGGER IF NOT EXISTS news_ad AFTER DELETE ON news BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, summary) VALUES('delete', old.rowid, old.title, old.summary);
END;
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA)
    return conn


def upsert_prices(conn: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
    INSERT INTO prices (symbol, date, label, kind, price, prev_close, change_pct,
                        volume, day_high, day_low, market_cap, extra_json)
    VALUES (:symbol, :date, :label, :kind, :price, :prev_close, :change_pct,
            :volume, :day_high, :day_low, :market_cap, :extra_json)
    ON CONFLICT(symbol, date) DO UPDATE SET
        price=excluded.price, prev_close=excluded.prev_close,
        change_pct=excluded.change_pct, volume=excluded.volume,
        day_high=excluded.day_high, day_low=excluded.day_low,
        market_cap=excluded.market_cap, extra_json=excluded.extra_json;
    """
    for r in rows:
        r.setdefault("extra_json", None)
        if isinstance(r.get("extra_json"), (dict, list)):
            r["extra_json"] = json.dumps(r["extra_json"])
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def upsert_news(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert new articles only (dedupe by URL). Returns count of NEW rows."""
    sql = """
    INSERT OR IGNORE INTO news (url, title, summary, source, published, collected, tickers)
    VALUES (:url, :title, :summary, :source, :published, :collected, :tickers);
    """
    before = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    conn.executemany(sql, rows)
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    return after - before


def upsert_calendar(conn: sqlite3.Connection, rows: list[dict]) -> int:
    sql = """
    INSERT OR REPLACE INTO calendar (date, symbol, kind, title, detail, collected)
    VALUES (:date, :symbol, :kind, :title, :detail, :collected);
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def save_digest(conn: sqlite3.Connection, date: str, summary_md: str,
                market: dict, headlines_n: int) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO digests (date, summary_md, market_json, headlines_n, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (date, summary_md, json.dumps(market), headlines_n, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def get_digest(conn: sqlite3.Connection, date: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM digests WHERE date = ?", (date,)).fetchone()


def latest_digest(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM digests ORDER BY date DESC LIMIT 1").fetchone()
