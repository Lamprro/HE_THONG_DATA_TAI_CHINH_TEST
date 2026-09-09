from __future__ import annotations

import asyncio
import logging

from app.core.config import news_scheduler_interval_seconds
from app.news.service import NewsPipelineError, news_pipeline_service

logger = logging.getLogger(__name__)


class NewsPipelineScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._loop(), name="news-pipeline-scheduler")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stopped.is_set():
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=news_scheduler_interval_seconds())
            except asyncio.TimeoutError:
                pass
            if self._stopped.is_set():
                break
            try:
                await asyncio.to_thread(news_pipeline_service.run_once)
            except NewsPipelineError:
                # DB may intentionally be absent in stateless demo deployments.
                pass
            except Exception:
                logger.exception("Scheduled NEWS pipeline run failed")


news_pipeline_scheduler = NewsPipelineScheduler()
