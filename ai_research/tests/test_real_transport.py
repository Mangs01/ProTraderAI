"""AI-R3A offline HTTP, approval, schema and resource-boundary tests."""

import ast
import builtins
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
import subprocess
import urllib.request

import pytest

from ai_research import foundation as f
from ai_research.__main__ import synthetic_snapshot
from ai_research import openai_provider as o
from ai_research import real_transport as r


@pytest.fixture(autouse=True)
def forbid_network_and_credentials(monkeypatch):
    attempts = []
    def denied(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Real network or credential access forbidden")
    for name in ("connect", "connect_ex", "send", "sendall", "sendto"):
        monkeypatch.setattr(socket.socket, name, denied)
    for name in ("create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, denied)
    monkeypatch.setattr(urllib.request, "urlopen", denied)
    monkeypatch.setattr(r.http.client, "HTTPSConnection", denied)
    # Patch only the dedicated credential helper: pytest itself legitimately uses env.
    monkeypatch.setattr(r.RealOpenAIHTTPTransport, "_future_credential", denied)
    yield
    assert not attempts


def ready(**budget_changes):
    snapshot = synthetic_snapshot()
    approval = f.approve_snapshot(snapshot, operator_approved=True)
    entry = o.attest_provenance(snapshot, approval=approval, origin="approved_synthetic",
                               operator_attested=True)
    budget = r.RequestBudget(max_requests=1, max_cost_microusd=50000)
    budget = replace(budget, **budget_changes)
    transport = r.RealOpenAIHTTPTransport(model="offline-test-placeholder", budget=budget)
    preview = transport.preview(snapshot, approval=approval, allowlist=(entry,))
    review = transport.review_payload(preview, operator_reviewed=True)
    return snapshot, approval, (entry,), transport, preview, review


def response(snapshot, **changes):
    envelope = {
        "created_at": 1756315696, "instructions": None, "access_programs": None,
        "metadata": {}, "parallel_tool_calls": False, "temperature": None, "top_p": None,
        "tools": [], "tool_choice": "auto", "id": "offline-test", "object": "response", "status": "completed",
        "model": "offline-test-placeholder", "error": None, "incomplete_details": None,
        "output": [{"id": "msg_offline", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(f.MockResearchProvider()._report(snapshot)),
                                 "annotations": [], "logprobs": []}]}],
        "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200,
                  "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": 0}},
    }
    envelope.update(changes)
    return json.dumps(envelope).encode()


def simulate(bundle, *, exchange=None, pricing="default", credential="offline-dummy-not-a-key"):
    snapshot, approval, allowlist, transport, _, review = bundle
    exchange = r.FakeHTTPExchange(response(snapshot)) if exchange is None else exchange
    pricing = r.OfflineTestPricing(transport.model, 1, 1) if pricing == "default" else pricing
    result = transport.simulate(snapshot, approval=approval, allowlist=allowlist, review=review,
        exchange=exchange, pricing=pricing, fake_credential=credential)
    return result, exchange


def test_disabled_by_default_and_missing_authorization():
    s, a, entries, t, _, review = ready()
    assert t.analyze(s, approval=a, allowlist=entries)["error_code"] == "REAL_TRANSPORT_DISABLED"
    t.enabled = True
    assert t.analyze(s, approval=a, allowlist=entries, review=review)["error_code"] == "SEPARATE_FUTURE_AUTHORIZATION_REQUIRED"
    auth = r.FutureAuthorization(review, separately_authorized=True)
    assert t.analyze(s, approval=a, allowlist=entries, review=review, authorization=auth)["error_code"] == "API_COMPATIBILITY_UNVERIFIED"


def test_preview_exact_payload_no_tools_and_unverified_status():
    s, a, entries, t, preview, _ = ready()
    assert preview == t.preview(s, approval=a, allowlist=entries)
    assert preview["payload_sha256"] == r._hash(preview["request_json"])
    assert preview["snapshot_sha256"] == a.snapshot_sha256
    assert set(preview["payload"]) == {"model", "input", "max_output_tokens", "store", "text"}
    assert preview["payload"]["store"] is False
    assert preview["external_execution_authorized"] is False
    assert preview["api_compatibility_status"] == "UNVERIFIED"
    assert preview["pricing_status"] == "UNVERIFIED"
    assert preview["model_account_availability"] == "UNVERIFIED"
    assert preview["actual_billed_cost_microusd"] is None


def test_review_and_snapshot_mismatch():
    bundle = ready()
    s, a, entries, t, preview, review = bundle
    with pytest.raises(o.ProviderFailure):
        t.review_payload(preview)
    bundle = (*bundle[:5], replace(review, payload_sha256="0" * 64))
    result, exchange = simulate(bundle)
    assert result["error_code"] == "PAYLOAD_HASH_MISMATCH" and exchange.requests == 0
    s["net_pnl"] = 1.0
    result, exchange = simulate(bundle)
    assert result["error_code"] == "APPROVAL_MISMATCH" and exchange.requests == 0


