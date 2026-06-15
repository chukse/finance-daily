# Finance Daily

A self-updating financial briefing tool. Every day it pulls prices, macro data,
news headlines, and earnings dates from free sources, stores everything in a local
database (so history never disappears), writes a summarized daily brief, and serves
it all in a searchable web dashboard.

```
collect (yfinance + RSS)  →  store (SQLite + full-text search)  →  summarize (Claude)  →  dashboard + daily .md
```

## What it tracks

- **Watchlist** — your tickers (`config.yaml`): price, % move, volume, market cap.
- **Macro** — S&P, Nasdaq, Dow, Russell, VIX, 10Y yield, dollar, oil, gold, BTC.
- **News** — headlines from Yahoo Finance, CNBC, MarketWatch, Reuters, WSJ, the Fed.
- **Earnings** — next earnings date for each watchlist company.

Everything is **free** and key-free except the AI narrative summary, which uses the
Claude API (cents per day). Without a key, it writes a clean templated brief instead.

## Setup

```bash
cd /home/chuks/finance_daily
# deps already installed in .venv

# (optional) enable AI summaries:
cp .env.example .env      # then paste your ANTHROPIC_API_KEY into .env
```

## Run it

```bash
# one daily collection run (safe to run repeatedly; dedupes news)
.venv/bin/python -m finance_daily.pipeline

# open the dashboard (today's brief + search over all history)
.venv/bin/streamlit run dashboard.py
```

## Automate it (runs every morning)

```bash
bash scripts/install_cron.sh   # installs a 06:30 Mon–Sat cron job
sudo service cron start        # make sure cron is running on WSL
crontab -l                     # verify
```

> WSL must be awake at 06:30 for the local job to fire. To make it fully
> hands-off regardless of your machine, move `run_daily.sh` to a small cloud VM
> or scheduled function — the code is identical.

## Customize

Edit `config.yaml`:
- `watchlist` — your tickers (stocks, ETFs, `BTC-USD`, etc.)
- `macro` — the market-wide instruments shown up top
- `news_feeds` — add/remove any RSS feed
- `summary.model` — Claude model for the brief (default `claude-sonnet-4-6`)

## Where things live

- `data/finance.db` — all history (prices, news, briefs). Back this up.
- `data/digests/YYYY-MM-DD.md` — each day's brief as a plain markdown file (grep-friendly).
- `data/logs/` — daily run logs from cron.
```
