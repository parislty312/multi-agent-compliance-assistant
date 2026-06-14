FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    WORKFLOW_DB_PATH=/app/data/workflows.db

WORKDIR /app

RUN addgroup --system compliance \
    && adduser --system --ingroup compliance --home /app compliance

COPY pyproject.toml README.md ./
COPY src ./src
COPY frontend ./frontend
COPY policies ./policies
COPY rules ./rules
COPY benchmarks ./benchmarks

RUN pip install --no-cache-dir . \
    && mkdir -p /app/data \
    && chown -R compliance:compliance /app

USER compliance

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
