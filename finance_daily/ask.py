"""Natural-language Q&A over markets — Claude with live-data tools.

The model interprets a question (e.g. "which AI chip makers are doing well?"),
decides which tickers are relevant, calls get_quotes / search_news to ground
itself in real current data, then answers.
"""
from __future__ import annotations

import json

import yfinance as yf

from .search import search_news as _search_news

SYSTEM = (
    "You are a sharp markets analyst answering a user's question. Work from REAL "
    "data, not memory: when a question is about how companies/assets are performing, "
    "use the get_quotes tool to pull current prices and recent moves before answering. "
    "You decide which tickers are relevant — e.g. for 'AI chip makers' consider NVDA, "
    "AMD, TSM, AVGO, MU, ARM, INTC, QCOM. Use search_news to ground claims about "
    "recent events. Then give a concise, specific answer in markdown: lead with a "
    "direct answer, then a short ranked list or table with the actual numbers you "
    "fetched. Be quantitative. Do not give investment advice or price predictions; "
    "describe what the data shows. If a ticker returns no data, say so briefly."
)

TOOLS = [
    {
        "name": "get_quotes",
        "description": (
            "Get current price and recent performance for one or more tickers "
            "(stocks, ETFs, crypto like BTC-USD). Returns latest price and % change "
            "over 1 day, 5 days, and 1 month. Use this to judge how things are doing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ticker symbols, e.g. ['NVDA','AMD','TSM']",
                }
            },
            "required": ["symbols"],
        },
    },
    {
        "name": "search_news",
        "description": (
            "Full-text search the local database of financial news headlines "
            "collected over recent days. Use to find what's been reported about a "
            "company, sector, or theme."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


def _get_quotes(symbols: list[str]) -> dict:
    symbols = [s.strip().upper() for s in symbols if s.strip()][:25]
    if not symbols:
        return {"error": "no symbols"}
    try:
        data = yf.download(symbols, period="1mo", interval="1d", auto_adjust=False,
                           progress=False, threads=True, group_by="ticker")
    except Exception as e:
        return {"error": str(e)}
    multi = len(symbols) > 1
    out = {}
    for s in symbols:
        try:
            close = (data[s] if multi else data)["Close"].dropna()
            if close.empty:
                out[s] = {"error": "no data"}
                continue
            last = float(close.iloc[-1])

            def pct(n):
                if len(close) > n:
                    base = float(close.iloc[-n - 1])
                    return round((last - base) / base * 100, 2) if base else None
                return None

            first = float(close.iloc[0])
            out[s] = {
                "price": round(last, 2),
                "chg_1d_pct": pct(1),
                "chg_5d_pct": pct(5),
                "chg_1mo_pct": round((last - first) / first * 100, 2) if first else None,
            }
        except Exception:
            out[s] = {"error": "no data"}
    return out


def _run_tool(name: str, inp: dict, conn) -> object:
    if name == "get_quotes":
        return _get_quotes(inp.get("symbols", []))
    if name == "search_news":
        rows = _search_news(conn, inp.get("query", ""), limit=15)
        return [
            {"title": r["title"], "source": r["source"],
             "date": r["published"] or r["collected"]}
            for r in rows
        ]
    return {"error": f"unknown tool {name}"}


def answer_question(question: str, conn, api_key: str,
                    model: str = "claude-sonnet-4-6", max_steps: int = 6):
    """Run the tool-use loop and return (answer_markdown, tool_log)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": question}]
    tool_log = []

    for _ in range(max_steps):
        resp = client.messages.create(
            model=model, max_tokens=1500, system=SYSTEM, tools=TOOLS, messages=messages
        )
        if resp.stop_reason != "tool_use":
            answer = "".join(b.text for b in resp.content if b.type == "text")
            return answer or "_(No answer produced.)_", tool_log

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                result = _run_tool(b.name, b.input, conn)
                tool_log.append({"tool": b.name, "input": b.input})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(result, default=str),
                })
        messages.append({"role": "user", "content": results})

    return "_(Stopped after several steps — try narrowing the question.)_", tool_log
