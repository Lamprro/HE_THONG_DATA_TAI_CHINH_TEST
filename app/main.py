from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.cafef import router as cafef_router
from app.api.v1.news import router as news_router
from app.api.v1.proxy import router as proxy_router
from app.api.v1.system import router as system_router
from app.api.v1.vndirect import router as vndirect_router
from app.api.v1.vnstock import router as vnstock_router
from app.api.v1.news_pipeline import router as news_pipeline_router
from app.news.scheduler import news_pipeline_scheduler

TAGS = [
    {
        "name": "system",
        "description": "Health check and provider registry for the Financial Data API Playground.",
    },
    {
        "name": "third-party-proxy",
        "description": (
            "Allowlisted passthrough proxy. External systems call this API, the Python "
            "service forwards the request to a third-party provider and returns the "
            "upstream body/status/content-type without wrapping or JSON transformation."
        ),
    },
    {
        "name": "vnstock-market",
        "description": "Vietnam equity market data via VnStock Unified UI v4.",
    },
    {
        "name": "vnstock-company",
        "description": "Company reference/profile data via VnStock.",
    },
    {
        "name": "vnstock-fundamental",
        "description": "Financial statements and ratios via VnStock.",
    },
    {
        "name": "vnstock-news-community",
        "description": "Company-tagged news available through the public/community VnStock Reference API.",
    },
    {
        "name": "vnstock-news-crawler",
        "description": "Dedicated vnstock_news RSS/Sitemap crawler APIs. vnstock_news is a sponsor/private package and these endpoints become active when that package is installed in the runtime.",
    },
    {
        "name": "news-pipeline",
        "description": "Persistent NEWS processing from validated raw payloads into news_articles.",
    },
]

@asynccontextmanager
async def lifespan(_: FastAPI):
    await news_pipeline_scheduler.start()
    yield
    await news_pipeline_scheduler.stop()


app = FastAPI(
    title="Financial Data & News API Playground",
    version="0.5.0",
    summary="Normalized financial-data adapters plus transparent third-party passthrough",
    description=(
        "Provider-oriented API playground for the AI Financial Data Analysis project. "
        "V0.5 provides a shared market_price.v1 contract for VnStock and CafeF while "
        "keeping the allowlisted third-party passthrough layer under /api/v1/proxy. "
        "This lets another backend "
        "call the Python service as middleware while receiving the upstream response "
        "without the Python service changing the response body structure."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(system_router, prefix="/api/v1")
app.include_router(proxy_router, prefix="/api/v1/proxy")
app.include_router(vnstock_router, prefix="/api/v1/vnstock")
app.include_router(news_router, prefix="/api/v1/vnstock-news")
app.include_router(vndirect_router, prefix="/api/v1/vndirect")
app.include_router(cafef_router, prefix="/api/v1/cafef")
app.include_router(news_pipeline_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
