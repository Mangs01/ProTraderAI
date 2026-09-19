"""Non-200 diagnostics with fake responses only and the global network guard."""
import json
import traceback
from unittest.mock import Mock

import pytest
import requests
from loguru import logger

from broker.historical_client import HistoricalClient, HistoricalSafetyError, HistoricalTransport

PARAMS = dict(exchange="NSE", symboltoken="3045", interval="FIVE_MINUTE",
              fromdate="2026-09-04 09:15", todate="2026-09-04 15:30")
SECRETS = ("fake-api-key", "fake-client", "123456", "JBSWY3DPEHPK3PXP",
           "10.23.45.67", "192.0.2.123", "Aa:Bb:01:23:45:Ff", "fake.jwt.signature")


def response(status, body):
    item = requests.Response()
    item.status_code = status
    item._content = body
    return item


def client_for(item):
    session = Mock()
    session.post.return_value = item
    transport = HistoricalTransport(network_enabled=True, session=session)
    client = HistoricalClient(api_key=SECRETS[0], client_code=SECRETS[1],
        pin=SECRETS[2], totp_secret=SECRETS[3], client_local_ip=SECRETS[4],
        client_public_ip=SECRETS[5], client_mac=SECRETS[6], transport=transport)
    client._jwt = SECRETS[7]
    return client, session


def capture(item):
    client, session = client_for(item)
    with pytest.raises(HistoricalSafetyError) as caught:
        client.getCandleData(PARAMS)
    session.post.assert_called_once()
    assert caught.value.__context__ is None
    return caught.value


@pytest.mark.parametrize("status,body,expected", [
    (403, b'{"status":false,"errorCode":"AB1010","message":"Invalid token"}',
     {"api_success": False, "api_error_code": "AB1010", "response_kind": "JSON_RESPONSE"}),
    (401, b'{"status":false,"errorcode":"AG8001"}',
     {"api_success": False, "api_error_code": "AG8001", "response_kind": "JSON_RESPONSE"}),
    (429, b'{"status":false,"error_code":429}',
     {"api_success": False, "api_error_code": 429, "response_kind": "JSON_RESPONSE"}),
    (403, b"<html>private gateway body</html>", {"response_kind": "NON_JSON_RESPONSE"}),
    (403, b"", {"response_kind": "EMPTY_RESPONSE"}),
    (500, b"private upstream failure", {"response_kind": "NON_JSON_RESPONSE"}),
], ids=["403-json", "401-json", "429-json", "403-html", "403-empty", "500-text"])
def test_response_categories(status, body, expected):
    error = capture(response(status, body))
    assert dict(error.diagnostics) == {"http_status": status, **expected}
    assert "message" not in error.diagnostics
    assert body.decode() not in str(error) if body else True
    with pytest.raises(TypeError):
        error.diagnostics["http_status"] = 200


@pytest.mark.parametrize("secret", SECRETS, ids=[
    "key", "client", "pin", "totp", "local", "public", "mac", "jwt"])
def test_sensitive_and_arbitrary_fields_never_escape(secret, capsys, caplog):
    body = json.dumps({"status": False, "errorCode": secret,
        "message": "rejected " + secret, "headers": {"Authorization": secret},
        "data": {"refreshToken": secret, "feedToken": secret},
        "html": "<html>" + secret + "</html>"}).encode()
    logs = []
    sink = logger.add(lambda message: logs.append(str(message)))
    try:
        error = capture(response(403, body))
    finally:
        logger.remove(sink)
    assert dict(error.diagnostics) == {
        "http_status": 403, "response_kind": "JSON_RESPONSE", "api_success": False}
    captured = capsys.readouterr()
    assert not (captured.out + captured.err + caplog.text + "".join(logs))
    rendered = str(error.diagnostics) + "".join(traceback.format_exception(error))
    assert secret not in rendered
    assert "<html>" not in rendered
    assert "headers" not in rendered


@pytest.mark.parametrize("attribute", [
    "_api_key", "_client_code", "_pin", "_totp_secret", "_jwt"])
def test_allowlisted_code_matching_runtime_secret_is_omitted(attribute):
    client, session = client_for(response(403, b'{"errorCode":"AB1010"}'))
    setattr(client, attribute, "AB1010")
    with pytest.raises(HistoricalSafetyError) as caught:
        client.getCandleData(PARAMS)
    assert dict(caught.value.diagnostics) == {
        "http_status": 403, "response_kind": "JSON_RESPONSE"}
    session.post.assert_called_once()


@pytest.mark.parametrize("field", ["jwtToken", "refreshToken", "feedToken", "cookies"])
def test_code_matching_sensitive_response_field_is_omitted(field):
    error = capture(response(403, json.dumps({
        "errorCode": "AB1010", "data": {field: "AB1010"}}).encode()))
    assert "api_error_code" not in error.diagnostics


