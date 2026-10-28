FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
# config.yaml va montata in /app/config.yaml; var/ (database, feed, log) su un volume.
VOLUME ["/app/var"]
EXPOSE 8099
CMD ["offerte", "serve", "--host", "0.0.0.0"]
