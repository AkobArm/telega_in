FROM python:3.10-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m appuser

COPY src/ ./src/
COPY .env .

COPY docker/wait-for-postgres.sh /wait-for-postgres.sh
RUN chmod +x /wait-for-postgres.sh

RUN mkdir -p /app/sessions && chown -R appuser:appuser /app

USER appuser

CMD ["/wait-for-postgres.sh", "db", "python", "src/collector.py"]