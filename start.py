import os
import re
import sys


def data_dir():
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return "/data"
    path = "/tmp/ai-partner"
    os.makedirs(path, exist_ok=True)
    return path


def ensure_localhost():
    try:
        with open("/etc/hosts", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return
    if re.search(r"(?m)^\s*127\.0.0.1\b.*\blocalhost\b", text):
        return
    try:
        with open("/etc/hosts", "a", encoding="utf-8") as handle:
            if text and not text.endswith("\n"):
                handle.write("\n")
            handle.write("127.0.0.1 localhost\n")
    except OSError:
        return


def main():
    port = os.environ.get("PORT", "").strip()
    if not port.isdigit():
        print("PORT must be set to the port to bind.", file=sys.stderr)
        sys.exit(1)
    chosen = data_dir()
    os.environ["DATA_DIR"] = chosen
    os.environ["TMPDIR"] = chosen
    ensure_localhost()

    from gunicorn.app.base import BaseApplication

    class Standalone(BaseApplication):
        def __init__(self):
            self.options = {
                "bind": f"0.0.0.0:{port}",
                "workers": 1,
                "worker_class": "gthread",
                "threads": 8,
                "timeout": 120,
                "graceful_timeout": 30,
                "accesslog": "-",
                "errorlog": "-",
            }
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key, value)

        def load(self):
            from api.index import app

            return app

    Standalone().run()


if __name__ == "__main__":
    main()
