"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI

from .api import router
from .database import create_db_and_tables
from fastapi.middleware.cors import CORSMiddleware

PROJECT_DIRECTORY = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIRECTORY / ".env")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


app = FastAPI(
    title="API Chatbot Pâtisserie",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "API Chatbot opérationnelle",
        "documentation": "/docs",
    }


def run() -> None:
    """Run the development server through the project script."""
    import uvicorn

    uvicorn.run("server.main:app", reload=True)
