FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY config ./config
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /bin/bash appuser \
    && chmod +x /entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

