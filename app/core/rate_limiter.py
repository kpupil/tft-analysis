"""进程内令牌桶 / 滑动窗口限流（无需 Redis）。

采集是单进程异步，内存窗口足够。Riot 限流是双层（1s + 120s），
这里并行维护两个窗口。切换 prod key 时只改 config 的速率数字，代码不动。
"""
import time
import asyncio
from collections import deque

from app.core.config import settings


class SlidingWindowLimiter:
    def __init__(self, per_second: int, per_two_min: int):
        self._windows = [(1.0, per_second, deque()), (120.0, per_two_min, deque())]
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                wait = 0.0
                for span, limit, dq in self._windows:
                    while dq and dq[0] <= now - span:
                        dq.popleft()
                    if len(dq) >= limit:
                        wait = max(wait, dq[0] + span - now)
                if wait > 0:
                    await asyncio.sleep(wait + 0.01)
                    continue
                for _, _, dq in self._windows:
                    dq.append(time.monotonic())
                return


limiter = SlidingWindowLimiter(settings.rate_per_second, settings.rate_per_two_min)
