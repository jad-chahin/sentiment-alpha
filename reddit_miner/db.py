import sqlite3
import time
from typing import Iterable, Optional

CURRENT_ANALYSIS_TAG_KEY = "current_analysis_tag"


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        comment_id TEXT PRIMARY KEY,
        subreddit TEXT NOT NULL,
        submission_id TEXT,
        submission_title TEXT,
        author TEXT,
        created_utc INTEGER,
        score INTEGER,
        body TEXT NOT NULL,
        scraped_at INTEGER NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS comment_analysis (
        analysis_tag TEXT NOT NULL,
        comment_id TEXT NOT NULL,
        model TEXT NOT NULL,
        analyzed_at INTEGER NOT NULL,
        status TEXT NOT NULL,   -- ok | error | skipped
        error TEXT,
        PRIMARY KEY (analysis_tag, comment_id)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS mentions (
        analysis_tag TEXT NOT NULL,
        comment_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        sentiment TEXT NOT NULL,
        model TEXT NOT NULL,
        analyzed_at INTEGER NOT NULL,
        PRIMARY KEY (analysis_tag, comment_id, ticker),
        FOREIGN KEY (comment_id) REFERENCES comments(comment_id)
    )
    """)

    # App state (e.g., currently selected analysis tag)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_subreddit_created ON comments(subreddit, created_utc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mentions_tag_ticker ON mentions(analysis_tag, ticker)")
    conn.commit()


def set_app_state(conn: sqlite3.Connection, *, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_state(key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_app_state(conn: sqlite3.Connection, *, key: str) -> str | None:
    cur = conn.execute("SELECT value FROM app_state WHERE key = ? LIMIT 1", (key,))
    row = cur.fetchone()
    if row and row[0]:
        return str(row[0])
    return None


def set_current_analysis_tag(conn: sqlite3.Connection, *, analysis_tag: str) -> None:
    set_app_state(conn, key=CURRENT_ANALYSIS_TAG_KEY, value=analysis_tag)


def get_current_analysis_tag(conn: sqlite3.Connection) -> str | None:
    return get_app_state(conn, key=CURRENT_ANALYSIS_TAG_KEY)


def save_comment(
    conn: sqlite3.Connection,
    *,
    comment_id: str,
    subreddit: str,
    submission_id: str,
    submission_title: str,
    author: Optional[str],
    created_utc: int,
    score: int,
    body: str
) -> None:
    now = int(time.time())
    conn.execute("""
    INSERT OR IGNORE INTO comments(comment_id, subreddit, submission_id, submission_title, author, created_utc, score, body, scraped_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (comment_id, subreddit, submission_id, submission_title, author, int(created_utc), int(score), body, now))


def mark_analyzed_ok(conn: sqlite3.Connection, *, analysis_tag: str, comment_id: str, model: str) -> None:
    now = int(time.time())
    conn.execute("""
    INSERT OR REPLACE INTO comment_analysis(analysis_tag, comment_id, model, analyzed_at, status, error)
    VALUES (?, ?, ?, ?, 'ok', NULL)
    """, (analysis_tag, comment_id, model, now))


def mark_analyzed_skipped(conn: sqlite3.Connection, *, analysis_tag: str, comment_id: str, model: str) -> None:
    now = int(time.time())
    conn.execute("""
    INSERT OR REPLACE INTO comment_analysis(analysis_tag, comment_id, model, analyzed_at, status, error)
    VALUES (?, ?, ?, ?, 'skipped', NULL)
    """, (analysis_tag, comment_id, model, now))


def mark_analyzed_error(conn: sqlite3.Connection, *, analysis_tag: str, comment_id: str, model: str, error: str) -> None:
    now = int(time.time())
    conn.execute("""
    INSERT OR REPLACE INTO comment_analysis(analysis_tag, comment_id, model, analyzed_at, status, error)
    VALUES (?, ?, ?, ?, 'error', ?)
    """, (analysis_tag, comment_id, model, now, error[:2000]))


def save_mentions(
    conn: sqlite3.Connection,
    *,
    analysis_tag: str,
    comment_id: str,
    model: str,
    sentiment_rows: Iterable[tuple[str, str]]
) -> None:
    now = int(time.time())
    conn.executemany("""
    INSERT OR REPLACE INTO mentions(analysis_tag, comment_id, ticker, sentiment, model, analyzed_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, [(analysis_tag, comment_id, t, s, model, now) for (t, s) in sentiment_rows])


def fetch_candidates(
    conn: sqlite3.Connection,
    *,
    analysis_tag: str,
    limit: int,
    retry_errors: bool,
    subreddits: tuple[str, ...] | None = None,
    include_skipped: bool = False,
) -> list[tuple[str, str]]:
    subreddit_filter = ""
    params: list = [analysis_tag]

    if subreddits:
        subreddit_filter = f" AND c.subreddit IN ({','.join('?' for _ in subreddits)}) "
        params.extend(list(subreddits))

    skipped_clause = " OR a.status = 'skipped' " if include_skipped else ""

    if retry_errors:
        sql = f"""
        SELECT c.comment_id, c.body
        FROM comments c
        LEFT JOIN comment_analysis a
          ON a.comment_id = c.comment_id AND a.analysis_tag = ?
        WHERE (a.comment_id IS NULL OR a.status = 'error'{skipped_clause})
        {subreddit_filter}
        ORDER BY c.created_utc DESC
        LIMIT ?
        """
    else:
        sql = f"""
        SELECT c.comment_id, c.body
        FROM comments c
        LEFT JOIN comment_analysis a
          ON a.comment_id = c.comment_id AND a.analysis_tag = ?
        WHERE (a.comment_id IS NULL{skipped_clause})
        {subreddit_filter}
        ORDER BY c.created_utc DESC
        LIMIT ?
        """

    params.append(limit)
    cur = conn.execute(sql, params)
    return cur.fetchall()


def fetch_sentiment_counts(
    conn: sqlite3.Connection,
    *,
    analysis_tag: str,
    subreddits: tuple[str, ...] | None = None
):
    if subreddits:
        cur = conn.execute(f"""
        SELECT m.ticker, m.sentiment, COUNT(*) as n
        FROM mentions m
        JOIN comments c ON c.comment_id = m.comment_id
        WHERE m.analysis_tag = ?
          AND c.subreddit IN ({','.join('?' for _ in subreddits)})
        GROUP BY m.ticker, m.sentiment
        """, (analysis_tag, *subreddits))
    else:
        cur = conn.execute("""
        SELECT ticker, sentiment, COUNT(*) as n
        FROM mentions
        WHERE analysis_tag = ?
        GROUP BY ticker, sentiment
        """, (analysis_tag,))
    return cur.fetchall()


def fetch_ticker_summary(
    conn,
    *,
    analysis_tag: str,
    subreddits: tuple[str, ...] | None = None,
    limit: int = 200
):
    if subreddits:
        sub_filter = f" AND c.subreddit IN ({','.join('?' for _ in subreddits)}) "
        params = (analysis_tag, *subreddits, limit)
        sql = f"""
        SELECT
          m.ticker AS ticker,
          SUM(CASE WHEN m.sentiment='bullish' THEN 1 ELSE 0 END) AS bullish,
          SUM(CASE WHEN m.sentiment='bearish' THEN 1 ELSE 0 END) AS bearish,
          SUM(CASE WHEN m.sentiment='neutral' THEN 1 ELSE 0 END) AS neutral,
          COUNT(*) AS mentions,
          (SUM(CASE WHEN m.sentiment='bullish' THEN 1 ELSE 0 END) -
           SUM(CASE WHEN m.sentiment='bearish' THEN 1 ELSE 0 END)) AS score
        FROM mentions m
        JOIN comments c ON c.comment_id = m.comment_id
        WHERE m.analysis_tag = ?
        {sub_filter}
        GROUP BY m.ticker
        ORDER BY score DESC, mentions DESC
        LIMIT ?
        """
        cur = conn.execute(sql, params)
    else:
        cur = conn.execute("""
        SELECT
          ticker,
          SUM(CASE WHEN sentiment='bullish' THEN 1 ELSE 0 END) AS bullish,
          SUM(CASE WHEN sentiment='bearish' THEN 1 ELSE 0 END) AS bearish,
          SUM(CASE WHEN sentiment='neutral' THEN 1 ELSE 0 END) AS neutral,
          COUNT(*) AS mentions,
          (SUM(CASE WHEN sentiment='bullish' THEN 1 ELSE 0 END) -
           SUM(CASE WHEN sentiment='bearish' THEN 1 ELSE 0 END)) AS score
        FROM mentions
        WHERE analysis_tag = ?
        GROUP BY ticker
        ORDER BY score DESC, mentions DESC
        LIMIT ?
        """, (analysis_tag, limit))
    return cur.fetchall()


def list_analysis_tags(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("""
    SELECT analysis_tag, MAX(analyzed_at) AS last_seen
    FROM comment_analysis
    GROUP BY analysis_tag
    ORDER BY last_seen DESC
    """)
    tags = [r[0] for r in cur.fetchall() if r and r[0]]

    cur2 = conn.execute("""
    SELECT DISTINCT analysis_tag
    FROM mentions
    """)
    mention_tags = {r[0] for r in cur2.fetchall() if r and r[0]}

    for t in mention_tags:
        if t not in tags:
            tags.append(t)

    return tags


def get_latest_analysis_tag(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute("""
    SELECT analysis_tag
    FROM comment_analysis
    ORDER BY analyzed_at DESC
    LIMIT 1
    """)
    row = cur.fetchone()
    if row and row[0]:
        return row[0]

    cur = conn.execute("""
    SELECT analysis_tag
    FROM mentions
    ORDER BY analyzed_at DESC
    LIMIT 1
    """)
    row = cur.fetchone()
    if row and row[0]:
        return row[0]

    return None


def fetch_distinct_mentioned_tickers(
    conn: sqlite3.Connection,
    *,
    analysis_tag: str,
    subreddits: tuple[str, ...] | None = None
) -> list[str]:
    if subreddits:
        cur = conn.execute(f"""
        SELECT DISTINCT m.ticker
        FROM mentions m
        JOIN comments c ON c.comment_id = m.comment_id
        WHERE m.analysis_tag = ?
          AND c.subreddit IN ({','.join('?' for _ in subreddits)})
        """, (analysis_tag, *subreddits))
    else:
        cur = conn.execute("""
        SELECT DISTINCT ticker
        FROM mentions
        WHERE analysis_tag = ?
        """, (analysis_tag,))
    return [r[0] for r in cur.fetchall() if r and r[0]]


def delete_mentions_for_tickers(conn: sqlite3.Connection, *, analysis_tag: str, tickers: Iterable[str]) -> int:
    ticker_list = [t for t in dict.fromkeys(tickers) if t]
    if not ticker_list:
        return 0

    deleted = 0
    chunk_size = 900

    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i:i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        cur = conn.execute(
            f"DELETE FROM mentions WHERE analysis_tag = ? AND ticker IN ({placeholders})",
            (analysis_tag, *chunk),
        )
        if cur.rowcount and cur.rowcount > 0:
            deleted += cur.rowcount

    return deleted
