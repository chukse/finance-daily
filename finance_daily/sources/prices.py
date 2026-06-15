"""Price + macro snapshots via yfinance (no API key required).

One efficient batched download per group, then per-symbol fast_info/info for
stats. Designed to degrade gracefully — a missing symbol is skipped, not fatal.
"""
from __future__ import annotations

import math
from datetime import date as _date

import yfinance as yf


def _safe(v):
    """Coerce NaN/inf to None so SQLite stores clean nulls."""
    if v is None:
        return None
    try:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
    except (TypeError, ValueError):
        return None
    return v


def _snapshot(symbol: str, label: str | None, kind: str, today: str) -> dict | None:
    """Pull a single symbol's latest snapshot. Returns None on hard failure."""
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        last = hist.iloc[-1]
        price = float(last["Close"])
        prev_close = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else None
        change_pct = ((price - prev_close) / prev_close * 100.0) if prev_close else None

        market_cap = None
        try:
            fi = t.fast_info
            market_cap = _safe(getattr(fi, "market_cap", None))
        except Exception:
            pass

        return {
            "symbol": symbol,
            "date": today,
            "label": label,
            "kind": kind,
            "price": _safe(price),
            "prev_close": _safe(prev_close),
            "change_pct": _safe(change_pct),
            "volume": int(last["Volume"]) if not math.isnan(last.get("Volume", float("nan"))) else None,
            "day_high": _safe(float(last["High"])),
            "day_low": _safe(float(last["Low"])),
            "market_cap": market_cap,
            "extra_json": None,
        }
    except Exception:
        return None


def collect_watchlist(symbols: list[str], today: str | None = None) -> list[dict]:
    today = today or _date.today().isoformat()
    out = []
    for s in symbols:
        snap = _snapshot(s, None, "watchlist", today)
        if snap:
            out.append(snap)
    return out


def collect_macro(macro_map: dict[str, str], today: str | None = None) -> list[dict]:
    today = today or _date.today().isoformat()
    out = []
    for sym, label in macro_map.items():
        snap = _snapshot(sym, label, "macro", today)
        if snap:
            out.append(snap)
    return out
