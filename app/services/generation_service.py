import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings

logger = logging.getLogger("generation")
GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


async def stream_groq_answer(prompt: str) -> AsyncIterator[str]:
    if not settings.groq_api_key:
        raise RuntimeError("Generation provider is not configured")
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": "You are a precise document question-answering assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        async with client.stream("POST", GROQ_CHAT_COMPLETIONS_URL, headers=headers, json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                logger.error("Groq API error (%d): %s", response.status_code, body.decode("utf-8", errors="replace"))
                response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    return
                chunk = json.loads(data)
                token = chunk["choices"][0].get("delta", {}).get("content")
                if token:
                    yield token
