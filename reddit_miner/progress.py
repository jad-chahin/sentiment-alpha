import sys
import time


class ProgressBar:
    def __init__(self, total: int, prefix: str = "", width: int = 30):
        self.total = max(1, int(total))
        self.prefix = prefix
        self.width = max(5, int(width))
        self.start = time.time()
        self.last_draw = 0.0

    def update(self, current: int) -> None:
        now = time.time()
        # Throttle redraw slightly
        if now - self.last_draw < 0.05 and current < self.total:
            return
        self.last_draw = now

        cur = max(0, min(int(current), self.total))
        frac = cur / self.total
        filled = int(self.width * frac)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = int(now - self.start)

        msg = f"\r{self.prefix} [{bar}] {cur}/{self.total} ({frac * 100:5.1f}%)  {elapsed}s"
        sys.stdout.write(msg)
        sys.stdout.flush()

        if cur >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()
