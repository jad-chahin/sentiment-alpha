from dataclasses import dataclass
from typing import Optional

from . import defaults


def _split_list(s: str) -> tuple[str, ...]:
    parts = [p.strip() for p in s.replace(",", " ").split()]
    return tuple(p for p in parts if p)


def _prompt_str(label: str, default: str) -> str:
    s = input(f"{label} [{default}]: ").strip()
    return s if s else default


def _prompt_int(label: str, default: int, min_value: int | None = None) -> int | None:
    while True:
        s = input(f"{label} [{default}]: ").strip()
        if not s:
            return default
        try:
            v = int(s)
            if min_value is not None and v < min_value:
                print(f"Please enter a value >= {min_value}.")
                continue
            return v
        except ValueError:
            print("Please enter an integer.")


def _prompt_optional_int(label: str, default: Optional[int]) -> Optional[int]:
    d = "all" if default is None else str(default)
    while True:
        s = input(f"{label} [{d}] (enter 'all' for unlimited): ").strip().lower()
        if not s:
            return default
        if s == "all":
            return None
        try:
            return int(s)
        except ValueError:
            print("Please enter an integer or 'all'.")


def _choose_mode() -> tuple[bool, bool]:
    print("\nConfigure settings for:")
    print("  1) Scrape only")
    print("  2) Analyze only")
    print("  3) Scrape + Analyze")
    while True:
        c = input("> ").strip().lower()
        if c == "1":
            return True, False
        if c == "2":
            return False, True
        if c == "3":
            return True, True
        print("Choose 1, 2, or 3.")


@dataclass
class RunConfig:
    # scrape
    db_path: str
    subreddits: tuple[str, ...]
    listing: str
    post_limit: int
    more_limit: Optional[int]
    max_comments_per_post: int
    bot_usernames: tuple[str, ...] = ("AutoModerator", "VisualMod")

    # analyze
    analysis_tag: str = defaults.DEFAULT_ANALYSIS_TAG
    analysis_limit: int = defaults.DEFAULT_ANALYSIS_LIMIT
    model: str = defaults.DEFAULT_OPENAI_MODEL
    max_requests_per_minute: int = defaults.DEFAULT_MAX_REQUESTS_PER_MINUTE
    top_n: int = defaults.DEFAULT_TOP_N

    @staticmethod
    def defaults() -> "RunConfig":
        return RunConfig(
            db_path=defaults.DEFAULT_DB_PATH,
            subreddits=defaults.DEFAULT_SUBREDDITS,
            listing=defaults.DEFAULT_LISTING,
            post_limit=defaults.DEFAULT_POST_LIMIT,
            more_limit=defaults.DEFAULT_MORE_LIMIT,
            max_comments_per_post=defaults.DEFAULT_MAX_COMMENTS_PER_POST,
            analysis_tag=defaults.DEFAULT_ANALYSIS_TAG,
            analysis_limit=defaults.DEFAULT_ANALYSIS_LIMIT,
            model=defaults.DEFAULT_OPENAI_MODEL,
            max_requests_per_minute=defaults.DEFAULT_MAX_REQUESTS_PER_MINUTE,
            top_n=defaults.DEFAULT_TOP_N,
        )

    @staticmethod
    def from_user_input(*, do_scrape: bool | None = None, do_analyze: bool | None = None) -> "RunConfig":
        """
        Prompts only for settings relevant to the chosen action(s).

        IMPORTANT: If do_scrape/do_analyze are not provided (None),
        we prompt for the mode here so we don't accidentally ask for everything.
        """
        if do_scrape is None or do_analyze is None:
            do_scrape, do_analyze = _choose_mode()

        print("\n--- Choose settings ---")

        db_path = _prompt_str("Database file", defaults.DEFAULT_DB_PATH)

        subs = _prompt_str(
            "Subreddits (comma/space separated)",
            ", ".join(defaults.DEFAULT_SUBREDDITS),
        )
        subreddits = _split_list(subs) or defaults.DEFAULT_SUBREDDITS

        # Start from defaults
        listing = defaults.DEFAULT_LISTING
        post_limit = defaults.DEFAULT_POST_LIMIT
        max_comments = defaults.DEFAULT_MAX_COMMENTS_PER_POST
        more_limit = defaults.DEFAULT_MORE_LIMIT

        analysis_tag = defaults.DEFAULT_ANALYSIS_TAG
        analysis_limit = defaults.DEFAULT_ANALYSIS_LIMIT
        model = defaults.DEFAULT_OPENAI_MODEL
        rpm = defaults.DEFAULT_MAX_REQUESTS_PER_MINUTE
        top_n = defaults.DEFAULT_TOP_N

        if do_scrape:
            listing = _prompt_str("Listing (hot/new/rising/top)", defaults.DEFAULT_LISTING).lower()
            if listing not in {"hot", "new", "rising", "top"}:
                print("Invalid listing; using default.")
                listing = defaults.DEFAULT_LISTING

            post_limit = _prompt_int("Posts per subreddit", defaults.DEFAULT_POST_LIMIT, min_value=1)
            max_comments = _prompt_int("Max comments per post", defaults.DEFAULT_MAX_COMMENTS_PER_POST, min_value=1)
            more_limit = _prompt_optional_int("replace_more limit", defaults.DEFAULT_MORE_LIMIT)

        if do_analyze:
            analysis_tag = _prompt_str("Analysis tag", defaults.DEFAULT_ANALYSIS_TAG)
            analysis_limit = _prompt_int("Max comments to analyze per run", defaults.DEFAULT_ANALYSIS_LIMIT, min_value=1)
            model = _prompt_str("OpenAI model", defaults.DEFAULT_OPENAI_MODEL)
            rpm = _prompt_int(
                "Max OpenAI requests per minute (0 disables pacing)",
                defaults.DEFAULT_MAX_REQUESTS_PER_MINUTE,
                min_value=0,
            )
            top_n = _prompt_int("Top N to display in report", defaults.DEFAULT_TOP_N, min_value=1)

        return RunConfig(
            db_path=db_path,
            subreddits=subreddits,
            listing=listing,
            post_limit=post_limit,
            more_limit=more_limit,
            max_comments_per_post=max_comments,
            analysis_tag=analysis_tag,
            analysis_limit=analysis_limit,
            model=model,
            max_requests_per_minute=rpm,
            top_n=top_n,
        )
