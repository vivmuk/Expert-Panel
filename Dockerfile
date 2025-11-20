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

# Copy start script and make executable
COPY start.sh /app/start.sh

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app && \
    chmod +x /app/start.sh
USER app

# Set PORT environment variable with default (Railway will override)
ENV PORT=5000

# Expose port (Railway sets PORT dynamically)
EXPOSE $PORT

# Health check (Railway also does healthchecks, but this is a fallback)
# Note: HEALTHCHECK uses shell form, so ${PORT} will work
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the application using start script which handles PORT correctly
# Use shell form to ensure bash is used
CMD ["/bin/bash", "/app/start.sh"] 