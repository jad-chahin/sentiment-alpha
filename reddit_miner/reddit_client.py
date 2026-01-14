from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import praw


@runtime_checkable
class _SubredditLike(Protocol):
    def hot(self, *, limit: int): ...
    def new(self, *, limit: int): ...
    def rising(self, *, limit: int): ...
    def top(self, *, limit: int): ...


def get_reddit() -> praw.Reddit:
    cid = os.getenv("REDDIT_CLIENT_ID")
    csec = os.getenv("REDDIT_CLIENT_SECRET")
    ua = os.getenv("REDDIT_USER_AGENT", "reddit-miner")

    if not cid or not csec:
        raise RuntimeError(
            "Missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET. Put them in .env or env vars."
        )

    return praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua)


def get_feed(subreddit: _SubredditLike, listing: str, limit: int):
    if listing not in {"hot", "new", "rising", "top"}:
        raise ValueError("listing must be one of: hot, new, rising, top")

    fn = getattr(subreddit, listing, None)
    if fn is None:
        raise AttributeError(f"subreddit object has no listing method: {listing}")

    return fn(limit=int(limit))
