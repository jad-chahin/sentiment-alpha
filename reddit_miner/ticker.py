import re
from functools import lru_cache

import yfinance as yf

ENABLE_KEYWORD_SHORTCUT = False
ENABLE_YFINANCE_VALIDATION = False

# Finance hint words
_HINT_WORDS_RAW: list[str] = [
    "buy", "buys", "buying", "bought",
    "accumulate", "accumulating", "accumulated",
    "add", "adds", "adding", "added",
    "increase", "increases", "increasing", "increased",
    "entry", "enter", "entering", "entered",
    "long", "upside", "up", "higher", "high",
    "rise", "rises", "rising", "rose",
    "gain", "gains", "gaining", "gained",
    "climb", "climbs", "climbing", "climbed",
    "jump", "jumps", "jumping", "jumped",
    "pop", "pops", "popping", "popped",
    "rally", "rallies", "rallying", "rallied",
    "surge", "surges", "surging", "surged",
    "soar", "soars", "soaring", "soared",
    "recover", "recovers", "recovering", "recovered",
    "rebound", "rebounds", "rebounding", "rebounded",
    "bounce", "bounces", "bouncing", "bounced",
    "uptick", "upticks", "green",
    "bullish", "bull", "bulls",
    "outperform", "outperforms", "outperforming", "outperformed",
    "beat", "beats", "beating", "hold", "holdings"

    "sell", "sells", "selling", "sold",
    "dump", "dumps", "dumping", "dumped",
    "exit", "exits", "exiting", "exited",
    "reduce", "reduces", "reducing", "reduced",
    "trim", "trims", "trimming", "trimmed",
    "cut", "cuts", "cutting",
    "short", "shorts", "shorting", "shorted",
    "downside", "down", "lower", "low",
    "fall", "falls", "falling", "fell",
    "drop", "drops", "dropping", "dropped",
    "decline", "declines", "declining", "declined",
    "lose", "loses", "losing", "lost",
    "slip", "slips", "slipping", "slipped",
    "slide", "slides", "sliding", "slid",
    "plunge", "plunges", "plunging", "plunged",
    "crash", "crashes", "crashing", "crashed",
    "tank", "tanks", "tanking", "tanked",
    "selloff", "sell-off", "red",
    "bearish", "bear", "bears",
    "weaken", "weakens", "weakening", "weakened",
    "underperform", "underperforms", "underperforming", "underperformed",
    "miss", "misses", "missing", "missed",
    "lose", "loses", "losing", "lost"
]


def _compile_hints(words: list[str]) -> re.Pattern:
    cleaned: list[str] = []
    seen: set[str] = set()

    for w in words:
        w = (w or "").strip().lower()
        if not w or w in seen:
            continue
        seen.add(w)
        cleaned.append(w)

    # longest-first helps to match more specific tokens first
    cleaned.sort(key=len, reverse=True)

    patterns: list[str] = []
    for w in cleaned:
        if "-" in w:
            parts = [re.escape(p) for p in w.split("-") if p]
            if len(parts) >= 2:
                patterns.append(r"[-\s]?".join(parts))
            else:
                patterns.append(re.escape(w))
        else:
            patterns.append(re.escape(w))

    return re.compile(r"(?i)\b(" + "|".join(patterns) + r")\b")


_FINANCE_HINTS = _compile_hints(_HINT_WORDS_RAW)


def has_finance_hint(text: str) -> bool:
    return bool(text) and bool(_FINANCE_HINTS.search(text))


def normalize_ticker(sym: str) -> str:
    sym = (sym or "").strip().upper()
    if not sym:
        return ""

    if sym.startswith("$"):
        sym = sym[1:]

    # strip common exchange prefix like "NASDAQ:" / "NYSE:"
    sym = re.sub(r"^[A-Z]+:", "", sym)

    # keep only allowed chars
    sym = re.sub(r"[^A-Z0-9.\-/]", "", sym)

    # normalize share-class separators
    sym = sym.replace("/", ".")
    if re.fullmatch(r"[A-Z]{1,6}-[A-Z0-9]{1,3}", sym):
        sym = sym.replace("-", ".")

    return sym


@lru_cache(maxsize=4096)
def is_real_ticker_yf(t: str) -> bool:
    try:
        info = yf.Ticker(t).info
        return bool(info)
    except Exception:
        return False


def find_invalid_tickers(tickers: list[str]) -> set[str]:
    if not ENABLE_YFINANCE_VALIDATION:
        return set()

    invalid: set[str] = set()
    for t in tickers:
        tt = normalize_ticker(t)
        if not tt:
            continue
        if not is_real_ticker_yf(tt):
            invalid.add(tt)
    return invalid
