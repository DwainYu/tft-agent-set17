# TFT 数据采集向导

## 目标

采集指定服务器的 **王者（Challenger）段位** 玩家对局数据，用于阵容分析、Meta 研究和玩家行为洞察。

## 整体流程

```
Step 1                Step 2                Step 3
获取玩家列表    →     获取对局 ID    →     获取对局详情
(League API)         (Match API)          (Match API)
platform 路由         regional 路由        regional 路由
```

## 路由说明（重要）

Riot API 有两套路由，**不能混用**：

| 路由类型 | Base URL | 适用接口 | 示例值 |
|----------|----------|----------|--------|
| **Platform** | `https://{platform}.api.riotgames.com` | League / Summoner / Status | `jp1`, `kr`, `na1` |
| **Regional** | `https://{region}.api.riotgames.com` | Match | `asia`, `europe`, `americas` |

**Platform → Regional 映射表：**

| Platform | Regional | 包含服务器 |
|----------|----------|-----------|
| `jp1` | `asia` | JP |
| `kr` | `asia` | KR |
| `tw2` | `asia` | TW |
| `sg2` | `sea` | SG, PH, TH, VN, MY, ID |
| `euw1`, `eun1`, `tr1`, `ru` | `europe` | EUW, EUNE, TR, RU |
| `na1`, `br1`, `la1`, `la2`, `oc1` | `americas` | NA, BR, LAN, LAS, OCE |

> Step 1 用 platform（如 `jp1`），Step 2/3 用 regional（如 `asia`）。

---

## Step 1: 获取王者玩家列表

**目的**: 拿到指定服务器所有 Challenger 玩家的 PUUID。

### 接口

```
GET https://{platform}.api.riotgames.com/tft/league/v1/challenger
```

### 请求参数

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| `queue` | query | 否 | `RANKED_TFT`（默认）或 `RANKED_TFT_DOUBLE_UP` |
| `api_key` | query | 是 | Riot API Key |

### 请求示例

```
GET https://jp1.api.riotgames.com/tft/league/v1/challenger?queue=RANKED_TFT&api_key=RGAPI-xxx
```

### 响应结构

```json
{
  "tier": "CHALLENGER",
  "queue": "RANKED_TFT",
  "entries": [
    {
      "puuid": "6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKO...",
      "leaguePoints": 1818,
      "rank": "I",
      "wins": 460,
      "losses": 220,
      "veteran": true,
      "inactive": false,
      "freshBlood": false,
      "hotStreak": true
    },
    { "... 更多玩家 ...": "" }
  ]
}
```

### 关键字段

| 字段 | 说明 |
|------|------|
| `puuid` | 玩家唯一标识，**Step 2/3 的核心参数** |
| `leaguePoints` | LP 积分，按此字段降序排列 |
| `wins` / `losses` | 胜场/负场 |
| `veteran` | 该段位是否打了足够多场 |
| `hotStreak` | 是否连胜中 |

### 数据规模

JP1 服务器约 75 个 Challenger 玩家。每个服务器数量固定，Challenger > Grandmaster(~500) > Master(~1000)。

### 产物

```json
// data/raw/challengers.json
{ "count": 75, "puuids": ["puuid1", "puuid2", "..."] }
```

---

## Step 2: 获取对局 ID 列表

**目的**: 遍历每个 Challenger 玩家，按时间范围查对局 ID。

### 接口

```
GET https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids
```

> 注意：这里用 **regional** 路由（`asia`），不是 platform（`jp1`）。

### 请求参数

| 参数 | 位置 | 必填 | 类型 | 说明 |
|------|------|------|------|------|
| `puuid` | path | 是 | string | 玩家 PUUID（来自 Step 1） |
| `startTime` | query | 否 | long | 起始时间（Epoch 秒） |
| `endTime` | query | 否 | long | 结束时间（Epoch 秒） |
| `start` | query | 否 | int | 分页起始索引，默认 0 |
| `count` | query | 否 | int | 返回数量，默认 20，最大 100 |
| `api_key` | query | 是 | string | Riot API Key |

### 请求示例

```
GET https://asia.api.riotgames.com/tft/match/v1/matches/by-puuid/6eLOz-k1Xno8Cs2SwDQtaTI4q79m4F.../ids?startTime=1783872000&endTime=1784131199&count=100&api_key=RGAPI-xxx
```

### 时间参数计算（Python）

```python
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
start_time = int(datetime(2026, 7, 11, 0, 0, 0, tzinfo=CST).timestamp())  # 1783872000
end_time   = int(datetime(2026, 7, 13, 23, 59, 59, tzinfo=CST).timestamp())  # 1784131199
```

### 响应结构

```json
[
  "JP1_592504790",
  "JP1_592501982",
  "JP1_592501054",
  "..."
]
```

返回纯字符串数组，每个元素是一个 matchId。

### 去重逻辑

同一场对局中 8 名玩家可能有多个 Challenger，所以不同 PUUID 会返回重复的 matchId。**必须全局去重**。

### 数据规模估算

| 参数 | 典型值 |
|------|--------|
| 75 个 Challenger 玩家 | 每人 3 天约 10-30 场 |
| 原始 matchId 总数 | ~900-1500 |
| 去重后 | ~400-500 |
| 原因 | 每局 8 人只有 1-2 个 Challenger，重合度高 |

### 产物

```json
// data/raw/match_ids.json
{ "count": 471, "ids": ["JP1_592504790", "JP1_592501982", "..."] }
```

---

## Step 3: 获取对局详情

**目的**: 逐场拉取完整的对局数据（8 名玩家的阵容、装备、排名等）。

### 接口

