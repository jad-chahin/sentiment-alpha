from __future__ import annotations

import os
import sys
import shutil
from typing import Any, Iterable, Sequence

def _ask_top_n(*, default: int, max_n: int) -> int:
    default = int(default) if default and int(default) > 0 else 20
    max_n = int(max_n) if max_n and int(max_n) > 0 else 500

    while True:
        prompt = f"\nHow many tickers to include in the report? (Enter for {default}, or 'all'): "
        s = input(prompt).strip().lower()

        if not s:
            return min(default, max_n)

        if s in {"all", "a"}:
            return max_n

        try:
            n = int(s)
            if n > 0:
                return min(n, max_n)
        except ValueError:
            pass

        print("Please enter a positive number, press Enter, or type 'all'.")

def _summary_lines(summary: dict[str, Any]) -> list[str]:
    keys_order = [
        "db_path",
        "subreddits",
        "listing",
        "post_limit",
        "max_comments_per_post",
        "analysis_tag",
        "model",
        "saved",
        "analyzed_model_calls",
    ]
    lines: list[str] = []
    for k in keys_order:
        if k in summary:
            lines.append(f"{k}: {summary.get(k)}")
    for k, v in summary.items():
        if k not in keys_order:
            lines.append(f"{k}: {v}")
    return lines or ["No summary."]

def _coerce_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0

def _normalize_row(r: Sequence[Any]) -> tuple[str, int, int, int, int, int]:
    ticker = str(r[0]) if len(r) > 0 else "-"
    bullish = _coerce_int(r[1]) if len(r) > 1 else 0
    bearish = _coerce_int(r[2]) if len(r) > 2 else 0
    neutral = _coerce_int(r[3]) if len(r) > 3 else 0
    mentions = _coerce_int(r[4]) if len(r) > 4 else 0
    score = _coerce_int(r[5]) if len(r) > 5 else 0
    return ticker, bullish, bearish, neutral, mentions, score

def _read_key() -> str:
    if os.name == "nt":
        try:
            import msvcrt
        except Exception:
            return ""
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            if ch2 == b"H":
                return "up"
            if ch2 == b"P":
                return "down"
            if ch2 == b"I":
                return "page_up"
            if ch2 == b"Q":
                return "page_down"
            return ""
        if ch == b"\r":
            return "enter"
        if ch == b"\x1b":
            return "esc"
        try:
            return ch.decode(errors="ignore").lower()
        except Exception:
            return ""

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            if seq == "[5":
                sys.stdin.read(1)
                return "page_up"
            if seq == "[6":
                sys.stdin.read(1)
                return "page_down"
            return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def _clear_screen() -> None:
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()

def _pager(lines: list[str]) -> None:
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        for line in lines:
            print(line)
        return

    height = shutil.get_terminal_size((80, 24)).lines
    view_height = max(5, height - 2)
    pos = 0
    max_pos = max(0, len(lines) - view_height)

    while True:
        _clear_screen()
        window = lines[pos:pos + view_height]
        for line in window:
            print(line)
        status = f"Lines {pos + 1}-{min(pos + view_height, len(lines))} of {len(lines)}  (Up/Down, PgUp/PgDn, Q to exit)"
        print(status)
        key = _read_key()
        if key in {"q", "esc"}:
            return
        if key in {"down", "enter"}:
            pos = min(max_pos, pos + 1)
        elif key == "up":
            pos = max(0, pos - 1)
        elif key == "page_down":
            pos = min(max_pos, pos + view_height)
        elif key == "page_up":
            pos = max(0, pos - view_height)

def print_report_rich(
    *,
    summary: dict[str, Any],
    rows: Iterable[Sequence[Any]],
    top_n: int = 20,
    prompt_for_top_n: bool = True,
) -> None:
    rows_list = list(rows or [])
    max_available = len(rows_list)

    if prompt_for_top_n:
        cap = max_available if max_available > 0 else max(1, int(top_n or 20))
        n_to_show = _ask_top_n(default=int(top_n or 20), max_n=cap)
    else:
        n_to_show = min(int(top_n or 20), max_available) if max_available else int(top_n or 20)

    display_rows = rows_list[: max(0, int(n_to_show))]

    lines: list[str] = ["=== Run Summary ==="]
    lines.extend(_summary_lines(summary))
    lines.append("")
    lines.append(f"=== Top {len(display_rows)} tickers ===")
    if not display_rows:
        lines.append("No tickers found.")
        _pager(lines)
        return

    header = f"{'Ticker':<10} {'Bull':>6} {'Bear':>6} {'Neut':>6} {'Ment':>6} {'Score':>6}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in display_rows:
        t, b, be, n, m, s = _normalize_row(r)
        lines.append(f"{t:<10} {b:>6} {be:>6} {n:>6} {m:>6} {s:>6}")

    if max_available and len(display_rows) < max_available:
        lines.append("")
        lines.append(f"Showing {len(display_rows)} of {max_available} tickers provided.")

    _pager(lines)
