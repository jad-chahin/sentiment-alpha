from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import praw
import prawcore
from openai import OpenAI
import openai

from . import db as dbmod
from .credentials import get_secret
from .analyzer import analyze_comment
from . import ticker as tickermod


try:
    from .progress import ProgressBar  # type: ignore
except Exception:  # pragma: no cover
    ProgressBar = None  # type: ignore


@dataclass
class AnalyzeOutcome:
    analyzed: int = 0
    errors: int = 0
    analyzed_model_calls: int = 0
    stopped_reason: str | None = None  # "quota" | "timeout" | "ctrl_c"


def _now() -> float:
    return time.monotonic()


def _sleep_with_deadline(seconds: float, *, deadline: float | None) -> None:
    if seconds <= 0:
        return
    if deadline is None:
        time.sleep(seconds)
        return
    remaining = deadline - _now()
    if remaining <= 0:
        return
    time.sleep(min(seconds, remaining))


def _is_quota_exhausted(err: Exception) -> bool:
    msg = (str(err) or "").lower()
    return ("insufficient_quota" in msg) or ("quota" in msg and ("exceed" in msg or "exceeded" in msg))


def _is_retryable(err: Exception) -> bool:
    return isinstance(
        err,
        (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ),
    )


def _is_fatal_auth(err: Exception) -> bool:
    return isinstance(err, (openai.AuthenticationError, openai.PermissionDeniedError))


def _backoff_seconds(attempt: int) -> float:
    return min(1.0 * (2 ** attempt), 20.0)


def _progress(total: int, prefix: str):
    """
    Returns a tiny wrapper with update(i) that won't crash if ProgressBar differs/missing.
    """
    if ProgressBar is None:
        class _NoPB:
            def update(self, _i: int) -> None:
                return
        return _NoPB()

    try:
        pb = ProgressBar(total=total, prefix=prefix)
    except TypeError:
        class _NoPB:
            def update(self, _i: int) -> None:
                return
        return _NoPB()

    if not hasattr(pb, "update"):
        class _NoPB:
            def update(self, _i: int) -> None:
                return
        return _NoPB()

    return pb


def _build_reddit() -> praw.Reddit:
    cid = get_secret("REDDIT_CLIENT_ID")
    csec = get_secret("REDDIT_CLIENT_SECRET")
    ua = get_secret("REDDIT_USER_AGENT") or "reddit-miner"
    if not cid or not csec:
        raise RuntimeError("Missing Reddit credentials (client_id/client_secret). Use Setup to enter them.")
    return praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua)


def _cleanup_invalid_tickers(conn, *, analysis_tag: str) -> int:
    """
    If yfinance validation is enabled, delete mentions for tickers that yfinance says are invalid.
    Runs once per analyze() call, and checks each unique ticker at most once (cached).
    """
    if not tickermod.ENABLE_YFINANCE_VALIDATION:
        return 0

    tickers = dbmod.fetch_distinct_mentioned_tickers(conn, analysis_tag=analysis_tag, subreddits=None)
    if not tickers:
        return 0

    invalid = tickermod.find_invalid_tickers(tickers)
    if not invalid:
        return 0

    deleted = dbmod.delete_mentions_for_tickers(conn, analysis_tag=analysis_tag, tickers=sorted(invalid))
    conn.commit()
    return deleted


def scrape(
    conn,
    *,
    subreddits: tuple[str, ...],
    listing: str,
    post_limit: int,
    more_limit: int | None,
    max_comments_per_post: int,
    bot_usernames: Iterable[str],
) -> int:
    """
    Scrape comments into the DB. Safe to Ctrl+C. Returns # comments saved this run.
    """
    reddit = _build_reddit()
    bots = set(bot_usernames or ())

    total_posts = max(0, int(post_limit)) * max(1, len(subreddits))
    pb = _progress(total_posts or 1, "Scraping posts")

    saved = 0
    posts_done = 0

    try:
        for sub in subreddits:
            sr = reddit.subreddit(sub)

            if listing == "new":
                feed = sr.new(limit=post_limit)
            elif listing == "rising":
                feed = sr.rising(limit=post_limit)
            elif listing == "top":
                feed = sr.top(limit=post_limit)
            else:
                feed = sr.hot(limit=post_limit)

            for submission in feed:
                try:
                    submission.comments.replace_more(limit=more_limit)
                    comments = submission.comments.list()
                except Exception:
                    comments = []

                take = comments[:max_comments_per_post] if max_comments_per_post else comments

                for c in take:
                    try:
                        author = getattr(c, "author", None)
                        author_name = str(author) if author else None
                        if author_name in bots:
                            continue

                        body = (getattr(c, "body", "") or "").strip()
                        if not body:
                            continue

                        dbmod.save_comment(
                            conn,
                            comment_id=str(getattr(c, "id")),
                            subreddit=str(sub),
                            submission_id=str(getattr(submission, "id", "")),
                            submission_title=str(getattr(submission, "title", "") or ""),
                            author=author_name,
                            created_utc=int(getattr(c, "created_utc", 0) or 0),
                            score=int(getattr(c, "score", 0) or 0),
                            body=body,
                        )
                        saved += 1

                        if saved % 50 == 0:
                            conn.commit()
                    except Exception:
                        continue

                posts_done += 1
                pb.update(posts_done)

        conn.commit()
        return saved

    except KeyboardInterrupt:
        conn.commit()
        return saved
    except (prawcore.exceptions.OAuthException, prawcore.exceptions.ResponseException, prawcore.exceptions.Forbidden):
        conn.commit()
        raise