def test_mutated_model_or_budget_requires_new_review():
    for field in ("model", "budget"):
        bundle = ready()
        t = bundle[3]
        if field == "model":
            t.model = "different-placeholder"
        else:
            t.budget = replace(t.budget, max_cost_microusd=40000)
        result, exchange = simulate(bundle)
        assert result["error_code"] == "PAYLOAD_HASH_MISMATCH" and exchange.requests == 0


def test_empty_allowlist_and_stage_references_rejected():
    bundle = ready()
    result, exchange = simulate((bundle[0], bundle[1], (), *bundle[3:]))
    assert result["error_code"] == "PROVENANCE_NOT_ALLOWLISTED" and exchange.requests == 0
    bundle[0]["source_description"] = "Stage C observations"
    result, exchange = simulate(bundle)
    assert result["ai_commentary"] is None and exchange.requests == 0


@pytest.mark.parametrize("credential", [None, "", "contains space", "value\n", 123])
def test_missing_or_invalid_fake_credentials(credential):
    result, exchange = simulate(ready(), credential=credential)
    assert result["error_code"] == "CREDENTIAL_REQUIRED_OR_INVALID" and exchange.requests == 0


def test_unknown_pricing_model_and_exceeded_budget():
    result, exchange = simulate(ready(), pricing=None)
    assert result["error_code"] == "UNKNOWN_PRICING" and exchange.requests == 0
    result, exchange = simulate(ready(), pricing=r.OfflineTestPricing("another-placeholder", 1, 1))
    assert result["error_code"] == "UNKNOWN_MODEL" and exchange.requests == 0
    result, exchange = simulate(ready(max_cost_microusd=1))
    assert result["error_code"] == "COST_BUDGET_EXCEEDED" and exchange.requests == 0


@pytest.mark.parametrize("changes", [{"max_requests": 2}, {"max_requests": True},
    {"max_cost_microusd": 0}, {"timeout_seconds": 0}, {"timeout_seconds": float("nan")},
    {"max_output_tokens": True}])
def test_invalid_budgets(changes):
    with pytest.raises(o.ProviderFailure):
        replace(r.RequestBudget(max_requests=1, max_cost_microusd=50000), **changes)


def test_explicit_model_and_budget_required():
    s, a, entries, _, _, _ = ready()
    for t in (r.RealOpenAIHTTPTransport(), r.RealOpenAIHTTPTransport(model="offline-test-placeholder")):
        with pytest.raises(o.ProviderFailure):
            t.preview(s, approval=a, allowlist=entries)


def test_valid_response_usage_and_estimated_cost_not_billing():
    bundle = ready()
    before = json.dumps(bundle[0], sort_keys=True)
    result, exchange = simulate(bundle)
    assert result["report"] == f.MockResearchProvider()._report(bundle[0])
    assert result["reported_usage"]["total_tokens"] == 200
    assert result["estimated_max_cost_microusd"] == 14048
    assert result["actual_billed_cost_microusd"] is None
    assert exchange.requests == 1 and exchange.closes == 1
    assert all(0 < value <= 5 for value in exchange.timeout_values)
    assert json.dumps(bundle[0], sort_keys=True) == before


@pytest.mark.parametrize("failure", ["connect_timeout", "read_timeout"])
def test_timeouts_never_retry(failure):
    result, exchange = simulate(ready(), exchange=r.FakeHTTPExchange(failure=failure))
    assert result["error_code"] == "TIMEOUT" and exchange.requests <= 1 and exchange.closes == 1


def test_deadline_reduces_each_socket_timeout_and_blocks_slow_body():
    bundle = ready()
    exchange = r.FakeHTTPExchange(response(bundle[0]) + b" " * 9000, read_delays=(2, 4))
    result, exchange = simulate(bundle, exchange=exchange)
    assert result["error_code"] == "TIMEOUT" and exchange.requests == 1
    assert 3 in exchange.timeout_values


@pytest.mark.parametrize("status,code", [(429, "HTTP_429_NO_RETRY"), (500, "HTTP_5XX_NO_RETRY"),
    (503, "HTTP_5XX_NO_RETRY"), (302, "HTTP_STATUS_REJECTED"), (401, "HTTP_STATUS_REJECTED")])
def test_http_errors_never_retry_or_follow_redirect(status, code):
    result, exchange = simulate(ready(), exchange=r.FakeHTTPExchange(b"redacted", status=status))
    assert result["error_code"] == code and exchange.requests == 1 and exchange.reads == 0


