"""对局详情采集：从数据库队列拉取 match detail 并存入 raw_matches。

只保留排位对局（queue_id == RANKED_QUEUE_ID），非排位的丢弃。
幂等去重 + 可中断续传：
- 待抓 match id 来自 match_discovery；
- 已保存的排位局写入 raw_matches；
- 已确认的非排位局标记 skipped，避免下次再请求浪费限流。
"""
import asyncio

from app.collector.repository import (
    load_fetch_candidates,
    mark_failed,
    mark_skipped,
    save_raw_match,
)
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.riot_client import RiotClient


def _is_ranked(detail: dict) -> bool:
    info = detail.get("info", {})
    queue_id = info.get("queue_id", info.get("queueId"))
    return queue_id == settings.ranked_queue_id


async def collect_matches() -> None:
    init_db()
    client = RiotClient()
    kept = dropped = 0
    try:
        with SessionLocal() as session:
            candidates = load_fetch_candidates(session, settings.fetch_batch_size)
            if not candidates:
                print("[collect] 没有待抓 match，先跑 discover.py 或等待重试时间")
                return

            for discovery in candidates:
                try:
                    detail = await client.match_detail(discovery.match_id, discovery.platform)
                    if _is_ranked(detail):
                        save_raw_match(session, discovery, detail)
                        kept += 1
                    else:
                        mark_skipped(session, discovery, "non-ranked queue")
                        dropped += 1
                except Exception as exc:  # noqa: BLE001 - worker must record and continue.
                    session.rollback()
                    mark_failed(session, discovery, f"{type(exc).__name__}: {exc}")

        print(
            f"[collect] 本轮处理 {len(candidates)} 个 | "
            f"保留排位 {kept} | 丢弃非排位 {dropped}"
        )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(collect_matches())
