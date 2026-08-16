FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install OS dependencies for WeasyPrint and Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        shared-mime-info && \
    playwright install-deps && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user and setup directories with correct permissions
RUN groupadd -g 10001 onyx && \
    useradd -u 10001 -g onyx -m -s /bin/bash onyx && \
    mkdir -p /app/data /app/data/exports && \
    chown -R onyx:onyx /app

# Copy application code with non-root ownership
COPY --chown=onyx:onyx . .

# Ensure data directory permissions
RUN mkdir -p /app/data /app/data/exports && \
    chown -R onyx:onyx /app/data

USER 10001

EXPOSE 8000

# Run Alembic migrations and then start Uvicorn server
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8000"]
