from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

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
]

app = FastAPI(
    title="Financial Data API Playground",
    version="0.2.0",
    summary="Test financial-data providers directly from Swagger UI",
    description=(
        "Provider-oriented API playground for the AI Financial Data Analysis project. "
        "Open an endpoint, click **Try it out**, enter parameters and click **Execute**. "
        "V0.2 starts with VnStock; DNSE, SSI, World Bank and other providers can be added as independent routers/adapters."
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


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
