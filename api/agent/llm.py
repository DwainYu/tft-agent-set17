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
你的任务是根据用户问题选择合适的工具来获取数据。

可用工具：
{tool_descriptions}

规则：
1. 如果用户问阵容/搭配，使用 query_comps
2. 如果用户问装备/出装，使用 query_items 或 query_specific
3. 如果用户搜索装备名称，使用 search_items
4. 如果用户问英雄信息，使用 get_champion_info
5. 如果用户问羁绊信息，使用 get_trait_info
6. 如果需要语义搜索，使用 rag_search
7. 如果需要英雄协同分析，使用 calc_synergy
8. 可以组合多个工具

请以 JSON 数组格式返回工具调用计划，每个元素包含 tool、args、reason 字段。
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