```
GET https://{region}.api.riotgames.com/tft/match/v1/matches/{matchId}
```

### 请求参数

| 参数 | 位置 | 必填 | 说明 |
|------|------|------|------|
| `matchId` | path | 是 | 对局 ID（如 `JP1_592504790`） |
| `api_key` | query | 是 | Riot API Key |

### 请求示例

```
GET https://asia.api.riotgames.com/tft/match/v1/matches/JP1_592504790?api_key=RGAPI-xxx
```

### 响应结构（顶层）

```json
{
  "metadata": {
    "data_version": "6",
    "match_id": "JP1_592504790",
    "participants": ["puuid1", "puuid2", "... (8个)"]
  },
  "info": {
    "endOfGameResult": "GameComplete",
    "gameCreation": 1783922269000,
    "gameId": 592504790,
    "game_datetime": 1783924031749,
    "game_length": 1748.1,
    "game_version": "Linux Version 16.13.791.5903 ...",
    "queueId": 1100,
    "queue_id": 1100,
    "tft_game_type": "standard",
    "tft_set_core_name": "TFTSet17",
    "tft_set_number": 17,
    "participants": [ ... ]
  }
}
```

### info 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `game_datetime` | long | 对局开始时间（Epoch 毫秒） |
| `game_length` | float | 对局时长（秒） |
| `queue_id` | int | 队列类型：1100=Ranked, 1090=Normal, 1160=Hyper Roll |
| `tft_set_number` | int | 赛季编号（17 = Set 17 Space Gods） |
| `participants` | array | 8 名玩家的详细数据 |

### participant 字段说明（每个玩家）

| 字段 | 类型 | 说明 |
|------|------|------|
| `puuid` | string | 玩家 PUUID |
| `riotIdGameName` | string | Riot ID 名称 |
| `riotIdTagline` | string | Riot ID 标签（#后的部分） |
| `placement` | int | 最终排名（1=吃鸡, 8=最后） |
| `win` | bool | 是否第一名 |
| `level` | int | 最终等级 |
| `gold_left` | int | 剩余金币 |
| `last_round` | int | 存活到的最后回合 |
| `total_damage_to_players` | int | 对其他玩家造成的总伤害 |
| `players_eliminated` | int | 淘汰的玩家数 |
| `time_eliminated` | float | 被淘汰时间（秒） |
| `traits` | array | 羁绊列表 |
| `units` | array | 棋盘上的棋子列表 |
| `companion` | object | 小小英雄信息 |

### traits 字段说明（每个羁绊）

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 羁绊 ID（如 `TFT17_SpaceGroove`） |
| `num_units` | int | 激活所需棋子数 |
| `style` | int | 激活等级样式（0=未激活） |
| `tier_current` | int | 当前激活等级 |
| `tier_total` | int | 最大可达等级 |

### units 字段说明（每个棋子）

| 字段 | 类型 | 说明 |
|------|------|------|
| `character_id` | string | 棋子 ID（如 `TFT17_Ahri`） |
| `tier` | int | 星级（1/2/3） |
| `rarity` | int | 费用（不可信，大量 0 值） |
| `itemNames` | string[] | 装备列表（字符串数组） |

### 产物

```json
// data/raw/matches_raw.json  (~20 MB)
[
  { "metadata": {...}, "info": {...} },
  { "metadata": {...}, "info": {...} },
  "..."
]
```

---

## 速率限制

Dev Key 的限制：

| 限制类型 | 阈值 | 说明 |
|----------|------|------|
| App Rate | 20 请求/秒 | 所有接口共享 |
| Method Rate | 100 请求/120秒 | 每个接口独立计算 |

被限流时返回 `429`，响应头 `Retry-After` 告诉你等几秒。

**实际采集耗时**（471 场对局）：约 10 分钟。

---

## 脚本用法

```bash
# 完整采集 Step 1-3（约 10 分钟）
uv run python data_collection/scripts/fetch_challenger_matches.py

# 仅 Step 1-2（秒级完成，用于快速获取 match ID 列表）
uv run python data_collection/scripts/fetch_challenger_matches.py --skip-details

# 限制对局数（调试用）
uv run python data_collection/scripts/fetch_challenger_matches.py --max-matches 10

# 清洗为 CSV 平表
uv run python data_collection/scripts/clean_data.py
```

脚本支持 **断点续传**：已保存的中间文件会被自动复用，跳过已完成的步骤。删除 `data/raw/` 中的对应文件即可重跑。

---

## 已知限制

| 限制 | 说明 | 影响 |
|------|------|------|
| 无 augments | Set 17 Match API 不返回强化符文 | 无法分析强化选择 |
| unit.name 为空 | 只有 character_id | 需本地映射显示名 |
| unit.rarity 不准 | 大量 0 值 | 费用信息不可信 |
| game_version | Linux 构建字符串 | 需解析才能读版本号 |

---

## 数据文件总览

| 文件 | 内容 | 大小 |
|------|------|------|
| `data/raw/challengers.json` | 75 个 Challenger PUUID | 6.5 KB |
| `data/raw/match_ids.json` | 471 个去重对局 ID | 10.3 KB |
| `data/raw/matches_raw.json` | 471 场完整对局 JSON | 19.9 MB |
| `data/cleaned/matches.csv` | 427 场 Ranked 对局 | 37.6 KB |
| `data/cleaned/participants.csv` | 3,416 行玩家数据 | 518 KB |
| `data/cleaned/units.csv` | 29,828 行棋子数据 | 3.8 MB |
| `data/cleaned/traits.csv` | 37,196 行羁绊数据 | 5.2 MB |
| `data/cleaned/items.csv` | 42,485 行装备数据 | 6.2 MB |
