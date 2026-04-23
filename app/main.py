import logging
from fastapi import FastAPI
from app.api.webhooks import router as webhooks_router

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="AI-Powered PR Reviewer",
    description="Enterprise-Grade FastAPI Webhook Receiver for GitHub PRs",
    version="1.0.0"
)

# Include routers
app.include_router(webhooks_router)

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}
