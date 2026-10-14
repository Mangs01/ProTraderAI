# AI-R3A-R1 audit handoff v1

Date: **2026-10-14**. Contract pin: [Responses v1](contracts/responses-v1/CONTRACT.md).
This phase recovers the audit findings and verifies public documentation only.
No AI-R3A-R2 fixes, production API calls, credentials, trading actions, commits
or live activation are authorized or performed.

## Evidence provenance

The prior **180 passed, 104 deselected, no files changed** result and eight gaps
are supplied by the operator in this task. No original R1 audit report or raw
test log was located among the pre-existing ai_research files. AI_R3A.md is the
earlier transport-preparation document and explicitly says its contract was
unverified. The previous count is retained as handoff evidence, not presented
as an independently recovered execution log or a full official specification.

Current implementation and all three existing test modules were inspected.
The complete existing offline suite independently passed **284 tests**; its
frozen research and trading hash checks also passed. The repository initially
had untracked ai_research and research metadata paths. Those outside paths were
not edited. The pin manifest records byte hashes of the pre-existing package
files; offline validation checks that they remain unchanged.

## Eight findings and R2 acceptance work

| # | Local finding and evidence | Official fact / unresolved boundary | Future offline acceptance work |
| --- | --- | --- | --- |
| 1 | real_transport._parse rejects created_at through its envelope allowlist | C defines numeric Unix created_at, not optional | Validate documented envelope metadata without weakening report validation |
| 2 | output_text allowlist excludes logprobs, including [] | C defines logprobs; C/M show empty arrays | Accept and type-check documented benign metadata; retain explicit annotation policy |
| 3 | output must contain exactly one message; reasoning before it fails | C allows typed arrays; M shows preceding reasoning | Validate reasoning separately and identify acceptable assistant report content; reject tools |
| 4 | provider.preview has no text.format | C/S specify json_schema with name/schema and strict=true | Produce a supported snapshot-specific report schema and preserve AI-R1 equality/provenance checks |
| 5 | id is not validated; omitted error/incomplete_details are treated as null; many official fields rejected | C distinguishes optional, required and nullable; status/usage themselves are optional | Define local completed-only success policy, full relevant field validation, typed statuses, refusals, incomplete and failure fixtures |
| 6 | PayloadReview/_reviewed binds snapshot, payload, model, request count and cost, but not all RequestBudget fields | Resource authorization binding is local policy, not an API guarantee | Bind input/output ceilings, wire/report byte limits, deadline and every effective resource limit; require fresh review for changes |
| 7 | _http accesses connection.sock after getresponse and before every read; FakeHTTPExchange always supplies a socket | HTTP response may own a readable stream after the connection relinquishes its socket; no OpenAI-specific guarantee established | Model connection-close lifecycle and complete bounded reads/cleanup with end-to-end deadline tests; do not activate the unreachable branch |
| 8 | no model chosen; pricing registry empty; bytes used for token estimate; request attempts are instance-local; hard DNS/header deadline unproven | R confirms reasoning output consumes token budget and can be billable without visible text | Keep model/pricing unresolved; design conservative token/framing bounds, hard deadline handling and authorization-wide accounting for failed/ambiguous attempts |

C/S/R/M are the official URLs in the linked contract and manifest. Findings 1–6
and 8 follow direct source inspection; new synthetic offline tests reproduce the
specific parser/binding defects. Finding 7 is reproduced with a modeled
response-owned reader and connection.sock=None, not a real HTTP exchange. No
OpenAI documentation is cited as a Python transport lifecycle specification.

Two additional current-documentation mismatches belong within findings 5/8:
C includes input_tokens_details.cache_write_tokens (the parser permits only
cached_tokens), and request max_output_tokens has minimum 16 (local budget/config
validation permits smaller positive values). These are documented mismatches,
not implemented fixes. Current examples are not substitutes for a complete
wire envelope; existing fake envelopes omit some documented fields.

## Decisions and unresolved assumptions

The pin is sufficient to begin **offline R2 implementation: READY**. It supports
request format, relevant response metadata, item types, refusals, incomplete
responses, statuses, usage and strict-schema constraints. R2 must distinguish
the general documented contract from its intentionally narrower no-tools,
completed-only research profile. Exact message/phase multiplicity policy,
unknown future metadata policy and missing-versus-null handling need explicit
local decisions. Encrypted reasoning is optional in the type definition even
though C describes default population; do not invent an unconditional requirement.

No concrete model snapshot, model-specific schema compatibility, account access,
official pricing, tokenizer/framing bound, billing guarantee, hard total deadline
or durable authorization-wide ledger has been established. They remain blockers
to any future live execution assessment, not blockers to offline R2 fixes and
synthetic tests. No model ID in an example is selected or certified for this
project. No claim of live API readiness is made.

All runtime locks remain: API_COMPATIBILITY_STATUS=UNVERIFIED, empty production
pricing registry, enabled=false default, fake-only HTTP helper, independent
future authorization and final live-preflight hard stop. Documentation retrieval
does not promote any of these gates.

## Files and offline validation

New files only: this handoff; contracts/responses-v1/CONTRACT.md, manifest.json,
fixtures.json, extract_sources.py, build_pin.py, test_contract_pin.py and four
source HTML/text pairs. HTML bytes are retained and hashed; readable text is
deterministically derived and independently hashed. Synthetic fixtures are
labelled fragments, not paid API captures or complete official envelopes.

Run from the project root with plugin autoload disabled to keep validation local:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -B -m pytest -q -p no:cacheprovider --confcutdir=ai_research ai_research/tests ai_research/contracts/responses-v1/test_contract_pin.py
```

The pin checks source-byte integrity and reproducible text extraction, unchanged
package bytes/live locks, documented vocabulary and synthetic gap reproductions.
It does not validate a complete OpenAPI schema, server behavior, model access or
any paid endpoint. Do not rerun build_pin.py to bless changes; it refuses to
overwrite an existing pin. A later retrieval belongs in a new version.

Final validation results are recorded in contracts/responses-v1/validation.txt.
