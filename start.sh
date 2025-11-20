#!/bin/bash
# Railway start script - uses PORT environment variable

# Exit on error
set -e

# Use PORT from environment (Railway sets this automatically)
PORT=${PORT:-5000}

# Ensure we're in the right directory
cd /app || exit 1

echo "=========================================="
echo "Starting Expert Panel Application"
echo "PORT: $PORT"
echo "Working Directory: $(pwd)"
echo "Python Version: $(python3 --version 2>&1 || python --version)"
echo "=========================================="

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo "ERROR: app.py not found in $(pwd)!"
    echo "Files in current directory:"
    ls -la
    exit 1
fi

# Test Python import (this will catch import errors early)
echo "Testing app import..."
python3 -c "import app; print('✓ App imported successfully')" 2>&1 || python -c "import app; print('✓ App imported successfully')" 2>&1 || {
    echo "ERROR: Failed to import app module"
    echo "Python path:"
    python3 -c "import sys; print('\n'.join(sys.path))" 2>&1 || python -c "import sys; print('\n'.join(sys.path))" 2>&1
    echo "Trying to import app with verbose errors:"
    python3 -c "import app" 2>&1 || python -c "import app" 2>&1
    exit 1
}

echo ""
echo "Starting gunicorn on 0.0.0.0:$PORT"
echo ""

# Start gunicorn with all configuration
# Using python3 explicitly, fallback to python
PYTHON_CMD=$(command -v python3 || command -v python)

exec $PYTHON_CMD -m gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 600 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance \
    app:app

