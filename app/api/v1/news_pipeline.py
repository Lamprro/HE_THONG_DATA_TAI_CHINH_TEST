from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg import Error as PsycopgError

from app.news.service import NewsPipelineError, news_pipeline_service

router = APIRouter(prefix="/news-pipeline", tags=["news-pipeline"])


class PipelineControlRequest(BaseModel):
    enabled: bool = Field(..., description="true starts scheduled runs; false stops them")


def unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail={"message": "NEWS pipeline database is unavailable", "reason": str(exc), "hint": "Configure DATABASE_URL and ensure the NEWS pipeline database migration has been applied"})


@router.get("/status", summary="Read NEWS crawler status")
def status() -> dict:
    try:
        return news_pipeline_service.status()
    except (NewsPipelineError, PsycopgError) as exc:
        raise unavailable(exc) from exc


@router.put("/control", summary="Enable or disable automatic NEWS crawling")
def control(request: PipelineControlRequest) -> dict:
    try:
        return news_pipeline_service.set_enabled(request.enabled)
    except (NewsPipelineError, PsycopgError) as exc:
        raise unavailable(exc) from exc


@router.post("/runs", summary="Run the NEWS pipeline now")
async def run_now(limit: int = Query(100, ge=1, le=1000)) -> dict:
    try:
        return await asyncio.to_thread(news_pipeline_service.run_once, limit)
    except (NewsPipelineError, PsycopgError) as exc:
        raise unavailable(exc) from exc


@router.get("/articles", summary="List normalized news articles stored by the pipeline")
def list_articles(
    limit: int = Query(20, ge=1, le=100, description="Maximum returned articles"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
) -> dict:
    try:
        return news_pipeline_service.list_articles(limit=limit, offset=offset)
    except (NewsPipelineError, PsycopgError) as exc:
        raise unavailable(exc) from exc


@router.post("/company-matches/runs", summary="Run rule-based company matching for stored news articles")
def match_existing_articles(limit: int = Query(100, ge=1, le=1000, description="Maximum stored articles to match")) -> dict:
    try:
        return news_pipeline_service.match_existing_articles(limit=limit)
    except (NewsPipelineError, PsycopgError) as exc:
        raise unavailable(exc) from exc


@router.get("/company-matches", summary="List company matches created from news articles")
def list_company_matches(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    try:
        return news_pipeline_service.list_company_matches(limit=limit, offset=offset)
    except (NewsPipelineError, PsycopgError) as exc:
        raise unavailable(exc) from exc
