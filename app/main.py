from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.news import router as news_router
from app.api.v1.system import router as system_router
from app.api.v1.vnstock import router as vnstock_router

TAGS = [
    {
        "name": "system",
        "description": "Health check and provider registry for the Financial Data API Playground.",
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
]

app = FastAPI(
    title="Financial Data & News API Playground",
    version="0.3.0",
    summary="Test financial-data and news providers directly from Swagger UI",
    description=(
        "Provider-oriented API playground for the AI Financial Data Analysis project. "
        "Open an endpoint, click **Try it out**, enter parameters and click **Execute**. "
        "V0.3 includes VnStock market/fundamental data, company-tagged news through community VnStock, "
        "and a separate adapter/API surface for the sponsor/private vnstock_news crawler. "
        "DNSE, SSI, official disclosures, macro and other providers can be added as independent routers/adapters."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(system_router, prefix="/api/v1")
app.include_router(vnstock_router, prefix="/api/v1/vnstock")
app.include_router(news_router, prefix="/api/v1/vnstock-news")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
