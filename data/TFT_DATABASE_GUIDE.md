## TFT 统一数据库 — tft.db

本文档详细说明 `data/tft.db` 的结构、数据来源、导入流程和使用方法。

---

### 一、概览

`tft.db` 是一个 SQLite 数据库（WAL 模式），作为项目的统一数据层，整合了三类数据源：Data Dragon 静态资源、Riot API 对局数据推导的英雄-羁绊映射、以及自动生成的英雄别名字典。

| 属性 | 值 |
|------|------|
| 路径 | `data/tft.db` |
| 引擎 | SQLite 3 (WAL mode, synchronous=NORMAL) |
| 大小 | 324 KB |
| 表数量 | 7 |
| 导入脚本 | `data_collection/scripts/import_data_dragon.py` |
| 数据版本 | Data Dragon 16.13.1 (Set 17) |

---

### 二、数据源

| 数据源 | 路径 | 用途 |
|--------|------|------|
| Data Dragon 中文 | `asset/data/zh_CN/*.json` | 英雄/装备/羁绊/强化的中文名 |
| Data Dragon 英文 | `asset/data/en_US/*.json` | 英雄/装备/羁绊/强化的英文名 |
| Data Dragon 图标 | `asset/img/{champion,items,traits,augment}/` | 所有游戏资源的 PNG 图标 |
| 对局数据 (units) | `data_collection/data/cleaned/units.csv` | 推导英雄-羁绊映射 |
| 对局数据 (traits) | `data_collection/data/cleaned/traits.csv` | 推导英雄-羁绊映射 |

导入时 zh_CN 和 en_US 的 JSON 通过 `id` 字段 JOIN，同一张表里同时保存中英文名称。

---

### 三、表结构

#### 3.1 champions — 英雄表

存储 Set 17 的 63 个真实英雄（排除了 cost=0 的教学单位、克隆体、假单位和敌方单位）。

```sql
CREATE TABLE champions (
    id          TEXT PRIMARY KEY,   -- Data Dragon ID, 如 "TFT17_Briar"
    name_zh     TEXT NOT NULL,      -- 中文名, 如 "贝蕾亚"
    name_en     TEXT,               -- 英文名, 如 "Briar"
    tier        INTEGER,            -- 稀有度 1-5 (对应星级)
    cost        INTEGER,            -- 商店费用 1-5 金币
    icon_path   TEXT                -- 图标相对路径 (相对于 asset/img/)
);
```

**数据示例**：

| id | name_zh | name_en | tier | cost | icon_path |
|----|---------|---------|------|------|-----------|
| TFT17_Bard | 巴德 | Bard | 5 | 5 | champion/TFT17_Bard_splash_centered_8.TFT_Set17.png |
| TFT17_AurelionSol | 奥瑞利安·索尔 | Aurelion Sol | 4 | 4 | champion/TFT17_AurelionSol_splash_centered_...png |
| TFT17_Briar | 贝蕾亚 | Briar | 1 | 1 | champion/TFT17_Briar_splash_centered_10.TFT_Set17.png |

**费用分布**：cost 1 = 14 个, cost 2 = 13 个, cost 3 = 13 个, cost 4 = 14 个, cost 5 = 9 个。

**过滤规则**：`cost > 0` 且 `id` 以 `TFT17` 开头，排除 `_TraitClone`、`_FakeUnit`、`Enemy_` 后缀的条目。

#### 3.2 items — 装备表

存储 Set 17 的全部 516 个装备，包括基础组件（如暴风大剑）、合成装备、Set 17 专属装备（纹章、消耗品等）。

```sql
CREATE TABLE items (
    id          TEXT PRIMARY KEY,   -- Data Dragon ID, 如 "TFT_Item_BFSword"
    name_zh     TEXT NOT NULL,      -- 中文名, 如 "暴风大剑"
    name_en     TEXT,               -- 英文名, 如 "B.F. Sword"
    icon_path   TEXT                -- 图标相对路径 (相对于 asset/img/)
);
```

**数据示例**：

| id | name_zh | name_en |
|----|---------|---------|
| TFT_Item_BFSword | 暴风大剑 | B.F. Sword |
| TFT_Item_GargoyleStoneplate | 石像鬼石板甲 | Gargoyle Stoneplate |
| TFT17_Consumable_MechaTransformer | 机甲变形器 | Mecha Transformer |

**过滤规则**：`id` 以 `TFT17` 或 `TFT_Item_` 开头。

#### 3.3 traits — 羁绊表

存储 Set 17 的 43 个羁绊，包括职业、起源和英雄专属羁绊。

```sql
CREATE TABLE traits (
    id          TEXT PRIMARY KEY,   -- Data Dragon ID, 如 "TFT17_DarkStar"
    name_zh     TEXT NOT NULL,      -- 中文名, 如 "暗星"
    name_en     TEXT,               -- 英文名, 如 "Dark Star"
    icon_path   TEXT                -- 图标相对路径 (相对于 asset/img/)
);
```

