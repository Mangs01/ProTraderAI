import importlib
import sys
from unittest.mock import Mock

import pandas as pd
import pytest
from loguru import logger

from broker.historical_client import (
    HistoricalAcquisition, HistoricalClient, HistoricalSafetyError, HistoricalTransport,
)
from data.historical_cache import HistoricalCache


SECRETS = ["FAKE_API_KEY", "FAKE_CLIENT", "FAKE_PIN", "JBSWY3DPEHPK3PXP", "FAKE_JWT"]


def client(transport):
    return HistoricalClient(api_key=SECRETS[0], client_code=SECRETS[1], pin=SECRETS[2],
        totp_secret=SECRETS[3], transport=transport, client_local_ip="127.0.0.1",
        client_public_ip="192.0.2.1", client_mac="00:00:00:00:00:00")


def rows():
    return [[str(t),100,101,99,100,1000] for t in pd.date_range(
        "2026-09-01 09:15", "2026-09-01 15:10", freq="5min", tz="Asia/Kolkata")]


def acquire(c, sleep=None):
    a = HistoricalAcquisition(c)
    result = a.get_historical_data("NSE", "3045", "FIVE_MINUTE",
        "2026-09-01 09:15", "2026-09-01 15:30", chunk_days=30,
        cas_eligible=True, max_retries=2, retry_backoff_seconds=5,
        sleep_fn=sleep or Mock())
    return a, result


def test_imports_never_load_sdk():
    for name in ("broker.angelone", "data.historical_downloader", "data.historical_cache",
                 "data.historical", "broker.historical_client", "research.ema_harness", "live.live_feed"):
        importlib.import_module(name)
    assert not any(n == "SmartApi" or n.startswith("SmartApi.") for n in sys.modules)


def test_default_transport_is_disabled():
    with pytest.raises(HistoricalSafetyError, match="disabled"):
        HistoricalTransport().post("login", {}, {})


@pytest.mark.parametrize("operation", ["placeOrder", "modifyOrder", "cancelOrder", "orderBook",
    "tradeBook", "position", "holdings", "funds", "websocket", "LiveFeed", "getProfile"])
def test_forbidden_operations_fail_closed(operation):
    transport = Mock()
    c = client(transport)
    with pytest.raises(HistoricalSafetyError):
        getattr(c, operation)()
    with pytest.raises(HistoricalSafetyError):
        HistoricalTransport(network_enabled=True).post(operation, {}, {})
    transport.post.assert_not_called()


def test_authentication_then_candles_without_profile():
    transport = Mock()
    transport.post.side_effect = [{"status": True, "data": {"jwtToken": SECRETS[4]}},
        {"status": True, "data": rows()}]
    c = client(transport)
    assert c.authenticate() is None
    a, result = acquire(c)
    assert result["status"] is True
    assert len(result["data"]) == 72
    assert [call.args[0] for call in transport.post.call_args_list] == ["login", "candles"]
    assert transport.post.call_args.args[2]["Authorization"] == "Bearer " + SECRETS[4]
    assert not hasattr(a, "place_order")


def test_secret_safe_retry_and_diagnostics():
    transport = Mock()
    transport.post.side_effect = [{"status": True, "data": {"jwtToken": SECRETS[4]}},
        RuntimeError("Authorization " + " ".join(SECRETS)),
        {"status": False, "message": " ".join(SECRETS), "errorcode": SECRETS[0]}]
    output = []
    sink = logger.add(lambda message: output.append(str(message)))
    try:
        c = client(transport); c.authenticate()
        sleep = Mock()
        a, result = acquire(c, sleep)
        assert result is None
        sleep.assert_called_once_with(5)
        text = "".join(output) + str(a.last_download_diagnostics)
        assert all(secret not in text for secret in SECRETS)
    finally:
        logger.remove(sink)


def test_malformed_response_and_no_publication(tmp_path):
    transport = Mock()
    transport.post.side_effect = [{"status": True, "data": {"jwtToken": SECRETS[4]}},
        {"status": True, "data": [[SECRETS[0]]]}, {"status": True, "data": [[SECRETS[0]]]}]
    c = client(transport); c.authenticate()
    a, result = acquire(c)
    assert result is None
    assert SECRETS[0] not in str(a.last_download_diagnostics)
    assert list(tmp_path.iterdir()) == []


def test_incomplete_session_rejected_by_shared_downloader(tmp_path):
    transport = Mock()
    transport.post.side_effect = [{"status": True, "data": {"jwtToken": SECRETS[4]}},
        {"status": True, "data": rows()[:-1]}]
    c = client(transport); c.authenticate()
    a, result = acquire(c)
    assert result is None
    assert "15:10" in a.last_download_diagnostics["validation_error"]
    cache = HistoricalCache("NSE", "3045", "FIVE_MINUTE", cache_dir=tmp_path, cas_eligible=True)
    with pytest.raises(ValueError):
        cache.save(rows()[:-1], "2026-09-01 09:15", "2026-09-01 15:30")
    assert list(tmp_path.iterdir()) == []


def test_transport_uses_only_fixed_url_without_redirects():
    session = Mock()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = {"status": True}
    t = HistoricalTransport(network_enabled=True, session=session)
    t.post("login", {}, {})
    assert session.post.call_args.args[0].endswith("/loginByPassword")
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert session.post.call_args.kwargs["verify"] is True
    assert session.trust_env is False


def test_failed_auth_does_not_expose_secrets():
    transport = Mock()
    transport.post.side_effect = RuntimeError(" ".join(SECRETS))
    with pytest.raises(HistoricalSafetyError) as error:
        client(transport).authenticate()
    assert all(secret not in str(error.value) for secret in SECRETS)


def test_network_blocker_is_active():
    import socket
    import requests
    from conftest import NetworkForbidden
    with pytest.raises(NetworkForbidden):
        socket.getaddrinfo("example.invalid", 443)
    with pytest.raises(NetworkForbidden):
        requests.get("https://example.invalid")


def test_redirect_response_is_rejected_without_following():
    session = Mock()
    session.post.return_value.status_code = 302
    with pytest.raises(HistoricalSafetyError):
        HistoricalTransport(network_enabled=True, session=session).post("login", {}, {})
    session.post.assert_called_once()
    session.post.return_value.json.assert_not_called()


def test_candles_before_authentication_do_not_reach_transport():
    transport = Mock()
    c = client(transport)
    with pytest.raises(HistoricalSafetyError, match="authentication required"):
        c.getCandleData(dict(exchange="NSE", symboltoken="3045", interval="FIVE_MINUTE",
            fromdate="2026-09-01 09:15", todate="2026-09-01 15:30"))
    transport.post.assert_not_called()
