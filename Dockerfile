FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    HOME=/tmp

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev && chown -R root:root /app

ENV PATH=/app/.venv/bin:$PATH \
    BIND_HOST=0.0.0.0 \
    PORT=8000

USER 65532:65532
EXPOSE 8000
ENTRYPOINT ["python", "-m"]
