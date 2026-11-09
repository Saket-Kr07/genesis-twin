"""Genesis Twin API. Run from the backend folder:
    uvicorn app.main:app --reload --port 8000
Interactive docs: http://localhost:8000/docs"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from . import models  # noqa: F401  (registers the tables)
from .db import Base, engine
from . import functions
from .routers import auth, body, experiments, pathogens, research, twin, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Genesis Twin API",
    version="0.2.0",
    description=(
        "Skeleton following backend/api-contract.md. "
        "All outputs are simulations for research and education. They are not medical advice."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/health/functions", tags=["health"])
def health_functions():
    """Which functions are real and which are still dummy (for the team to check)."""
    return functions.SOURCE


app.include_router(auth.router)
app.include_router(body.router)
app.include_router(twin.router)
app.include_router(pathogens.router)
app.include_router(research.router)
app.include_router(experiments.router)
app.include_router(uploads.router)
