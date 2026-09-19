# Reuse the NAS Chromium image; override with a verified image for another architecture.
ARG CHROMIUM_IMAGE=lscr.io/linuxserver/chromium:arm64v8-67a9c4d9-ls26
FROM ${CHROMIUM_IMAGE}
USER root
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
WORKDIR /app
ENV VIRTUAL_ENV=/app/.venv
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY jev_ultrafast ./jev_ultrafast
RUN uv sync --frozen --no-dev --no-editable --python /usr/bin/python3 \
    && mkdir -p /data/chrome /data/harness /app/artifacts \
    && chown -R abc:abc /data /app/artifacts
COPY docker ./docker
COPY scripts/verify_wikipedia.py ./scripts/verify_wikipedia.py
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 BH_HOME=/data/harness BH_RUNTIME_DIR=/tmp/harness-runtime BH_RECORD=0
USER abc
# Bypass the inherited desktop /init. Compose init supplies PID 1 and zombie reaping.
ENTRYPOINT []
CMD ["python", "docker/run.py"]
