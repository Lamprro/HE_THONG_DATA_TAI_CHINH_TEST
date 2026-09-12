from __future__ import annotations

import os


def database_url() -> str | None:
    """Return the PostgreSQL URL without ever exposing it in API responses."""
    return os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")


def news_scheduler_interval_seconds() -> int:
    value = int(os.getenv("NEWS_CRAWLER_INTERVAL_SECONDS", "900"))
    return max(value, 60)
