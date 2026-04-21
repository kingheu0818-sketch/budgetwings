FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
RUN python -m venv /opt/venv

COPY pyproject.toml README.md ./
COPY agents ./agents
COPY bot ./bot
COPY db ./db
COPY engine ./engine
COPY llm ./llm
COPY models ./models
COPY rag ./rag
COPY tools ./tools
COPY cli.py config.py ./

RUN pip install --upgrade pip && pip install .

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . .

CMD ["python", "cli.py", "run", "--city", "深圳,上海,北京,广州,成都,杭州", "--persona", "worker", "--top", "10", "--engine", "graph"]
