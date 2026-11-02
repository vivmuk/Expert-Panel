"""Identify the deployed build on hosts that do not expose a commit SHA, such as a Docker build without .git."""
import functools
import hashlib
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
_EXTENSIONS = (".py", ".html", ".css", ".js", ".json", ".md", ".webp", ".png", ".svg", ".mp3")


def commit_sha():
    for name in ("RAILWAY_GIT_COMMIT_SHA", "VERCEL_GIT_COMMIT_SHA", "GIT_COMMIT"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


@functools.lru_cache(maxsize=1)
def fingerprint(root=_ROOT):
    """A short hash of every shipped file under server/. Equal fingerprints mean the same source."""
    digest = hashlib.sha256()
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name != "__pycache__")
        for name in sorted(files):
            if not name.endswith(_EXTENSIONS):
                continue
            path = os.path.join(folder, name)
            digest.update(os.path.relpath(path, root).replace(os.sep, "/").encode())
            digest.update(b"\0")
            with open(path, "rb") as handle:
                digest.update(handle.read())
            digest.update(b"\0")
    return digest.hexdigest()[:12]
