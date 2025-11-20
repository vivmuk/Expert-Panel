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

# Don't set PORT here - Railway will inject it at runtime via environment variable
# EXPOSE is not needed - Railway handles port mapping internally and dynamically discovers ports
# Railway will automatically detect which port the app listens on

# Note: Railway handles healthchecks via railway.json configuration
# We don't need a Dockerfile HEALTHCHECK as Railway does this automatically

# Run the application using start script which handles PORT correctly
# Use shell form to ensure bash is used
CMD ["/bin/bash", "/app/start.sh"] 