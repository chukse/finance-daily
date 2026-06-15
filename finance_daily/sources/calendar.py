"""Earnings calendar for watchlist names via yfinance (no API key required).

Pulls the next scheduled earnings date per watchlist ticker. Economic-calendar
data (CPI, FOMC, jobs) needs a keyed provider; we surface those via the Fed RSS
feed in news instead, and this module stays key-free.
"""
from __future__ import annotations

from datetime import date as _date

import yfinance as yf


def collect_earnings(symbols: list[str], today: str | None = None) -> list[dict]:
    today = today or _date.today().isoformat()
    rows: list[dict] = []
    for s in symbols:
        try:
            t = yf.Ticker(s)
            cal = t.get_earnings_dates(limit=8)
            if cal is None or cal.empty:
                continue
            future = cal[cal.index.date >= _date.today()]
            if future.empty:
                continue
            next_dt = future.index.min()
            est = future.loc[next_dt].get("EPS Estimate")
            detail = f"EPS estimate: {est}" if est is not None else ""
            rows.append({
                "date": next_dt.date().isoformat(),
                "symbol": s,
                "kind": "earnings",
                "title": f"{s} earnings",
                "detail": detail,
                "collected": today,
            })
        except Exception:
            continue
    return rows
