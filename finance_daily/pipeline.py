"""The daily run: collect → store → summarize → write markdown.

Usage:
    python -m finance_daily.pipeline            # run for today
    python -m finance_daily.pipeline --date 2026-06-13
"""
from __future__ import annotations

import argparse
import sys
from datetime import date as _date

from . import db
from .config import load_config, db_path, digests_dir, anthropic_key
from .sources import prices, news, calendar
from .summarize import make_summary


def run(today: str | None = None) -> dict:
    cfg = load_config()
    today = today or _date.today().isoformat()
    conn = db.connect(db_path(cfg))

    log = lambda m: print(f"[{today}] {m}", flush=True)

    # --- collect prices + macro ---
    log("Collecting watchlist prices…")
    wl = prices.collect_watchlist(cfg.get("watchlist", []), today)
    log(f"  {len(wl)} watchlist symbols")
    log("Collecting macro…")
    mc = prices.collect_macro(cfg.get("macro", {}), today)
    log(f"  {len(mc)} macro symbols")
    db.upsert_prices(conn, [dict(r) for r in wl + mc])

    # --- collect news ---
    log("Collecting news feeds…")
    articles = news.collect_news(cfg.get("news_feeds", []), today, cfg.get("watchlist", []))
    new_n = db.upsert_news(conn, articles)
    log(f"  {len(articles)} fetched, {new_n} new")

    # --- earnings calendar ---
    log("Collecting earnings calendar…")
    try:
        cal_rows = calendar.collect_earnings(cfg.get("watchlist", []), today)
        db.upsert_calendar(conn, cal_rows)
        log(f"  {len(cal_rows)} upcoming earnings")
    except Exception as e:
        log(f"  earnings skipped: {e}")

    # --- summarize ---
    market = {"watchlist": wl, "macro": mc}
    # Use today's freshly collected headlines (most recent first) for the brief.
    headlines = sorted(articles, key=lambda a: a.get("published") or "", reverse=True)
    log("Generating summary…" + (" (Claude)" if anthropic_key() else " (templated — no API key)"))
    summary_md = make_summary(today, market, headlines, cfg)
    db.save_digest(conn, today, summary_md, market, len(articles))

    # --- write markdown file ---
    ddir = digests_dir(cfg)
    ddir.mkdir(parents=True, exist_ok=True)
    md_path = ddir / f"{today}.md"
    md_path.write_text(summary_md, encoding="utf-8")
    log(f"Wrote {md_path}")

    conn.close()
    return {"date": today, "watchlist": len(wl), "macro": len(mc),
            "news_new": new_n, "md_path": str(md_path)}


def main():
    ap = argparse.ArgumentParser(description="Finance Daily pipeline")
    ap.add_argument("--date", help="override collection date (YYYY-MM-DD)")
    args = ap.parse_args()
    result = run(args.date)
    print("\nDone:", result, file=sys.stderr)


if __name__ == "__main__":
    main()
