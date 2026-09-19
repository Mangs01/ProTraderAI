"""Fake-data request contracts; prepare requests only, never send or import SDK."""
import json
import sys
import traceback
from unittest.mock import Mock

import pytest
import requests
from loguru import logger

from broker.historical_client import HistoricalClient, HistoricalSafetyError, HistoricalTransport

ROOT = "https://apiconnect.angelone.in"
LOGIN = ROOT + "/rest/auth/angelbroking/user/v1/loginByPassword"
CANDLES = ROOT + "/rest/secure/angelbroking/historical/v1/getCandleData"
PARAMS = dict(exchange="NSE", symboltoken="3045", interval="FIVE_MINUTE",
              fromdate="2026-09-04 09:15", todate="2026-09-04 15:30")
JWT = "fake-header.fake-payload.fake-signature"
HEADERS = {
    "Content-type": "application/json", "Accept": "application/json",
    "X-PrivateKey": "fake-api-key", "X-ClientLocalIP": "10.23.45.67",
    "X-ClientPublicIP": "192.0.2.123", "X-MACAddress": "Aa:Bb:01:23:45:Ff",
    "X-UserType": "USER", "X-SourceID": "WEB",
}


class PreparingSession(requests.Session):
    """Use real Requests preparation, returning fake responses without send."""

    def __init__(self, token=JWT):
        super().__init__()
        self.token = token
        self.captured = []

    def post(self, url, **kwargs):
        prepared = self.prepare_request(requests.Request(
            "POST", url, headers=kwargs["headers"], json=kwargs["json"]))
        self.captured.append((prepared, kwargs))
        if url == LOGIN:
            body = {"status": True, "data": {"jwtToken": self.token,
                    "refreshToken": "fake-refresh", "feedToken": "fake-feed"}}
        else:
            assert url == CANDLES
            body = {"status": True, "data": [
                ["2026-09-04T09:15:00+05:30", 100, 101, 99, 100, 1000]]}
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(body).encode("utf-8")
        return response


def make_client(session):
    return HistoricalClient(
        api_key=HEADERS["X-PrivateKey"], client_code="fake-client",
        pin="fake-pin", totp_secret="JBSWY3DPEHPK3PXP",
        client_local_ip=HEADERS["X-ClientLocalIP"],
        client_public_ip=HEADERS["X-ClientPublicIP"],
        client_mac=HEADERS["X-MACAddress"],
        transport=HistoricalTransport(network_enabled=True, session=session))


def test_prepared_login_and_candle_contract(monkeypatch, capsys, caplog):
    session = PreparingSession()
    send = Mock(side_effect=AssertionError("Prepared request must never be sent"))
    monkeypatch.setattr(session, "send", send)
    client = make_client(session)
    assert client.authenticate() is None
    assert client.getCandleData(PARAMS)["status"] is True
    login, candle = (entry[0] for entry in session.captured)
    assert (login.url, candle.url) == (LOGIN, CANDLES)
    assert login.method == candle.method == "POST"
    assert session.captured[0][1]["headers"] == HEADERS
    assert session.captured[1][1]["headers"] == {
        **HEADERS, "Authorization": "Bearer " + JWT}
    for key, value in HEADERS.items():
        assert login.headers[key] == candle.headers[key] == value
    assert "Content-type" in list(candle.headers)
    assert candle.headers["Content-Type"] == "application/json"
    assert "Authorization" not in login.headers
    assert candle.headers["Authorization"] == "Bearer " + JWT
    assert candle.headers["User-Agent"] == requests.utils.default_user_agent()
    for _, options in session.captured:
        assert options["timeout"] == 7
        assert options["allow_redirects"] is False
        assert options["verify"] is True
    assert session.trust_env is False
    send.assert_not_called()
    assert not any(n == "SmartApi" or n.startswith("SmartApi.") for n in sys.modules)
    captured = capsys.readouterr()
    assert not captured.out and not captured.err and not caplog.text


