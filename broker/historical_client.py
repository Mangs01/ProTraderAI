"""Opt-in, SDK-free authentication and candle transport. Never logs secrets."""
from types import MappingProxyType
from ipaddress import IPv4Address
import re
import json

import pyotp
import requests

from data.historical_cache import validate_candle_data
from data.historical_downloader import HistoricalDownloader


# Only fixed protocol codes may leave the response boundary. Unknown codes and
# all server messages are omitted; do not broaden this to arbitrary scalar text.
_SAFE_ERROR_CODES = frozenset({
    "AB1004", "AB1006", "AB1010", "AB1011", "AG8001", "AG8002", "AG8003",
    "UNAUTHORIZED", "FORBIDDEN", "TOO_MANY_REQUESTS", "RATE_LIMITED",
    "INTERNAL_SERVER_ERROR", "401", "403", "429", "500",
})
_SECRET_FIELDS = frozenset({
    "authorization", "jwttoken", "refreshtoken", "feedtoken", "apikey",
    "privatekey", "clientcode", "password", "pin", "mpin", "totp", "totpsecret",
    "clientlocalip", "clientpublicip", "macaddress", "clientmac", "cookie",
    "cookies", "setcookie",
})


def _secret_scalars(value):
    if type(value) is dict:
        for item in value.values():
            yield from _secret_scalars(item)
    elif type(value) in (list, tuple):
        for item in value:
            yield from _secret_scalars(item)
    elif type(value) in (str, int, float) and str(value):
        text = str(value)
        yield text
        if text.startswith("Bearer "):
            yield text[len("Bearer "):]


def _response_secrets(value):
    if type(value) is dict:
        for key, item in value.items():
            normalized = re.sub(r"[^a-z]", "", key.lower()).removeprefix("x")
            if normalized in _SECRET_FIELDS:
                yield from _secret_scalars(item)
            else:
                yield from _response_secrets(item)
    elif type(value) is list:
        for item in value:
            yield from _response_secrets(item)


def _sanitize_diagnostics(candidate, sensitive=()):
    """Rebuild from fixed keys and constants, never retain response objects."""
    result = {}
    status = candidate.get("http_status")
    if type(status) is int and 100 <= status <= 599:
        result["http_status"] = status
    kind = candidate.get("response_kind")
    if type(kind) is str and kind in {
            "JSON_RESPONSE", "NON_JSON_RESPONSE", "EMPTY_RESPONSE"}:
        result["response_kind"] = kind
    success = candidate.get("api_success")
    if type(success) is bool:
        result["api_success"] = success
    code = candidate.get("api_error_code")
    if type(code) in (str, int):
        text = str(code)
        if text in _SAFE_ERROR_CODES and not any(
                secret and secret.casefold() in text.casefold()
                for secret in sensitive):
            result["api_error_code"] = code
    return result


def _response_diagnostics(response, sensitive):
    candidate = {"http_status": response.status_code}
    body = response.content
    if type(body) not in (bytes, str):
        candidate["response_kind"] = "NON_JSON_RESPONSE"
        return _sanitize_diagnostics(candidate, sensitive)
    if not body.strip():
        candidate["response_kind"] = "EMPTY_RESPONSE"
        return _sanitize_diagnostics(candidate, sensitive)
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError, RecursionError):
        candidate["response_kind"] = "NON_JSON_RESPONSE"
        return _sanitize_diagnostics(candidate, sensitive)
    candidate["response_kind"] = "JSON_RESPONSE"
    if type(parsed) is dict:
        candidate["api_success"] = parsed.get("status")
        codes = [parsed[key] for key in ("errorCode", "errorcode", "error_code")
                 if key in parsed]
        # Ambiguous aliases fail closed, including scalar type disagreement.
        if codes and all(type(code) is type(codes[0]) and code == codes[0]
                         for code in codes):
            candidate["api_error_code"] = codes[0]
        sensitive = (*sensitive, *_response_secrets(parsed))
    return _sanitize_diagnostics(candidate, sensitive)


class HistoricalSafetyError(RuntimeError):
    def __init__(self, message, *, diagnostics=None):
        super().__init__(message)
        self.diagnostics = MappingProxyType(
            _sanitize_diagnostics(diagnostics or {}))


_ROUTES = MappingProxyType({
    "login": "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
    "candles": "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData",
})


class HistoricalTransport:
    """Only two fixed POST endpoints; redirects and environment proxies disabled."""

    def __init__(self, *, network_enabled=False, session=None):
        self._enabled = network_enabled
        self._session = session
        self._sensitive_values = ()
        self._response_sensitive_values = ()

    def post(self, operation, payload, headers):
        if operation not in _ROUTES:
            raise HistoricalSafetyError("Historical operation is not allowed")
        if not self._enabled:
            raise HistoricalSafetyError("Historical network access is disabled")
        diagnostics = {}
        try:
            if self._session is None:
                self._session = requests.Session()
            self._session.trust_env = False
            response = self._session.post(
                _ROUTES[operation], json=payload, headers=headers,
                timeout=7, allow_redirects=False, verify=True,
            )
            if response.status_code == 200:
                result = response.json()
                if operation == "login":
                    self._response_sensitive_values = tuple(
                        _response_secrets(result))
                return result
            diagnostics = _sanitize_diagnostics(
                {"http_status": response.status_code})
            cookie_values = []
            for owner in (self._session, response):
                jar = getattr(owner, "cookies", None)
                if isinstance(jar, requests.cookies.RequestsCookieJar):
                    cookie_values.extend(jar.values())
            sensitive = (
                *self._sensitive_values, *self._response_sensitive_values,
                *_secret_scalars(headers), *_secret_scalars(payload),
                *_secret_scalars(cookie_values),
            )
            diagnostics = _response_diagnostics(response, sensitive)
        except Exception:
            # Do not propagate response objects or value-bearing parser errors.
            pass
        # Raise outside handlers so no exception context retains response data.
        raise HistoricalSafetyError(
            "Historical transport failed", diagnostics=diagnostics)


