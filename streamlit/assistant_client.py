from __future__ import annotations

import os

import httpx


ASSISTANT_API_URL = os.getenv(
    "ASSISTANT_API_URL",
    "http://assistant-api:8000",
)

ASSISTANT_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=600.0,
    write=30.0,
    pool=30.0,
)


def check_assistant_health() -> dict:
    """
    Check communication with the StockPilot Assistant API.
    """

    response = httpx.get(
        f"{ASSISTANT_API_URL}/health",
        timeout=20.0,
    )

    response.raise_for_status()

    return response.json()


def send_message(
    message: str,
) -> dict:
    """
    Send one user message to the StockPilot Assistant API.
    """

    message = message.strip()

    if not message:
        raise ValueError(
            "Le message ne peut pas être vide."
        )

    response = httpx.post(
        f"{ASSISTANT_API_URL}/chat",
        json={
            "message": message,
        },
        timeout=ASSISTANT_TIMEOUT,
    )

    response.raise_for_status()

    payload = response.json()

    return {
        "model":
            payload.get(
                "model",
                "unknown",
            ),

        "answer":
            payload.get(
                "answer",
                "",
            ),

        "tools_used":
            payload.get(
                "tools_used",
                [],
            ),

        "route":
            payload.get(
                "route",
                {},
            ),

        "error":
            payload.get(
                "error",
            ),
    }