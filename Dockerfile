FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends chromium fonts-noto-core fonts-noto-cjk tini \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY jev_ultrafast ./jev_ultrafast
RUN uv sync --frozen --no-dev --no-editable \
    && useradd --uid 1000 --create-home jev \
    && mkdir -p /data/chrome /data/harness /app/artifacts \
    && chown -R jev:jev /data /app/artifacts
COPY docker ./docker
COPY scripts/verify_wikipedia.py ./scripts/verify_wikipedia.py
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 BH_HOME=/data/harness BH_RUNTIME_DIR=/tmp/harness-runtime BH_RECORD=0
USER jev
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "docker/run.py"]
