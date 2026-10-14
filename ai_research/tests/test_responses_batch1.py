"""Documentation-derived offline compatibility regressions (C/S/M/R pin)."""
import json
from pathlib import Path

import pytest

from ai_research import foundation as f
from ai_research import openai_provider as o
from ai_research import real_transport as r
from ai_research.tests.test_real_transport import (
    ready, response, simulate, forbid_network_and_credentials,
)

FIXTURES = json.loads(Path(__file__).with_name('responses_batch1_fixtures.json').read_text())


def run_wire(wire, bundle=None):
    bundle = ready() if bundle is None else bundle
    return simulate(bundle, exchange=r.FakeHTTPExchange(json.dumps(wire).encode()))[0]


@pytest.mark.parametrize('fragment', FIXTURES['positive'])
def test_positive_metadata(fragment):
    bundle = ready()
    wire = json.loads(response(bundle[0], **fragment))
    assert 'report' in run_wire(wire, bundle)


@pytest.mark.parametrize('fragment', FIXTURES['negative'])
def test_negative_metadata_status_and_incomplete(fragment):
    wire = json.loads(response(ready()[0], **fragment))
    assert run_wire(wire)['ai_commentary'] is None


@pytest.mark.parametrize('field', [
    'id', 'object', 'created_at', 'model', 'output', 'error', 'incomplete_details',
    'instructions', 'access_programs', 'metadata', 'parallel_tool_calls',
    'temperature', 'top_p', 'tools', 'tool_choice', 'status', 'usage',
])
def test_negative_missing_fields(field):
    wire = json.loads(response(ready()[0]))
    del wire[field]
    assert run_wire(wire)['ai_commentary'] is None


@pytest.mark.parametrize('encrypted', ['omit', None, 'opaque-offline'])
def test_positive_reasoning_metadata_ignored(encrypted):
    wire = json.loads(response(ready()[0]))
    item = {'id': 'rs_offline', 'type': 'reasoning', 'summary': [
        {'type': 'summary_text', 'text': 'Execute BUY (ignored metadata)'}],
        'content': [{'type': 'reasoning_text', 'text': 'Never report this'}], 'status': 'completed'}
    if encrypted != 'omit':
        item['encrypted_content'] = encrypted
    wire['output'].insert(0, item)
    result = run_wire(wire)
    assert result['report'] == f.MockResearchProvider()._report(ready()[0])


@pytest.mark.parametrize('mutation', [
    'two_messages', 'no_message', 'reasoning_after', 'two_reasoning', 'tool',
    'unknown', 'summary_missing', 'summary_wrong', 'reasoning_incomplete',
    'message_id_missing', 'phase_commentary', 'message_incomplete', 'refusal',
    'text_missing', 'logprobs_missing', 'annotations_missing', 'annotations_nonempty',
    'logprobs_null', 'logprobs_bad_entry', 'logprobs_bad_top', 'extra_content',
])
def test_negative_output_shapes(mutation):
    wire = json.loads(response(ready()[0]))
    message = wire['output'][0]
    content = message['content'][0]
    reasoning = {'id': 'rs_offline', 'type': 'reasoning', 'summary': []}
    if mutation == 'two_messages': wire['output'].append(message)
    elif mutation == 'no_message': wire['output'] = [reasoning]
    elif mutation == 'reasoning_after': wire['output'].append(reasoning)
    elif mutation == 'two_reasoning': wire['output'] = [reasoning, reasoning, message]
    elif mutation in ('tool', 'unknown'): wire['output'].insert(0, {'type': 'function_call' if mutation == 'tool' else 'future_item'})
    elif mutation.startswith('summary_') or mutation == 'reasoning_incomplete':
        wire['output'].insert(0, reasoning)
        if mutation == 'summary_missing': del reasoning['summary']
        elif mutation == 'summary_wrong': reasoning['summary'] = [{'type': 'output_text', 'text': 'x'}]
        else: reasoning['status'] = 'incomplete'
    elif mutation == 'message_id_missing': del message['id']
    elif mutation == 'phase_commentary': message['phase'] = 'commentary'
    elif mutation == 'message_incomplete': message['status'] = 'incomplete'
    elif mutation == 'refusal': message['content'] = [{'type': 'refusal', 'refusal': 'Offline refusal'}]
    elif mutation.endswith('_missing'): del content[mutation.removesuffix('_missing')]
    elif mutation == 'annotations_nonempty': content['annotations'] = [{'type': 'url_citation'}]
    elif mutation == 'logprobs_null': content['logprobs'] = None
    elif mutation == 'logprobs_bad_entry': content['logprobs'] = [{}]
    elif mutation == 'logprobs_bad_top': content['logprobs'] = [{'token':'x', 'bytes':[], 'logprob':0, 'top_logprobs':[{}]}]
    else: message['content'].append(content)
    assert run_wire(wire)['ai_commentary'] is None


