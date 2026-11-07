# Feature acceptance matrix

Classes: **live** means a public GET in this hardening run. **mock** means a local test with a provider double. **unverified** means the code exists and this run did not observe the provider or the channel. **planned** means not built. A mock does not verify Venice, Exa, Supermemory, or Keiki.

| Surface | Class | Evidence |
|---|---|---|
| `/chat` page and job (intake, research, 20 experts, debate, judge, chart, kit) | mock, page live | `tests/test_chatjob.py`. `GET /chat` 200 and the free-engagement sentence. No live model call in this run. |
| Same-browser resume of one job | unverified | `server/static/chat.js` stores one `ai-partner-chat-v2` slot. No browser test. A project list is planned. |
| `/connect`, `/get-started.md`, `/signup`, `/llms.txt`, `/skills.zip` | live page, mock signup | Public GETs. `tests/test_onboard.py` mints a key locally. Signup was not called on the hosts. |
| `/v1/*`, `/mcp` | live auth gate, mock model | Public `GET /v1/models` and `GET /mcp` are 401. Model calls are doubled in tests. |
| Voice transcription and TTS | mock | `server/api/voice.py`, `tests/test_voice_and_demos.py`. Not called on the hosts. |
| Keiki signed push and MCP intake | mock | `tests/test_keiki.py`, `tests/test_keiki_intake.py`. Email roundtrip is reported, not observed here. iMessage unverified. Spend unknown. |
| `/demos` Maritime, Keiki, Orchid and kit zips | live static | Public GET 200. Schema tests in `tests/test_voice_and_demos.py`. These are stored demos, not a live panel run. |
| Reports, pptx, catalog artifacts, harness and skill pack | mock | `tests/test_live_report.py`, `tests/test_skillpack.py`, `tests/test_chatjob.py`. Not generated on the hosts in this run. |
| Supermemory | mock write shape, unverified live | `server/chatmemory.py` posts `https://api.supermemory.ai/v3/documents` with `content`, `customId`, `containerTags`, `metadata`. Search still uses `/ns/{ns}/search` in code and is mocked. Host key unknown. A repeated `customId` appends at the provider. This process skips an identical snapshot only until restart. |
| Nine panel modes, including the four the README once called stubs | mock, modes list live | `GET /api/modes` lists all nine as `available`. `tests/test_modes.py`. No live panel run. |
| Legacy runs, engagement store, brand generation | mock gate | `tests/test_legacy_boundary.py`. Partner key required before DB or provider work. Shared store, not per-client isolation. Railway currently returns `no_store` when `VERCEL=1`. Maritime's store was empty on the investigation GET. Production after deploy is unverified until `--expect-gated`. |
| React launcher `$2` confirm and 3× breaker | mock of the breaker path only | `web/src/pages/NewEngagement.tsx`, `server/pipeline/runner.py`. Not the `/chat` path. |
| Slack or Telegram as a live AI Partner channel | planned | Listed as Keiki channel types a customer could connect. The chat page does not mark them Live. |
| CI | added in this PR | `.github/workflows/ci.yml` runs pytest with no secrets and no provider calls. The workflow result on GitHub is unverified until the PR runs. |