def analyze(
    conn,
    *,
    analysis_tag: str,
    model: str,
    limit: int,
    retry_errors: bool,
    max_requests_per_minute: int,
    subreddits: tuple[str, ...] | None = None,
    timeout_seconds: int | None = None
) -> AnalyzeOutcome:
    """
    Analyze up to `limit` comments. Saves progressively. Ctrl+C commits and exits.

    Shortcut mode (--shortcut):
      - skips OpenAI calls when has_finance_hint(text) is False
      - still marks comment as analyzed_ok so it won't be revisited

    Validation mode (--validate):
      - after the run ends, checks each unique ticker once via yfinance
      - deletes mentions for invalid tickers for this analysis_tag
    """

    outcome = AnalyzeOutcome()
    deadline = _now() + timeout_seconds if timeout_seconds else None

    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OpenAI API key. Use Setup to enter it.")

    client = OpenAI(api_key=api_key)

    candidates = dbmod.fetch_candidates(
        conn,
        analysis_tag=analysis_tag,
        limit=int(limit),
        retry_errors=bool(retry_errors),
        subreddits=subreddits,
    )

    pb = _progress((len(candidates) if candidates else 1), "Analyzing comments")

    interval = 60.0 / float(max_requests_per_minute) if max_requests_per_minute and max_requests_per_minute > 0 else 0.0
    next_call_at = _now()

    def _pace() -> None:
        nonlocal next_call_at
        if interval <= 0:
            return
        now = _now()
        if now < next_call_at:
            _sleep_with_deadline(next_call_at - now, deadline=deadline)
        next_call_at = _now() + interval

    try:
        for idx, (comment_id, body) in enumerate(candidates, start=1):
            if deadline is not None and _now() >= deadline:
                outcome.stopped_reason = "timeout"
                conn.commit()
                _cleanup_invalid_tickers(conn, analysis_tag=analysis_tag)
                pb.update(idx - 1)
                return outcome

            text = (body or "").strip()
            if not text:
                pb.update(idx)
                continue

            # --- Shortcut: skip OpenAI if heuristic says "unlikely ticker/finance" ---
            if tickermod.ENABLE_KEYWORD_SHORTCUT and not tickermod.has_finance_hint(text):
                dbmod.mark_analyzed_ok(conn, analysis_tag=analysis_tag, comment_id=str(comment_id), model=model)
                outcome.analyzed += 1
                if outcome.analyzed % 50 == 0:
                    conn.commit()
                pb.update(idx)
                continue

            attempt = 0
            while True:
                if deadline is not None and _now() >= deadline:
                    outcome.stopped_reason = "timeout"
                    conn.commit()
                    _cleanup_invalid_tickers(conn, analysis_tag=analysis_tag)
                    pb.update(idx - 1)
                    return outcome

                try:
                    _pace()
                    rows = analyze_comment(client, model=model, text=text)
                    outcome.analyzed_model_calls += 1

                    dbmod.save_mentions(
                        conn,
                        analysis_tag=analysis_tag,
                        comment_id=str(comment_id),
                        model=model,
                        sentiment_rows=rows,
                    )
                    dbmod.mark_analyzed_ok(conn, analysis_tag=analysis_tag, comment_id=str(comment_id), model=model)
                    outcome.analyzed += 1

                    if outcome.analyzed % 10 == 0:
                        conn.commit()
                    break

                except KeyboardInterrupt:
                    conn.commit()
                    outcome.stopped_reason = "ctrl_c"
                    _cleanup_invalid_tickers(conn, analysis_tag=analysis_tag)
                    pb.update(idx - 1)
                    return outcome

                except Exception as e:
                    if _is_fatal_auth(e):
                        conn.commit()
                        raise

                    if isinstance(e, openai.RateLimitError) and _is_quota_exhausted(e):
                        # Store the real message for debugging
                        dbmod.mark_analyzed_error(
                            conn,
                            analysis_tag=analysis_tag,
                            comment_id=str(comment_id),
                            model=model,
                            error=f"{type(e).__name__}: {e}",
                        )
                        conn.commit()
                        outcome.stopped_reason = "quota"
                        _cleanup_invalid_tickers(conn, analysis_tag=analysis_tag)
                        pb.update(idx - 1)
                        return outcome

                    if _is_retryable(e):
                        wait_s = _backoff_seconds(attempt)
                        attempt += 1
                        _sleep_with_deadline(wait_s, deadline=deadline)
                        continue

                    dbmod.mark_analyzed_error(
                        conn,
                        analysis_tag=analysis_tag,
                        comment_id=str(comment_id),
                        model=model,
                        error=f"{type(e).__name__}: {e}",
                    )
                    outcome.errors += 1
                    conn.commit()
                    break

            pb.update(idx)

        conn.commit()
        _cleanup_invalid_tickers(conn, analysis_tag=analysis_tag)
        return outcome

    except KeyboardInterrupt:
        conn.commit()
        outcome.stopped_reason = "ctrl_c"
        _cleanup_invalid_tickers(conn, analysis_tag=analysis_tag)
        return outcome
