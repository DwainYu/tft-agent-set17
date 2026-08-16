"""LLM provider — OpenAI-compatible chat model with graceful fallback.

When ``OPENAI_API_BASE`` is configured (vLLM, Ollama, OpenAI, etc.) a real
``ChatOpenAI`` instance is returned.  Otherwise a lightweight
``RuleBasedPlanner`` mimics tool-calling using the existing IntentRouter
heuristics so the agent graph still works without any LLM infrastructure.
"""
from __future__ import annotations

import logging
from typing import Any

from api.config import get_settings

logger = logging.getLogger(__name__)


def get_llm() -> Any:
    """Return a LangChain chat model bound to the configured endpoint.

    Returns ``None`` when no LLM endpoint is configured — callers should
    fall back to rule-based planning.
    """
    settings = get_settings()
    if not settings.OPENAI_API_BASE:
        logger.info("No OPENAI_API_BASE configured — using rule-based planner")
        return None

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            base_url=settings.OPENAI_API_BASE,
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        logger.info("LLM connected: %s @ %s", settings.LLM_MODEL, settings.OPENAI_API_BASE)
        return llm
    except Exception as exc:
        logger.warning("Failed to initialise LLM: %s — falling back to rules", exc)
        return None


# ---------------------------------------------------------------------------
# System prompt for the TFT planner
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
你是云顶之弈 Set 17 "Space Gods" 的专业 AI 助手。
你的任务是根据用户问题选择一个或多个工具来获取数据。

可用工具：
{tool_descriptions}

## 工具选择规则

1. 问阵容/搭配/主C → query_comps
2. 问装备/出装 → query_items 或 query_specific
3. 搜索装备名称 → search_items
4. 问英雄信息（费用、羁绊）→ get_champion_info
5. 问羁绊详情（成员）→ get_trait_info
6. 两个英雄是否搭配 → calc_synergy
7. 版本概览 → get_version_meta

## 多工具组合（重要）

当问题涉及多个维度时，**必须**组合多个工具。示例：

- "锐雯主C配什么装备" →
  [{{"tool":"query_comps","args":{{"champion_ids":["TFT17_Riven"]}},"reason":"查锐雯核心阵容"}},
   {{"tool":"query_items","args":{{"champion_id":"TFT17_Riven"}},"reason":"查锐雯推荐装备"}}]

- "劫和慎搭配吗" →
  [{{"tool":"calc_synergy","args":{{"champion_a":"TFT17_Zed","champion_b":"TFT17_Shen"}},"reason":"计算羁绊协同"}},
   {{"tool":"get_champion_info","args":{{"champion_id":"TFT17_Zed"}},"reason":"补充劫的信息"}}]

- "锐雯阵容里的主C是谁，出什么装" →
  [{{"tool":"query_comps","args":{{"champion_ids":["TFT17_Riven"]}},"reason":"查阵容"}},
   {{"tool":"query_items","args":{{"champion_id":"TFT17_Riven"}},"reason":"查装备"}}]

## RAG 兜底（重要）

当问题是**开放性/策略性**问题，没有明确指向某个英雄或装备时，使用 rag_search 做语义检索：

- "什么阵容克制游侠" → [{{"tool":"rag_search","args":{{"query":"克制游侠的阵容"}},"reason":"开放性问题，语义检索"}}]
- "这版本前期怎么过渡" → [{{"tool":"rag_search","args":{{"query":"前期过渡策略"}},"reason":"策略性问题"}}]
- "暗星羁绊怎么玩" → [{{"tool":"get_trait_info","args":{{"trait_name":"暗星"}},"reason":"查羁绊成员"}},{{"tool":"rag_search","args":{{"query":"暗星羁绊玩法"}},"reason":"补充玩法攻略"}}]

判断标准：问题里**没有**可识别的具体英雄名/装备名，且不是问版本概览 → 优先 rag_search。

## 输出格式

以 JSON 数组格式返回工具调用计划，每个元素包含 tool、args、reason 字段。
可以返回 1 个或多个工具调用。
"""

CRITIC_SYSTEM_PROMPT = """\
你是云顶之弈数据分析专家。请评估以下工具返回的结果质量：
- 结果是否为空？
- 结果是否与用户问题相关？
- 是否需要补充查询？

如果结果充分，回复 "PASS"。
如果需要重试，回复 "RETRY: <原因>"。
"""

REFLECT_SYSTEM_PROMPT = """\
你是云顶之弈 Set 17 专业顾问。根据以下工具查询结果，用中文给出简洁、专业的回答。
回答应包含：阵容推荐、装备建议、运营要点等实用信息。
不要编造数据，只基于提供的查询结果回答。
"""
