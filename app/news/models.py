from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsArticle:
    canonical_url: str
    title: str
    sapo: str | None
    content_text: str
    author: str | None
    language: str
    published_at: datetime | None
    external_id: str | None
    metadata: dict
