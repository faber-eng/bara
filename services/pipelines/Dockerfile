FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /srv/services/pipelines

COPY services/pipelines/pyproject.toml services/pipelines/uv.lock services/pipelines/.python-version ./
RUN uv sync --frozen --no-dev

COPY config/ /srv/config/
COPY data/aoi/ /srv/data/aoi/
COPY data/dams_riau_sample.geojson /srv/data/
COPY services/api/contracts.py /srv/services/api/contracts.py
COPY services/pipelines/adapters/ adapters/
COPY services/pipelines/domain/ domain/
COPY services/pipelines/ee_lib/ ee_lib/
COPY services/pipelines/jobs/ jobs/
COPY services/pipelines/api_contracts.py ./

RUN useradd --system --uid 10001 --no-create-home bara
USER bara

ENTRYPOINT ["python", "-m"]
CMD ["jobs.weekly_rankings", "--region", "riau"]
