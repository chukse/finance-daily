"""Search across all stored history — news (full-text), digests, and prices."""
from __future__ import annotations

import sqlite3


def search_news(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[sqlite3.Row]:
    """Full-text search over every headline ever collected."""
    q = query.strip()
    if not q:
        return []
    try:
        return conn.execute(
            """SELECT n.title, n.summary, n.source, n.url, n.published, n.collected, n.tickers
               FROM news_fts f JOIN news n ON n.rowid = f.rowid
               WHERE news_fts MATCH ?
               ORDER BY COALESCE(n.published, n.collected) DESC
               LIMIT ?""",
            (q, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # Fall back to LIKE if the query has FTS-special characters.
        like = f"%{q}%"
        return conn.execute(
            """SELECT title, summary, source, url, published, collected, tickers
               FROM news WHERE title LIKE ? OR summary LIKE ?
               ORDER BY COALESCE(published, collected) DESC LIMIT ?""",
            (like, like, limit),
        ).fetchall()


def search_digests(conn: sqlite3.Connection, query: str, limit: int = 30) -> list[sqlite3.Row]:
    like = f"%{query.strip()}%"
    return conn.execute(
        """SELECT date, summary_md FROM digests
           WHERE summary_md LIKE ? ORDER BY date DESC LIMIT ?""",
        (like, limit),
    ).fetchall()


def price_history(conn: sqlite3.Connection, symbol: str, limit: int = 365) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT date, price, change_pct, volume FROM prices
           WHERE symbol = ? ORDER BY date DESC LIMIT ?""",
        (symbol.upper(), limit),
    ).fetchall()


def list_symbols(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol").fetchall()
    return [r["symbol"] for r in rows]
