from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Direction = Literal["推荐阵容", "推荐装备", "查专属", "检索装备"]


class AskRequest(BaseModel):
    """Client request to the /ask endpoint."""
    question: str = Field(..., min_length=1, max_length=500)
    direction: Direction | None = Field(
        default=None,
        description="Explicit intent hint.",
    )
    conversation_id: str | None = None


class ChampionInfo(BaseModel):
    id: str
    name_zh: str
    name_en: str | None = None
    cost: int
    icon_path: str | None = None
    role: str | None = None


class TraitInfo(BaseModel):
    id: str
    name_zh: str
    name_en: str | None = None
    icon_path: str | None = None


class ItemDelta(BaseModel):
    name_zh: str
    name_en: str | None = None
    target: str | None = None
    delta: float


class CompCard(BaseModel):
    comp_name: str
    avg_placement: float | None = None
    sample_size: int | None = None
    champions: list[ChampionInfo]
    synergies: list[str]
    emblems: list[ItemDelta]
    artifacts: list[ItemDelta]
    flex_slot: dict | None = None


class AskResponse(BaseModel):
    card: CompCard | None = None
    summary: str
