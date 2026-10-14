"""Offline evidence checks, not fixes or a replacement API response validator.

Batch 1 and Batch 2 offline regression expectations; source pin unchanged.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import urllib.request

import pytest

from ai_research import real_transport as r
from ai_research.tests import test_real_transport as helpers
from extract_sources import Text

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
FIXTURES = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def forbid_external_execution(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Offline pin validation forbids network and credentials")
    for name in ("connect", "connect_ex", "send", "sendall", "sendto"):
        monkeypatch.setattr(socket.socket, name, denied)
    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        monkeypatch.setattr(socket, name, denied)
    monkeypatch.setattr(urllib.request, "urlopen", denied)
    monkeypatch.setattr(r.http.client, "HTTPSConnection", denied)
    monkeypatch.setattr(r.RealOpenAIHTTPTransport, "_future_credential", denied)


@pytest.mark.parametrize("source", MANIFEST["sources"], ids=lambda s: s["source_id"])
def test_retained_source_integrity_and_readable_derivative(source):
    assert source["official_url"].startswith("https://developers.openai.com/")
    assert source["retrieval_date"] == "2026-10-14"
    for entry in source["files"]:
        path = ROOT / entry["path"]
        assert path.resolve().is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    parser = Text()
    parser.feed((ROOT / source["files"][0]["path"]).read_text(encoding="utf-8"))
    assert "\n".join(parser.parts) + "\n" == (
        ROOT / source["files"][1]["path"]).read_text(encoding="utf-8")


def test_unchanged_package_bytes_and_live_locks_preserved():
    # R1 baseline hashes remain immutable. Only explicitly authorized R2 files
    # are exempt; source pins and untouched package files still verify bytewise.
    for name, expected in MANIFEST["existing_ai_research_sha256"].items():
        if name not in {"openai_provider.py", "real_transport.py",
                        "tests/test_openai_provider.py", "tests/test_real_transport.py"}:
            assert hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() == expected
    assert r.API_COMPATIBILITY_STATUS == "UNVERIFIED"
    assert not r.VERIFIED_MODEL_PRICING
    bundle = helpers.ready()
    s, a, entries, transport, _, review = bundle
    assert transport.analyze(s, approval=a, allowlist=entries)["error_code"] == "REAL_TRANSPORT_DISABLED"
    transport.enabled = True
    authorization = r.FutureAuthorization(review, separately_authorized=True)
    assert transport.analyze(s, approval=a, allowlist=entries, review=review,
        authorization=authorization)["error_code"] == "API_COMPATIBILITY_UNVERIFIED"


def test_fixture_vocabulary_exists_in_retained_reference():
    doc = (ROOT / "sources/responses-create.txt").read_text(encoding="utf-8")
    for value in (*FIXTURES["response_statuses"], *FIXTURES["item_statuses"],
                  *FIXTURES["incomplete_reasons"]):
        assert '"' + value + '"' in doc
    assert FIXTURES["reference_version"] == MANIFEST["reference_version"]


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["id"])
def test_documented_fragments_are_accepted_offline(case):
    bundle = helpers.ready()
    envelope = json.loads(helpers.response(bundle[0]))
    if case["location"] == "envelope":
        envelope.update(case["fragment"])
    elif case["location"] == "output_text":
        envelope["output"][0]["content"][0].update(case["fragment"])
    elif case["location"] == "prepend_output":
        envelope["output"].insert(0, case["fragment"])
    elif case["location"] == "usage":
        envelope["usage"].update(case["fragment"])
    else:
        pytest.fail("Unknown fixture location")
    exchange = r.FakeHTTPExchange(json.dumps(envelope).encode())
    result, exchange = helpers.simulate(bundle, exchange=exchange)
    assert "report" in result
    assert exchange.requests == 1 and exchange.closes == 1


def test_request_uses_strict_structured_output_format():
    fmt = helpers.ready()[4]["payload"]["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True


@pytest.mark.parametrize("field", ["id", "error", "incomplete_details"])
def test_envelope_rejects_missing_documented_fields(field):
    bundle = helpers.ready()
    envelope = json.loads(helpers.response(bundle[0]))
    del envelope[field]
    result, _ = helpers.simulate(bundle,
        exchange=r.FakeHTTPExchange(json.dumps(envelope).encode()))
    assert result["ai_commentary"] is None


@pytest.mark.parametrize("changes", [
    {"max_input_tokens": 12001}, {"max_response_bytes": 32769},
    {"max_report_bytes": 16385}, {"timeout_seconds": 5.1},
])
def test_resource_limit_changes_invalidate_current_review(changes):
    bundle = helpers.ready()
    transport = bundle[3]
    old_preview, old_review = bundle[4:]
    transport.budget = replace(transport.budget, **changes)
    new_preview = transport.preview(bundle[0], approval=bundle[1], allowlist=bundle[2])
    assert old_preview["request_json"] == new_preview["request_json"]
    with pytest.raises(r.o.ProviderFailure):
        transport._reviewed(new_preview, old_review)
    result, _ = helpers.simulate(bundle)
    assert result["error_code"] == "PAYLOAD_HASH_MISMATCH"


def test_connection_close_lifecycle_assumption_with_response_owned_reader(monkeypatch):
    # Model connection.sock becoming None at getresponse while response.read1
    # remains usable (the response owns the closing connection's file reader).
    bundle = helpers.ready()
    exchange = r.FakeHTTPExchange(helpers.response(bundle[0]))
    exchange.headers_received = False

    def getresponse(self):
        self.headers_received = True
        return self

    monkeypatch.setattr(r.FakeHTTPExchange, "getresponse", getresponse)
    monkeypatch.setattr(r.FakeHTTPExchange, "sock", property(
        lambda self: None if self.headers_received else self))
    result, exchange = helpers.simulate(bundle, exchange=exchange)
    assert "report" in result
    assert exchange.requests == 1 and exchange.closes == 1 and exchange.reads > 0

