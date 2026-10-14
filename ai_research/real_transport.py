"""AI-R3A transport preparation. Real execution is blocked by local evidence gates.

No credentials, files or sockets are accessed on import, preview or simulation.
Offline compatibility uses the pinned Responses contract; live readiness is UNVERIFIED.
"""

from dataclasses import asdict, dataclass, field
import hashlib
import http.client
import json
import os
import ssl
import time
import threading
from types import MappingProxyType

from . import foundation as f
from . import openai_provider as o


API_COMPATIBILITY_STATUS = "UNVERIFIED"
# Intentionally empty: never promote operator guesses to official model/pricing evidence.
VERIFIED_MODEL_PRICING = MappingProxyType({})
CREDENTIAL_ENVIRONMENT_VARIABLE = "PROTRADERAI_OPENAI_RESEARCH_API_KEY"
HOST = "api.openai.com"
PATH = "/v1/responses"


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RequestBudget:
    max_requests: int
    max_cost_microusd: int
    max_input_tokens: int = 12000
    max_output_tokens: int = 2048
    max_request_bytes: int = 16384
    max_response_bytes: int = 32768
    max_report_bytes: int = 16384
    timeout_seconds: float = 5.0

    def __post_init__(self):
        # One request only: no automatic retries, including potentially billable timeouts.
        o._check(type(self.max_requests) is int and self.max_requests == 1, "ONE_REQUEST_ONLY")
        for key, upper in (("max_cost_microusd", 1000000), ("max_input_tokens", 65536),
                           ("max_output_tokens", 8192), ("max_request_bytes", 65536),
                           ("max_response_bytes", 65536),
                           ("max_report_bytes", 65536)):
            value = getattr(self, key)
            o._check(type(value) is int and 1 <= value <= upper, "INVALID_BUDGET")
        o._check(type(self.timeout_seconds) in (int, float) and
                 0.05 <= self.timeout_seconds <= 30, "INVALID_TIMEOUT")


class _OfflineReservation:
    """One review's process-local, atomic reservation; never a billing ledger."""
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = self.tokens = self.cost_microusd = 0

    def reserve(self, budget, estimate):
        with self.lock:
            o._check(self.requests < budget.max_requests, "REQUEST_BUDGET_EXHAUSTED")
            o._check(self.cost_microusd + estimate <= budget.max_cost_microusd, "COST_BUDGET_EXCEEDED")
            self.requests += 1
            self.tokens += budget.max_input_tokens + budget.max_output_tokens
            self.cost_microusd += estimate
            # No release: success, failure and ambiguous attempts retain full reservation.


@dataclass(frozen=True)
class PayloadReview:
    snapshot_sha256: str
    payload_sha256: str
    model: str
    max_cost_microusd: int
    max_requests: int
    resource_settings: tuple
    _reservation: _OfflineReservation = field(default_factory=_OfflineReservation, compare=False, repr=False)


@dataclass(frozen=True)
class FutureAuthorization:
    """Separate operator attestation, not authentication. No grant is made in AI-R3A."""
    review: PayloadReview
    separately_authorized: bool = False


@dataclass(frozen=True)
class OfflineTestPricing:
    """Fake model/rates only. This type is never accepted for live execution."""
    model: str
    input_microusd_per_token: int
    output_microusd_per_token: int

    def __post_init__(self):
        o.OpenAIConfig(model=self.model)
        o._check(self.model is not None, "MODEL_REQUIRED")
        for value in (self.input_microusd_per_token, self.output_microusd_per_token):
            o._check(type(value) is int and 1 <= value <= 1000000, "INVALID_TEST_PRICING")


def _strict_json(text):
    try:
        return json.loads(text, object_pairs_hook=o._unique_object,
                          parse_constant=o._invalid_constant)
    except (ValueError, TypeError, RecursionError):
        raise o.ProviderFailure("MALFORMED_RESPONSE") from None


