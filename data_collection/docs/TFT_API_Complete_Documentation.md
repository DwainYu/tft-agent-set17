# TFT API 接口文档

> **Base URL**: `https://{platform}.api.riotgames.com`
>
> **platform 可选值**: `br1` · `eun1` · `euw1` · `jp1` · `kr` · `la1` · `la2` · `me1` · `na1` · `oc1` · `ru` · `sg2` · `tr1` · `tw2` · `vn2` · `pbe1`（测试服）
>
> **版本**: `55d92749088467cdc4bb517458b1eb6caa5234a8`
>
> **认证**: 所有请求需在 query string 中传入 `api_key` 参数，或使用 OAuth2 Bearer Token

---

## 目录

1. [TFT League V1 — 天梯段位](#1-tft-league-v1--天梯段位)
   - [1.1 根据 PUUID 查询段位](#11-根据-puuid-查询段位)
   - [1.2 查询 Challenger 段位](#12-查询-challenger-段位)
   - [1.3 查询指定 Tier/Division 段位条目](#13-查询指定-tierdivision-段位条目)
   - [1.4 查询 Grandmaster 段位](#14-查询-grandmaster-段位)
   - [1.5 查询 Master 段位](#15-查询-master-段位)
   - [1.6 查询 Rated 天梯排行榜](#16-查询-rated-天梯排行榜)
2. [TFT Match V1 — 对局详情](#2-tft-match-v1--对局详情)
   - [2.1 根据 PUUID 查询对局 ID 列表](#21-根据-puuid-查询对局-id-列表)
   - [2.2 根据 Match ID 查询对局详情](#22-根据-match-id-查询对局详情)
3. [TFT Status V1 — 服务状态](#3-tft-status-v1--服务状态)
   - [3.1 查询平台状态](#31-查询平台状态)
4. [TFT Summoner V1 — 召唤师信息](#4-tft-summoner-v1--召唤师信息)
   - [4.1 根据 PUUID 查询召唤师](#41-根据-puuid-查询召唤师)
   - [4.2 根据 Access Token 查询当前召唤师](#42-根据-access-token-查询当前召唤师)
5. [通用错误码](#5-通用错误码)

---

## 1. TFT League V1 — 天梯段位

### 1.1 根据 PUUID 查询段位

**接口**: `GET /tft/league/v1/by-puuid/{puuid}`

**描述**: 查询指定 PUUID 玩家在 **所有队列**（RANKED_TFT 和 RANKED_TFT_DOUBLE_UP）中的段位信息。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-league-v1/GET_getLeagueEntriesByPUUID

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `puuid` | path | string | 是 | 玩家 PUUID |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://jp1.api.riotgames.com/tft/league/v1/by-puuid/{puuid}?api_key=RGAPI-xxx
```

#### 响应

返回 `LeagueEntryDTO[]` 数组。数组中每个元素的字段定义如下：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `puuid` | string | 玩家 PUUID |
| `leagueId` | string | 天梯 ID（UUID 格式，同一服务器所有 Challenger/Grandmaster/Master 玩家共用一个 leagueId） |
| `summonerId` | string | 召唤师 ID（加密后） |
| `summonerName` | string | 召唤师名称 |
| `queueType` | string | 队列类型：`RANKED_TFT`（单排）/ `RANKED_TFT_DOUBLE_UP`（双人模式） |
| `tier` | string | 段位等级：`IRON` / `BRONZE` / `SILVER` / `GOLD` / `PLATINUM` / `EMERALD` / `DIAMOND` |
| `rank` | string | 段位等级细分：`I` / `II` / `III` / `IV` |
| `leaguePoints` | integer | 段位积分 (LP)，范围 0-100（Diamond 以上段位 LP 可超过 100） |
| `wins` | integer | 胜场数 |
| `losses` | integer | 负场数 |
| `veteran` | boolean | 是否为老玩家（该段位打了足够多场） |
| `inactive` | boolean | 是否处于不活跃状态（长期未打排位赛） |
| `freshBlood` | boolean | 是否为新晋玩家（最近才晋升到该段位） |
| `hotStreak` | boolean | 是否处于连胜状态（连续赢得多场） |

#### 响应示例

```json
[
  {
    "puuid": "6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKOJIfg9U9dxf-ZbqQC2HxTUA",
    "leagueId": "c5a4a000-0000-0000-0000-000000000000",
    "summonerId": "aB3xYz...encrypted",
    "summonerName": "PlayerName",
    "queueType": "RANKED_TFT",
    "tier": "DIAMOND",
    "rank": "II",
    "leaguePoints": 75,
    "wins": 120,
    "losses": 95,
    "veteran": true,
    "inactive": false,
    "freshBlood": false,
    "hotStreak": false
  },
  {
    "puuid": "6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKOJIfg9U9dxf-ZbqQC2HxTUA",
    "leagueId": "c5a4a001-0000-0000-0000-000000000000",
    "summonerId": "aB3xYz...encrypted",
    "summonerName": "PlayerName",
    "queueType": "RANKED_TFT_DOUBLE_UP",
    "tier": "PLATINUM",
    "rank": "I",
    "leaguePoints": 42,
    "wins": 30,
    "losses": 25,
    "veteran": false,
    "inactive": false,
    "freshBlood": true,
    "hotStreak": true
  }
]
```

> 该玩家同时存在于单排（DIAMOND II）和双人模式（PLATINUM I）两个队列中，所以数组返回两条记录。

---

### 1.2 查询 Challenger 段位

**接口**: `GET /tft/league/v1/challenger`

**描述**: 获取 Challenger（最强王者）段位的全部玩家列表。每个服务器（平台）的 Challenger 人数固定（约 250 人）。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-league-v1/GET_getChallengerLeague

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `queue` | query | string | 否 | 队列类型，默认 `RANKED_TFT`。可选值：`RANKED_TFT` / `RANKED_TFT_DOUBLE_UP` |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://jp1.api.riotgames.com/tft/league/v1/challenger?queue=RANKED_TFT&api_key=RGAPI-xxx
```

#### 响应

返回 `LeagueListDTO` 对象，其 `entries` 数组中每个元素为 `LeagueEntryDTO`。

**LeagueListDTO（顶层）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `tier` | string | 段位等级，此接口固定为 `"CHALLENGER"` |
| `queue` | string | 队列类型，如 `"RANKED_TFT"` |
| `entries` | `LeagueEntryDTO[]` | 段位条目列表，每个元素字段同 1.1 响应 |

> 注：Challenger 玩家无 `summonerName`/`summonerId`/`leagueId` 字段，使用 `puuid` 标识。

#### 响应示例（真实数据，JP1 服务器，截选前 3 名）

```json
{
  "tier": "CHALLENGER",
  "queue": "RANKED_TFT",
  "entries": [
    {
      "puuid": "6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKOJIfg9U9dxf-ZbqQC2HxTUA",
      "leaguePoints": 1818,
      "rank": "I",
      "wins": 460,
      "losses": 220,
      "veteran": true,
      "inactive": false,
      "freshBlood": false,
      "hotStreak": true
    },
    {
      "puuid": "fi_uqJywiBT-5fl_w4XCbCjyrZtasjKY3sg6vcZdfb6X1caYv2f5y3Q6GbzrA2XEZRw6aEpNAT-PFQ",
      "leaguePoints": 1800,
      "rank": "I",
      "wins": 214,
      "losses": 78,
      "veteran": true,
      "inactive": false,
      "freshBlood": false,
      "hotStreak": true
    },
    {
      "puuid": "y96Z_nqwad_YkHY7S9mkpBMVftVJSo6AkVVO20O0fEV2KKRVvKzSOdhJ5H2C-RZBx8Ivbri1z3y0uQ",
      "leaguePoints": 1677,
      "rank": "I",
      "wins": 356,
      "losses": 206,
      "veteran": true,
      "inactive": false,
      "freshBlood": false,
      "hotStreak": false
    }
  ]
}
```

> `entries` 按 `leaguePoints` 降序排列，第一名 1818 LP，最后一名约 713 LP（JP1 服务器 Challenger 共 75 人）。

---

### 1.3 查询指定 Tier/Division 段位条目

**接口**: `GET /tft/league/v1/entries/{tier}/{division}`

**描述**: 获取指定段位和 Division 的所有段位条目，支持分页。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-league-v1/GET_getLeagueEntries

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `tier` | path | string | 是 | 段位等级：`IRON` / `BRONZE` / `SILVER` / `GOLD` / `PLATINUM` / `EMERALD` / `DIAMOND` |
| `division` | path | string | 是 | 段位细分：`I` / `II` / `III` / `IV` |
| `queue` | query | string | 否 | 队列类型，默认 `RANKED_TFT`。可选值：`RANKED_TFT` / `RANKED_TFT_DOUBLE_UP` |
| `page` | query | integer | 否 | 页码，默认 `1`（从第 1 页开始） |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://kr.api.riotgames.com/tft/league/v1/entries/DIAMOND/I?queue=RANKED_TFT&page=1&api_key=RGAPI-xxx
```

#### 响应

返回 `LeagueEntryDTO[]` 数组，每个元素字段定义同 1.1。

#### 响应示例

```json
[
  {
    "puuid": "AbCdEf...encrypted",
    "leagueId": "c5a4a000-...",
    "summonerId": "XyZ123...encrypted",
    "summonerName": "DiamondPlayer",
    "queueType": "RANKED_TFT",
    "tier": "DIAMOND",
    "rank": "I",
    "leaguePoints": 95,
    "wins": 210,
    "losses": 180,
    "veteran": true,
    "inactive": false,
    "freshBlood": false,
    "hotStreak": false
  }
]
```

---

### 1.4 查询 Grandmaster 段位

**接口**: `GET /tft/league/v1/grandmaster`

**描述**: 获取 Grandmaster（宗师）段位的全部玩家列表。每个服务器约 500 人。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-league-v1/GET_getGrandmasterLeague

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `queue` | query | string | 否 | 队列类型，默认 `RANKED_TFT`。可选值：`RANKED_TFT` / `RANKED_TFT_DOUBLE_UP` |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://kr.api.riotgames.com/tft/league/v1/grandmaster?queue=RANKED_TFT&api_key=RGAPI-xxx
```

#### 响应

返回 `LeagueListDTO` 对象，`tier` 固定为 `"GRANDMASTER"`。`entries` 数组结构同 1.2 的 Challenger 响应。

#### 响应示例

```json
{
  "tier": "GRANDMASTER",
  "queue": "RANKED_TFT",
  "entries": [
    {
      "puuid": "GM_player_puuid_encrypted",
      "leaguePoints": 1200,
      "rank": "I",
      "wins": 350,
      "losses": 200,
      "veteran": true,
      "inactive": false,
      "freshBlood": false,
      "hotStreak": true
    }
  ]
}
```

---

### 1.5 查询 Master 段位

**接口**: `GET /tft/league/v1/master`

**描述**: 获取 Master（大师）段位的全部玩家列表。每个服务器约 1000 人。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-league-v1/GET_getMasterLeague

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `queue` | query | string | 否 | 队列类型，默认 `RANKED_TFT`。可选值：`RANKED_TFT` / `RANKED_TFT_DOUBLE_UP` |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://kr.api.riotgames.com/tft/league/v1/master?queue=RANKED_TFT&api_key=RGAPI-xxx
```

#### 响应

返回 `LeagueListDTO` 对象，`tier` 固定为 `"MASTER"`。`entries` 数组结构同 1.2。

#### 响应示例

```json
{
  "tier": "MASTER",
  "queue": "RANKED_TFT",
  "entries": [
    {
      "puuid": "Master_player_puuid_encrypted",
      "leaguePoints": 500,
      "rank": "I",
      "wins": 280,
      "losses": 250,
      "veteran": false,
      "inactive": false,
      "freshBlood": true,
      "hotStreak": false
    }
  ]
}
```

---

### 1.6 查询 Rated 天梯排行榜

**接口**: `GET /tft/league/v1/rated-ladders/{queue}/top`

**描述**: 获取指定队列的 Rated 天梯排行榜（Hyper Roll / Turbo 模式的积分排行）。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-league-v1/GET_getTopRatedLadder

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `queue` | path | string | 是 | 队列类型：`RANKED_TFT_TURBO`（Hyper Roll 模式） |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://kr.api.riotgames.com/tft/league/v1/rated-ladders/RANKED_TFT_TURBO/top?api_key=RGAPI-xxx
```

#### 响应

返回 `TopRatedLadderEntryDto[]` 数组，每个元素字段定义如下：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `summonerId` | string | 召唤师 ID（加密后） |
| `summonerName` | string | 召唤师名称 |
| `ratedTier` | string | Rated 段位等级：`GRAY`（最低）/ `GREEN` / `BLUE` / `PURPLE` / `ORANGE`（最高） |
| `ratedRating` | integer | Rated 积分 |
| `wins` | integer | 胜场数 |
| `previousUpdateLadderPosition` | integer | 上次更新时的天梯排名位置（用于显示排名变动） |

#### 响应示例

```json
[
  {
    "summonerId": "abc123...encrypted",
    "summonerName": "TurboPlayer",
    "ratedTier": "ORANGE",
    "ratedRating": 2800,
    "wins": 500,
    "previousUpdateLadderPosition": 1
  },
  {
    "summonerId": "def456...encrypted",
    "summonerName": "AnotherPlayer",
    "ratedTier": "PURPLE",
    "ratedRating": 2200,
    "wins": 380,
    "previousUpdateLadderPosition": 3
  }
]
```

---

## 2. TFT Match V1 — 对局详情

> **重要**: 此模块的 platform 为 **regional** 类型，与 League/Summoner 不同。
>
> **可选值**: `americas` · `asia` · `europe` · `sea` · `esports` · `esportseu`
>
> 选择规则：根据玩家所在服务器对应的 region 路由（如 JP/KR/TW → `asia`，EUW/EUNE → `europe`，NA/BR → `americas`）

### 2.1 根据 PUUID 查询对局 ID 列表

**接口**: `GET /tft/match/v1/matches/by-puuid/{puuid}/ids`

**描述**: 获取指定玩家的对局 ID 列表，支持分页和时间范围过滤。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-match-v1/GET_getMatchIdsByPUUID

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `puuid` | path | string | 是 | 玩家 PUUID |
| `start` | query | integer | 否 | 起始索引，默认 `0`（配合 count 实现分页） |
| `count` | query | integer | 否 | 返回数量，默认 `20`，最大 `100` |
| `startTime` | query | long | 否 | 开始时间（Epoch 秒级时间戳）。注意：2021-06-16 之前的对局不会被收录 |
| `endTime` | query | long | 否 | 结束时间（Epoch 秒级时间戳） |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://asia.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count=20&api_key=RGAPI-xxx
```

#### 响应

返回 `string[]`，每个元素为一个 matchId（格式为 `{region}{number}`，如 `JP1_1234567890`）。

#### 响应示例

```json
[
  "JP1_5482317891",
  "JP1_5482109834",
  "JP1_5481998765",
  "JP1_5481887654",
  "JP1_5481776543",
  "JP1_5481665432",
  "JP1_5481554321",
  "JP1_5481443210",
  "JP1_5481332109",
  "JP1_5481221098",
  "JP1_5481110987",
  "JP1_5480999876",
  "JP1_5480888765",
  "JP1_5480777654",
  "JP1_5480666543",
  "JP1_5480555432",
  "JP1_5480444321",
  "JP1_5480333210",
  "JP1_5480222109",
  "JP1_5480111098"
]
```

---

### 2.2 根据 Match ID 查询对局详情

**接口**: `GET /tft/match/v1/matches/{matchId}`

**描述**: 获取指定对局的完整详情，包含 8 名玩家的阵容、装备、排名等全部信息。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-match-v1/GET_getMatch

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `matchId` | path | string | 是 | 对局 ID（如 `JP1_5482317891`） |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://asia.api.riotgames.com/tft/match/v1/matches/JP1_5482317891?api_key=RGAPI-xxx
```

#### 响应

返回 `MatchDto` 对象，顶层包含 `metadata` 和 `info` 两个子对象。

**MatchDto（顶层）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `metadata` | MetadataDto | 对局元数据（对局 ID、数据版本、参与者列表） |
| `info` | InfoDto | 对局详细信息（游戏模式、时间、8 名玩家的详细数据） |

**MetadataDto（metadata 子对象）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `data_version` | string | 数据版本号（如 `"2"`） |
| `match_id` | string | 对局 ID |
| `participants` | `string[]` | 参与者 PUUID 列表（8 个玩家的 PUUID） |

**InfoDto（info 子对象）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `game_datetime` | long | 对局开始时间（Epoch 毫秒时间戳） |
| `game_length` | float | 对局时长（秒） |
| `game_version` | string | 游戏版本号（如 `"15.1.123"`） |
| `queue_id` | integer | 队列类型 ID（1100=单排，1130=双人，1160=Hyper Roll） |
| `tft_game_type` | string | 游戏模式类型 |
| `tft_set_core_name` | string | 赛季核心名称（如 `"TFTSet17"`） |
| `tft_set_number` | integer | 赛季编号（如 `17`） |
| `participants` | `ParticipantDto[]` | 8 名玩家的详细数据（数组长度 = 8） |

**ParticipantDto（participants 数组中每个元素）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `puuid` | string | 玩家 PUUID |
| `placement` | integer | 最终排名（1=第一名/吃鸡，8=最后一名） |
| `level` | integer | 最终等级 |
| `gold_left` | integer | 剩余金币 |
| `last_round` | integer | 最后存活的回合数 |
| `time_eliminated` | float | 被淘汰时间（秒） |
| `companion` | object | 小小英雄信息（`content_ID`、`skin_ID`、`species`） |
| `traits` | `TraitDto[]` | 激活的羁绊列表 |
| `units` | `UnitDto[]` | 棋盘上的棋子列表 |
| `augments` | `string[]` | 选择的强化符文列表（最多 3 个） |
| `tensors` | object | Tensor 数据（如适用） |

**TraitDto（traits 数组中每个元素）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `name` | string | 羁绊名称（如 `"TFTSet17_SpaceGods"`） |
| `num_units` | integer | 激活该羁绊所需的棋子数量 |
| `style` | integer | 羁绊激活等级（1=铜/2=银/3=金/4=白金/5=彩色） |
| `tier_current` | integer | 当前激活的羁绊等级 |
| `tier_total` | integer | 该羁绊最大可达等级 |

**UnitDto（units 数组中每个元素）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `character_id` | string | 棋子 ID（如 `"TFTSet17_Ahri"`） |
| `name` | string | 棋子显示名称 |
| `tier` | integer | 棋子星级（1/2/3 星） |
| `rarity` | integer | 棋子费用（1=1费，5=5费） |
| `items` | `string[]` | 装备列表（装备 ID 数组，如 `["TFT_Item_BlueBuff", ...]`） |

#### 响应示例

```json
{
  "metadata": {
    "data_version": "2",
    "match_id": "JP1_5482317891",
    "participants": [
      "puuid_player_1",
      "puuid_player_2",
      "puuid_player_3",
      "puuid_player_4",
      "puuid_player_5",
      "puuid_player_6",
      "puuid_player_7",
      "puuid_player_8"
    ]
  },
  "info": {
    "game_datetime": 1752105600000,
    "game_length": 2145.5,
    "game_version": "15.1.123",
    "queue_id": 1100,
    "tft_game_type": "standard",
    "tft_set_core_name": "TFTSet17",
    "tft_set_number": 17,
    "participants": [
      {
        "puuid": "puuid_player_1",
        "placement": 1,
        "level": 10,
        "gold_left": 42,
        "last_round": 48,
        "time_eliminated": 2145.5,
        "companion": {
          "content_ID": "tft_companion_icon_001",
          "skin_ID": 1,
          "species": "TFT_Companion_Pengu"
        },
        "augments": [
          "TFTAugment_Portals",
          "TFTAugment_BalancedBudget",
          "TFTAugment_FinalSpike"
        ],
        "traits": [
          {
            "name": "TFTSet17_SpaceGods",
            "num_units": 5,
            "style": 3,
            "tier_current": 3,
            "tier_total": 5
          },
          {
            "name": "TFTSet17_Artillery",
            "num_units": 4,
            "style": 2,
            "tier_current": 2,
            "tier_total": 4
          }
        ],
        "units": [
          {
            "character_id": "TFTSet17_Ahri",
            "name": "Ahri",
            "tier": 3,
            "rarity": 4,
            "items": ["TFT_Item_RabadonsDeathcap", "TFT_Item_JeweledGauntlet", "TFT_Item_GiantSlayer"]
          },
          {
            "character_id": "TFTSet17_Mordekaiser",
            "name": "Mordekaiser",
            "tier": 2,
            "rarity": 3,
            "items": ["TFT_Item_GargoyleStoneplate", "TFT_Item_WarmogsArmor"]
          },
          {
            "character_id": "TFTSet17_Sett",
            "name": "Sett",
            "tier": 2,
            "rarity": 2,
            "items": []
          }
        ]
      },
      {
        "puuid": "puuid_player_8",
        "placement": 8,
        "level": 6,
        "gold_left": 5,
        "last_round": 22,
        "time_eliminated": 980.2,
        "companion": {
          "content_ID": "tft_companion_icon_002",
          "skin_ID": 2,
          "species": "TFT_Companion_Choncc"
        },
        "augments": ["TFTAugment_BinaryAirdrop"],
        "traits": [],
        "units": []
      }
    ]
  }
}
```

> 完整对局数据包含 8 名玩家的详细信息。`placement: 1` 为本局第一名（吃鸡），`placement: 8` 为最后一名。

---

## 3. TFT Status V1 — 服务状态

### 3.1 查询平台状态

**接口**: `GET /tft/status/v1/platform-data`

**描述**: 获取指定平台的服务状态（维护公告、故障通知等）。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-status-v1/GET_getPlatformData

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `api_key` | query | string | 是 | API Key |

> 无需额外参数，平台由 URL 中的 `{platform}` 决定。

#### 请求示例

```
GET https://jp1.api.riotgames.com/tft/status/v1/platform-data?api_key=RGAPI-xxx
```

#### 响应

返回 `PlatformDataDto` 对象：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | string | 平台 ID（如 `"JP1"`） |
| `name` | string | 平台名称（如 `"Japan"`） |
| `locales` | `string[]` | 支持的语言区域列表（如 `["ja_JP", "en_US"]`） |
| `maintenances` | `StatusDto[]` | 计划维护公告列表 |
| `incidents` | `StatusDto[]` | 当前故障/事件列表 |

**StatusDto（maintenances / incidents 数组中每个元素）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | integer | 事件 ID |
| `maintenance_status` | string | 维护状态：`scheduled` / `in_progress` / `complete` |
| `incident_severity` | string | 事件严重程度：`info` / `warning` / `critical` |
| `titles` | `ContentDto[]` | 事件标题（多语言） |
| `updates` | `UpdateDto[]` | 事件更新记录列表 |
| `created_at` | string | 创建时间（ISO 8601） |
| `archive_at` | string | 归档时间（ISO 8601） |
| `updated_at` | string | 最后更新时间（ISO 8601） |
| `platforms` | `string[]` | 受影响的平台列表 |

**ContentDto（titles 数组中每个元素）：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `locale` | string | 语言区域（如 `"ja_JP"`） |
| `content` | string | 内容文本 |

#### 响应示例

```json
{
  "id": "JP1",
  "name": "Japan",
  "locales": ["ja_JP", "en_US"],
  "maintenances": [],
  "incidents": []
}
```

> 正常情况下 `maintenances` 和 `incidents` 均为空数组，表示当前无维护或故障。

---

## 4. TFT Summoner V1 — 召唤师信息

### 4.1 根据 PUUID 查询召唤师

**接口**: `GET /tft/summoner/v1/summoners/by-puuid/{encryptedPUUID}`

**描述**: 通过 PUUID 查询召唤师基础信息。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-summoner-v1/GET_getByPUUID

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `encryptedPUUID` | path | string | 是 | 玩家 PUUID |
| `api_key` | query | string | 是 | API Key |

#### 请求示例

```
GET https://jp1.api.riotgames.com/tft/summoner/v1/summoners/by-puuid/6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKOJIfg9U9dxf-ZbqQC2HxTUA?api_key=RGAPI-xxx
```

#### 响应

返回 `SummonerDTO` 对象：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | string | 召唤师 ID（加密后） |
| `accountId` | string | 账号 ID（加密后） |
| `puuid` | string | 玩家 PUUID |
| `profileIconId` | integer | 头像图标 ID（可用于拼接头像 URL：`https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{profileIconId}.png`） |
| `revisionDate` | long | 最后修改时间（Epoch 毫秒时间戳，玩家最近一局游戏结束的时间） |
| `summonerLevel` | long | 召唤师等级 |

#### 响应示例

```json
{
  "id": "aB3xYz7KpMnQwErTyUiOpAsDfGhJkL",
  "accountId": "XyZ9AbCdEfGhIjKlMnOpQrStUvWxYz",
  "puuid": "6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKOJIfg9U9dxf-ZbqQC2HxTUA",
  "profileIconId": 6499,
  "revisionDate": 1752105600000,
  "summonerLevel": 580
}
```

---

### 4.2 根据 Access Token 查询当前召唤师

**接口**: `GET /tft/summoner/v1/summoners/me`

**描述**: 通过 OAuth2 Access Token 查询当前认证用户的召唤师信息。适用于需要用户授权的场景（如第三方应用）。

**官方文档**: https://developer.riotgames.com/api-methods/#tft-summoner-v1/GET_getByAccessToken

#### 安全要求

| 认证类型 | Scope | 说明 |
|----------|-------|------|
| OAuth2 (`rso`) | `openid` | 需在 HTTP Header 中传入 `Authorization: Bearer {access_token}` |

#### 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `Authorization` | header | string | 是 | `Bearer {access_token}` |

> 无需 `api_key` query 参数，认证完全由 OAuth2 Token 完成。

#### 请求示例

```
GET https://jp1.api.riotgames.com/tft/summoner/v1/summoners/me
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

#### 响应

返回 `SummonerDTO` 对象，字段定义与 4.1 完全相同。

#### 响应示例

```json
{
  "id": "aB3xYz7KpMnQwErTyUiOpAsDfGhJkL",
  "accountId": "XyZ9AbCdEfGhIjKlMnOpQrStUvWxYz",
  "puuid": "6eLOz-k1Xno8Cs2SwDQtaTI4q79m4FPIC95O0No_W4zA9tl2qDy6wiKOJIfg9U9dxf-ZbqQC2HxTUA",
  "profileIconId": 6499,
  "revisionDate": 1752105600000,
  "summonerLevel": 580
}
```

---

## 5. 通用错误码

以下 HTTP 错误码适用于所有接口：

| 状态码 | 说明 | 常见原因 |
|--------|------|----------|
| `400` | Bad Request | 请求参数格式错误（如非法的 tier/division 值） |
| `401` | Unauthorized | 缺少或无效的 API Key |
| `403` | Forbidden | API Key 无权限访问该接口（如 Production Key 访问受限接口） |
| `404` | Not Found | 数据不存在（如 PUUID 对应的玩家无段位记录、matchId 不存在） |
| `405` | Method Not Allowed | 使用了不支持的 HTTP 方法（如对 GET 接口使用 POST） |
| `415` | Unsupported Media Type | 请求的 Content-Type 不被支持 |
| `429` | Rate Limit Exceeded | 请求频率超限。需遵守 Riot 的 rate limit（分 application 和 method 两级） |
| `500` | Internal Server Error | Riot 服务器内部错误 |
| `502` | Bad Gateway | 网关错误 |
| `503` | Service Unavailable | 服务不可用（维护中或过载） |
| `504` | Gateway Timeout | 网关超时 |

#### 429 错误响应示例

```json
{
  "status": {
    "message": "Rate limit exceeded",
    "status_code": 429
  }
}
```

> 收到 429 时，需读取响应头中的 `Retry-After` 字段（单位：秒），等待该时间后再重试。

---

*本文档基于 OpenAPI 3.0.0 规范 (`tft-api-openapi.json`) 及 Riot API 实际返回数据整理。*
