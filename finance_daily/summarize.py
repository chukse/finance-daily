"""Daily narrative summary. Uses Claude when ANTHROPIC_API_KEY is set,
otherwise falls back to a clean templated summary so the app always works.
"""
from __future__ import annotations

from .config import anthropic_key

SYSTEM = (
    "You are a sharp financial-markets analyst writing a concise daily brief for "
    "an informed reader. Be specific and quantitative. Lead with the single most "
    "important thing that happened. Group related moves. Note what's driving them "
    "when the headlines make it clear. Avoid hype and disclaimers. Use short "
    "markdown sections. Do not give investment advice."
)


def _fmt_pct(v):
    if v is None:
        return "n/a"
    return f"{v:+.2f}%"


def _market_lines(market: dict) -> str:
    lines = []
    for row in market.get("macro", []):
        lines.append(f"- {row['label']} ({row['symbol']}): {row.get('price')} ({_fmt_pct(row.get('change_pct'))})")
    lines.append("")
    lines.append("Watchlist:")
    for row in market.get("watchlist", []):
        lines.append(f"- {row['symbol']}: {row.get('price')} ({_fmt_pct(row.get('change_pct'))})")
    return "\n".join(lines)


def _headline_lines(headlines: list[dict], limit: int) -> str:
    out = []
    for h in headlines[:limit]:
        src = h.get("source", "")
        out.append(f"- [{src}] {h.get('title','')}")
    return "\n".join(out)


def templated_summary(date: str, market: dict, headlines: list[dict]) -> str:
    macro = market.get("macro", [])
    movers = sorted(
        [r for r in market.get("watchlist", []) if r.get("change_pct") is not None],
        key=lambda r: abs(r["change_pct"]), reverse=True,
    )
    up = [m for m in movers if m["change_pct"] > 0][:3]
    down = [m for m in movers if m["change_pct"] < 0][:3]

    parts = [f"# Daily Market Brief — {date}", "", "## Market snapshot"]
    for r in macro:
        parts.append(f"- **{r['label']}**: {_fmt_pct(r.get('change_pct'))}")
    parts.append("")
    parts.append("## Notable watchlist moves")
    if up:
        parts.append("**Up:** " + ", ".join(f"{m['symbol']} {_fmt_pct(m['change_pct'])}" for m in up))
    if down:
        parts.append("**Down:** " + ", ".join(f"{m['symbol']} {_fmt_pct(m['change_pct'])}" for m in down))
    parts.append("")
    parts.append("## Top headlines")
    for h in headlines[:12]:
        parts.append(f"- [{h.get('source','')}] {h.get('title','')}")
    parts.append("")
    parts.append("_Templated summary (no ANTHROPIC_API_KEY set — add one for an AI narrative)._")
    return "\n".join(parts)


def claude_summary(date: str, market: dict, headlines: list[dict],
                   model: str, max_headlines: int) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    user = (
        f"Date: {date}\n\n"
        f"MARKET DATA\n{_market_lines(market)}\n\n"
        f"HEADLINES (most recent first)\n{_headline_lines(headlines, max_headlines)}\n\n"
        "Write the daily brief now. Sections: a one-line TL;DR, '## What moved markets', "
        "'## Watchlist', '## Stories worth knowing'. Keep it tight."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    body = "".join(block.text for block in resp.content if block.type == "text")
    return f"# Daily Market Brief — {date}\n\n{body}"


def make_summary(date: str, market: dict, headlines: list[dict], cfg: dict) -> str:
    scfg = cfg.get("summary", {})
    if anthropic_key():
        try:
            return claude_summary(
                date, market, headlines,
                model=scfg.get("model", "claude-sonnet-4-6"),
                max_headlines=scfg.get("max_headlines", 60),
            )
        except Exception as e:
            return templated_summary(date, market, headlines) + f"\n\n> _AI summary failed: {e}_"
    return templated_summary(date, market, headlines)
