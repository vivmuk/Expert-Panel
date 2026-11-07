import os
import socket

import pytest

os.environ.setdefault("VENICE_API_KEY", "test-not-a-real-key")
os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("AI_PARTNER_SIGNING_SECRETS", "v1:test-signing-secret")
os.environ["SUPERMEMORY_API_KEY"] = ""

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
_orig_create_connection = socket.create_connection
_orig_connect = socket.socket.connect


def _allow_address(address):
    if not isinstance(address, tuple) or not address:
        return True
    return address[0] in _LOCAL_HOSTS


def _guarded_create_connection(address, *args, **kwargs):
    if not _allow_address(address):
        raise RuntimeError(f"outbound connection blocked in tests: {address[0]}")
    return _orig_create_connection(address, *args, **kwargs)


def _guarded_connect(self, address):
    if not _allow_address(address):
        raise RuntimeError(f"outbound connection blocked in tests: {address[0]}")
    return _orig_connect(self, address)


socket.create_connection = _guarded_create_connection
socket.socket.connect = _guarded_connect


@pytest.fixture(autouse=True)
def _fresh_limits():
    from server.api.chat import reset_limits
    from server.budget import reset
    from server.chatmemory import reset_written

    reset_limits()
    reset()
    reset_written()
    yield
