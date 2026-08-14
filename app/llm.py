"""Keep all LLM and embedding traffic on the local Ollama host."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from langchain_ollama import ChatOllama

from app.config import settings

# Libraries that phone home unless explicitly disabled.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY", "False")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("POSTHOG_DISABLED", "1")
if settings.hf_hub_offline:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def chat_llm(*, json_mode: bool = True) -> ChatOllama:
    kwargs: dict[str, Any] = {
        "model": settings.ollama_chat_model,
        "base_url": settings.ollama_host,
        "temperature": 0.1,
    }
    if json_mode:
        kwargs["format"] = "json"
    return ChatOllama(**kwargs)


def _model_present(names: list[str], wanted: str) -> bool:
    wanted = (wanted or "").strip()
    if not wanted:
        return False
    stem = wanted.split(":")[0]
    return any(wanted in n or n.startswith(stem) for n in names)


def ping_ollama() -> dict[str, Any]:
    url = settings.ollama_host.rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            names = [m.get("name", "") for m in resp.json().get("models", [])]
            return {
                "ok": True,
                "host": settings.ollama_host,
                "models": names,
                "chat_model": settings.ollama_chat_model,
                "vision_model": settings.ollama_vision_model,
                "chat_present": _model_present(names, settings.ollama_chat_model),
                "vision_present": _model_present(names, settings.ollama_vision_model),
            }
    except Exception as exc:  # noqa: BLE001 — surface connection errors to UI
        return {"ok": False, "host": settings.ollama_host, "error": str(exc), "models": []}


def parse_json_payload(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        return None
    match = JSON_FENCE.search(raw)
    if match:
        raw = match.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None
