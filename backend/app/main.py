"""Genesis Twin API. Run from the backend folder:
    uvicorn app.main:app --reload --port 8000
Interactive docs: http://localhost:8000/docs"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from . import models  # noqa: F401  (registers the tables)
from .db import Base, engine
from .routers import auth, body, pathogens, research, twin


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Genesis Twin API",
    version="0.1.0",
    description=(
        "Dummy-data skeleton following backend/api-contract.md. "
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


app.include_router(auth.router)
app.include_router(body.router)
app.include_router(twin.router)
app.include_router(pathogens.router)
app.include_router(research.router)
