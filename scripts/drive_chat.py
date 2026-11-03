"""Drive one full /api/chat engagement against a host and report every step.

Usage: python scripts/drive_chat.py https://ai-partner-hq.vercel.app [--size small]

Exits 0 when the job reaches the Top 5 (and, with --size, the finished skill pack).
"""
import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile

PROBLEM = (
    "Decide how Maritime should host a public web agent for a team that already has a repo. "
    "Team: 4 engineers. Tools: git and a browser. Maturity 2."
)


def post(base, message, state):
    body = json.dumps({"message": message, "state": state}).encode()
    request = urllib.request.Request(
        base.rstrip("/") + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "ai-partner-drive-chat"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            status, data = response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            data = json.loads(exc.read())
        except ValueError:
            data = {"error": {"code": "http", "message": f"HTTP {exc.code}"}}
    return status, data, time.time() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--size", choices=("small", "medium", "large"))
    parser.add_argument("--problem", default=PROBLEM)
    parser.add_argument("--save", help="write the final job state to this JSON file")
    args = parser.parse_args()

    state, message, total = {}, args.problem, time.time()
    for turn in range(1, 31):
        status, data, took = post(args.base, message, state)
        state = data.get("state") or state
        card = (data.get("card") or {}).get("kind", "-")
        error = data.get("error") or {}
        print(
            f"{turn:2d}  HTTP {status}  {took:5.1f}s  phase={state.get('phase')}  card={card}  "
            f"experts={len(state.get('experts') or [])}  debate={len(state.get('debate') or [])}  "
            f"top5={len(state.get('top5') or [])}  calls={state.get('calls')}"
            + (f"  error={error.get('code')}: {error.get('message')}" if error else "")
        )
        if error or status >= 400:
            return 1
        message = ""
        if data.get("next"):
            continue
        if state.get("phase") == "ask_size" and args.size:
            message = args.size
            continue
        break

    if args.save:
        with open(args.save, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
    top5 = state.get("top5") or []
    print(f"\n{time.time() - total:.0f}s total. Phase {state.get('phase')}.")
    print(f"{len(state.get('sources') or [])} sources, {len(state.get('experts') or [])} experts, "
          f"{len(state.get('debate') or [])} debate statements, {len(top5)} in the Top 5.")
    for rank, item in enumerate(top5, 1):
        print(f"  {rank}. {item['title']} (confidence {item['confidence']}, impact {item['impact']}, effort {item['effort']})")
    if len(top5) != 5:
        return 1
    if args.size and state.get("phase") != "done":
        return 1
    if args.size:
        for route in ("skill-pack", "kit"):
            names = download_zip(args.base, route, state)
            skills = [name for name in names if name.endswith("SKILL.md")]
            print(f"/api/chat/{route}: {len(names)} files, {len(skills)} SKILL.md")
            if not names or (route == "skill-pack" and not skills):
                return 1
    return 0


def download_zip(base, route, state):
    request = urllib.request.Request(
        base.rstrip("/") + f"/api/chat/{route}",
        data=json.dumps({"state": state}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "ai-partner-drive-chat"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            blob = response.read()
    except urllib.error.HTTPError as exc:
        print(f"/api/chat/{route}: HTTP {exc.code}")
        return []
    return zipfile.ZipFile(io.BytesIO(blob)).namelist()


if __name__ == "__main__":
    sys.exit(main())
