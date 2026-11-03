"""Write the cached guide audio. Needs VENICE_API_KEY. No other key."""
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.voice_actions import TOUR, WELCOME


def main():
    key = os.environ.get("VENICE_API_KEY", "")
    if not key:
        print("Set VENICE_API_KEY.", file=sys.stderr)
        sys.exit(1)
    base = os.environ.get("VENICE_BASE_URL", "https://api.venice.ai/api/v1").rstrip("/")
    model = os.environ.get("TTS_MODEL", "tts-xai-v1")
    voice = os.environ.get("TTS_VOICE", "carina")
    folder = os.path.join(ROOT, "server", "static", "voice")
    os.makedirs(folder, exist_ok=True)
    lines = [("welcome.mp3", WELCOME)] + [(f"tour-{index}.mp3", text) for index, text in enumerate(TOUR, start=1)]
    for name, text in lines:
        response = requests.post(
            base + "/audio/speech",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "voice": voice, "input": text},
            timeout=60,
        )
        response.raise_for_status()
        path = os.path.join(folder, name)
        with open(path, "wb") as handle:
            handle.write(response.content)
        print(path, len(response.content))


if __name__ == "__main__":
    main()
