
from fastapi import FastAPI

from app.api.metrics import router as metrics_router

app = FastAPI(
    title="TraceLens API",
    description="Observability and incident analysis platform",
    version="0.1.0",
)

app.include_router(metrics_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
