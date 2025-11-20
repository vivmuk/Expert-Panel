FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Set default PORT (Railway will override this at runtime)
ENV PORT=5000

# Railway injects PORT at runtime
# Use shell form of CMD so environment variables are expanded
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 600 --keep-alive 2 --max-requests 1000 --max-requests-jitter 50 --preload --access-logfile - --error-logfile - --log-level info --capture-output --enable-stdio-inheritance --forwarded-allow-ips="*" app:app 