def test_same_review_cannot_trigger_second_potentially_billable_attempt():
    bundle = ready()
    first, _ = simulate(bundle, exchange=r.FakeHTTPExchange(status=429))
    second, exchange = simulate(bundle)
    assert first["error_code"] == "HTTP_429_NO_RETRY"
    assert second["error_code"] == "REQUEST_BUDGET_EXHAUSTED" and exchange.requests == 0


@pytest.mark.parametrize("length", ["auto", None])
def test_oversized_declared_and_streaming_responses(length):
    result, exchange = simulate(ready(), exchange=r.FakeHTTPExchange(b"x" * 40000, content_length=length))
    assert result["error_code"] == "RESPONSE_SIZE_LIMIT" and exchange.requests == 1


def test_truncated_response_and_wrong_media_type():
    result, _ = simulate(ready(), exchange=r.FakeHTTPExchange(b"{}", content_length="100"))
    assert result["error_code"] == "INCOMPLETE_RESPONSE"
    result, _ = simulate(ready(), exchange=r.FakeHTTPExchange(b"{}", content_type="text/html"))
    assert result["error_code"] == "INVALID_CONTENT_TYPE"


@pytest.mark.parametrize("body", [b"not json", b"null", b"[]", b'{"x":1,"x":2}',
                                  b'{"x":NaN}', b"\xff"])
def test_malformed_response(body):
    result, exchange = simulate(ready(), exchange=r.FakeHTTPExchange(body))
    assert result["ai_commentary"] is None and exchange.requests == 1


@pytest.mark.parametrize("changes", [
    {"status": "incomplete"}, {"model": "unconfigured-model"}, {"error": {"message": "redacted"}},
    {"tools": [{"type": "function"}]}, {"output": [{"type": "function_call"}]}, {"usage": {}},
    {"usage": {"input_tokens": 100000, "output_tokens": 1, "total_tokens": 100001}},
    {"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
               "input_tokens_details": {"cached_tokens": True}}},
    {"usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
               "output_tokens_details": {"unknown": 1}}},
])
def test_incomplete_or_schema_invalid_wire_response(changes):
    bundle = ready()
    result, _ = simulate(bundle, exchange=r.FakeHTTPExchange(response(bundle[0], **changes)))
    assert result["ai_commentary"] is None


@pytest.mark.parametrize("tamper", ["metric", "command", "extra", "label", "refusal"])
def test_invalid_report_rejected(tamper):
    bundle = ready()
    wire = json.loads(response(bundle[0]))
    item = wire["output"][0]["content"][0]
    report = json.loads(item["text"])
    if tamper == "metric":
        report["verified_input_metrics"]["values"]["net_pnl"] = 999
    elif tamper == "command":
        report["observations"][0]["text"] = "Execute a BUY order"
    elif tamper == "extra":
        report["tool_calls"] = []
    elif tamper == "label":
        report["observations"][0]["category"] = "FACT_FROM_INPUT"
    else:
        item["type"] = "refusal"
    item["text"] = json.dumps(report)
    result, _ = simulate(bundle, exchange=r.FakeHTTPExchange(json.dumps(wire).encode()))
    assert result["ai_commentary"] is None


def test_real_helper_also_locked_and_unknown_fake_rejected():
    bundle = ready()
    with pytest.raises(o.ProviderFailure):
        bundle[3]._http(bundle[4], "offline-dummy")
    with pytest.raises(o.ProviderFailure):
        bundle[3]._http(bundle[4], "offline-dummy", fake=object())


def test_failure_preserves_original_snapshot():
    bundle = ready()
    before = json.dumps(bundle[0], sort_keys=True)
    result, _ = simulate(bundle, exchange=r.FakeHTTPExchange(b"invalid JSON"))
    assert result["ai_commentary"] is None
    assert json.dumps(bundle[0], sort_keys=True) == before


def test_no_file_or_command_access_in_preview_and_fake_http(monkeypatch):
    bundle = ready()
    def denied(*args, **kwargs):
        raise AssertionError("File or command access forbidden")
    with monkeypatch.context() as guard:
        for owner, name in ((builtins, "open"), (builtins, "eval"), (builtins, "exec"),
                            (Path, "open"), (os, "scandir"), (os, "getenv"),
                            (os, "system"), (subprocess, "Popen")):
            guard.setattr(owner, name, denied)
        result, _ = simulate(bundle)
        assert "report" in result


def test_imports_isolated_and_baseline_frozen_checks_retained():
    source = Path(r.__file__).read_text(encoding="utf-8")
    allowed = {"dataclasses", "hashlib", "http.client", "json", "os", "ssl", "time", "types", "threading"}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            assert all(alias.name in allowed for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                assert all(alias.name in {"foundation", "openai_provider"} for alias in node.names)
            else:
                assert node.module in allowed
    assert r.VERIFIED_MODEL_PRICING == {}
    # Existing AI-R1 tests retain explicit 72 frozen and 31 trading hash checks.
    assert (Path(__file__).parent / "test_foundation.py").is_file()
