"""Agent orchestration module — LangGraph state machine for TFT Set 17.

Architecture::

    START → planner → executor → critic → reflect → END
                       ↑                    |
                       └── retry (≤3) ──────┘

Nodes:
  - planner:   decide which tools to call (LLM tool-calling or rule-based fallback)
  - executor:  run the planned tools via ToolRegistry
  - critic:    evaluate tool results (LLM assessment or heuristic check)
  - reflect:   compose the final answer (LLM generation or template)

Checkpoint: SqliteSaver (dev) / PostgresSaver (prod)
Human-in-loop: interrupt_before=["executor"] — user can inspect/modify the plan
"""

from api.agent.graph import build_agent_graph, get_agent_app
from api.agent.state import AgentState
from api.agent.tools import ToolRegistry

__all__ = ["AgentState", "ToolRegistry", "build_agent_graph", "get_agent_app"]
