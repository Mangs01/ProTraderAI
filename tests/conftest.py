"""Block network before test-module collection, including import side effects."""
import socket
import urllib.request

import pytest
import requests


class NetworkForbidden(BaseException):
    pass


def _deny_network(*args, **kwargs):
    # BaseException prevents retry/SDK broad Exception handlers hiding attempts.
    raise NetworkForbidden("Network is forbidden during offline tests")


def pytest_configure(config):
    guard = pytest.MonkeyPatch()
    config._offline_network_guard = guard
    for name in ("connect", "connect_ex", "sendto", "sendall", "send"):
        guard.setattr(socket.socket, name, _deny_network)
    guard.setattr(socket, "create_connection", _deny_network)
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        guard.setattr(socket, name, _deny_network)
    guard.setattr(requests.sessions.Session, "request", _deny_network)
    guard.setattr(urllib.request, "urlopen", _deny_network)


def pytest_unconfigure(config):
    guard = getattr(config, "_offline_network_guard", None)
    if guard is not None:
        guard.undo()
