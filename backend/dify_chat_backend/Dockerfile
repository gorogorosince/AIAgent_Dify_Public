FROM python:3.12 as builder

WORKDIR /app

RUN pip install poetry
RUN poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock ./
RUN poetry install

COPY . .

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app .

RUN mkdir -p /data && chown nobody:nogroup /data

ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8080

USER nobody

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
