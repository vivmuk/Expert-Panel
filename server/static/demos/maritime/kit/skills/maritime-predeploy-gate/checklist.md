# Ordered Pre-Deploy Checklist (fail closed)

Run in order. Stop at first failure.

1. Root-level `Dockerfile` exists.
2. Base image is digest-pinned (`FROM x@sha256:...`).
3. Lockfile committed.
4. `.dockerignore` excludes `.git`, `.env`, test fixtures.
5. `EXPOSE` port matches the actual listener.
6. `GET /health` returns 200.
7. `CONTRACT.md` present and complete.
8. Rate limiter and input validator present at the edge.
9. Max-wake budget documented.
10. Idle-sleep configuration set deliberately.