**数据示例**：

| id | name_zh | name_en |
|----|---------|---------|
| TFT17_DarkStar | 暗星 | Dark Star |
| TFT17_AssassinTrait | 刺客 | Rogue |
| TFT17_ShieldTank | 圣盾使 | Shield Bearer |
| TFT17_BlitzcrankUniqueTrait | 崭新出厂 | Factory New |

#### 3.4 augments — 强化表

存储 Set 17 的 32 个强化（包括英雄专属强化和通用强化），带完整的效果描述。

```sql
CREATE TABLE augments (
    id              TEXT PRIMARY KEY,   -- Data Dragon ID, 如 "TFT17_Augment_PykeCarry"
    name_zh         TEXT NOT NULL,      -- 中文名, 如 "职业杀手"
    name_en         TEXT,               -- 英文名, 如 "Contract Killer"
    description_zh  TEXT,               -- 中文描述 (可能含 HTML 标签)
    description_en  TEXT,               -- 英文描述
    icon_path       TEXT                -- 图标相对路径 (相对于 asset/img/)
);
```

**注意**：`description` 字段可能包含 `<br>` 等 HTML 标签，前端渲染时需要注意。

#### 3.5 champion_traits — 英雄-羁绊映射表

记录每个英雄拥有哪些羁绊。这是一张关联表，数据不是来自 Data Dragon（Data Dragon 的 champion JSON 不含羁绊字段），而是从 429 场排位赛的对局数据中通过 PMI 算法推导得出。

```sql
CREATE TABLE champion_traits (
    champion_id TEXT NOT NULL,
    trait_id    TEXT NOT NULL,
    PRIMARY KEY (champion_id, trait_id),
    FOREIGN KEY (champion_id) REFERENCES champions(id),
    FOREIGN KEY (trait_id) REFERENCES traits(id)
);
```

**推导算法 — PMI（点互信息）**：

```
PMI(champion, trait) = log₂( P(champion, trait) / (P(champion) × P(trait)) )
```

PMI 衡量的是"英雄 c 和羁绊 t 共同出现的频率是否高于随机期望"。通用羁绊（如重装战士、太空律动）因为几乎每个玩家都有，P(trait) 很高，导致 PMI 值低，从而被自然过滤掉。专属羁绊（如暗星、霸天机甲）只在特定英雄出场时才激活，P(trait) 较低但 P(c,t) 相对较高，PMI 值高，被保留。

**参数**：

| 参数 | 值 | 说明 |
|------|------|------|
| MIN_PMI | 1.5 | PMI 阈值，越高越严格 |
| MIN_APPEARANCES | 5 | 英雄最少出场次数 |
| MAX_TRAITS_PER_CHAMPION | 4 | 每个英雄最多保留的羁绊数 |

**当前结果**：173 条映射，覆盖 60/63 个英雄。

| 羁绊数 | 英雄数 |
|--------|--------|
| 1 个 | 10 个英雄 |
| 2 个 | 11 个英雄 |
| 3 个 | 15 个英雄 |
| 4 个 | 24 个英雄 |
| 0 个 | 3 个英雄（Nasus、Blitzcrank、Nunu，因为独有羁绊过于特殊） |

#### 3.6 aliases — 英雄别名字典

用于意图识别阶段：把用户输入的各种英雄名称（中文、英文、拼音、缩写）映射到统一的 `champion_id`。

```sql
CREATE TABLE aliases (
    alias       TEXT PRIMARY KEY,   -- 别名, 如 "龙王", "asol", "Aurelion Sol"
    champion_id TEXT NOT NULL,      -- 对应的 champion id
    FOREIGN KEY (champion_id) REFERENCES champions(id)
);

CREATE INDEX idx_aliases_champion ON aliases(champion_id);
```

**自动生成规则**：

每个英雄自动生成以下别名：

- 中文官方名（如 "贝蕾亚"）
- 英文官方名（如 "Briar"）
- 英文小写（如 "briar"）
- ID 短名（如 "Briar"，从 `TFT17_Briar` 提取）
- 英文短名去掉空格和标点（如 "miss fortune" → "missfortune"）

当前共 214 个别名，覆盖全部 63 个英雄。后续可以手工补充玩家常用昵称（如 "龙王" → `TFT17_AurelionSol`，"加里奥" → `TFT17_Galio`）。

#### 3.7 item_stats — 装备统计表（待填充）

预留给装备 delta 值（装备对平均排名的影响分）的聚合统计。

```sql
CREATE TABLE item_stats (
    item_id     TEXT NOT NULL,      -- 装备 ID (FK items.id)
    champion_id TEXT,               -- 英雄 ID (NULL = 全局统计)
    delta_rank  REAL,               -- 排名影响值 (负数 = 排名更好)
    sample_size INTEGER,            -- 样本量
    PRIMARY KEY (item_id, champion_id)
);
```

