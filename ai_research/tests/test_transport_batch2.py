"""Memory-only transport lifecycle, authorization and accounting regressions."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
import http.client
import io
import json
import os
import threading

import pytest

from ai_research import openai_provider as o
from ai_research import real_transport as r
from ai_research.tests.test_real_transport import (
    ready, response, simulate, forbid_network_and_credentials,
)


@pytest.mark.parametrize('connection_close', [False, True])
@pytest.mark.parametrize('chunked', [False, True])
@pytest.mark.parametrize('chunk_size', [1, 4096])
def test_reader_lifecycle_and_cleanup(connection_close, chunked, chunk_size):
    bundle = ready()
    exchange = r.FakeHTTPExchange(response(bundle[0]), connection_close=connection_close,
                                  chunked=chunked, chunk_size=chunk_size)
    result, exchange = simulate(bundle, exchange=exchange)
    assert 'report' in result
    assert exchange.closes == exchange.response_closes == 1
    assert all(0 < size <= 4096 for size in exchange.read_sizes)
    assert (exchange.sock is None) == connection_close


@pytest.mark.parametrize('phase', ['connect', 'request', 'header', 'body'])
@pytest.mark.parametrize('delay', [4.999, 5, 5.001])
def test_deadline_at_every_blocking_phase(phase, delay):
    bundle = ready()
    kwargs = {phase + '_delay': delay} if phase != 'body' else {'read_delays': (delay,)}
    exchange = r.FakeHTTPExchange(response(bundle[0]), **kwargs)
    result, exchange = simulate(bundle, exchange=exchange)
    if delay < 5:
        assert 'report' in result
    else:
        assert result['error_code'] == 'TIMEOUT'
    assert exchange.closes == 1
    assert all(0 < timeout <= 5 for timeout in exchange.timeout_values)
    if phase == 'connect' and delay >= 5:
        assert exchange.requests == 0
    if phase in ('connect', 'request', 'header') and delay >= 5:
        assert exchange.reads == 0


def test_cumulative_deadline_not_reset_per_operation():
    bundle = ready()
    exchange = r.FakeHTTPExchange(response(bundle[0]), connect_delay=1, request_delay=1,
                                  header_delay=1, read_delays=(2,))
    result, exchange = simulate(bundle, exchange=exchange)
    assert result['error_code'] == 'TIMEOUT'
    assert exchange.timeout_values == [5, 4, 3, 2]
    assert exchange.response_closes == exchange.closes == 1


@pytest.mark.parametrize('body_size', [8192, 8193])
@pytest.mark.parametrize('framing', ['length', 'eof', 'chunked'])
def test_wire_size_exact_and_one_over(body_size, framing):
    bundle = ready(max_response_bytes=8192)
    exchange = r.FakeHTTPExchange(b'x' * body_size,
        content_length='auto' if framing == 'length' else None, chunked=framing == 'chunked')
    if body_size == 8192:
        assert bundle[3]._http(bundle[4], 'offline-dummy', fake=exchange) == b'x' * 8192
    else:
        with pytest.raises(o.ProviderFailure, match='RESPONSE_SIZE_LIMIT'):
            bundle[3]._http(bundle[4], 'offline-dummy', fake=exchange)
    assert exchange.offset <= 8193
    assert exchange.closes == exchange.response_closes == 1
    assert all(0 < size <= 4096 for size in exchange.read_sizes)


@pytest.mark.parametrize('kind', ['length', 'chunked'])
def test_truncated_framing(kind):
    bundle = ready()
    exchange = r.FakeHTTPExchange(response(bundle[0]),
        content_length='9000' if kind == 'length' else None,
        chunked=kind == 'chunked', chunked_complete=False)
    result, exchange = simulate(bundle, exchange=exchange)
    assert result['error_code'] == 'INCOMPLETE_RESPONSE'
    assert exchange.closes == exchange.response_closes == 1


@pytest.mark.parametrize('complete', [False, True])
def test_stdlib_chunk_decoder_with_memory_only_socket(monkeypatch, complete):
    bundle = ready()
    body = response(bundle[0])
    stream = io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
                        b'Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n' +
                        hex(len(body))[2:].encode() + b'\r\n' + body + b'\r\n' +
                        (b'0\r\n\r\n' if complete else b''))
    class MemorySocket:
        def makefile(self, mode):
            return stream
    parsed = http.client.HTTPResponse(MemorySocket())
    parsed.begin()
    exchange = r.FakeHTTPExchange(connection_close=True)
    def getresponse(self):
        self.headers_received = True
        return parsed
    monkeypatch.setattr(r.FakeHTTPExchange, 'getresponse', getresponse)
    result, exchange = simulate(bundle, exchange=exchange)
    assert ('report' in result) == complete
    if not complete:
        assert result['error_code'] == 'INCOMPLETE_RESPONSE'
    assert parsed.isclosed() and stream.closed and exchange.closes == 1


def test_response_close_failure_still_closes_connection(monkeypatch):
    def broken(self):
        self.exchange.response_closes += 1
        raise OSError('synthetic cleanup failure')
    monkeypatch.setattr(r._FakeHTTPResponse, 'close', broken)
    result, exchange = simulate(ready())
    assert result['ai_commentary'] is None
    assert exchange.response_closes == exchange.closes == 1


@pytest.mark.parametrize('field', [field.name for field in fields(r.RequestBudget) if field.name != 'max_requests'])
def test_all_resource_changes_invalidate_review(field):
    bundle = ready()
    transport = bundle[3]
    old_value = getattr(transport.budget, field)
    transport.budget = replace(transport.budget, **{field: old_value + 1})
    result, exchange = simulate(bundle)
    assert result['error_code'] == 'PAYLOAD_HASH_MISMATCH'
    assert exchange.requests == 0


def test_request_count_cannot_be_expanded():
    with pytest.raises(o.ProviderFailure, match='ONE_REQUEST_ONLY'):
        replace(ready()[3].budget, max_requests=2)


def test_review_rejects_stale_budget_preview():
    bundle = ready()
    bundle[3].budget = replace(bundle[3].budget, timeout_seconds=6)
    with pytest.raises(o.ProviderFailure, match='PAYLOAD_HASH_MISMATCH'):
        bundle[3].review_payload(bundle[4], operator_reviewed=True)


def shared_attempt(bundle, transport, exchange, authorization):
    return transport.simulate(bundle[0], approval=bundle[1], allowlist=bundle[2],
        review=authorization.review, authorization=authorization, exchange=exchange,
        pricing=r.OfflineTestPricing(transport.model, 1, 1), fake_credential='offline-dummy')


@pytest.mark.parametrize('outcome', ['success', 'connect_timeout', 'read_timeout', 'headers',
                                    'malformed', 'incomplete', 'http_error', 'size'])
def test_shared_authorization_retains_reservations_across_instances(outcome):
    bundle = ready()
    auth = r.FutureAuthorization(bundle[5], separately_authorized=True)
    body = response(bundle[0])
    kwargs = {}
    if outcome in ('connect_timeout', 'read_timeout'): kwargs['failure'] = outcome
    if outcome == 'headers': kwargs['header_delay'] = 6
    if outcome == 'malformed': body = b'{}'
    if outcome == 'incomplete': body = response(bundle[0], status='incomplete')
    if outcome == 'http_error': kwargs['status'] = 429
    if outcome == 'size': body = b'x' * 40000
    first = shared_attempt(bundle, bundle[3], r.FakeHTTPExchange(body, **kwargs), auth)
    assert ('report' in first) == (outcome == 'success')
    ledger = auth.review._reservation
    assert (ledger.requests, ledger.tokens, ledger.cost_microusd) == (1, 14048, 14048)
    second_transport = r.RealOpenAIHTTPTransport(model=bundle[3].model, budget=bundle[3].budget)
    second_exchange = r.FakeHTTPExchange(response(bundle[0]))
    second = shared_attempt(bundle, second_transport, second_exchange, auth)
    assert second['error_code'] == 'REQUEST_BUDGET_EXHAUSTED'
    assert second_exchange.requests == second_exchange.closes == 0
    assert (ledger.requests, ledger.tokens, ledger.cost_microusd) == (1, 14048, 14048)


def test_concurrent_reservation_is_atomic():
    bundle = ready()
    auth = r.FutureAuthorization(bundle[5], separately_authorized=True)
    start = threading.Barrier(2)
    exchanges = [r.FakeHTTPExchange(response(bundle[0])) for _ in range(2)]
    def attempt(index):
        transport = r.RealOpenAIHTTPTransport(model=bundle[3].model, budget=bundle[3].budget)
        start.wait(timeout=5)
        return shared_attempt(bundle, transport, exchanges[index], auth)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum('report' in result for result in results) == 1
    assert sum(exchange.requests for exchange in exchanges) == 1
    assert auth.review._reservation.requests == 1


def test_equal_new_review_cannot_reset_shared_authorization():
    bundle = ready()
    auth = r.FutureAuthorization(bundle[5], separately_authorized=True)
    simulate(bundle)
    new_review = bundle[3].review_payload(bundle[4], operator_reviewed=True)
    assert new_review == auth.review
    exchange = r.FakeHTTPExchange(response(bundle[0]))
    result = bundle[3].simulate(bundle[0], approval=bundle[1], allowlist=bundle[2],
        review=new_review, authorization=auth, exchange=exchange,
        pricing=r.OfflineTestPricing(bundle[3].model, 1, 1), fake_credential='offline-dummy')
    assert result['error_code'] == 'SEPARATE_FUTURE_AUTHORIZATION_REQUIRED'
    assert exchange.requests == 0
    assert replace(auth.review)._reservation is auth.review._reservation


@pytest.mark.parametrize('one_over', [False, True])
def test_cost_reservation_boundary(one_over):
    bundle = ready(max_cost_microusd=14048 - int(one_over))
    result, exchange = simulate(bundle)
    assert ('report' in result) != one_over
    if one_over:
        assert result['error_code'] == 'COST_BUDGET_EXCEEDED' and exchange.requests == 0
        assert bundle[5]._reservation.requests == 0


@pytest.mark.parametrize('kind', ['request_bytes', 'input_tokens', 'report_bytes', 'output_tokens'])
@pytest.mark.parametrize('one_over', [False, True])
def test_resource_exact_and_one_over(kind, one_over):
    bundle = ready()
    transport = bundle[3]
    if kind in ('request_bytes', 'input_tokens'):
        field = 'max_request_bytes' if kind == 'request_bytes' else 'max_input_tokens'
        exact = len(bundle[4]['request_json'].encode())
        transport.budget = replace(transport.budget, **{field: exact - int(one_over)})
        if one_over:
            with pytest.raises(o.ProviderFailure):
                transport.preview(bundle[0], approval=bundle[1], allowlist=bundle[2])
        else:
            assert transport.preview(bundle[0], approval=bundle[1], allowlist=bundle[2])['estimated_input_size_bytes'] == exact
    else:
        wire = json.loads(response(bundle[0]))
        if kind == 'report_bytes':
            exact = len(wire['output'][0]['content'][0]['text'].encode())
            transport.budget = replace(transport.budget, max_report_bytes=exact - int(one_over))
        else:
            wire['usage']['output_tokens'] = transport.budget.max_output_tokens + int(one_over)
            wire['usage']['total_tokens'] = wire['usage']['input_tokens'] + wire['usage']['output_tokens']
        if one_over:
            with pytest.raises(o.ProviderFailure): transport._parse(json.dumps(wire).encode(), bundle[0], 1)
        else:
            assert 'report' in transport._parse(json.dumps(wire).encode(), bundle[0], 1)


@pytest.mark.parametrize('flags,expected', [
    (0, 'REAL_TRANSPORT_DISABLED'), (1, 'SEPARATE_FUTURE_AUTHORIZATION_REQUIRED'),
    (2, 'API_COMPATIBILITY_UNVERIFIED'), (3, 'MODEL_PRICING_UNVERIFIED'),
    (4, 'LIVE_PREFLIGHT_NOT_AUTHORIZED_IN_AI_R3A'),
])
def test_every_analyze_gate_cannot_access_credentials_or_http(monkeypatch, flags, expected):
    bundle = ready()
    transport = bundle[3]
    transport.enabled = flags >= 1
    auth = r.FutureAuthorization(bundle[5], separately_authorized=True) if flags >= 2 else None
    if flags >= 3: monkeypatch.setattr(r, 'API_COMPATIBILITY_STATUS', 'VERIFIED')
    if flags >= 4: monkeypatch.setattr(r, 'VERIFIED_MODEL_PRICING', {transport.model: object()})
    def denied(*args, **kwargs):
        pytest.fail('Credential or HTTP access attempted')
    monkeypatch.setattr(transport, '_http', denied)
    monkeypatch.setattr(os, 'getenv', denied)
    result = transport.analyze(bundle[0], approval=bundle[1], allowlist=bundle[2],
                               review=bundle[5], authorization=auth)
    assert result['error_code'] == expected and result['ai_commentary'] is None
    assert bundle[5]._reservation.requests == 0


def test_credential_helper_stays_locked_with_all_evidence_stubbed(monkeypatch):
    bundle = ready()
    bundle[3].enabled = True
    monkeypatch.setattr(r, 'API_COMPATIBILITY_STATUS', 'VERIFIED')
    monkeypatch.setattr(r, 'VERIFIED_MODEL_PRICING', {bundle[3].model: object()})
    # The imported autouse fixture guards public entry points; exercise the real helper.
    # Exercise the original helper, saved before the autouse fixture patches it.
    with pytest.raises(o.ProviderFailure, match='CREDENTIAL_ACCESS_LOCKED'):
        ORIGINAL_CREDENTIAL_HELPER(bundle[3], r.FutureAuthorization(bundle[5], True))


ORIGINAL_CREDENTIAL_HELPER = r.RealOpenAIHTTPTransport._future_credential


def test_preview_and_simulation_safe_with_intermediate_evidence_stubbed(monkeypatch):
    bundle = ready()
    transport = bundle[3]
    transport.enabled = True
    monkeypatch.setattr(r, 'API_COMPATIBILITY_STATUS', 'VERIFIED')
    monkeypatch.setattr(r, 'VERIFIED_MODEL_PRICING', {transport.model: object()})
    def denied(*args, **kwargs):
        pytest.fail('Environment lookup attempted')
    monkeypatch.setattr(os, 'getenv', denied)
    preview = transport.preview(bundle[0], approval=bundle[1], allowlist=bundle[2])
    assert preview['live_readiness'] == 'BLOCKED'
    assert preview['external_execution_authorized'] is False
    result, exchange = simulate(bundle)
    assert 'report' in result and exchange.requests == 1
    with pytest.raises(o.ProviderFailure, match='LIVE_EXECUTION_LOCKED_IN_AI_R3A'):
        transport._http(preview, 'offline-dummy')


@pytest.mark.parametrize('pricing', [None, {'model': 'offline-test-placeholder'},
                                    r.OfflineTestPricing('different-placeholder', 1, 1)])
def test_missing_or_unverified_pricing_cannot_reserve_or_send(pricing):
    bundle = ready()
    result, exchange = simulate(bundle, pricing=pricing)
    assert result['ai_commentary'] is None
    assert exchange.requests == 0 and bundle[5]._reservation.requests == 0


@pytest.mark.parametrize('one_over', [False, True])
def test_reported_input_usage_boundary(one_over):
    bundle = ready()
    wire = json.loads(response(bundle[0]))
    wire['usage']['input_tokens'] = bundle[3].budget.max_input_tokens + int(one_over)
    wire['usage']['total_tokens'] = wire['usage']['input_tokens'] + wire['usage']['output_tokens']
    if one_over:
        with pytest.raises(o.ProviderFailure, match='USAGE_BUDGET_EXCEEDED'):
            bundle[3]._parse(json.dumps(wire).encode(), bundle[0], 1)
    else:
        assert 'report' in bundle[3]._parse(json.dumps(wire).encode(), bundle[0], 1)


@pytest.mark.parametrize('bad_transfer', ['gzip', 'chunked_with_length'])
def test_unsupported_or_ambiguous_transfer_framing(monkeypatch, bad_transfer):
    original = r._FakeHTTPResponse.getheader
    def header(self, name, default=None):
        if name == 'Transfer-Encoding':
            return 'gzip' if bad_transfer == 'gzip' else 'chunked'
        return original(self, name, default)
    monkeypatch.setattr(r._FakeHTTPResponse, 'getheader', header)
    result, exchange = simulate(ready())
    assert result['error_code'] == 'INVALID_TRANSFER_ENCODING'
    assert exchange.reads == 0 and exchange.closes == exchange.response_closes == 1


@pytest.mark.parametrize('returned', [b'x' * 4097, 'not bytes'])
def test_reader_cannot_return_unbounded_or_nonbyte_data(monkeypatch, returned):
    monkeypatch.setattr(r._FakeHTTPResponse, 'read1', lambda self, size: returned)
    result, exchange = simulate(ready())
    assert result['error_code'] == 'INVALID_HTTP_READ'
    assert exchange.closes == exchange.response_closes == 1
