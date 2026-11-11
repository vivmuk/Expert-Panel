"""Test guards.

Blocks socket.create_connection and socket.socket.connect to any host other than
localhost, and requests.Session.request to those same hosts. This is the path
Venice, Exa, Supermemory, and Keiki use. It does not wrap socket.connect_ex,
socket.sendto, subprocess, or proxy configuration, so it is not proof that
every form of egress is impossible.
"""
import os
import socket
from urllib.parse import urlparse

import pytest
import requests

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

_orig_session_request = requests.sessions.Session.request


def _guarded_session_request(self, method, url, *args, **kwargs):
    host = urlparse(str(url)).hostname
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(f"provider request blocked in tests: {method} {url}")
    return _orig_session_request(self, method, url, *args, **kwargs)


requests.sessions.Session.request = _guarded_session_request


@pytest.fixture(autouse=True)
def _fresh_limits():
    from server.api.auth import reset_limits as reset_auth
    from server.api.chat import reset_limits
    from server.budget import reset
    from server.chat_send import reset_reported
    from server.chatmemory import reset_written
    from server.entitlement import _open
    from server.mailer import reset as reset_mailer

    reset_limits()
    reset_auth()
    reset()
    reset_written()
    reset_reported()
    reset_mailer()
    _open.set(None)
    yield