def test_smoke_json_matches_sdk_data_serialization():
    session = PreparingSession()
    client = make_client(session)
    client.authenticate()
    client.getCandleData(PARAMS)
    actual = session.captured[1][0]
    # Reproduce SDK Requests arguments from source inspection, not SDK execution.
    sdk_prepared = session.prepare_request(requests.Request(
        "POST", CANDLES, data=json.dumps(PARAMS),
        headers={**HEADERS, "Authorization": "Bearer " + JWT}))
    assert actual.body == sdk_prepared.body.encode("utf-8")
    assert actual.headers == sdk_prepared.headers
    decoded = json.loads(actual.body)
    assert decoded == PARAMS
    assert isinstance(decoded["symboltoken"], str)
    assert len(decoded) == 5


@pytest.mark.parametrize("token", [JWT, "a." + "b" * 8192 + ".c", "a-b_c.d-e_f.g-h_i"],
                         ids=["ordinary", "long", "base64url"])
def test_jwt_is_preserved_and_prefixed_once(token):
    session = PreparingSession(token)
    client = make_client(session)
    client.authenticate()
    assert client._jwt == token
    client.getCandleData(PARAMS)
    header = session.captured[1][0].headers["Authorization"]
    assert header == "Bearer " + token
    assert header.count("Bearer ") == 1
    assert header[len("Bearer "):] == token
    assert "fake-refresh" not in header and "fake-feed" not in header
    assert not any(c in header for c in ('"', "\r", "\n"))
    assert header == header.strip()


@pytest.mark.parametrize("token", [None, "", 123, {"token": "fake"}],
                         ids=["missing", "empty", "number", "object"])
def test_refresh_and_feed_are_never_jwt_fallbacks(token):
    session = PreparingSession(token)
    client = make_client(session)
    with pytest.raises(HistoricalSafetyError, match="^Historical authentication failed$"):
        client.authenticate()
    assert client._jwt is None
    with pytest.raises(HistoricalSafetyError, match="authentication required"):
        client.getCandleData(PARAMS)
    assert len(session.captured) == 1


def test_failed_reauthentication_clears_previous_jwt():
    session = PreparingSession()
    client = make_client(session)
    client.authenticate()
    session.token = None
    with pytest.raises(HistoricalSafetyError):
        client.authenticate()
    assert client._jwt is None
    with pytest.raises(HistoricalSafetyError, match="authentication required"):
        client.getCandleData(PARAMS)
    assert all(request.url == LOGIN for request, _ in session.captured)


def test_403_body_is_not_exposed_or_retried(capsys, caplog):
    marker = "fake-sensitive-response-marker"
    session = Mock()
    session.post.return_value.status_code = 403
    session.post.return_value.json.side_effect = AssertionError(marker)
    client = make_client(session)
    client._jwt = JWT
    logs = []
    sink = logger.add(lambda message: logs.append(str(message)))
    try:
        with pytest.raises(HistoricalSafetyError) as error:
            client.getCandleData(PARAMS)
    finally:
        logger.remove(sink)
    session.post.assert_called_once()
    session.post.return_value.json.assert_not_called()
    captured = capsys.readouterr()
    assert not (captured.out + captured.err + caplog.text + "".join(logs))
    rendered = "".join(traceback.format_exception(error.value))
    for value in (marker, JWT, *[HEADERS[k] for k in (
            "X-PrivateKey", "X-ClientLocalIP", "X-ClientPublicIP", "X-MACAddress")]):
        assert value not in rendered


@pytest.mark.parametrize("token", [" " + JWT, JWT + " ", "Bearer " + JWT],
                         ids=["leading-space", "trailing-space", "already-prefixed"])
def test_server_token_text_is_not_normalized(token):
    # Characterize the same raw-token assumption used by the SDK; this is not
    # evidence that any malformed token was returned in the real smoke test.
    session = PreparingSession(token)
    client = make_client(session)
    client.authenticate()
    assert client._jwt == token
    client.getCandleData(PARAMS)
    assert session.captured[1][0].headers["Authorization"] == "Bearer " + token