**delta_rank 的计算逻辑**（待实现）：

```
delta = avg_placement(英雄 c 携带装备 i) - avg_placement(英雄 c 不携带装备 i)
```

负值表示携带该装备时排名更好。例如 `delta = -0.47` 意味着有这件装备时平均排名提升 0.47 位。`champion_id` 为 NULL 时表示该装备在所有英雄上的全局 delta 值。

---

### 四、图标资源映射

数据库中的 `icon_path` 字段是相对于 `asset/img/` 的相对路径。完整路径为：

```
asset/img/{icon_path}
```

示例：

| 类型 | icon_path | 完整路径 |
|------|-----------|----------|
| 英雄 | champion/TFT17_Briar_splash_centered_10.TFT_Set17.png | asset/img/champion/TFT17_Briar_splash_centered_10.TFT_Set17.png |
| 装备 | items/TFT_Item_BFSword.png | asset/img/items/TFT_Item_BFSword.png |
| 羁绊 | traits/Trait_Icon_17_DarkStar.TFT_Set17.png | asset/img/traits/Trait_Icon_17_DarkStar.TFT_Set17.png |
| 强化 | augment/ContractKiller_II.TFT_Set17.png | asset/img/augment/ContractKiller_II.TFT_Set17.png |

后端提供静态服务时，可以挂载 `asset/img/` 目录，前端通过 `/assets/champion/TFT17_Briar_splash_centered_10.TFT_Set17.png` 等路径引用。

---

### 五、导入流程

导入脚本 `import_data_dragon.py` 按以下顺序执行：

```
1. 建表 (CREATE TABLE IF NOT EXISTS)
2. 导入英雄   ← asset/data/{zh_CN,en_US}/champion.json
3. 导入装备   ← asset/data/{zh_CN,en_US}/item.json
4. 导入羁绊   ← asset/data/{zh_CN,en_US}/trait.json
5. 导入强化   ← asset/data/{zh_CN,en_US}/augments.json
6. 推导映射   ← data_collection/data/cleaned/{units,traits}.csv
7. 生成别名   ← champions 表
```

运行方式：

```bash
uv run python data_collection/scripts/import_data_dragon.py
```

脚本支持重复运行（`INSERT OR REPLACE` / `INSERT OR IGNORE`），不会产生重复数据。每次运行会完全覆盖基础表（champions/items/traits/augments），重新推导 champion_traits，追加新别名。

---

### 六、常用查询

**查询英雄及其羁绊**：

```sql
SELECT c.name_zh, c.cost, GROUP_CONCAT(t.name_zh, '、') as traits
FROM champions c
JOIN champion_traits ct ON c.id = ct.champion_id
JOIN traits t ON t.id = ct.trait_id
GROUP BY c.id
ORDER BY c.cost DESC;
```

**按别名搜索英雄**：

```sql
SELECT c.id, c.name_zh, c.name_en, c.cost
FROM aliases a
JOIN champions c ON a.champion_id = c.id
WHERE a.alias LIKE '%龙王%';
```

**查询某件装备的中英文名**：

```sql
SELECT name_zh, name_en FROM items WHERE id = 'TFT_Item_GuinsoosRageblade';
-- 鬼索的狂暴之刃 / Guinsoo's Rageblade
```

**查询 Set 17 所有 5 费英雄**：

```sql
SELECT id, name_zh, name_en FROM champions WHERE cost = 5 ORDER BY name_zh;
```

**pandas 直接读取**：

```python
import sqlite3, pandas as pd

conn = sqlite3.connect('data/tft.db')
df = pd.read_sql("""
    SELECT c.name_zh as hero, c.cost, t.name_zh as trait
    FROM champion_traits ct
    JOIN champions c ON c.id = ct.champion_id
    JOIN traits t ON t.id = ct.trait_id
""", conn)
conn.close()
```

---

### 七、已知局限

1. **champion_traits 不完整**：3 个英雄（Nasus、Blitzcrank、Nunu）因为独有羁绊过于特殊，PMI 算法未能检测到。需要手工补充或降低阈值。
2. **别名不够丰富**：当前 214 个别名只覆盖了中/英文官方名和 ID 短名，缺少玩家常用昵称（如"龙王""加里奥""刀妹"）。需要手工维护一张别名字典。
3. **item_stats 未填充**：装备 delta 值的计算脚本尚未实现，该表当前为空。
4. **无 augment-champion 映射**：augments 表只存储了强化本身的信息，没有记录哪些强化属于哪些英雄。Data Dragon 的 augments JSON 中没有这个关联字段。
5. **Data Dragon 版本绑定**：当前数据基于 16.13.1 版本。版本更新后需要重新导入，但 `INSERT OR REPLACE` 可以安全覆盖旧数据。
