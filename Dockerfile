FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy start script first (before other files to allow caching)
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Use CMD with start.sh script which handles PORT correctly
CMD ["/bin/bash", "/app/start.sh"] 