class FakeHTTPExchange:
    """Scripted bytes and failures. No callbacks, sleeping, credentials or network."""
    def __init__(self, body=b"", *, status=200, failure=None, read_delays=(),
                 content_length="auto", content_type="application/json",
                 connection_close=False, chunked=False, chunked_complete=True,
                 connect_delay=0, request_delay=0, header_delay=0, chunk_size=4096):
        o._check(type(body) is bytes and type(status) is int, "INVALID_FAKE_HTTP")
        o._check(failure in (None, "connect_timeout", "read_timeout"), "INVALID_FAKE_HTTP")
        o._check(type(read_delays) is tuple and len(read_delays) <= 100 and
                 all(type(delay) in (int, float) and 0 <= delay <= 60 for delay in read_delays),
                 "INVALID_FAKE_HTTP")
        for value in (connection_close, chunked, chunked_complete):
            o._check(type(value) is bool, "INVALID_FAKE_HTTP")
        for value in (connect_delay, request_delay, header_delay):
            o._check(type(value) in (int, float) and 0 <= value <= 60, "INVALID_FAKE_HTTP")
        o._check(type(chunk_size) is int and 1 <= chunk_size <= 4096, "INVALID_FAKE_HTTP")
        self.connection_close, self.chunked = connection_close, chunked
        self.chunked_complete, self.chunk_size = chunked_complete, chunk_size
        self.connect_delay, self.request_delay, self.header_delay = connect_delay, request_delay, header_delay
        self.headers_received = False
        self.response_closes = 0
        self.read_sizes = []
        self.body, self.status, self.failure = body, status, failure
        o._check(content_length is None or type(content_length) is str, "INVALID_FAKE_HTTP")
        o._check(type(content_type) is str, "INVALID_FAKE_HTTP")
        self.content_length, self.content_type = content_length, content_type
        self.read_delays = read_delays
        self.elapsed = 0.0
        self.offset = self.reads = self.requests = self.closes = 0
        self.timeout_values = []

    def monotonic(self):
        return self.elapsed

    def connect(self):
        self.elapsed += self.connect_delay
        if self.failure == "connect_timeout":
            raise TimeoutError

    @property
    def sock(self):
        return None if self.connection_close and self.headers_received else self

    def settimeout(self, value):
        self.timeout_values.append(value)

    def request(self, method, path, *, body, headers):
        o._check(method == "POST" and path == PATH, "INVALID_REQUEST")
        self.requests += 1
        self.elapsed += self.request_delay
        # Never retain Authorization headers, even in offline simulations.

    def getresponse(self):
        self.elapsed += self.header_delay
        self.headers_received = True
        return _FakeHTTPResponse(self)

    def getheader(self, name, default=None):
        if name == "Transfer-Encoding":
            return "chunked" if self.chunked else default
        if name == "Content-Length":
            if self.chunked:
                return None
            return str(len(self.body)) if self.content_length == "auto" else self.content_length
        if name == "Content-Type":
            return self.content_type
        return default

    def read1(self, size):
        self.read_sizes.append(size)
        if self.failure == "read_timeout":
            raise TimeoutError
        if self.reads < len(self.read_delays):
            self.elapsed += self.read_delays[self.reads]
        self.reads += 1
        if self.chunked and not self.chunked_complete and self.offset >= len(self.body):
            raise http.client.IncompleteRead(b"")
        result = self.body[self.offset:self.offset + min(size, self.chunk_size)]
        self.offset += len(result)
        return result

    def close(self):
        self.closes += 1


class _FakeHTTPResponse:
    """Response owns its reader independently of connection.sock; decoded chunks."""
    def __init__(self, exchange):
        self.exchange = exchange
        self.status = exchange.status

    def getheader(self, name, default=None):
        return self.exchange.getheader(name, default)

    def read1(self, size):
        return self.exchange.read1(size)

    def close(self):
        self.exchange.response_closes += 1


def _number(value):
    return type(value) in (int, float) and -float("inf") < value < float("inf")


