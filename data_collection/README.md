# TFT Data Collection

JP1 Challenger 段位对局数据采集（Set 17 Space Gods）。

## 目录结构

```
data_collection/
├── README.md                           # 本文件
├── scripts/
│   ├── fetch_challenger_matches.py     # 数据采集脚本
│   └── clean_data.py                   # 数据清洗脚本
├── docs/                               # API 规范与文档
│   ├── riot-api-openapi.json           #   Riot 通用 API OpenAPI 规范
│   ├── tft-api-openapi.json            #   TFT API OpenAPI 规范
│   └── TFT_API_Complete_Documentation.md  # TFT API 完整文档
└── data/
    ├── raw/                            # 原始 API 响应（勿手动修改）
    │   ├── challengers.json            #   Challenger 玩家 PUUID 列表
    │   ├── match_ids.json              #   去重后的对局 ID 列表
    │   ├── matches_raw.json            #   完整对局详情 JSON (~20 MB)
    │   └── data_overview.json          #   原始数据概览统计
    └── cleaned/                        # 清洗后的 CSV 平表
        ├── matches.csv                 #   对局维度: 日期、时长、版本
        ├── participants.csv            #   玩家×对局: 排名、等级、伤害
        ├── units.csv                   #   棋子维度: 角色、星级、装备数
        ├── traits.csv                  #   羁绊维度: 名称、等级、是否激活
        ├── items.csv                   #   装备维度: 装备名、所属棋子
        └── cleaning_report.json        #   清洗统计报告
```

## 环境搭建

本项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python 环境和依赖。

```bash
# 首次: 根据 pyproject.toml 创建虚拟环境并安装所有依赖
uv sync

# 后续: 新增依赖
uv add <package>
```

依赖列表（定义在 `pyproject.toml`）：`aiohttp`、`python-dotenv`、`pandas`、`requests`

运行脚本时始终使用 `uv run`，自动使用项目虚拟环境（`.venv`）：

```bash
uv run python data_collection/scripts/fetch_challenger_matches.py
uv run python data_collection/scripts/clean_data.py
```

## 使用方式

### 1. 数据采集

从 Riot API 拉取 Challenger 对局数据（支持断点续传）：

```bash
# 完整采集（Step 1-4，约 10 分钟）
uv run python data_collection/scripts/fetch_challenger_matches.py

# 仅拉取 Challenger 列表 + Match IDs（跳过对局详情）
uv run python data_collection/scripts/fetch_challenger_matches.py --skip-details

# 限制对局数量
uv run python data_collection/scripts/fetch_challenger_matches.py --max-matches 100
```

**断点续传**: 如果 `data/raw/` 中已有中间文件，脚本会自动跳过已完成的步骤。
删除对应文件即可重新采集该步骤。

### 2. 数据清洗

将原始 JSON 清洗为 CSV 平表：

```bash
uv run python data_collection/scripts/clean_data.py
```

**过滤规则**:
- 仅保留 `queue_id=1100`（Ranked TFT 排位赛）
- 排除参与者 < 8 人的对局
- 排除时长 < 5 分钟的异常对局
- 标记 `trait.style=0` 为未激活羁绊

## 数据说明

### 采集参数

| 参数 | 值 |
|------|-----|
| 服务器 | JP1 (Japan) |
| Regional 路由 | asia |
| 时间范围 | 2026-07-11 ~ 2026-07-13 (CST) |
| 目标对局数 | 500 |
| 实际获取 | 471（去重后），Ranked 过滤后 427 |

### CSV 表关联关系

```
matches.csv (match_id)
    ↓ 1:N
participants.csv (match_id, puuid)
    ↓ 1:N
units.csv (match_id, puuid)
    ↓ 1:N
items.csv (match_id, puuid, character_id)

participants.csv (match_id, puuid)
    ↓ 1:N
traits.csv (match_id, puuid)
```

所有表通过 `match_id` + `puuid` 关联。

### 已知限制

- **无强化符文数据**: Set 17 Match API 不返回 `augments` 字段
- **unit.name 为空**: 仅有 `character_id`（如 `TFT17_Aatrox`），需本地映射显示名
- **unit.rarity 不可信**: 大量 0 值，不按费用分级
- **game_version**: 原始值为 Linux 构建字符串（如 `16.13.791.5903`），已解析为版本号

### Queue ID 参考

| queue_id | 类型 | 说明 |
|----------|------|------|
| 1100 | Ranked TFT | 排位赛（核心数据） |
| 1090 | Normal TFT | 普通模式 |
| 1160 | Hyper Roll | 快节奏模式 |

## API Key

在**项目根目录**的 `.env` 文件中配置：

```
API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Dev Key 有效期 24 小时，过期后需更换。Production Key 无此限制。
