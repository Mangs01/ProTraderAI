"""Offline identity preflight with fake environment values only."""
import runpy
import socket
import traceback
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import dotenv
import pytest
import requests
from loguru import logger

import config
import broker.historical_client as historical

IDENTITY = {
    "CLIENT_LOCAL_IP": "10.23.45.67",
    "CLIENT_PUBLIC_IP": "192.0.2.123",
    "CLIENT_MAC": "Aa:bB:01:23:45:fF",
}


@pytest.fixture
def configured(monkeypatch):
    def load(overrides=None):
        for field, value in {**IDENTITY, **(overrides or {})}.items():
            if value is None:
                monkeypatch.delenv(field, raising=False)
            else:
                monkeypatch.setenv(field, value)
        for field in ("API_KEY", "CLIENT_CODE", "MPIN", "TOTP_SECRET"):
            monkeypatch.setenv(field, "fake-credential")
        # Exercise real configuration loading without reading the actual .env.
        monkeypatch.setattr(dotenv, "load_dotenv", lambda: None)
        path = Path(__file__).resolve().parents[1] / "config" / "settings.py"
        monkeypatch.setattr(config, "settings", SimpleNamespace(**runpy.run_path(str(path))))
    return load


@pytest.fixture(autouse=True)
def no_activity(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected network or historical API activity")
    guards = []
    for owner, name in (
        (socket, "getaddrinfo"), (socket, "gethostbyname"),
        (socket, "create_connection"), (socket.socket, "connect"),
        (requests.sessions.Session, "request"),
        (historical.HistoricalTransport, "post"),
        (historical.HistoricalClient, "authenticate"),
        (historical.HistoricalClient, "getCandleData"),
    ):
        guard = Mock(side_effect=forbidden)
        monkeypatch.setattr(owner, name, guard)
        guards.append(guard)
    yield
    for guard in guards:
        guard.assert_not_called()


def test_valid_mapping(configured, monkeypatch, capsys, caplog):
    configured()
    constructor = Mock(wraps=historical.HistoricalClient)
    monkeypatch.setattr(historical, "HistoricalClient", constructor)
    client = historical.create_historical_client()
    arguments = constructor.call_args.kwargs
    for field, argument in (("CLIENT_LOCAL_IP", "client_local_ip"),
                            ("CLIENT_PUBLIC_IP", "client_public_ip"),
                            ("CLIENT_MAC", "client_mac")):
        assert arguments[argument] == IDENTITY[field]
    assert client._identity == tuple(IDENTITY.values())
    assert client._transport._enabled is False
    assert client._transport._session is None
    captured = capsys.readouterr()
    assert not captured.out and not captured.err and not caplog.text


@pytest.mark.parametrize("field", list(IDENTITY))
@pytest.mark.parametrize("invalid", [None, "", " ", "invalid-sensitive-input"],
                         ids=["missing", "empty", "whitespace", "malformed"])
def test_invalid_before_construction(configured, monkeypatch, capsys, caplog, field, invalid):
    configured({field: invalid})
    constructor = Mock()
    monkeypatch.setattr(historical, "HistoricalClient", constructor)
    logs = []
    sink = logger.add(lambda message: logs.append(str(message)))
    try:
        with pytest.raises(historical.HistoricalSafetyError) as error:
            historical.create_historical_client()
    finally:
        logger.remove(sink)
    constructor.assert_not_called()
    assert str(error.value) == field
    assert error.value.__context__ is None
    captured = capsys.readouterr()
    assert captured.out + captured.err + caplog.text + "".join(logs) == ""
    rendered = "".join(traceback.format_exception(error.value))
    for value in [*IDENTITY.values(), "invalid-sensitive-input"]:
        assert value not in rendered


@pytest.mark.parametrize("field", ["CLIENT_LOCAL_IP", "CLIENT_PUBLIC_IP"])
@pytest.mark.parametrize("value", ["256.1.2.3", "1.2.3", "1.2.3.4.5", "01.2.3.4",
    "1.2.3.4/24", "::1", "1234", "1.2.3.4\n", " 1.2.3.4", "?.2.3.4"])
def test_strict_ipv4(configured, field, value):
    configured({field: value})
    with pytest.raises(historical.HistoricalSafetyError, match=f"^{field}$"):
        historical.create_historical_client()


@pytest.mark.parametrize("value", ["AA-BB-CC-DD-EE-FF", "AA:BB:CC:DD:EE",
    "AA:BB:CC:DD:EE:FF:00", "A:BB:CC:DD:EE:FF", "GG:BB:CC:DD:EE:FF",
    "AA:BB:CC:DD:EE:FF\n", " AA:BB:CC:DD:EE:FF"])
def test_strict_mac(configured, value):
    configured({"CLIENT_MAC": value})
    with pytest.raises(historical.HistoricalSafetyError, match="^CLIENT_MAC$"):
        historical.create_historical_client()