def _validate_envelope(e, model):
    required = {"id", "object", "created_at", "model", "output", "error", "incomplete_details",
                "instructions", "access_programs", "metadata", "parallel_tool_calls",
                "temperature", "top_p", "tools", "tool_choice"}
    optional = {"status", "usage", "completed_at", "background", "max_output_tokens",
                "max_tool_calls", "previous_response_id", "conversation", "service_tier"}
    o._check(type(e) is dict and required <= set(e), "REQUIRED_RESPONSE_FIELDS")
    o._check(set(e) <= required | optional, "UNKNOWN_RESPONSE_FIELDS")
    o._check(type(e["id"]) is str and bool(e["id"]) and e["object"] == "response" and
             e["model"] == model and _number(e["created_at"]) and e["created_at"] >= 0,
             "INVALID_RESPONSE_METADATA")
    # Conservative local success policy; docs do not establish cross-field invariants.
    o._check(type(e.get("status")) is str and e["status"] == "completed" and
             e["error"] is None and e["incomplete_details"] is None,
             "INCOMPLETE_OR_INVALID_RESPONSE")
    o._check(e["instructions"] is None or type(e["instructions"]) is str,
             "UNSUPPORTED_RESPONSE_METADATA")
    access = e["access_programs"]
    o._check(access is None or (type(access) is dict and set(access) == {"cyber"} and
             access["cyber"] in ("standard", "daybreak_blue", "daybreak_red")), "INVALID_RESPONSE_METADATA")
    metadata = e["metadata"]
    o._check(metadata is None or (type(metadata) is dict and len(metadata) <= 16 and
             all(type(k) is str and len(k) <= 64 and type(v) is str and len(v) <= 512
                 for k, v in metadata.items())), "INVALID_RESPONSE_METADATA")
    o._check(type(e["parallel_tool_calls"]) is bool and type(e["tools"]) is list and
             e["tools"] == [] and e["tool_choice"] in ("auto", "none"), "UNSUPPORTED_RESPONSE_METADATA")
    for key, high in (("temperature", 2), ("top_p", 1)):
        o._check(e[key] is None or (_number(e[key]) and 0 <= e[key] <= high), "INVALID_RESPONSE_METADATA")
    for key in ("completed_at", "max_output_tokens", "max_tool_calls"):
        if key in e:
            o._check(e[key] is None or (_number(e[key]) and e[key] >= 0), "INVALID_RESPONSE_METADATA")
    if "background" in e:
        o._check(e["background"] is None or e["background"] is False, "UNSUPPORTED_RESPONSE_METADATA")
    if "previous_response_id" in e:
        o._check(e["previous_response_id"] is None or type(e["previous_response_id"]) is str,
                 "INVALID_RESPONSE_METADATA")
    if "conversation" in e:
        c = e["conversation"]
        o._check(c is None or (type(c) is dict and set(c) == {"id"} and type(c["id"]) is str),
                 "INVALID_RESPONSE_METADATA")
    if "service_tier" in e:
        o._check(e["service_tier"] in (None, "auto", "default", "flex", "scale", "priority", "fast", "ultrafast"),
                 "INVALID_RESPONSE_METADATA")
    # Usage is optional/nullable on the wire, but mandatory for local bounded success.
    o._check(type(e.get("usage")) is dict, "INVALID_USAGE")


def _validate_reasoning(item):
    o._check(type(item) is dict and {"id", "type", "summary"} <= set(item) <=
             {"id", "type", "summary", "content", "encrypted_content", "status"} and
             type(item["id"]) is str and bool(item["id"]) and item["type"] == "reasoning",
             "OUTPUT_SCHEMA_MISMATCH")
    for key, kind in (("summary", "summary_text"), ("content", "reasoning_text")):
        if key in item:
            o._check(type(item[key]) is list and all(type(entry) is dict and
                     set(entry) == {"type", "text"} and entry["type"] == kind and
                     type(entry["text"]) is str for entry in item[key]), "OUTPUT_SCHEMA_MISMATCH")
    if "encrypted_content" in item:
        o._check(item["encrypted_content"] is None or type(item["encrypted_content"]) is str,
                 "OUTPUT_SCHEMA_MISMATCH")
    if "status" in item:
        o._check(item["status"] == "completed", "OUTPUT_SCHEMA_MISMATCH")


def _validate_logprobs(entries):
    o._check(type(entries) is list, "OUTPUT_SCHEMA_MISMATCH")
    def valid(entry, top=False):
        keys = {"token", "bytes", "logprob"} | (set() if top else {"top_logprobs"})
        return (type(entry) is dict and set(entry) == keys and type(entry["token"]) is str and
                type(entry["bytes"]) is list and all(_number(v) for v in entry["bytes"]) and
                _number(entry["logprob"]) and (top or (type(entry["top_logprobs"]) is list and
                all(valid(v, True) for v in entry["top_logprobs"]))))
    o._check(all(valid(entry) for entry in entries), "OUTPUT_SCHEMA_MISMATCH")


