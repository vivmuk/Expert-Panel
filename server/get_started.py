"""Agent playbook. The host is filled from the request."""
import io
import os
import zipfile

SKILLS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills"))

_PLAYBOOK = """# Set up AI Partner for your AI coding agent

Use this playbook to prepare the current agent to run a strategy engagement with the user's team. AI Partner is the harness that replaces the consulting engagement: research, a panel of 20 AI experts, a judge's Top 5, a work chart, and the files the team runs. The team directs the agents and owns every decision. Install the key, the skills, and the MCP connection once.

## How to run

Do the actions yourself when you have a terminal, a browser, or a writable config file. Global or user-scoped installation is the default. Pause only for the user's sign-in, or for a click you cannot perform. Do not stop at a list of commands for the user to copy.

If a step is blocked, write down why and continue with the remaining steps.

## 1. Get a free API key

Your first engagement is free. No card is required.

One engagement returns:

- a research brief that keeps its citations
- a 20-expert panel, a two-round debate, and the judge's Top 5
- a maturity score
- a work chart
- 1 harness and 3 skills

Open https://HOST/signup for the user, then pause while they finish. Or call this yourself:

```sh
curl -sS -X POST "https://HOST/api/signup" \\
  -H "content-type: application/json" \\
  -d '{"email":"USER_EMAIL"}'
```

The response contains `key` once. It looks like `ap_...`. Store it in the user's environment as `AI_PARTNER_API_KEY`, or in the client's secret store. Never echo the key into the chat, the shell transcript you show the user, a commit, or a config file that is checked in. Refer to it as `$AI_PARTNER_API_KEY` after that.

To log in again, open https://HOST/signup and submit the same email, or repeat the POST. Re-issuing returns a new key. The response does not include the previous key.

Confirm the variable is set without printing it:

```sh
test -n "$AI_PARTNER_API_KEY" && printf 'AI_PARTNER_API_KEY is set\\n'
```

The public engagement is `POST /api/chat` and the page at `/chat`. It does not use this key. `/v1/*` and `/mcp` do.

`/api/runs`, `/api/engagements`, and `POST /api/branding/ensure` and `POST /api/branding/generate` also require the key. Any valid partner key can list, read, rename, and delete every row in that one SQLite database, and can read or cancel runs held in that process. The key is not a client id. This does not isolate one caller's engagements from another's.

## 2. Add guidance (skills)

Install the AI Partner skill pack once for this agent. The repo ships three skills in the agent-skills format: `run-engagement`, `read-top5`, and `build-harness`.

Preferred, when `npx` can reach GitHub:

```sh
npx skills add vivmuk/Expert-Panel --global
```

Choose the current agent if prompted. Confirm the install path.

If that command is unavailable or the client does not read that pack, download the same three skills and install them into the client's skills folder. Do not replace unrelated skills.

```sh
curl -sS -L "https://HOST/skills.zip" -o /tmp/ai-partner-skills.zip
```

Unpack the zip into the folder this agent already uses, for example:

- Claude Code: `~/.claude/skills`
- Cursor: `~/.cursor/skills`
- Codex: merge a short pointer into `AGENTS.md` that names the three skills and the path where you unpacked them

Confirm the three `SKILL.md` files are on disk before you continue.

## 3. Connect the MCP server

The server is `https://HOST/mcp`. Send `Authorization: Bearer $AI_PARTNER_API_KEY` on every request. Inspect the existing MCP config first and merge the `ai-partner` entry. Do not overwrite other servers.

Use one route for this client.

### Claude Code

```bash
claude mcp add --transport http ai-partner --scope user https://HOST/mcp --header "Authorization: Bearer $AI_PARTNER_API_KEY"
```

If an `ai-partner` entry already exists, inspect it with `claude mcp list` and update only that entry.

### Codex CLI

Inspect first:

```bash
codex mcp list
```

Then add the remote server:

```bash
codex mcp add ai-partner --url https://HOST/mcp --header "Authorization: Bearer $AI_PARTNER_API_KEY"
```

If that client rejects `--header`, merge the same URL and header into its user-level MCP config and leave every other server in place.

### Cursor

Merge this into `~/.cursor/mcp.json`. Keep every server that is not `ai-partner`.

```json
{
  "mcpServers": {
    "ai-partner": {
      "url": "https://HOST/mcp",
      "headers": {
        "Authorization": "Bearer $AI_PARTNER_API_KEY"
      }
    }
  }
}
```

### VS Code with GitHub Copilot

Merge this into the user MCP config (`mcp.json`). Keep other servers.

```json
{
  "servers": {
    "ai-partner": {
      "type": "http",
      "url": "https://HOST/mcp",
      "headers": {
        "Authorization": "Bearer ${env:AI_PARTNER_API_KEY}"
      }
    }
  }
}
```

Then run MCP: List Servers and start `ai-partner`.

### Windsurf

Merge this into `~/.codeium/windsurf/mcp_config.json`. Keep other servers.

```json
{
  "mcpServers": {
    "ai-partner": {
      "serverUrl": "https://HOST/mcp",
      "headers": {
        "Authorization": "Bearer $AI_PARTNER_API_KEY"
      }
    }
  }
}
```

Refresh the MCP list in Windsurf after saving.

### Gemini CLI

Merge this into `~/.gemini/settings.json`. Keep other servers. `mcp-remote` passes the header.

```json
{
  "mcpServers": {
    "ai-partner": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://HOST/mcp", "--header", "Authorization: Bearer $AI_PARTNER_API_KEY"]
    }
  }
}
```

Run Gemini CLI and use `/mcp list`.

### OpenCode

```bash
opencode mcp add ai-partner --global --url https://HOST/mcp --header "Authorization: Bearer $AI_PARTNER_API_KEY"
```

If the CLI has no `--header` flag, merge the URL and the Authorization header into OpenCode's MCP config and leave the other servers untouched.

### Claude.ai and ChatGPT

In the Claude app or ChatGPT, add a custom connector.

- MCP URL: `https://HOST/mcp`
- Header: `Authorization: Bearer $AI_PARTNER_API_KEY`

Paste the URL. Do not paste the key into the chat transcript. Put it in the connector's header field.

### OpenAI-compatible clients

Point any OpenAI SDK at this base URL. The key is `AI_PARTNER_API_KEY`.

- Base URL: `https://HOST/v1`
- Models: `ai-partner` for one engagement with 5 catalog artifacts, `ai-partner-full` for the full catalog

Send `ai_partner_state` back on the next request. The field is on the raw response.

### Grok Bot

Grok Bot is a desktop agent. It connects remote MCP servers as connectors and can follow a pasted instruction. Do this after the other agents.

Paste this into a Grok Bot chat:

```text
Set up AI Partner for me. Fetch https://HOST/get-started.md and follow it.
```

Manual route: add a custom connector.

- URL: `https://HOST/mcp`
- Transport: streamable HTTP
- Header: `Authorization: Bearer $AI_PARTNER_API_KEY`

Do not paste the key into the chat. Put it only in the connector header.

Verify: Ask Grok Bot: list the AI Partner tools.

## 4. Verify

Call the MCP tool `list_artifacts`. A working connection returns the catalog groups.

Then call `start_job` with one line, for example: `Decide how a four-person software team should host a public web agent.`

Show the user that first reply. Keep the returned state for the next turn. Do not show the API key.

If the tools are missing, refresh the client's MCP server list once. Record MCP as blocked only after that refresh fails.

## Completion

Report only what you verified:

```text
AI Partner agent setup is ready
Key: stored in <env|secret store|blocked: reason>
Skills: <installed|blocked: reason>
MCP: <connected|blocked: reason>
Verified: <list_artifacts succeeded|blocked: reason>; <start_job first reply|not run: reason>
```

## Sources

- https://HOST/signup
- https://HOST/connect
- https://HOST/openapi.json
- https://HOST/llms.txt
"""


