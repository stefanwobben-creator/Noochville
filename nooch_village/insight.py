from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class Insight(BaseModel):
    id: str
    claim: str
    source: str
    source_date: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    links_to: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
