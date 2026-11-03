import os

import pytest

os.environ.setdefault("VENICE_API_KEY", "test-not-a-real-key")
os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("AI_PARTNER_SIGNING_SECRETS", "v1:test-signing-secret")


@pytest.fixture(autouse=True)
def _fresh_limits():
    from server.api.chat import reset_limits
    from server.budget import reset
    from server.chatmemory import reset_written

    reset_limits()
    reset()
    reset_written()
    yield