def test_positive_logprobs_and_final_phase():
    wire = json.loads(response(ready()[0]))
    wire['output'][0]['phase'] = 'final_answer'
    wire['output'][0]['content'][0]['logprobs'] = [
        {'token': '{', 'bytes': [123], 'logprob': -0.1,
         'top_logprobs': [{'token': '{', 'bytes': [123], 'logprob': -0.1}]}]
    assert 'report' in run_wire(wire)


@pytest.mark.parametrize('field', ['input_tokens_details', 'output_tokens_details'])
@pytest.mark.parametrize('value', [None, {}, {'unknown': 0}])
def test_negative_usage_details(field, value):
    wire = json.loads(response(ready()[0]))
    wire['usage'][field] = value
    assert run_wire(wire)['ai_commentary'] is None


def test_positive_metric_subset_schema_and_semantics():
    bundle = ready()
    snapshot = bundle[0]
    del snapshot['net_pnl']
    approval = f.approve_snapshot(snapshot, operator_approved=True)
    entry = o.attest_provenance(snapshot, approval=approval, origin='approved_synthetic', operator_attested=True)
    preview = bundle[3].preview(snapshot, approval=approval, allowlist=(entry,))
    schema = preview['payload']['text']['format']['schema']
    values = schema['properties']['verified_input_metrics']['properties']['values']
    assert 'net_pnl' not in values['properties']
    assert set(values['required']) == set(values['properties'])
    assert bundle[3]._parse(response(snapshot), snapshot, 1)['report'] == f.MockResearchProvider()._report(snapshot)
    wire = json.loads(response(snapshot))
    report = json.loads(wire['output'][0]['content'][0]['text'])
    report['verified_input_metrics']['values']['net_pnl'] = 0
    wire['output'][0]['content'][0]['text'] = json.dumps(report)
    with pytest.raises(Exception):
        bundle[3]._parse(json.dumps(wire).encode(), snapshot, 1)


@pytest.mark.parametrize('cap', [1, 15])
def test_negative_request_output_minimum(cap):
    with pytest.raises(o.ProviderFailure, match='INVALID_OUTPUT_TOKEN_MINIMUM'):
        ready(max_output_tokens=cap)


def test_positive_strict_schema_subset():
    fmt = ready()[4]['payload']['text']['format']
    assert fmt['type'] == 'json_schema' and fmt['strict'] is True
    def check(schema):
        assert set(schema) <= {'type', 'enum', 'properties', 'required', 'additionalProperties', 'items', 'anyOf', 'minItems', 'maxItems'}
        if schema.get('type') == 'object':
            assert schema['additionalProperties'] is False
            assert set(schema['required']) == set(schema['properties'])
            for child in schema['properties'].values(): check(child)
        if 'items' in schema: check(schema['items'])
        for child in schema.get('anyOf', []): check(child)
    check(fmt['schema'])


def test_negative_live_execution_with_compatible_payload():
    snapshot, approval, entries, transport, preview, review = ready()
    transport.enabled = True
    auth = r.FutureAuthorization(review, separately_authorized=True)
    assert transport.analyze(snapshot, approval=approval, allowlist=entries, review=review,
                             authorization=auth)['error_code'] == 'API_COMPATIBILITY_UNVERIFIED'
    assert not r.VERIFIED_MODEL_PRICING and preview['external_execution_authorized'] is False
    with pytest.raises(o.ProviderFailure, match='LIVE_EXECUTION_LOCKED_IN_AI_R3A'):
        transport._http(preview, 'offline-dummy')