class HistoricalClient:
    """Only authenticate and getCandleData are available; fake transport injectable."""

    def __init__(self, *, api_key, client_code, pin, totp_secret,
                 transport=None, client_local_ip=None, client_public_ip=None,
                 client_mac=None):
        self._transport = transport if transport is not None else HistoricalTransport()
        self._api_key = api_key
        self._client_code = client_code
        self._pin = pin
        self._totp_secret = totp_secret
        self._identity = (client_local_ip, client_public_ip, client_mac)
        self._jwt = None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        raise HistoricalSafetyError("Operation unavailable on historical-only client")

    def _post(self, operation, payload):
        if operation not in _ROUTES:
            raise HistoricalSafetyError("Historical operation is not allowed")
        if not all(self._identity):
            raise HistoricalSafetyError("Explicit client network identity is required")
        headers = {
            "Content-type": "application/json", "Accept": "application/json",
            "X-PrivateKey": self._api_key, "X-UserType": "USER", "X-SourceID": "WEB",
            "X-ClientLocalIP": self._identity[0], "X-ClientPublicIP": self._identity[1],
            "X-MACAddress": self._identity[2],
        }
        if operation == "candles":
            if not self._jwt:
                raise HistoricalSafetyError("Historical authentication required")
            headers["Authorization"] = "Bearer " + self._jwt
        sensitive = tuple(_secret_scalars((
            self._api_key, self._client_code, self._pin, self._totp_secret,
            *self._identity, self._jwt, headers, payload,
        )))
        if isinstance(self._transport, HistoricalTransport):
            self._transport._sensitive_values = sensitive
        diagnostics = {}
        try:
            return self._transport.post(operation, payload, headers)
        except HistoricalSafetyError as error:
            diagnostics = _sanitize_diagnostics(error.diagnostics, sensitive)
        except Exception:
            pass
        raise HistoricalSafetyError(
            "Historical request failed", diagnostics=diagnostics)

    def authenticate(self):
        diagnostics = {}
        try:
            otp = pyotp.TOTP(self._totp_secret).now()
            result = self._post("login", {
                "clientcode": self._client_code, "password": self._pin, "totp": otp,
            })
            token = result["data"]["jwtToken"] if result.get("status") is True else None
            if not isinstance(token, str) or not token:
                raise ValueError()
            self._jwt = token
        except HistoricalSafetyError as error:
            diagnostics = dict(error.diagnostics)
        except Exception:
            pass
        else:
            # Auth response and refresh/feed tokens never leave the boundary.
            return None
        self._jwt = None
        raise HistoricalSafetyError(
            "Historical authentication failed", diagnostics=diagnostics)

    def getCandleData(self, params):
        if set(params) != {"exchange", "symboltoken", "interval", "fromdate", "todate"}:
            raise HistoricalSafetyError("Unexpected historical request fields")
        result = self._post("candles", dict(params))
        # Untrusted API strings can echo secrets: replace them, do not log them.
        try:
            if not isinstance(result, dict) or result.get("status") is not True:
                return {"status": False, "message": "Historical API rejected request", "errorcode": "REJECTED", "data": None}
            data = validate_candle_data(result["data"])
            rows = data.values.tolist()
        except Exception:
            return {"status": False, "message": "Malformed historical response", "errorcode": "MALFORMED", "data": None}
        return {"status": True, "message": "SUCCESS", "errorcode": "", "data": rows}


class HistoricalAcquisition(HistoricalDownloader):
    """Reuse downloader without inheriting any general broker capabilities."""

    def __init__(self, client):
        self.api = client
        self.last_download_diagnostics = None


def create_historical_client():
    """Validate configured identity before construction; network stays disabled."""
    from config import settings

    identity = {}
    for field, argument in (
        ("CLIENT_LOCAL_IP", "client_local_ip"),
        ("CLIENT_PUBLIC_IP", "client_public_ip"),
        ("CLIENT_MAC", "client_mac"),
    ):
        value = getattr(settings, field, None)
        valid = isinstance(value, str) and bool(value)
        if valid and field == "CLIENT_MAC":
            valid = re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", value) is not None
        elif valid:
            try:
                IPv4Address(value)
            except ValueError:
                valid = False
        if not valid:
            # Outside the parser handler: do not retain value-bearing context.
            raise HistoricalSafetyError(field)
        identity[argument] = value

    return HistoricalClient(
        api_key=settings.API_KEY, client_code=settings.CLIENT_CODE,
        pin=settings.MPIN, totp_secret=settings.TOTP_SECRET,
        transport=HistoricalTransport(network_enabled=False), **identity,
    )
