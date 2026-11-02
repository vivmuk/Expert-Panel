import os
import uuid

from .config import Config


def save_download(blob, suffix):
    folder = os.path.join(Config.DATA_DIR, "downloads")
    os.makedirs(folder, exist_ok=True)
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
    return path
