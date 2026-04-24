from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.candidates import router as candidates_router
from api.routes.dashboard import router as dashboard_router
from api.routes.jobs import router as jobs_router
from api.routes.upload import router as upload_router
from db.mongo import close_mongo_connection, connect_to_mongo
from logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="AI-Powered ATS Backend",
    version="1.0.0",
    description="FastAPI backend for asynchronous AI-powered resume processing and candidate ranking.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(dashboard_router)


@app.on_event("startup")
async def startup() -> None:
    logger.info("[INFO] Starting ATS FastAPI backend")
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("[INFO] Shutting down ATS FastAPI backend")
    await close_mongo_connection()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