def render_get_started(host):
    return _PLAYBOOK.replace("https://HOST", host.rstrip("/"))


def render_llms(host):
    origin = host.rstrip("/")
    return "\n".join(
        [
            "# AI Partner",
            "",
            "> The strategy-engagement harness any agent can run. Your team directs the agents.",
            "",
            f"- [Get started]({origin}/get-started.md): setup playbook for a coding agent.",
            f"- [Keiki]({origin}/keiki.md): put AI Partner in iMessage, WhatsApp, Slack, Telegram and email through a Keiki agent.",
            f"- [OpenAPI]({origin}/openapi.json): HTTP API, including signup.",
            f"- [MCP]({origin}/mcp): streamable HTTP MCP. Send Authorization: Bearer $AI_PARTNER_API_KEY.",
            "- Grok Bot: paste the get-started line into a Grok Bot chat, or add a custom connector for that MCP URL. Ask Grok Bot: list the AI Partner tools.",
            "",
        ]
    )


def openapi_document(host):
    origin = host.rstrip("/")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "AI Partner",
            "version": "1.0.0",
            "description": "Strategy-engagement harness that replaces the consulting engagement. Agents start at /get-started.md.",
        },
        "servers": [{"url": origin}],
        "paths": {
            "/api/signup": {
                "post": {
                    "summary": "Issue a free Starter key. The first engagement is free.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["email"],
                                    "properties": {
                                        "email": {"type": "string"},
                                        "plan": {"type": "string", "enum": ["starter"]},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "A new ap_ key. Re-issue does not return the previous key."}},
                }
            },
            "/mcp": {"post": {"summary": "Streamable HTTP MCP"}},
            "/v1/chat/completions": {"post": {"summary": "OpenAI-compatible chat completion"}},
            "/get-started.md": {"get": {"summary": "Agent setup playbook"}},
        },
    }


def skills_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder, _, names in os.walk(SKILLS_ROOT):
            for name in names:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(folder, name)
                arc = os.path.relpath(path, SKILLS_ROOT)
                archive.write(path, arc)
    return buffer.getvalue()


def valid_email(value):
    if not isinstance(value, str):
        return ""
    email = value.strip().lower()
    if len(email) > 200 or email.count("@") != 1 or any(ch.isspace() for ch in email):
        return ""
    local, domain = email.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return ""
    return email
