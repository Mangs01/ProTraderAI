# AI-R3A-R2 Batch 1: offline compatibility

Result: **PASS** for the scoped offline profile against
`AI-R3A-R1-RESPONSES-CONTRACT-1`. This is not live readiness or a complete
implementation of the official Responses union. No model is certified.

Request preview now emits `text.format` with `type=json_schema`, `strict=true`,
and a snapshot-specific AI-R1 report schema. Objects require all properties and
reject additions; nested arrays use documented anyOf where necessary. Metric
properties include only metrics present in the approved snapshot. Enums bind
scalar values, while unchanged AI-R1 validation still enforces metric types,
equality, provenance, exact prose and disclaimer. Preview rejects output caps
below the documented minimum 16; budget/accounting classes remain unchanged.

The parser requires documented non-optional envelope fields. It validates
created_at, metadata, access_programs, sampling metadata and supported optional
completed_at/background/token limits/conversation/previous_response_id/service_tier.
Output messages require IDs, annotations and logprobs. Empty and typed nonempty
logprobs are accepted. Annotations remain empty-only under the local safety policy.
One validated reasoning item may precede exactly one completed assistant message.
Reasoning content is ignored as report content and is never executed or exposed.
Its encrypted_content may be absent, null or a string; status may be absent or
completed. Refusals, tools, unknown items and ambiguous message arrays fail closed.
Usage details require cache_write_tokens, cached_tokens and reasoning_tokens.
Integral nonnegative bounded counts and arithmetic remain local safeguards.

Conservative local policy: success requires explicit completed status, null error
and incomplete_details, and non-null usage. Missing/nullable optional usage or
missing optional status are documented wire possibilities but cannot yield local
success. All other documented statuses and incomplete reasons reject without a
retry. No cross-field failure invariant is inferred from the docs. A supplied
message phase must be null or final_answer; commentary is not a final report.
Only empty tools and auto/none tool_choice are accepted. Instruction arrays,
background execution and other unimplemented documented envelope unions (including
text/reasoning configuration, moderation and cache configuration) reject under
the scoped profile. Unknown future fields also reject. Full union support is
outside this Batch 1 profile; no unsupported shape is silently accepted.

Synthetic fixtures derive from C/S/M/R retained snapshots, never paid API captures.
The R1 manifest, source bytes, original fixtures and validation evidence are
unchanged. Pin tests now assert fixed compatibility behavior and exempt exactly
the four authorized edited implementation/test files from original package-byte
checks; all other baseline hashes and source-integrity checks remain enforced.

Validation with plugin autoload disabled:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -B -m pytest -q -p no:cacheprovider --confcutdir=ai_research ai_research/tests ai_research/contracts/responses-v1/test_contract_pin.py
```

Combined result: **394 passed**. New Batch 1 regressions: **9 positive passed,
82 negative passed**. Existing/updated suite and pin cases: **303 passed**.
Frozen research and trading hash checks pass. Network and credential access are
denied by offline test guards; only FakeHTTPExchange and synthetic data are used.

Live execution remains blocked: API_COMPATIBILITY_STATUS=UNVERIFIED, empty
VERIFIED_MODEL_PRICING, enabled=false default, separate authorization requirement,
fake-only HTTP helper and final live-preflight hard stop are unchanged.

Deferred Batch 2 gaps: binding every effective resource limit into review,
response-owned HTTP reader lifecycle, hard deadlines, authorization-wide attempt
and cost accounting, model/pricing/tokenizer evidence. Existing pin regressions
continue to reproduce the review-binding and connection-close defects. No network,
credentials, trading changes, frozen evidence edits, commits or pushes occurred.

Files changed: openai_provider.py; real_transport.py;
tests/test_openai_provider.py; tests/test_real_transport.py;
contracts/responses-v1/test_contract_pin.py.
Files added: tests/test_responses_batch1.py;
tests/responses_batch1_fixtures.json; AI_R3A_R2_BATCH1.md.