@pytest.mark.parametrize("value", [
    "unknown-server-content", "eyJhbGci.fake.signature", "AB1010 secret",
    {"nested": "AB1010"}, ["AB1010"], True, 1.5, None])
def test_unallowlisted_or_nonscalar_code_is_omitted(value):
    error = capture(response(403, json.dumps({"errorCode": value}).encode()))
    assert set(error.diagnostics) == {"http_status", "response_kind"}


@pytest.mark.parametrize("value", ["false", 0, 1, None, {}, []])
def test_api_success_requires_boolean(value):
    error = capture(response(403, json.dumps({"status": value}).encode()))
    assert "api_success" not in error.diagnostics


def test_conflicting_code_aliases_fail_closed():
    error = capture(response(403, b'{"errorCode":"AB1010","errorcode":"AG8001"}'))
    assert "api_error_code" not in error.diagnostics


def test_safe_code_survives_sensitive_message():
    error = capture(response(403, json.dumps({
        "errorCode": "AB1010", "message": SECRETS[7]}).encode()))
    assert error.diagnostics["api_error_code"] == "AB1010"
    assert "message" not in error.diagnostics


def test_login_wrapper_preserves_diagnostics_without_response_context():
    client, session = client_for(response(401, b'{"status":false,"errorCode":"AG8001"}'))
    with pytest.raises(HistoricalSafetyError) as caught:
        client.authenticate()
    assert caught.value.diagnostics["http_status"] == 401
    assert caught.value.diagnostics["api_error_code"] == "AG8001"
    assert caught.value.__context__ is None
    assert client._jwt is None
    session.post.assert_called_once()


def test_network_default_remains_disabled():
    session = Mock()
    transport = HistoricalTransport(session=session)
    with pytest.raises(HistoricalSafetyError, match="disabled"):
        transport.post("candles", PARAMS, {})
    session.post.assert_not_called()


def test_no_stale_diagnostics_after_transport_failure():
    client, session = client_for(response(403, b'{"errorCode":"AB1010"}'))
    with pytest.raises(HistoricalSafetyError):
        client.getCandleData(PARAMS)
    session.post.side_effect = RuntimeError(SECRETS[7])
    with pytest.raises(HistoricalSafetyError) as caught:
        client.getCandleData(PARAMS)
    assert dict(caught.value.diagnostics) == {}
    assert caught.value.__context__ is None
    assert SECRETS[7] not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("owner", ["session", "response"])
def test_cookie_value_collision_is_omitted(owner):
    item = response(403, b'{"errorCode":"AB1010"}')
    client, session = client_for(item)
    jar = requests.cookies.RequestsCookieJar()
    jar.set("fake_cookie", "AB1010")
    setattr(session if owner == "session" else item, "cookies", jar)
    with pytest.raises(HistoricalSafetyError) as caught:
        client.getCandleData(PARAMS)
    assert "api_error_code" not in caught.value.diagnostics


def test_direct_transport_bearer_collision_is_omitted():
    session = Mock()
    session.post.return_value = response(403, b'{"errorCode":"AB1010"}')
    transport = HistoricalTransport(network_enabled=True, session=session)
    with pytest.raises(HistoricalSafetyError) as caught:
        transport.post("candles", PARAMS, {"Authorization": "Bearer AB1010"})
    assert "api_error_code" not in caught.value.diagnostics


def test_http_status_survives_body_read_failure():
    class BrokenResponse:
        status_code = 403

        @property
        def content(self):
            raise ValueError(SECRETS[7])

    error = capture(BrokenResponse())
    assert dict(error.diagnostics) == {"http_status": 403}
    assert SECRETS[7] not in "".join(traceback.format_exception(error))


@pytest.mark.parametrize("body,kind", [
    (b"   ", "EMPTY_RESPONSE"),
    (b'{"status":', "NON_JSON_RESPONSE"),
    (b'["private text"]', "JSON_RESPONSE"),
])
def test_other_body_shapes(body, kind):
    error = capture(response(403, body))
    assert dict(error.diagnostics) == {"http_status": 403, "response_kind": kind}


@pytest.mark.parametrize("field", ["jwtToken", "refreshToken", "feedToken"])
def test_prior_login_response_secrets_are_filtered_on_candle_error(field):
    login_data = {"jwtToken": SECRETS[7], "refreshToken": "fake-refresh",
                  "feedToken": "fake-feed"}
    login_data[field] = "AB1010"
    client, session = client_for(response(200, json.dumps({
        "status": True, "data": login_data}).encode()))
    client.authenticate()
    session.post.return_value = response(403, b'{"errorCode":"AB1010"}')
    with pytest.raises(HistoricalSafetyError) as caught:
        client.getCandleData(PARAMS)
    assert "api_error_code" not in caught.value.diagnostics
    assert caught.value.diagnostics["http_status"] == 403
    assert session.post.call_count == 2
