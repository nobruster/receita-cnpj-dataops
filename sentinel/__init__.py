"""Componente B — Sentinel: time CrewAI que vigia o backbone (somente leitura) e é pontuado.

Telemetria do CrewAI desligada por padrão: o Sentinel só fala com o provedor de LLM configurado.
"""

import os

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
