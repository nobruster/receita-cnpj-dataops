"""Fábrica de LLM do Sentinel (OpenAI por padrão; Ollama opcional; none = sem LLM)."""

from __future__ import annotations

import os
from typing import Any

from pipeline.config import Settings, get_settings


def llm_available(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    if s.sentinel_llm_provider == "none":
        return False
    if s.sentinel_llm_provider == "openai":
        return bool(s.openai_api_key or os.environ.get("OPENAI_API_KEY"))
    return True


def build_llm(model: str, settings: Settings | None = None) -> Any:
    from crewai import LLM

    s = settings or get_settings()
    if s.sentinel_llm_provider == "ollama":
        return LLM(model=model if model.startswith("ollama/") else f"ollama/{model}", base_url=s.ollama_base_url)
    key = s.openai_api_key or os.environ.get("OPENAI_API_KEY")
    return LLM(model=model, api_key=key, temperature=0.1)
