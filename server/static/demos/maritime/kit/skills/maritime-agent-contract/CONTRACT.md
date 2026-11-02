# CONTRACT

- Port: `$PORT` (default 3000), bound to `0.0.0.0`
- Health: `GET /health` -> 200, unauthenticated
- Handler: `POST /run`
  - Request: `{"input": string}`
  - Response: `{"output": string}` or `{"error": string}`
- Env vars: `PORT`, `RATE_LIMIT_PER_MIN`, `MAX_WAKE_BUDGET`
- Rate limit: per-IP, returns 429 past threshold
- Idle sleep: configured deliberately (document value)
