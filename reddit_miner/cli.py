import os
import time
import datetime
import argparse

import prawcore
import openai

from .config import RunConfig
from . import db as dbmod
from .pipeline import scrape, analyze
from .db import fetch_ticker_summary
from .report import print_report_rich
from . import ticker as tickermod
from .credentials import (
    ensure_credentials,
    load_into_env_if_missing,
    set_openai_key_interactive,
    set_reddit_credentials_interactive,
    reset_all,
)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _menu(title: str, options: list[tuple[str, str]]) -> str:
    clear_screen()
    print("\n" + title)
    for key, label in options:
        print(f"  {key}) {label}")
    valid = {k for k, _ in options}
    while True:
        choice = input("> ").strip().lower()
        if choice in valid:
            return choice
        print(f"Choose one of: {', '.join(sorted(valid))}")


def _ask_yes_no(prompt: str) -> bool:
    while True:
        ans = input(f"{prompt} (y/n): ").strip().lower()
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _pause(msg: str = "Press Enter to continue...") -> None:
    input(f"\n{msg}")


def _clear_credential_env() -> None:
    for k in ["OPENAI_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]:
        os.environ.pop(k, None)


def _setup_menu() -> None:
    while True:
        choice = _menu(
            "Setup:",
            [
                ("1", "Set / change OpenAI API key"),
                ("2", "Set / change Reddit credentials"),
                ("3", "Reset / remove saved credentials"),
                ("b", "Back"),
            ],
        )

        if choice == "1":
            set_openai_key_interactive()
            os.environ.pop("OPENAI_API_KEY", None)
            load_into_env_if_missing()
            _pause()

        elif choice == "2":
            set_reddit_credentials_interactive()
            os.environ.pop("REDDIT_CLIENT_ID", None)
            os.environ.pop("REDDIT_CLIENT_SECRET", None)
            os.environ.pop("REDDIT_USER_AGENT", None)
            load_into_env_if_missing()
            _pause()

        elif choice == "3":
            confirm = input("Type 'reset' to confirm: ").strip().lower()
            if confirm == "reset":
                reset_all()
                _clear_credential_env()
                print("Credentials removed.")
            else:
                print("Cancelled.")
            _pause()

        elif choice == "b":
            return


def _choose_config_for_run(*, do_scrape: bool, do_analyze: bool) -> RunConfig | None:
    choice = _menu("Run settings:", [("1", "Default"), ("2", "Choose settings"), ("b", "Back")])
    if choice == "b":
        return None
    if choice == "1":
        return RunConfig.defaults()
    return RunConfig.from_user_input(do_scrape=do_scrape, do_analyze=do_analyze)


def _report_flow() -> None:
    cfg = RunConfig.defaults()
    if not os.path.exists(cfg.db_path):
        print(f"\nNo database found at: {cfg.db_path}")
        _pause()
        return

    conn = dbmod.connect(cfg.db_path)
    dbmod.init_db(conn)

    tag = dbmod.get_latest_analysis_tag(conn)
    if not tag:
        print("\nNo analysis found yet in this database.")
        _pause()
        return

    rows = fetch_ticker_summary(conn, analysis_tag=tag, subreddits=None, limit=500)

    summary = {
        "db_path": cfg.db_path,
        "subreddits": ("ALL",),
        "listing": "-",
        "post_limit": "-",
        "max_comments_per_post": "-",
        "analysis_tag": tag,
        "model": "-",
        "saved": "-",
        "analyzed_model_calls": "-",
    }
    print_report_rich(summary=summary, rows=rows, top_n=cfg.top_n)

    _pause()


def _pick_tag_for_clear(conn) -> str | None:
    tags = dbmod.list_analysis_tags(conn)
    if not tags:
        print("\nNo analysis tags found in this database.")
        _pause()
        return None

    options = [(str(i + 1), tags[i]) for i in range(len(tags))]
    options.append(("b", "Back"))
    choice = _menu("Select analysis tag:", options)
    if choice == "b":
        return None
    idx = int(choice) - 1
    if 0 <= idx < len(tags):
        return tags[idx]
    return None


def _clear_analysis(conn, *, analysis_tag: str) -> tuple[int, int]:
    cur1 = conn.execute("DELETE FROM mentions WHERE analysis_tag = ?", (analysis_tag,))
    cur2 = conn.execute("DELETE FROM comment_analysis WHERE analysis_tag = ?", (analysis_tag,))
    conn.commit()
    return cur1.rowcount or 0, cur2.rowcount or 0


def _clear_dataset(conn) -> tuple[int, int, int]:
    cur1 = conn.execute("DELETE FROM mentions")
    cur2 = conn.execute("DELETE FROM comment_analysis")
    cur3 = conn.execute("DELETE FROM comments")
    conn.commit()
    return cur1.rowcount or 0, cur2.rowcount or 0, cur3.rowcount or 0


def _clear_flow() -> None:
    cfg = RunConfig.defaults()
    if not os.path.exists(cfg.db_path):
        print(f"\nNo database found at: {cfg.db_path}")
        _pause()
        return

    conn = dbmod.connect(cfg.db_path)
    dbmod.init_db(conn)

    while True:
        choice = _menu(
            "Clear:",
            [
                ("1", "Clear analysis (pick a tag)"),
                ("2", "Clear dataset (comments + ALL analysis)"),
                ("b", "Back"),
            ],
        )

        if choice == "b":
            return

        if choice == "1":
            tag = _pick_tag_for_clear(conn)
            if not tag:
                continue
            print(f"\nThis will delete mentions + analysis for tag: {tag}")
            if not _ask_yes_no("Continue?"):
                continue
            dm, da = _clear_analysis(conn, analysis_tag=tag)
            print(f"Cleared: {dm} mentions, {da} analysis rows.")
            _pause()
            continue

        if choice == "2":
            print("\nThis will delete ALL comments and ALL analysis from this database.")
            if not _ask_yes_no("Continue?"):
                continue
            dm, da, dc = _clear_dataset(conn)
            print(f"Cleared: {dm} mentions, {da} analysis rows, {dc} comments.")
            _pause()
            continue


def _run_flow() -> None:
    action = _menu(
        "What do you want to do?",
        [
            ("1", "Scrape data"),
            ("2", "Analyze scraped data"),
            ("3", "Scrape then analyze"),
            ("b", "Back"),
        ],
    )
    if action == "b":
        return

    do_scrape = action in {"1", "3"}
    do_analyze = action in {"2", "3"}

    cfg = _choose_config_for_run(do_scrape=do_scrape, do_analyze=do_analyze)
    if cfg is None:
        return

    need_reddit = do_scrape
    need_openai = do_analyze

    try:
        ensure_credentials(need_openai=need_openai, need_reddit=need_reddit)
        load_into_env_if_missing()
    except KeyboardInterrupt:
        print("\nBack.")
        return

    conn = dbmod.connect(cfg.db_path)
    dbmod.init_db(conn)

    start = time.time()
    saved = 0
    outcome = None

    if do_scrape:
        print("\nScraping started. Press Ctrl+C to stop and save what’s been collected so far.")
        try:
            saved = scrape(
                conn,
                subreddits=cfg.subreddits,
                listing=cfg.listing,
                post_limit=cfg.post_limit,
                more_limit=cfg.more_limit,
                max_comments_per_post=cfg.max_comments_per_post,
                bot_usernames=cfg.bot_usernames,
            )
            conn.commit()
        except KeyboardInterrupt:
            conn.commit()
            print("\nScrape stopped. Data collected so far has been saved.")
            if action == "3":
                next_choice = _menu(
                    "Scrape interrupted:",
                    [("1", "Skip remaining scraping and start analysis now"), ("2", "Stop (back to main menu)")],
                )
                if next_choice == "2":
                    elapsed = datetime.timedelta(seconds=int(time.time() - start))
                    print("\nTime elapsed:", elapsed)
                    _pause()
                    return
        except (prawcore.exceptions.OAuthException, prawcore.exceptions.ResponseException, prawcore.exceptions.Forbidden) as e:
            print("\n[ERROR] Reddit credentials appear invalid or unauthorized.")
            print(f"Details: {e}")
            if _ask_yes_no("Open Setup to update them now?"):
                _setup_menu()
            return
        except Exception as e:
            conn.commit()
            print("\n[ERROR] Scrape failed.")
            print(e)
            _pause()
            return

    if do_analyze:
        print("\nAnalysis started. Press Ctrl+C to stop and save what’s been analyzed so far.")
        try:
            outcome = analyze(
                conn,
                analysis_tag=cfg.analysis_tag,
                model=cfg.model,
                limit=cfg.analysis_limit,
                retry_errors=False,
                max_requests_per_minute=cfg.max_requests_per_minute,
                subreddits=cfg.subreddits,
            )
            conn.commit()
        except KeyboardInterrupt:
            conn.commit()
            print("\nAnalysis stopped. Results analyzed so far have been saved.")
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            print("\n[ERROR] OpenAI API key appears invalid or unauthorized.")
            print(f"Details: {e}")
            if _ask_yes_no("Open Setup to update it now?"):
                _setup_menu()
            return
        except Exception as e:
            conn.commit()
            print("\n[ERROR] Analysis failed.")
            print(e)
            _pause()
            return

        summary_rows = fetch_ticker_summary(conn, analysis_tag=cfg.analysis_tag, subreddits=cfg.subreddits, limit=500)

        analyzed_calls = getattr(outcome, "analyzed_model_calls", "-") if outcome is not None else "-"
        summary = {
            "db_path": cfg.db_path,
            "subreddits": cfg.subreddits,
            "listing": cfg.listing,
            "post_limit": cfg.post_limit,
            "max_comments_per_post": cfg.max_comments_per_post,
            "analysis_tag": cfg.analysis_tag,
            "model": cfg.model,
            "saved": saved,
            "analyzed_model_calls": analyzed_calls,
        }
        print_report_rich(summary=summary, rows=summary_rows, top_n=cfg.top_n)

    elapsed = datetime.timedelta(seconds=int(time.time() - start))
    print("\nTime elapsed:", elapsed)
    _pause()


def run() -> None:
    # Parse flags once; missing flags default False
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Enable yfinance validation: after analysis, delete mentions for tickers that yfinance says are invalid.",
    )
    parser.add_argument(
        "--shortcut",
        action="store_true",
        help="Enable keyword shortcut: skip OpenAI analysis for comments unlikely to contain tickers/finance context.",
    )
    args, _unknown = parser.parse_known_args()

    tickermod.ENABLE_YFINANCE_VALIDATION = bool(args.validate)
    tickermod.ENABLE_KEYWORD_SHORTCUT = bool(args.shortcut)

    load_into_env_if_missing()

    while True:
        choice = _menu(
            "Main menu:",
            [("1", "Run"), ("2", "Report"), ("3", "Clear"), ("4", "Setup"), ("q", "Quit")],
        )

        if choice == "q":
            return
        if choice == "1":
            _run_flow()
        elif choice == "2":
            _report_flow()
        elif choice == "3":
            _clear_flow()
        elif choice == "4":
            _setup_menu()
