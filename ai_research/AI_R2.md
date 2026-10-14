# AI-R2: OpenAI adapter, offline only

AI-R1 source, tests, CLI and README are preserved byte-for-byte. The original
`ai_research.analyze` remains mock-only. Use the new opt-in dispatcher
`ai_research.openai_provider.analyze` for the adapter; its default is still Mock.
`OpenAIResearchProvider` implements the existing `ResearchProvider._report`
contract, with constructor-bound approval for direct interface calls.

No SDK, dependency, client, endpoint, credentials, environment access, file
loader or network switch is implemented. `offline_enabled` defaults to false
and can enable only the exact injected `MockOpenAITransport`. Unknown transports
and subclasses are rejected. In-process Python code is trusted; this is not an
OS sandbox against hostile monkeypatching or arbitrary operator code.

## Synthetic example

```python
from ai_research import approve_snapshot
from ai_research.__main__ import synthetic_snapshot
from ai_research.openai_provider import (
    OpenAIConfig, OpenAIResearchProvider, MockOpenAITransport, attest_provenance,
)

snapshot = synthetic_snapshot()
approval = approve_snapshot(snapshot, operator_approved=True)
entry = attest_provenance(snapshot, approval=approval,
    origin="approved_synthetic", operator_attested=True)
provider = OpenAIResearchProvider(
    config=OpenAIConfig(model="offline-test-placeholder"),
    approval=approval, allowlist=(entry,), transport=MockOpenAITransport())
preview = provider.preview(snapshot)  # does not send, even to the mock
assert preview["external_execution_authorized"] is False
assert provider.analyze(snapshot)["error_code"] == "PROVIDER_DISABLED"
```

The model string is a test placeholder, not a model availability claim. No model
is hardcoded in production defaults. An identifier, transport and explicit
cost-budget assumptions are required for enabled offline evaluation. No API key
is needed, inspected or accepted. Cost rates are operator assumptions, not
verified OpenAI prices.

## Boundary and preview

Both preview and evaluation require AI-R1 approval matching the canonical input
SHA256, plus a hash-specific allowlist entry. Only `approved_synthetic` and
`operator_reviewed_development` origins are accepted. The origin is an operator
attestation, not cryptographic proof of where data originated. No provenance is
inferred from labels or filenames. Operators must never attest sealed Stage B/C
data or private information as development data.

The preview contains provider, configured model, snapshot digest, canonical input
fields, UTF-8 size, byte-count token estimate, approval status, exact payload and
canonical `request_json`. The same JSON string is passed unchanged to the fake.
The candidate payload has `model`, `input`, `max_output_tokens` and `store=false`.
It contains fixed system instructions and JSON user data consisting of the
snapshot and expected report contract. No tools or function definitions exist.
This is an internal candidate contract; its live API compatibility is unverified.

AI-R1's existing strict report validator is unchanged. AI-R2 accepts only its
exact fixed templates, input metrics, provenance labels and disclaimer. Arbitrary
new commentary is rejected, even if superficially valid JSON. Duplicate JSON
keys, non-finite JSON constants, unknown fields, invented metrics, malformed
responses, code and trading commands fail closed. Failures return safe error
codes, the validated snapshot digest and `ai_commentary=null`; raw input remains
unchanged and no exception details are exposed. Nothing is written or logged.

## Bounded offline resilience

Defaults: one attempt, five-second timeout, twenty-second total time budget,
quarter-second exponential backoff, 16 KiB input/output limits, 12,000 input and
2,048 output tokens, 20,000 total reserved tokens, and 50,000 micro-USD budget.
Hard limits cap attempts at three, each timeout at thirty seconds, total time at
sixty seconds, and retry delay at two seconds. Oversized Retry-After fails closed.

Timeout and rate-limit failures alone may retry. Each attempt reserves the full
configured input/output token and cost ceilings, even on failure. Budgets apply
per analysis operation. The fake receives the timeout/output limits and reports
mock token usage, which is validated. Backoff is recorded as a deterministic
logical delay; there is no sleeping or live client. Byte-count token estimates
are not verified tokenizer measurements. Timeout ceilings are logical mock
reservations, not enforcement against a real blocking SDK. Real deadline and
token/cost accounting require a separately reviewed future transport.

## Verification and AI-R3 prerequisites

Run `python -B -m pytest -q -p no:cacheprovider ai_research/tests`. Existing AI-R1
tests explicitly verify frozen and trading file hashes. No dependencies added.

Before any AI-R3 external execution: obtain separate operator authorization;
verify official API request/schema compatibility, model access, tokenizer and
pricing; review actual transport and secret management; enforce real deadlines,
size/token/cost limits and retry delays; approve the exact preview and provenance;
and retain the complete separation from trading and sealed research. None of
those live capabilities is implemented or authorized in AI-R2.
