"""SentinelGate FastAPI Application and CLI entrypoint."""

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from sentinelgate.api.health import router as health_router
from sentinelgate.api.v1.analytics import router as analytics_router
from sentinelgate.api.v1.chat import router as chat_router
from sentinelgate.api.v1.guardrails import router as guardrails_router
from sentinelgate.config import settings

app = FastAPI(
    title="SentinelGate",
    description="Production-grade reverse proxy gateway for LLMs with real-time guardrails, semantic caching, and hallucination evaluation.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local dev & dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register API Routers
app.include_router(health_router, tags=["Health & Observability"])
app.include_router(chat_router, prefix="/v1", tags=["OpenAI Chat Proxy"])
app.include_router(guardrails_router, prefix="/v1", tags=["Guardrails Inspection"])
app.include_router(analytics_router, prefix="/v1", tags=["Analytics & Telemetry"])

# Serve Dashboard UI
DASHBOARD_PATH = Path(__file__).parent / "ui" / "static" / "index.html"


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to interactive Dashboard."""
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the real-time web dashboard."""
    if DASHBOARD_PATH.exists():
        return FileResponse(DASHBOARD_PATH)
    return {"message": "SentinelGate API is running. UI static file not found."}


def cli():
    """CLI entrypoint for running the SentinelGate gateway."""
    parser = argparse.ArgumentParser(description="Run the SentinelGate Guardrail Gateway.")
    parser.add_argument("--host", default=settings.host, help="Host address to bind")
    parser.add_argument("--port", type=int, default=settings.port, help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code change")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🛡️  Starting SentinelGate LLM Guardrail Gateway")
    print(f"📡  Listening on: http://{args.host}:{args.port}")
    print(f"📊  Live Dashboard: http://{args.host}:{args.port}/dashboard")
    print(f"📖  Swagger Docs:   http://{args.host}:{args.port}/docs")
    print(f"📈  Metrics:        http://{args.host}:{args.port}/metrics")
    print("=" * 60 + "\n")

    uvicorn.run("sentinelgate.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    cli()
