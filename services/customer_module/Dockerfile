FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Keep the container alive by default so you can `docker compose exec` into it
# and run one-off commands (train, ask, eval). Override with `command:` in
# docker-compose.yml or `docker compose run` for a one-shot invocation.
CMD ["tail", "-f", "/dev/null"]
