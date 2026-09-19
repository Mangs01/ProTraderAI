# Historical-only integration

Use HistoricalClient and HistoricalAcquisition from broker.historical_client for future controlled acquisition. Do not use main.py or AngelOneBroker.login for that operation: main remains the general backtest entry point, and the general broker deliberately retains its SDK behavior.

Imports never construct the SDK. General AngelOneBroker construction and LiveFeed construction load it lazily; these are explicitly outside the historical boundary. HistoricalClient never uses it.

The installed SDK generateSession obtains jwtToken from api.login before getProfile. Its getCandleData uses that bearer token via the normal request headers, not profile data. The separate historical authentication therefore stores only the login JWT and never requests a profile or exposes auth responses.

HistoricalTransport accepts only login and candles categories mapped to fixed HTTPS POST URLs on apiconnect.angelone.in. Network is disabled by default. A future authorized caller must explicitly supply HistoricalTransport(network_enabled=True) and real client local/public IP and MAC identity; there is no external IP discovery or fabricated identity. Redirects and environment proxies are disabled, TLS verification is enabled, timeout is seven seconds. Do not run any real acquisition as part of Phase 14A1.

HistoricalClient exposes authenticate and getCandleData. Unknown public operations fail closed. HistoricalAcquisition reuses the original downloader methods without inheriting order, account, or live functionality. Dependency injection is for trusted test doubles; it is not a security sandbox against malicious Python code.

Untrusted auth responses and transport exceptions never appear in diagnostic text. Historical API message/error-code strings are replaced with fixed safe messages/codes because they may echo credentials. OHLCV rows must validate before reaching downloader logging. Request headers, credentials, JWT, refresh/feed tokens are never logged or returned by authentication. This deliberately trades raw error-message fidelity for safety.

The shared downloader preserves chunk sizing, pacing, bounded retry/backoff, aggregation, CAS and legacy validation. The general broker inherits exactly the extracted methods. No strategy, risk, charge or session policy changed.

Pytest blocks socket connections/sends/DNS, requests Session.request and urllib.urlopen in pytest_configure, before test module collection. The blocker raises BaseException so broad SDK/retry Exception handlers cannot hide attempts. All fake transport tests operate under this guard. The required full suite includes existing strategy regression tests; no separate strategy experiment or historical acquisition is performed.

Phase 14A2: `create_historical_client()` reads CLIENT_LOCAL_IP, CLIENT_PUBLIC_IP,
and CLIENT_MAC through config.settings and maps them to client_local_ip,
client_public_ip, and client_mac. Before construction, it requires dotted-decimal
IPv4 addresses and exactly six colon-separated hexadecimal MAC byte pairs.
Missing, empty, or malformed fields raise HistoricalSafetyError naming only the
field. No values are discovered or logged. The factory always uses a disabled
transport and performs no authentication or requests. Direct constructor injection
remains available for existing fake-transport tests.

Phase 14A6: non-200 errors expose an immutable `HistoricalSafetyError.diagnostics`
mapping through transport, candle, and authentication boundaries. Allowlisted
keys are `http_status`, `response_kind`, `api_success`, and `api_error_code`.
Kinds are JSON_RESPONSE, NON_JSON_RESPONSE, and EMPTY_RESPONSE. Only real boolean
JSON status values are retained. Error codes must belong to the finite
`_SAFE_ERROR_CODES` set; unknown codes, conflicting aliases, and codes containing
known credential/token/identity/cookie values are omitted. No semantic meaning
is inferred from a code. All server messages and other response fields are
discarded, including messages that appear harmless. HTTP status remains useful
when parsing or sanitization cannot retain additional detail.

For a future explicitly authorized diagnostic run, catch HistoricalSafetyError
and report only its diagnostics mapping and fixed error message. Do not dump
exceptions with locals, request/response objects, headers, cookies, or raw bodies.
No automatic logging or retries were added. The outgoing request contract and
disabled network default are unchanged. Phase 14A6 uses fake responses only.
