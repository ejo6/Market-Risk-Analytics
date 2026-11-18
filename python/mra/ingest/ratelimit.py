import time
from collections import deque

class BudgetExhausted(Exception): ...

class SlidingWindowLimiter:
    """
    limits = [(max_calls, window_seconds), ...]  
    On Tiingo:
        Free: [(50, 3600), (1000, 86400)]
        Power: [(10000, 3600), (100000, 86400)]
        Commercial: [(20000, 3600), (150000, 86400)]
    """

    def __init__(self, limits: list[tuple], max_wait: float = 120):
        self.limits = limits
        self.max_wait = max_wait
        self.calls: deque[float] = deque()

    def acquire(self) -> None:
        longest = max(window_seconds for _, window_seconds in self.limits)
        while True:
            now = time.monotonic()

            # 1. Prune: Drop timestamps too old to matter for any limit:
            while self.calls and now - self.calls[0] >= longest:
                self.calls.popleft()

            # 2. Check how long until we get a free slot
            wait = 0
            for max_calls, window in self.limits:
                # All calls that fall in the window of choice
                recent = [time for time in self.calls if now - time < window]
                if len(recent) >= max_calls:
                    # If we've exceeded the call in the window, set wait until the oldest request is evicted
                    wait = max(wait, window - (now - recent[0]))

            # 3. Free slot under every limit (enqueue before we even try)
            #    Need to confirmt that failed requests still count against rate
            if wait <= 0: 
                self.calls.append(now)
                return # !!! Important bugfix

            # 4. Too long to wait, just bail in this request and raise exception
            if wait > self.max_wait:
                raise BudgetExhausted(f"Next slot in {wait:.0f}s")
            time.sleep(wait)
