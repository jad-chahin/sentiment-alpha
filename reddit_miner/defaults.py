DEFAULT_SUBREDDITS: tuple[str, ...] = ("stocks", "wallstreetbets")
DEFAULT_LISTING: str = "hot"  # hot | new | rising | top
DEFAULT_POST_LIMIT: int = 50
DEFAULT_MAX_COMMENTS_PER_POST: int = 500
DEFAULT_MORE_LIMIT: int | None = 0  # 0 = fast; higher = expand more "MoreComments"
DEFAULT_DB_PATH: str = "reddit_miner.db"

DEFAULT_ANALYSIS_TAG: str = "default"
DEFAULT_ANALYSIS_LIMIT: int = 5000
DEFAULT_TOP_N: int = 25

DEFAULT_OPENAI_MODEL: str = "gpt-5-nano"

# Speed: 0 disables pacing (no intentional sleeps). We still back off on actual retryable errors.
DEFAULT_MAX_REQUESTS_PER_MINUTE: int = 0
