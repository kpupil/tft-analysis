"""对局采集：种子 PUUID → match id 列表 → 原始 match JSON 落盘。

只保留排位对局（queue_id == RANKED_QUEUE_ID），非排位的丢弃。
幂等去重 + 可中断续传：
- 已保存的排位局（data/raw/ 里有文件）跳过；
- 已确认的非排位局记在 data/skip_ids.txt，避免下次再请求浪费限流。
"""
import asyncio
import glob
import json
import os

from app.core.config import settings
from app.core.riot_client import RiotClient

SEED_DIR = "data/seeds"
RAW_DIR = "data/raw"
SKIP_FILE = "data/skip_ids.txt"


def _load_skip() -> set[str]:
    if os.path.exists(SKIP_FILE):
        with open(SKIP_FILE) as f:
            return {line.strip() for line in f if line.strip()}
    return set()


def _is_ranked(detail: dict) -> bool:
    return detail.get("info", {}).get("queue_id") == settings.ranked_queue_id


async def collect_matches() -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    skip = _load_skip()
    skip_fp = open(SKIP_FILE, "a")
    client = RiotClient()
    kept = dropped = 0
    try:
        for platform in settings.region_list:
            seed_file = f"{SEED_DIR}/{platform}.json"
            if not os.path.exists(seed_file):
                print(f"[collect] 缺少种子 {seed_file}，先跑 seed.py")
                continue
            with open(seed_file) as f:
                seed_data = json.load(f)
            # 兼容旧版纯 PUUID 列表和新版带段位元数据的种子文件。
            if isinstance(seed_data, list):
                puuids = seed_data
            else:
                puuids = [p["puuid"] for p in seed_data.get("players", [])]
            for puuid in puuids:
                match_ids = await client.matches_by_puuid(
                    puuid, platform, count=settings.max_matches_per_player
                )
                for mid in match_ids:
                    # 已保存的排位局 / 已知的非排位局都跳过
                    if os.path.exists(f"{RAW_DIR}/{mid}.json") or mid in skip:
                        continue
                    detail = await client.match_detail(mid, platform)
                    if _is_ranked(detail):
                        with open(f"{RAW_DIR}/{mid}.json", "w") as f:
                            json.dump(detail, f)
                        kept += 1
                    else:
                        skip.add(mid)
                        skip_fp.write(mid + "\n")
                        skip_fp.flush()
                        dropped += 1
            n = len(glob.glob(f"{RAW_DIR}/*.json"))
            print(f"[collect] {platform} 完成 | 本轮保留排位 {kept} 丢弃非排位 {dropped} "
                  f"| 本地累计排位局 {n}")
    finally:
        skip_fp.close()
        await client.close()


if __name__ == "__main__":
    asyncio.run(collect_matches())
