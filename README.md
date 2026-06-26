# TFT Analysis — 对局采集

只负责一件事：从 Riot API 把高分段对局原始 JSON 抓到本地。
解析、入库、聚合、聚类等留给你自己实现。

## 流程

```
宗师/王者榜单种子 → 每个玩家的 match id 列表 → 拉取每局 match JSON → 存到 data/raw/
```

## 目录结构

```
tft-analysis/
├── app/
│   ├── core/
│   │   ├── config.py        # 配置（全部走 .env，dev/prod 通用）
│   │   ├── rate_limiter.py  # 进程内滑动窗口限流（1s + 120s 双窗口）
│   │   └── riot_client.py   # Riot API 异步客户端（429/5xx 退避重试）
│   └── collector/
│       ├── seed.py          # 拉各区域宗师/王者榜单 → data/seeds/{region}.json
│       └── collect.py       # 抓对局原始 JSON → data/raw/{match_id}.json
├── requirements.txt
├── .env.example
└── .env                     # 你的 key（已被 .gitignore 忽略）
```

## 用法

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m app.collector.seed      # 1. 拉榜单种子玩家
python -m app.collector.collect   # 2. 抓对局，落到 data/raw/
```

原始数据就在 `data/raw/*.json`，每个文件是一局完整的 tft-match-v1 响应。

## 去重 / 续传

- **采集去重**：抓之前检查 `data/raw/{match_id}.json` 是否已存在，存在即跳过。
  同一局被多个种子玩家共享时只抓一次。
- **可中断续传**：`collect` 随时 Ctrl+C，再跑会自动跳过已抓的对局。

## 配置（.env）

| 变量 | 说明 |
|------|------|
| `RIOT_API_KEY` | dev key（24h 过期）或 production key |
| `REGIONS` | 采集服务器；默认 `kr,euw1,na1`，分别覆盖韩服、西欧和北美 |
| `MIN_TIER` | 种子玩家最低段位；当前为 `GRANDMASTER` |
| `RATE_PER_SECOND` / `RATE_PER_TWO_MIN` | 限流配额，dev/prod 唯一区别就是这两个数 |
| `MAX_MATCHES_PER_PLAYER` | 每个种子玩家最多抓多少局 |

服务器会自动映射到 match-v1 的洲际路由，多服同时采集时无需再手动配置 `ROUTING`。

## dev → prod 切换

key 和速率全部走 `.env`，**换 Production Key 时不改任何代码**，只调 `RIOT_API_KEY` 和 `RATE_*`。

## 原始 match JSON 结构（供你后续解析参考）

```
metadata.match_id
metadata.participants[]              # PUUID 列表
info.game_datetime                   # Unix 毫秒
info.game_version                    # 版本字符串
info.tft_set_number                  # 当前 Set 号
info.participants[]
  ├── puuid / placement(1最好) / level / last_round / gold_left
  ├── traits[]    { name, num_units, tier_current, style }
  ├── units[]     { character_id, tier(星级), rarity, items[] }
  └── augments[]  # 3 个，对应 2-2 / 3-2 / 4-2
```
