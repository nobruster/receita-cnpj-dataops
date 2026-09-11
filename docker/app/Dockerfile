# Sentinel (CrewAI) + servidor MCP + ferramentas de linha de comando (chaos).
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false OTEL_SDK_DISABLED=true

WORKDIR /app
COPY requirements/app.txt /tmp/app.txt
RUN pip install -r /tmp/app.txt

COPY pipeline ./pipeline
COPY chaos ./chaos
COPY sentinel ./sentinel
COPY intelligence ./intelligence

CMD ["python", "-m", "sentinel.trigger", "--watch"]
