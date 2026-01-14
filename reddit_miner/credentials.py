from __future__ import annotations

import os
from getpass import getpass

import keyring
from keyring.errors import PasswordDeleteError

SERVICE = "RedditSentimentMiner"

OPENAI_KEY = "OPENAI_API_KEY"
REDDIT_CLIENT_ID = "REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET = "REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT = "REDDIT_USER_AGENT"

ALL_KEYS: tuple[str, ...] = (OPENAI_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT)


def get_secret(name: str) -> str | None:
    v = os.getenv(name)
    if v:
        return v
    return keyring.get_password(SERVICE, name)


def set_secret(name: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{name} cannot be empty.")
    keyring.set_password(SERVICE, name, value)


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(SERVICE, name)
    except PasswordDeleteError:
        # Treat "not found" as already deleted
        pass


def reset_all() -> None:
    for k in ALL_KEYS:
        delete_secret(k)


def require_secret(
    name: str,
    prompt: str,
    hidden: bool = True,
    default: str | None = None,
) -> str:
    existing = get_secret(name)
    if existing:
        return existing

    if default is not None and not hidden:
        raw = input(f"{prompt} [{default}]: ").strip()
        value = raw if raw else default
    else:
        value = getpass(prompt + ": ") if hidden else input(prompt + ": ").strip()

    set_secret(name, value)
    return value


def ensure_credentials(
    *,
    need_openai: bool,
    need_reddit: bool,
    default_user_agent: str = "reddit-miner",
) -> None:
    if need_openai:
        require_secret(OPENAI_KEY, "Paste your OpenAI API key", hidden=True)

    if need_reddit:
        require_secret(REDDIT_CLIENT_ID, "Paste your Reddit client_id", hidden=False)
        require_secret(REDDIT_CLIENT_SECRET, "Paste your Reddit client_secret", hidden=True)

        if not get_secret(REDDIT_USER_AGENT):
            set_secret(REDDIT_USER_AGENT, default_user_agent)


def set_openai_key_interactive() -> None:
    value = getpass("Paste your OpenAI API key (hidden): ").strip()
    if not value:
        print("No key entered.")
        return
    set_secret(OPENAI_KEY, value)
    print("OpenAI key saved.")


def set_reddit_credentials_interactive(default_user_agent: str = "reddit-miner") -> None:
    cid = input("Paste your Reddit client_id: ").strip()
    if not cid:
        print("No client_id entered.")
        return

    csec = getpass("Paste your Reddit client_secret (hidden): ").strip()
    if not csec:
        print("No client_secret entered.")
        return

    ua = input(f"Reddit user_agent [{default_user_agent}]: ").strip() or default_user_agent

    set_secret(REDDIT_CLIENT_ID, cid)
    set_secret(REDDIT_CLIENT_SECRET, csec)
    set_secret(REDDIT_USER_AGENT, ua)
    print("Reddit credentials saved.")


def load_into_env_if_missing() -> None:
    """
    Copies stored secrets into os.environ IF they are not already set.
    Useful when the rest of the app reads credentials via os.getenv().
    """
    for k in ALL_KEYS:
        if not os.getenv(k):
            v = get_secret(k)
            if v:
                os.environ[k] = v
