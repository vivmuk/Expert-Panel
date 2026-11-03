import os
import time
import uuid

from .config import Config

TTL_SECONDS = 24 * 60 * 60


def save_download(blob, suffix):
    folder = os.path.join(Config.DATA_DIR, "downloads")
    os.makedirs(folder, exist_ok=True)
    _sweep(folder)
    name = uuid.uuid4().hex + suffix
    path = os.path.join(folder, name)
    with open(path, "wb") as handle:
        handle.write(blob)
    return name


def download_path(name):
    if not name or "/" in name or "\\" in name or not name.endswith(".zip"):
        return None
    stem = name[: -len(".zip")]
    if len(stem) != 32 or any(ch not in "0123456789abcdef" for ch in stem):
        return None
    path = os.path.join(Config.DATA_DIR, "downloads", name)
    if not os.path.isfile(path):
        return None
    if time.time() - os.path.getmtime(path) > TTL_SECONDS:
        try:
            os.remove(path)
        except OSError:
            return None
        return None
    return path


def _sweep(folder):
    now = time.time()
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path) and now - os.path.getmtime(path) > TTL_SECONDS:
                os.remove(path)
        except OSError:
            continue
