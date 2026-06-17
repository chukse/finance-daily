"""Local web dashboard: today's brief + search over all history.

Run:  .venv/bin/streamlit run dashboard.py
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

import markdown as md
import pandas as pd
import streamlit as st
import yfinance as yf

from finance_daily import db, search
from finance_daily.config import load_config, db_path

LOGO = Path(__file__).parent / "assets" / "logo.png"

st.set_page_config(page_title="Economics · Market Brief",
                   page_icon=str(LOGO) if LOGO.exists() else "📊", layout="wide")
if LOGO.exists():
    try:
        st.logo(str(LOGO))
    except Exception:
        pass

# ---------------------------------------------------------------- styling
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=DM+Sans:wght@400;500;600;700&display=swap');

:root { --bg:#F3EBDD; --panel:#FBF6EC; --line:#E6D8C4; --ink:#2B2622; --terra:#B0653C;
        --dim:#8A7E70; --up:#4A7C59; --down:#B0493A; }

.stApp { background:
   radial-gradient(820px 460px at 85% -8%, rgba(176,101,60,.10), transparent 60%), var(--bg); }
html, body, [class*="css"], .stMarkdown, p, span, div, li { font-family: 'DM Sans', sans-serif; color: var(--ink); }
.block-container { padding-top: 2rem; max-width: 1150px; }
#MainMenu, footer, header { visibility: hidden; }
h1, h2, h3 { color: var(--ink); }
.stButton button { border-color: var(--terra); color: var(--terra); font-weight: 600; }

/* ---- hero ---- */
.hero-rule { border: none; border-top: 1px solid var(--terra); margin: 14px 0 22px; opacity: .5; }
.kicker { font-size: .72rem; letter-spacing: .3em; text-transform: uppercase; color: var(--terra);
          font-weight: 700; }
.wordmark { font-family:'Fraunces', serif; font-weight: 600; font-size: 2.3rem; line-height: 1.05;
            margin: .15rem 0 0; color: var(--ink); letter-spacing: -.5px; }
.sub { color: var(--dim); font-size: .85rem; margin-top: 6px; font-style: italic; }
.section-label { color: var(--terra); font-size: .7rem; letter-spacing: .16em; text-transform: uppercase;
                 font-weight: 700; margin: 10px 0 4px; }

/* ---- macro tiles ---- */
.tile-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
             gap: 12px; margin: 4px 0 26px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
        padding: 14px 16px; box-shadow: 0 1px 2px rgba(43,38,34,.04);
        transition: transform .12s, box-shadow .12s, border-color .12s; }
.tile:hover { transform: translateY(-2px); border-color: var(--terra);
              box-shadow: 0 6px 18px rgba(176,101,60,.18); }
.tile-label { font-size: .68rem; text-transform: uppercase; letter-spacing: .1em;
              color: var(--dim); font-weight: 700; }
.tile-value { font-family:'Fraunces', serif; font-size: 1.5rem; font-weight: 600;
              color: var(--ink); margin: 5px 0 2px; font-variant-numeric: tabular-nums; }
.tile-change { font-size: .9rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.spark { display:block; width:100%; height:30px; margin-top:9px; }
.up   { color: var(--up); }
.down { color: var(--down); }
.flat { color: var(--dim); }

/* ---- brief card ---- */
.brief { background: var(--panel); border: 1px solid var(--line); border-radius: 16px;
         padding: 8px 34px 26px; box-shadow: 0 1px 3px rgba(43,38,34,.05); }
.brief h1 { display:none; }
.brief h2 { font-family:'Fraunces', serif; font-weight: 600; font-size: 1.3rem; color: var(--ink);
            border-bottom: 1px solid var(--line); padding-bottom: 6px; margin-top: 28px; }
.brief strong { color: var(--terra); }
.brief table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: .92rem; }
.brief th { background: #F1E6D3; text-align: left; padding: 8px 10px; font-weight: 700;
            color: var(--ink); border-bottom: 2px solid var(--line); }
.brief td { padding: 8px 10px; border-bottom: 1px solid #EFE3CE; font-variant-numeric: tabular-nums; }
.brief blockquote { border-left: 3px solid var(--terra); background: rgba(176,101,60,.08);
                    margin:14px 0; padding: 10px 16px; color: var(--ink); border-radius: 0 8px 8px 0; }
.brief hr { border: none; border-top: 1px solid var(--line); margin: 20px 0; }

/* ---- news cards ---- */
.news-card { display:block; background: var(--panel); border:1px solid var(--line); border-radius:12px;
             padding:13px 16px; margin-bottom:10px; text-decoration:none !important;
             transition: border-color .12s, box-shadow .12s; }
.news-card:hover { border-color: var(--terra); box-shadow:0 4px 14px rgba(176,101,60,.14); }
.news-title { color: var(--ink); font-weight:600; font-size:1.0rem; line-height:1.3; }
.news-meta { color: var(--dim); font-size:.76rem; margin-top:7px; }
.badge { background: var(--terra); color:#FBF4E9; padding:2px 9px; border-radius:20px; font-size:.66rem;
         font-weight:700; letter-spacing:.04em; }
.tkr { background: rgba(176,101,60,.14); color:#9A5430; border:1px solid rgba(176,101,60,.4);
       padding:1px 8px; border-radius:20px; font-weight:700; }

/* ---- tabs ---- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
.stTabs [aria-selected="true"] { color: var(--terra) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--terra) !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

cfg = load_config()
conn = db.connect(db_path(cfg))


def _cls(v):
    if v is None:
        return "flat"
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def _arrow(v):
    if v is None:
        return "–"
    return "▲" if v > 0 else ("▼" if v < 0 else "—")


def sparkline_svg(series: list, up: bool) -> str:
    """Tiny inline SVG line chart of an intraday series, colored by direction."""
    pts = [float(v) for v in series if v is not None]
    if len(pts) < 2:
        return ""
    w, h, pad = 120.0, 30.0, 2.0
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1.0
    n = len(pts)
    coords = []
    for i, v in enumerate(pts):
        x = i / (n - 1) * w
        y = (h - pad) - (v - lo) / rng * (h - 2 * pad)
        coords.append(f"{x:.1f},{y:.1f}")
    line = " ".join(coords)
    color = "#4A7C59" if up else "#B0493A"
    fill = "rgba(74,124,89,.12)" if up else "rgba(176,73,58,.12)"
    area = f"0,{h} {line} {w},{h}"
    return (
        f'<svg class="spark" viewBox="0 0 {w:.0f} {h:.0f}" preserveAspectRatio="none">'
        f'<polygon points="{area}" fill="{fill}" stroke="none"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.6" '
        f'vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>'
    )


def macro_tiles(market: dict) -> str:
    tiles = []
    for r in market.get("macro", []):
        cp = r.get("change_pct")
        price = r.get("price")
        pv = f"{price:,.2f}" if isinstance(price, (int, float)) else "n/a"
        chg = f"{_arrow(cp)} {cp:+.2f}%" if cp is not None else "—"
        spark = sparkline_svg(r.get("spark", []), (cp or 0) >= 0)
        tiles.append(
            f'<div class="tile"><div class="tile-label">{html.escape(r["label"])}</div>'
            f'<div class="tile-value">{pv}</div>'
            f'<div class="tile-change {_cls(cp)}">{chg}</div>{spark}</div>'
        )
    return f'<div class="tile-grid">{"".join(tiles)}</div>'


def news_card(r) -> str:
    when = r["published"] or r["collected"]
    tkr = f' &nbsp;<span class="tkr">{html.escape(r["tickers"])}</span>' if r["tickers"] else ""
    return (
        f'<a class="news-card" href="{html.escape(r["url"])}" target="_blank">'
        f'<div class="news-title">{html.escape(r["title"] or "")}</div>'
        f'<div class="news-meta"><span class="badge">{html.escape(r["source"] or "")}</span> '
        f'&nbsp;{html.escape(str(when))}{tkr}</div></a>'
    )


def render_brief(summary_md: str):
    body = md.markdown(summary_md, extensions=["tables", "fenced_code"])
    st.markdown(f'<div class="brief">{body}</div>', unsafe_allow_html=True)


def _download(symbols, period, interval):
    try:
        return yf.download(list(symbols), period=period, interval=interval,
                           auto_adjust=False, progress=False, threads=True,
                           group_by="ticker")
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner="Fetching live prices…")
def live_quotes(symbols: tuple) -> dict:
    """Current quote + intraday sparkline per symbol. Two batched downloads, cached 5 min."""
    out = {s: {"price": None, "change_pct": None, "spark": []} for s in symbols}
    if not symbols:
        return out
    daily = _download(symbols, "5d", "1d")      # price + % vs prior close
    intra = _download(symbols, "1d", "5m")      # intraday line for the sparkline
    multi = len(symbols) > 1

    def col(data, s):
        if data is None:
            return None
        try:
            df = data[s] if multi else data
            return df["Close"].dropna()
        except Exception:
            return None

    for s in symbols:
        rec = out[s]
        close = col(daily, s)
        if close is not None and not close.empty:
            last = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) >= 2 else None
            rec["price"] = last
            rec["change_pct"] = ((last - prev) / prev * 100) if prev else None
        ic = col(intra, s)
        series = [float(x) for x in ic.tolist()] if ic is not None and len(ic) >= 2 else []
        if len(series) < 2 and close is not None:        # fallback to daily closes
            series = [float(x) for x in close.tolist()]
        rec["spark"] = series[-72:]
    return out


# ---------------------------------------------------------------- hero
latest = db.latest_digest(conn)
hero_date = latest["date"] if latest else "—"
hc1, hc2 = st.columns([1, 5], vertical_alignment="center")
with hc1:
    if LOGO.exists():
        st.image(str(LOGO), width=118)
with hc2:
    st.markdown(
        f'<div class="kicker">Economics</div>'
        f'<div class="wordmark">Daily Market Brief</div>'
        f'<div class="sub">Self-updating financial briefing · latest: {hero_date}</div>',
        unsafe_allow_html=True,
    )
st.markdown('<hr class="hero-rule">', unsafe_allow_html=True)

tab_today, tab_search, tab_history, tab_ticker = st.tabs(
    ["  Today's brief  ", "  🔍 Search  ", "  Past briefs  ", "  Ticker history  "]
)

# ---------------- Today's brief ----------------
with tab_today:
    if not latest:
        st.info("No data yet. Run the pipeline:  `.venv/bin/python -m finance_daily.pipeline`")
    else:
        macro_map = cfg.get("macro", {})
        default_watch = cfg.get("watchlist", [])
        macro_syms = tuple(macro_map.keys())

        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("↻ Refresh"):
                st.cache_data.clear()
                st.rerun()
        as_of = datetime.now(timezone.utc).strftime("%b %d · %H:%M UTC")
        with c2:
            st.caption(f"Live prices · as of {as_of} · auto-refreshes every 5 min")

        # macro tiles — live
        q = live_quotes(macro_syms)
        live_macro = {"macro": [{"label": lbl, "symbol": s, **q.get(s, {})}
                                for s, lbl in macro_map.items()]}
        st.markdown(macro_tiles(live_macro), unsafe_allow_html=True)

        # watchlist — user-customizable, saved in the page URL (?wl=...)
        st.markdown('<div class="section-label">Your watchlist · edit anytime</div>',
                    unsafe_allow_html=True)
        if "wl_input" not in st.session_state:
            st.session_state.wl_input = st.query_params.get("wl", ",".join(default_watch))
        wl_text = st.text_input(
            "watchlist", key="wl_input", label_visibility="collapsed",
            placeholder="NVDA, AMD, TSM, AAPL, BTC-USD",
            help="Comma-separated tickers. Crypto needs -USD (e.g. BTC-USD). "
                 "Your list is saved in the page URL — bookmark or share it.",
        )
        my_syms = []
        for t in wl_text.split(","):
            t = t.strip().upper()
            if t and t not in my_syms:
                my_syms.append(t)
        my_syms = my_syms[:30]
        joined = ",".join(my_syms)
        if st.query_params.get("wl") != joined:           # keep the URL in sync, no loop
            st.query_params["wl"] = joined
        if my_syms:
            wq = live_quotes(tuple(my_syms))
            live_wl = {"macro": [{"label": s, "symbol": s, **wq.get(s, {})} for s in my_syms]}
            st.markdown(macro_tiles(live_wl), unsafe_allow_html=True)
            missing = [s for s in my_syms if wq.get(s, {}).get("price") is None]
            if missing:
                st.caption("⚠️ No data for: " + ", ".join(missing)
                           + " — check the symbol (crypto needs -USD, e.g. SOL-USD).")
        else:
            st.caption("Add tickers above to build your watchlist.")

        # daily AI brief — morning snapshot
        st.markdown(f'<div class="section-label">Daily Brief · morning snapshot for '
                    f'{latest["date"]}</div>', unsafe_allow_html=True)
        render_brief(latest["summary_md"])

# ---------------- Search ----------------
with tab_search:
    st.subheader("Search every headline + brief ever collected")
    q = st.text_input("Search", placeholder="e.g. nvidia, rate cut, oil, earnings…",
                      label_visibility="collapsed")
    if q:
        news_hits = search.search_news(conn, q, limit=80)
        st.caption(f"{len(news_hits)} news matches")
        st.markdown("".join(news_card(r) for r in news_hits), unsafe_allow_html=True)
        dig_hits = search.search_digests(conn, q, limit=20)
        if dig_hits:
            st.markdown("---")
            st.caption(f"{len(dig_hits)} brief matches")
            for d in dig_hits:
                with st.expander(f"Brief — {d['date']}"):
                    render_brief(d["summary_md"])

# ---------------- Past briefs ----------------
with tab_history:
    rows = conn.execute("SELECT date, headlines_n FROM digests ORDER BY date DESC LIMIT 120").fetchall()
    if not rows:
        st.info("No briefs yet.")
    for r in rows:
        with st.expander(f"📅  {r['date']}   ·   {r['headlines_n']} headlines"):
            render_brief(db.get_digest(conn, r["date"])["summary_md"])

# ---------------- Ticker history ----------------
with tab_ticker:
    syms = search.list_symbols(conn)
    if not syms:
        st.info("No price history yet.")
    else:
        sym = st.selectbox("Symbol", syms)
        hist = search.price_history(conn, sym, limit=365)
        if hist:
            dfh = pd.DataFrame([dict(r) for r in hist]).sort_values("date")
            dfh["date"] = pd.to_datetime(dfh["date"])
            st.line_chart(dfh.set_index("date")["price"], color="#B0653C", height=320)
            st.dataframe(dfh.set_index("date"), width="stretch")
