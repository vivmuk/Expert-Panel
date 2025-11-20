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

# Railway injects PORT at runtime - we don't set it here
# Railway automatically discovers which port the app listens on

# Run the application
# Railway will set the PORT environment variable which start.sh will use
CMD ["/bin/bash", "/app/start.sh"] 