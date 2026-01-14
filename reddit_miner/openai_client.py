import os
import time
from collections import deque

from openai import OpenAI


class RateLimiter:
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max(1, int(max_per_minute))
        self.times: deque[float] = deque()

    def wait(self) -> None:
        now = time.monotonic()

        # Drop timestamps older than 60 seconds
        while self.times and (now - self.times[0]) > 60:
            self.times.popleft()

        # If at limit, sleep until the oldest timestamp falls out of the window
        if len(self.times) >= self.max_per_minute:
            sleep_for = 60 - (now - self.times[0]) + 0.25
            time.sleep(max(0.0, sleep_for))

            # Recompute window after sleeping to avoid drift
            now = time.monotonic()
            while self.times and (now - self.times[0]) > 60:
                self.times.popleft()

        self.times.append(time.monotonic())


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Put it in .env or env vars.")
    return OpenAI(api_key=api_key)
