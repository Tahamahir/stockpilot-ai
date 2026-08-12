from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.database import (
    test_database_connection,
)

from app.ollama_client import (
    ask_stockpilot,
    test_ollama_connection,
)


app = FastAPI(
    title="StockPilot AI Assistant API",
    version="0.2.0",
)


class ChatRequest(BaseModel):
    message: str

    context: dict[str, Any] = (
        Field(
            default_factory=dict
        )
    )


@app.get("/")
def root() -> dict:
    return {
        "service":
            "StockPilot AI Assistant API",

        "status":
            "running",
    }


@app.get("/health")
def health() -> dict:
    database = (
        test_database_connection()
    )

    ollama = (
        test_ollama_connection()
    )

    return {
        "status": "ok",
        "database": database,
        "ollama": ollama,
    }


@app.post("/chat")
def chat(
    request: ChatRequest,
) -> dict:
    return ask_stockpilot(
        user_message=
            request.message,

        context=
            request.context,
    )


@app.post("/chat/test")
def test_chat(
    request: ChatRequest,
) -> dict:
    return ask_stockpilot(
        user_message=
            request.message,

        context=
            request.context,
    )