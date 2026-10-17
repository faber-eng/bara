FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY services/api/pyproject.toml services/api/uv.lock services/api/.python-version ./
RUN uv sync --frozen --no-dev

COPY config/ /app/config/
COPY data/aoi/ /app/data/aoi/
COPY data/samples/ /app/samples/
COPY services/pipelines/ee_lib/ /app/ee_lib/
COPY services/api/ /app/

ENV BARA_CONFIG_DIR=/app/config \
    BARA_SAMPLES_DIR=/app/samples \
    GOOGLE_GENAI_USE_ENTERPRISE=True

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

RUN useradd --system --uid 10001 --no-create-home bara
USER bara

CMD exec uvicorn --factory main:create_app --host 0.0.0.0 --port ${PORT:-8080}
