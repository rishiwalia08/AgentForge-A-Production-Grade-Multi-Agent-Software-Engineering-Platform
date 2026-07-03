# Lock to stable Python version for AI ecosystem compatibility
FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies for compilation and PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package requirements
COPY requirements.txt .

# Install dependencies including psycopg2, redis, celery, alembic, slowapi, python-json-logger
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir celery redis psycopg2-binary alembic slowapi python-json-logger

# Copy application source
COPY . .

EXPOSE 8000

# Chain database migration upgrade before starting uvicorn in production
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
