from typing import Literal
from pydantic import BaseModel, Field
from openai import OpenAI
from .ticker import normalize_ticker
from openai.types.shared_params.reasoning import Reasoning

Sentiment = Literal["bullish", "bearish", "neutral"]


class Mention(BaseModel):
    ticker: str = Field(...)
    sentiment: Sentiment


class LineAnalysis(BaseModel):
    mentions: list[Mention] = Field(default_factory=list)


SYSTEM_INSTRUCTIONS = """
TASK: Extract traded equity/ETF tickers mentioned in ONE comment and label sentiment per ticker.

OUTPUT (return ONLY valid JSON matching exactly):
{"mentions":[{"ticker":"<TICKER>","sentiment":"bullish|bearish|neutral"}]}

IF NONE FOUND:
{"mentions":[]}

EXTRACTION RULES:
1) Prefer explicit tickers: $TSLA, TSLA, (TSLA), NASDAQ:aapl, NYSE:BRK.B.
2) Normalize: strip leading '$'; strip exchange prefix like "NASDAQ:"; uppercase output.
3) Share classes: allow one '.' (e.g., BRK.B). If written as BRK-B or BRK/B, normalize to BRK.B.
4) Only treat as a ticker if it clearly refers to a security; ignore random acronyms/caps.
5) You may map clearly unambiguous company/brand names to their primary ticker (e.g., Tesla->TSLA). If any ambiguity, omit rather than guess.
6) Exclude: crypto tokens (BTC/ETH), forex pairs, commodities, indices.
7) One entry per ticker maximum (dedupe). If multiple sentiments appear for the same ticker, use "neutral".

SENTIMENT RULES:
1) bullish: positive outlook, buy/long, calls, "going up", approval
2) bearish: negative outlook, sell/short, puts, "going down", disapproval
3) neutral: factual mention, question, unclear, sarcasm/hedged/conditional/mixed
4) Negations override: "not bullish", "don't buy", "won't go up" -> bearish; "not bearish" -> bullish
""".strip()


def analyze_comment(client: OpenAI, *, model: str, text: str) -> list[tuple[str, str]]:

    if len(text) > 2000:
        text = text[:2000]

    resp = client.responses.parse(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=text,
        text_format=LineAnalysis,
        max_output_tokens=1500,
        reasoning= Reasoning(effort="low")
    )

    parsed: LineAnalysis = resp.output_parsed

    out: dict[str, str] = {}
    for m in parsed.mentions:
        t = normalize_ticker(m.ticker)
        if not t:
            continue

        s = m.sentiment
        if t in out and out[t] != s:
            out[t] = "neutral"
        else:
            out[t] = s

    return list(out.items())
