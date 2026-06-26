# TFT Analysis — 数据库采集

当前阶段只做一件事：持续采集高分段 TFT 排位对局，并把采集状态与 Riot 原始
match JSON 存进数据库。解析、聚合、阵容统计、聚类等分析层后续再做。

## 生产形态

```
榜单种子玩家 -> 发现 match id -> 入队 -> 拉 match detail -> raw_matches.raw_json
```

采集链路拆成三步：

```bash
python -m app.collector.seed       # 1. 拉宗师/王者榜单，写 seed_players
python -m app.collector.discover   # 2. 按种子玩家发现 match id，写 match_discovery
python -m app.collector.collect    # 3. 从队列抓 match detail，写 raw_matches
```

初始化数据库：

```bash
python -m app.core.init_db
```

## 数据库选择

服务器部署建议使用 PostgreSQL。采集阶段需要可靠的唯一约束、状态更新、失败重试、
JSON 原文存储和后续查询索引，PostgreSQL 比文件目录、SQLite 或 DuckDB 更适合作为
主采集库。

本地默认 `DATABASE_URL=sqlite:///tft_analysis.db` 只是为了快速开发验证。部署到
服务器时请改成 PostgreSQL：

```env
DATABASE_URL=postgresql+psycopg://tft:password@127.0.0.1:5432/tft_analysis
```

## 核心表

`seed_players`

- 当前种子玩家池，按 `platform + puuid` 去重。
- 保存 tier、LP、胜负、最后一次榜单刷新时间。

`match_discovery`

- match id 队列，`match_id` 全局唯一。
- `status` 可为 `pending`、`retry`、`fetched`、`skipped`、`failed`。
- 非排位对局标记 `skipped`，失败请求记录 `attempts`、`last_error`、`next_retry_at`。

`raw_matches`

- 排位 match detail 主存储，`match_id` 全局唯一。
- 保存 `queue_id`、`tft_set_number`、`tft_set_core_name`、`game_version`、`patch`、
  `game_datetime` 和完整 `raw_json`。

## 配置

全部配置走 `.env`：

| 变量 | 说明 |
|------|------|
| `RIOT_API_KEY` | Riot dev key 或 production key |
| `DATABASE_URL` | 数据库连接；生产建议 PostgreSQL |
| `REGIONS` | 采集服务器；默认 `kr,euw1,na1` |
| `MIN_TIER` | 种子玩家最低段位；当前支持 `GRANDMASTER` |
| `RATE_PER_SECOND` / `RATE_PER_TWO_MIN` | Riot API 限流配额 |
| `MAX_MATCHES_PER_PLAYER` | 每个种子玩家每轮发现多少个最近 match id |
| `FETCH_BATCH_SIZE` | 每轮 fetch worker 处理多少个待抓 match |
| `RANKED_QUEUE_ID` | TFT 排位队列，默认 `1100` |

## 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m app.core.init_db
python -m app.collector.seed
python -m app.collector.discover
python -m app.collector.collect
```

## 服务器建议

建议目录：

```text
/opt/tft-analysis       # 代码
PostgreSQL              # 采集主库
systemd timer/worker    # 定时跑 seed/discover/collect
```

推荐调度：

- `seed`：每 6-12 小时刷新一次榜单种子。
- `discover`：每 5-15 分钟发现新 match id。
- `collect`：每 1 分钟跑一次，或常驻 worker 循环执行。

当前版本过滤不要放在采集入口硬丢数据。采集层保存排位原始 match；后续分析层再按
`tft_set_number`、`queue_id`、`patch` 做口径过滤。
