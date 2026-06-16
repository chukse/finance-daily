"""Local web dashboard: today's brief + search over all history.

Run:  .venv/bin/streamlit run dashboard.py
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

import markdown as md
import pandas as pd
import streamlit as st
import yfinance as yf

from finance_daily import db, search
from finance_daily.config import load_config, db_path

st.set_page_config(page_title="Finance Daily", page_icon="📈", layout="wide")

# ---------------------------------------------------------------- styling
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=DM+Sans:wght@400;500;600;700&display=swap');

:root { --bg:#0B0F14; --panel:#121821; --line:#1E2730; --txt:#D6E0EA; --dim:#6B7A8C;
        --neon:#00E676; --red:#FF4D5E; }

.stApp { background:
   radial-gradient(900px 500px at 80% -10%, rgba(0,230,118,.06), transparent 60%), var(--bg); }
html, body, [class*="css"], .stMarkdown, p, span, div, li { font-family: 'DM Sans', sans-serif; }
.block-container { padding-top: 2rem; max-width: 1150px; }
#MainMenu, footer, header { visibility: hidden; }

/* ---- hero ---- */
.hero { border-bottom: 1px solid var(--line); padding-bottom: 14px; margin-bottom: 22px; }
.hero h1 { font-family:'JetBrains Mono', monospace; font-weight: 800; font-size: 2.3rem;
           line-height: 1; margin: 0; letter-spacing: -1px; color: var(--txt); }
.hero h1 .blink { color: var(--neon); text-shadow: 0 0 12px rgba(0,230,118,.6); }
.hero .kicker { font-family:'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .25em;
                text-transform: uppercase; color: var(--neon); font-weight: 700; margin-bottom: 7px; }
.hero .sub { color: var(--dim); font-size: .85rem; margin-top: 7px;
             font-family:'JetBrains Mono', monospace; }

/* ---- macro tiles ---- */
.tile-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
             gap: 12px; margin: 4px 0 26px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
        padding: 14px 16px; transition: transform .12s, box-shadow .12s, border-color .12s; }
.tile:hover { transform: translateY(-2px); border-color: rgba(0,230,118,.5);
              box-shadow: 0 0 20px rgba(0,230,118,.10); }
.tile-label { font-family:'JetBrains Mono', monospace; font-size: .68rem; text-transform: uppercase;
              letter-spacing: .1em; color: var(--dim); font-weight: 600; }
.tile-value { font-family:'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 700;
              color: var(--txt); margin: 6px 0 2px; }
.tile-change { font-family:'JetBrains Mono', monospace; font-size: .9rem; font-weight: 700; }
.spark { display:block; width:100%; height:30px; margin-top:9px; }
.up   { color: var(--neon); }
.down { color: var(--red); }
.flat { color: var(--dim); }

/* ---- brief card ---- */
.brief { background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
         padding: 8px 34px 26px; }
.brief h1 { display:none; }
.brief h2 { font-family:'JetBrains Mono', monospace; font-weight: 700; font-size: 1.2rem;
            text-transform: uppercase; letter-spacing:.04em; border-bottom: 1px solid var(--line);
            padding-bottom: 7px; margin-top: 28px; color: var(--neon); }
.brief strong { color: var(--neon); }
.brief table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: .9rem;
               font-family:'JetBrains Mono', monospace; }
.brief th { background:#0E141B; text-align: left; padding: 8px 10px; font-weight: 700;
            color: var(--dim); border-bottom: 1px solid var(--line); text-transform:uppercase;
            font-size:.72rem; letter-spacing:.05em; }
.brief td { padding: 8px 10px; border-bottom: 1px solid #161D26; color: var(--txt); }
.brief blockquote { border-left: 3px solid var(--neon); background: rgba(0,230,118,.06);
                    margin:14px 0; padding: 10px 16px; color:#AEEFCB; border-radius: 0 8px 8px 0; }
.brief hr { border: none; border-top: 1px solid var(--line); margin: 20px 0; }

/* ---- news cards ---- */
.news-card { display:block; background: var(--panel); border:1px solid var(--line); border-radius:11px;
             padding:13px 16px; margin-bottom:10px; text-decoration:none !important;
             transition: border-color .12s, box-shadow .12s; }
.news-card:hover { border-color: rgba(0,230,118,.55); box-shadow:0 0 18px rgba(0,230,118,.10); }
.news-title { color: var(--txt); font-weight:600; font-size:1.0rem; line-height:1.3; }
.news-meta { color: var(--dim); font-size:.75rem; margin-top:7px; font-family:'JetBrains Mono', monospace; }
.badge { background: rgba(0,230,118,.15); color: var(--neon); border:1px solid rgba(0,230,118,.4);
         padding:2px 8px; border-radius:6px; font-size:.66rem; font-weight:700; letter-spacing:.04em; }
.tkr { background: rgba(255,77,94,.13); color: var(--red); border:1px solid rgba(255,77,94,.35);
       padding:1px 7px; border-radius:6px; font-weight:700; }

/* ---- tabs ---- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
.stTabs [aria-selected="true"] { color: var(--neon) !important; }
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
    color = "#00E676" if up else "#FF4D5E"
    fill = "rgba(0,230,118,.10)" if up else "rgba(255,77,94,.10)"
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
st.markdown(
    f'<div class="hero"><div class="kicker">Finance Daily · Market Terminal</div>'
    f'<h1>📈 Finance Daily<span class="blink">_</span></h1>'
    f'<div class="sub">// self-updating financial briefing &nbsp;·&nbsp; latest: {hero_date}</div></div>',
    unsafe_allow_html=True,
)

tab_today, tab_search, tab_history, tab_ticker = st.tabs(
    ["  Today's brief  ", "  🔍 Search  ", "  Past briefs  ", "  Ticker history  "]
)

# ---------------- Today's brief ----------------
with tab_today:
    if not latest:
        st.info("No data yet. Run the pipeline:  `.venv/bin/python -m finance_daily.pipeline`")
    else:
        macro_map = cfg.get("macro", {})
        watch = cfg.get("watchlist", [])
        all_syms = tuple(list(macro_map.keys()) + [w for w in watch if w not in macro_map])

        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("↻ Refresh"):
                st.cache_data.clear()
                st.rerun()
        q = live_quotes(all_syms)
        as_of = datetime.now(timezone.utc).strftime("%b %d · %H:%M UTC")
        with c2:
            st.caption(f"🟢 LIVE prices · as of {as_of} · auto-refreshes every 5 min")

        # macro tiles — live
        live_macro = {"macro": [{"label": lbl, "symbol": s, **q.get(s, {})}
                                for s, lbl in macro_map.items()]}
        st.markdown(macro_tiles(live_macro), unsafe_allow_html=True)

        # watchlist — live
        if watch:
            st.markdown('<div style="color:#6B7A8C;font-family:monospace;font-size:.72rem;'
                        'letter-spacing:.1em;text-transform:uppercase;margin:6px 0 2px;">'
                        'Watchlist</div>', unsafe_allow_html=True)
            live_wl = {"macro": [{"label": w, "symbol": w, **q.get(w, {})} for w in watch]}
            st.markdown(macro_tiles(live_wl), unsafe_allow_html=True)

        # AI brief — daily morning snapshot
        st.markdown(f'<div style="color:#6B7A8C;font-family:monospace;font-size:.72rem;'
                    f'letter-spacing:.1em;text-transform:uppercase;margin:18px 0 4px;">'
                    f'AI Brief · morning snapshot for {latest["date"]}</div>',
                    unsafe_allow_html=True)
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
            st.line_chart(dfh.set_index("date")["price"], color="#00E676", height=320)
            st.dataframe(dfh.set_index("date"), width="stretch")
