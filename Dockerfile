# Stage 1: build the React frontend
FROM node:22-slim AS webbuild
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime serving API + built frontend
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY --from=webbuild /web/dist ./web/dist

RUN useradd --create-home app && mkdir -p /data && chown -R app:app /app /data
USER app

ENV DATA_DIR=/data

# Single gthread worker with many threads: the in-process run registry and SSE
# streams require all requests to hit the same worker. timeout 0 keeps long
# runs and SSE streams alive; Railway sets PORT.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --worker-class gthread --workers 1 --threads 16 --timeout 0 --keep-alive 65 --access-logfile - --error-logfile - server.wsgi:app"]