class RealOpenAIHTTPTransport:
    """Separate from AI-R2. Live path disabled and guarded by missing official evidence."""
    def __init__(self, *, model=None, budget=None, enabled=False):
        o._check(type(enabled) is bool, "INVALID_CONFIGURATION")
        o.OpenAIConfig(model=model)
        o._check(budget is None or type(budget) is RequestBudget, "INVALID_BUDGET")
        self.model, self.budget, self.enabled = model, budget, enabled

    def preview(self, snapshot, *, approval, allowlist):
        o._check(self.model is not None, "MODEL_REQUIRED")
        o._check(type(self.budget) is RequestBudget, "EXPLICIT_BUDGET_REQUIRED")
        config = o.OpenAIConfig(model=self.model,
            max_input_bytes=self.budget.max_request_bytes,
            max_input_tokens=self.budget.max_input_tokens,
            max_output_tokens=self.budget.max_output_tokens)
        preview = o.OpenAIResearchProvider(config=config, approval=approval,
                                          allowlist=allowlist).preview(snapshot)
        preview["payload_sha256"] = _hash(preview["request_json"])
        preview["api_compatibility_status"] = API_COMPATIBILITY_STATUS
        preview["model_account_availability"] = "UNVERIFIED"
        preview["pricing_status"] = "VERIFIED" if self.model in VERIFIED_MODEL_PRICING else "UNVERIFIED"
        preview["estimated_cost_microusd"] = None
        preview["actual_billed_cost_microusd"] = None
        preview["budget"] = asdict(self.budget)
        preview["live_readiness"] = "BLOCKED"
        return preview

    def review_payload(self, preview, *, operator_reviewed=False):
        o._check(operator_reviewed is True, "EXACT_PAYLOAD_REVIEW_REQUIRED")
        o._check(preview["model"] == self.model and
                 preview["payload_sha256"] == _hash(preview["request_json"]), "PAYLOAD_HASH_MISMATCH")
        o._check(preview["budget"] == asdict(self.budget), "PAYLOAD_HASH_MISMATCH")
        return PayloadReview(preview["snapshot_sha256"], preview["payload_sha256"], self.model,
                             self.budget.max_cost_microusd, self.budget.max_requests,
                             tuple(sorted(asdict(self.budget).items())))

    def _reviewed(self, preview, review):
        o._check(type(review) is PayloadReview and
                 review == PayloadReview(preview["snapshot_sha256"], preview["payload_sha256"],
                    self.model, self.budget.max_cost_microusd, self.budget.max_requests,
                    tuple(sorted(asdict(self.budget).items()))),
                 "PAYLOAD_HASH_MISMATCH")

    def _estimate(self, preview, pricing):
        o._check(type(pricing) is OfflineTestPricing, "UNKNOWN_PRICING")
        o._check(pricing.model == self.model, "UNKNOWN_MODEL")
        # Full input ceiling + output cap reservation. It exceeds the byte heuristic.
        # Token framing/model behavior remains unverified; never treat this as billed cost.
        estimate = (self.budget.max_input_tokens * pricing.input_microusd_per_token +
                    self.budget.max_output_tokens * pricing.output_microusd_per_token)
        o._check(estimate <= self.budget.max_cost_microusd, "COST_BUDGET_EXCEEDED")
        return estimate

    def _http(self, preview, credential, *, fake=None):
        # Even direct private-helper calls cannot reach a real socket in AI-R3A.
        o._check(type(fake) is FakeHTTPExchange, "LIVE_EXECUTION_LOCKED_IN_AI_R3A")
        o._check(type(credential) is str and 0 < len(credential) <= 4096 and
                 credential.isascii() and not any(c.isspace() for c in credential),
                 "CREDENTIAL_REQUIRED_OR_INVALID")
        budget = self.budget
        o._check(len(preview["request_json"].encode("utf-8")) <= budget.max_request_bytes,
                 "INPUT_SIZE_LIMIT")
        clock = fake.monotonic
        deadline = clock() + budget.timeout_seconds
        connection = fake
        response = None
        def remaining():
            value = deadline - clock()
            o._check(value > 0, "TIMEOUT")
            return value
        try:
            # Fake-only path. No connection factory or credential discovery.
            connection.settimeout(remaining())
            connection.connect()
            remaining()
            io_socket = connection.sock
            o._check(io_socket is not None, "HTTP_FAILURE_NO_RETRY")
            io_socket.settimeout(remaining())
            connection.request("POST", PATH, body=preview["request_json"].encode("utf-8"),
                headers={"Authorization": "Bearer " + credential,
                         "Content-Type": "application/json", "Accept": "application/json",
                         "Accept-Encoding": "identity"})
            io_socket.settimeout(remaining())
            response = connection.getresponse()
            remaining()
            o._check(response.status != 429, "HTTP_429_NO_RETRY")
            o._check(not 500 <= response.status <= 599, "HTTP_5XX_NO_RETRY")
            o._check(response.status == 200, "HTTP_STATUS_REJECTED")
            o._check(response.getheader("Content-Type", "").split(";")[0].strip().lower()
                     == "application/json", "INVALID_CONTENT_TYPE")
            o._check(response.getheader("Content-Encoding", "identity") == "identity",
                     "ENCODED_RESPONSE_REJECTED")
            transfer = response.getheader("Transfer-Encoding")
            length = response.getheader("Content-Length")
            o._check(transfer in (None, "chunked") and not (transfer and length is not None),
                     "INVALID_TRANSFER_ENCODING")
            if length is not None:
                o._check(length.isdigit() and int(length) <= budget.max_response_bytes,
                         "RESPONSE_SIZE_LIMIT")
            chunks, size = [], 0
            while True:
                io_socket.settimeout(remaining())
                read_limit = min(4096, budget.max_response_bytes + 1 - size)
                chunk = response.read1(read_limit)
                remaining()
                o._check(type(chunk) is bytes and len(chunk) <= read_limit,
                         "INVALID_HTTP_READ")
                if not chunk:
                    break
                size += len(chunk)
                o._check(size <= budget.max_response_bytes, "RESPONSE_SIZE_LIMIT")
                chunks.append(chunk)
            o._check(length is None or size == int(length), "INCOMPLETE_RESPONSE")
            return b"".join(chunks)
        except http.client.IncompleteRead:
            raise o.ProviderFailure("INCOMPLETE_RESPONSE") from None
        except (TimeoutError,):
            raise o.ProviderFailure("TIMEOUT") from None
        except o.ProviderFailure:
            raise
        except Exception:
            raise o.ProviderFailure("HTTP_FAILURE_NO_RETRY") from None
        finally:
            # Both owners close, even if response cleanup itself fails.
            try:
                if response is not None and response is not connection:
                    response.close()
            finally:
                connection.close()

    def _parse(self, body, snapshot, estimated_cost):
        try:
            envelope = _strict_json(body.decode("utf-8"))
            _validate_envelope(envelope, self.model)
            outputs = envelope["output"]
            o._check(type(outputs) is list and 1 <= len(outputs) <= 2, "OUTPUT_SCHEMA_MISMATCH")
            if len(outputs) == 2:
                _validate_reasoning(outputs[0])
            message = outputs[-1]
            o._check(type(message) is dict and
                     {"id", "type", "role", "status", "content"} <= set(message) <=
                     {"id", "type", "role", "status", "content", "phase"} and
                     type(message["id"]) is str and bool(message["id"]) and
                     message["type"] == "message" and message["role"] == "assistant" and
                     message["status"] == "completed" and
                     message.get("phase") in (None, "final_answer"), "OUTPUT_SCHEMA_MISMATCH")
            content = message["content"]
            o._check(type(content) is list and len(content) == 1, "OUTPUT_SCHEMA_MISMATCH")
            item = content[0]
            o._check(type(item) is dict and set(item) == {"type", "text", "annotations", "logprobs"}
                     and item["type"] == "output_text" and item["annotations"] == []
                     and type(item["annotations"]) is list, "OUTPUT_SCHEMA_MISMATCH")
            _validate_logprobs(item["logprobs"])
            text = item["text"]
            o._check(type(text) is str and len(text.encode("utf-8")) <= self.budget.max_report_bytes,
                     "REPORT_SIZE_LIMIT")
            report = f.validate_report(_strict_json(text), snapshot)
            usage = envelope["usage"]
            o._check(type(usage) is dict and set(usage) <= {"input_tokens", "output_tokens", "total_tokens",
                     "input_tokens_details", "output_tokens_details"}, "INVALID_USAGE")
            for key, cap in (("input_tokens", self.budget.max_input_tokens),
                             ("output_tokens", self.budget.max_output_tokens),
                             ("total_tokens", self.budget.max_input_tokens + self.budget.max_output_tokens)):
                o._check(type(usage.get(key)) is int and 0 <= usage[key] <= cap, "USAGE_BUDGET_EXCEEDED")
            o._check(usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"], "INVALID_USAGE")
            for key, details, total in (
                ("input_tokens_details", {"cached_tokens", "cache_write_tokens"}, "input_tokens"),
                ("output_tokens_details", {"reasoning_tokens"}, "output_tokens")):
                nested = usage.get(key)
                o._check(type(nested) is dict and set(nested) == details and
                         all(type(v) is int and 0 <= v <= usage[total] for v in nested.values()),
                         "INVALID_USAGE")
            return {"report": report, "estimated_max_cost_microusd": estimated_cost,
                    "reported_usage": {k: usage[k] for k in ("input_tokens", "output_tokens", "total_tokens")},
                    "actual_billed_cost_microusd": None}
        except o.ProviderFailure:
            raise
        except Exception:
            raise o.ProviderFailure("RESPONSE_SCHEMA_MISMATCH") from None

    def simulate(self, snapshot, *, approval, allowlist, review, exchange, pricing=None,
                 fake_credential=None, authorization=None):
        """Offline-only evaluation of shared HTTP/response logic. Never reads environment."""
        digest = None
        try:
            preview = self.preview(snapshot, approval=approval, allowlist=allowlist)
            digest = preview["snapshot_sha256"]
            self._reviewed(preview, review)
            o._check(type(exchange) is FakeHTTPExchange, "FAKE_HTTP_REQUIRED")
            estimate = self._estimate(preview, pricing)
            if authorization is not None:
                o._check(type(authorization) is FutureAuthorization and
                         authorization.separately_authorized is True and
                         authorization.review == review and
                         authorization.review._reservation is review._reservation,
                         "SEPARATE_FUTURE_AUTHORIZATION_REQUIRED")
            o._check(type(review._reservation) is _OfflineReservation, "INVALID_RESERVATION")
            review._reservation.reserve(self.budget, estimate)
            body = self._http(preview, fake_credential, fake=exchange)
            return self._parse(body, o._approved(snapshot, approval), estimate)
        except o.ProviderFailure as exc:
            return self._error(digest, exc.code)
        except Exception:
            return self._error(digest, "INVALID_INPUT_OR_RESPONSE")

    def analyze(self, snapshot, *, approval, allowlist, review=None, authorization=None):
        """Future live entry point. No real request can pass AI-R3A's missing evidence gates."""
        digest = None
        try:
            o._check(self.enabled, "REAL_TRANSPORT_DISABLED")
            preview = self.preview(snapshot, approval=approval, allowlist=allowlist)
            digest = preview["snapshot_sha256"]
            self._reviewed(preview, review)
            o._check(type(authorization) is FutureAuthorization and
                     authorization.separately_authorized is True and authorization.review == review and
                     authorization.review._reservation is review._reservation,
                     "SEPARATE_FUTURE_AUTHORIZATION_REQUIRED")
            o._check(API_COMPATIBILITY_STATUS == "VERIFIED", "API_COMPATIBILITY_UNVERIFIED")
            o._check(self.model in VERIFIED_MODEL_PRICING, "MODEL_PRICING_UNVERIFIED")
            # No verified pricing entries or real activation exist in this phase.
            # A future reviewed phase must replace this hard stop with verified pricing,
            # tokenizer/overhead accounting and a durable authorization-wide ledger.
            raise o.ProviderFailure("LIVE_PREFLIGHT_NOT_AUTHORIZED_IN_AI_R3A")
        except o.ProviderFailure as exc:
            return self._error(digest, exc.code)
        except Exception:
            return self._error(digest, "INVALID_INPUT_OR_RESPONSE")

    @staticmethod
    def _error(digest, code):
        return {"schema_version": "AI-R3A-ERROR-1", "snapshot_sha256": digest,
                "error_code": code, "ai_commentary": None}

    def _future_credential(self, authorization):
        """Locked even when intermediate evidence flags are stubbed offline."""
        raise o.ProviderFailure("CREDENTIAL_ACCESS_LOCKED")
