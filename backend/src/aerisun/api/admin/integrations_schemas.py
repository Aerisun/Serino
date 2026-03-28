from __future__ import annotations

from pydantic import BaseModel

from aerisun.domain.agent.schemas import AgentUsageRead


class FeedLinkRead(BaseModel):
    key: str
    title: str
    url: str
    enabled: bool = True
    format: str = "rss"


class FeedLinkCollectionRead(BaseModel):
    items: list[FeedLinkRead]


class AdminAgentUsageRead(BaseModel):
    item: AgentUsageRead
