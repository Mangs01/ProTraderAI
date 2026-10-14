# AI-R3A: HTTP transport preparation, execution locked

Only this document, `real_transport.py` and `tests/test_real_transport.py` are
added. AI-R1/R2, both existing mock classes, and their entry points are unchanged.
There is no automatic import or activation from the CLI or trading code.

## Local documentation review

The local OpenAI Docs skill and its `references/official-docs.md` describe how to
retrieve official documentation. They do not contain a Responses API reference,
wire schema, model compatibility matrix, account entitlement or pricing table.
The repository has no official local Responses/pricing reference or installed
OpenAI SDK specification. No documentation was fetched and no probes were made.

| Item | Status |
| --- | --- |
| Candidate Responses request and response compatibility | UNVERIFIED |
| Configured model compatibility/account availability | UNVERIFIED |
| Official pricing | UNVERIFIED; production registry empty |
| Model tokenizer, framing and reasoning usage guarantees | UNVERIFIED |
| Hard end-to-end deadline across DNS and header parsing | UNVERIFIED |

The candidate request preserves AI-R2's canonical payload: model, two input
messages (fixed system instruction and JSON data), max_output_tokens, store=false.
No tools, function definitions, streaming, files or previous response references
are offered. No particular model is hardcoded or assumed available. The strict
candidate response envelope fails closed on unknown metadata; real API responses
may contain metadata this offline contract rejects. This is not a compatibility
claim. Official verification must precede changes to these accepted fields.

## Activation and credential boundary

`RealOpenAIHTTPTransport` defaults to enabled=false. Its future live entry point
requires an explicit model and RequestBudget, an approved snapshot hash, an
explicit provenance allowlist, exact payload review and a separate
FutureAuthorization bound to the snapshot, payload, model and request/cost limits.
The review record is operator attestation, not authentication or proof of origin.
No origin is inferred from filenames. No real grant is issued during this phase.

AI-R3A then stops at API_COMPATIBILITY_UNVERIFIED. The production pricing registry
is empty. A final LIVE_PREFLIGHT_NOT_AUTHORIZED_IN_AI_R3A gate blocks execution
even if evidence statuses are changed. The HTTP helper independently rejects any
call without the exact FakeHTTPExchange, preventing accidental direct-helper
network access. These locks must be explicitly reviewed in a separately
authorized future phase; setting enabled=true alone cannot activate anything.

The dedicated future credential variable is
`PROTRADERAI_OPENAI_RESEARCH_API_KEY`. The credential reader is guarded and is
not called by the blocked live entry point. There is no dotenv loader, key on
configuration objects, credential discovery, printing, or persistence. Offline
tests pass a literal dummy value directly to the fake HTTP path. Fake objects
discard Authorization headers. Exception messages and HTTP error bodies are
never included in results.

## HTTP and resilience preparation

The prepared HTTPS branch targets only api.openai.com:443 and /v1/responses,
using certificate validation, no redirects, no environment proxies and no SDK.
That branch is unreachable in AI-R3A. Shared HTTP logic is exercised against
FakeHTTPExchange with deterministic data and simulated clock/failures only.

The configured timeout defaults to five seconds, with a thirty-second hard cap.
The prepared connection gets a socket timeout; remaining monotonic deadline is
checked and reapplied before requests, headers and each bounded read1 operation.
The body limit defaults to 32 KiB, with a 64 KiB hard cap; declared lengths and
streamed bytes are both bounded, truncation is rejected, and JSON media type is
required. Deadline checks reject a slow body between bounded read1 operations.

Python's synchronous DNS resolution, TLS context creation and internal header
parsing are not demonstrated to obey a hard total deadline by these fake tests.
Do not describe this as a
verified whole-request wall-clock guarantee. A future reviewed transport must
address that boundary before live activation.

There are no retries: timeouts, HTTP 429, HTTP 5xx and all other failures stop.
The same transport instance permits one reserved attempt only, including failed
or ambiguous attempts. No silent repeat of a potentially billable request occurs.
No Retry-After sleep, fallback commentary, or token spending is performed.

## Budget and response contracts

A request budget is mandatory and max_requests must equal one. Input/output token
ceilings, cost limit, wire-body/report-size limits and timeout are validated.
Preview includes exact canonical request JSON and its SHA256, canonical input
fields, snapshot SHA256, approval/provenance status and byte-count token estimate.
Production estimated and actual billed costs remain null when pricing is unknown.

OfflineTestPricing is explicitly fake and accepted only by simulate(), never by
the live entry point. Offline preflight reserves the entire configured input
ceiling plus maximum output tokens at those fake rates, and rejects an exceeded
cost budget. This is a conservative test reservation, not a verified tokenizer
estimate, official price or billing guarantee. Production unknown pricing fails
closed; no rates are invented. Reported usage is separate from actual billed cost,
which remains null, and usage exceeding the configured caps is rejected.

Strict JSON parsing rejects duplicate keys, malformed UTF-8 and non-finite
constants. Incomplete/error responses, non-message/tool/refusal outputs, unexpected
fields, invalid usage and oversized output are rejected. Final commentary uses
AI-R1's unchanged exact-template report validator, including exact input metrics,
provenance labels and disclaimer. Failure returns a safe code and no commentary;
the original snapshot is unchanged. No returned code or commands are executed.

## Verification and remaining prerequisites

Run focused tests with `python -B -m pytest -q -p no:cacheprovider ai_research/tests`.
The existing AI-R1 preservation tests remain intact. No dependencies were added.

Before a first live test, a separately authorized phase must provide locally
verifiable official Responses/model/pricing documentation, confirm account model
access without assumptions, establish verified tokenizer/usage/cost bounds,
resolve the DNS/header deadline issue, review response metadata compatibility, implement
the authorization-wide ledger and live preflight wiring, and deliberately review
the execution locks. It must then receive distinct approval for the exact
synthetic snapshot, exact outbound payload and maximum billable budget, and
provision the dedicated environment variable at execution time. No API execution
or AI-R3B work is performed here.
