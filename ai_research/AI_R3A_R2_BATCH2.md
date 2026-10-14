# AI-R3A-R2 Batch 2: offline transport and authorization hardening

Result: **PASS for the authorized offline scope**. **Live readiness: BLOCKED**.
Hard wall-clock network deadlines and durable cross-process accounting remain
unproven. Their absence cannot enable live execution.

## Changes

`real_transport.py` now binds the complete RequestBudget to PayloadReview,
alongside the existing model, snapshot and canonical request hashes. Preview
shows every budget field. The new max_request_bytes setting replaces the implicit
16384-byte provider default with an explicit, reviewed limit (same default).
Request, response and report bytes, input/output token ceilings, request count,
cost ceiling and total timeout are all bound. Any valid resource-setting change
invalidates the previous review; request counts above one remain prohibited.
Reviewing a stale budget preview also fails. Enabled only controls the already
blocked entry point; toggling it grants no execution authority.

HTTP handling captures the I/O timeout handle before getresponse and reads from
the response-owned reader, without accessing connection.sock after headers.
Response and connection owners close independently, including when response
cleanup fails. The unreachable HTTPS connection factory was removed; the helper
still requires the exact FakeHTTPExchange type. Reads request at most 4096 bytes
and at most remaining budget plus one overflow byte. Oversized or non-byte reader
returns reject. Content-Length truncation and incomplete chunk framing reject;
unsupported transfer coding and simultaneous chunked/Content-Length reject.
No retries occur. Unknown-length EOF can be transport-complete without proving
application completeness: unchanged Batch 1 JSON/report validation still applies.

FakeHTTPExchange models a response-owned reader, connection-close or persistent
connections, decoded chunked bodies, incomplete chunks, short reads and delays
in connection setup, request sending, headers and body reads. One absolute fake
deadline is used throughout; remaining time is checked before and after blocking
phases and supplied to the retained I/O timeout handle. Reaching the deadline
exactly fails closed.

An atomic process-local reservation belongs to the operator-reviewed payload.
FutureAuthorization shares that review and reservation across transport instances.
Simulation can explicitly take that authorization; the legacy offline signature
also uses the review's shared reservation. Reconstructing a transport does not
reset it. Copies made with dataclasses.replace retain the reservation. A new,
equal review with a fresh reservation cannot be substituted into an existing
authorization. Reserving consumes one request, the full input-plus-output token
ceilings and the maximum cost calculated from explicitly fake rates. Success,
timeout, incomplete output, parse failure and other uncertain outcomes retain
that reservation with no refund. Concurrent attempts sharing it permit only one
request. Missing pricing or invalid authorization fails before reservation/send.
A fresh affirmative payload review creates a new offline reservation scope;
it is not a continuation of an old authorization or a durable billing record.

The credential helper now unconditionally rejects access. Preview and simulation
remain memory-only even with enabled and intermediate evidence flags stubbed.
All analyze gates retain fail-closed behavior, including the unchanged final
`LIVE_PREFLIGHT_NOT_AUTHORIZED_IN_AI_R3A` gate. No credential lookup or HTTP call
occurs at that gate. Default disabled execution, UNVERIFIED compatibility and the
empty production pricing registry remain unchanged.

## Validation

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -B -m pytest -q -p no:cacheprovider --confcutdir=ai_research ai_research/tests ai_research/contracts/responses-v1/test_contract_pin.py
```

Final combined result: **471 passed, 0 failed, 0 skipped, 0 deselected**.
New Batch 2 module: **77 passed**. Existing Batch 1 and earlier tests plus pinned
checks: **394 passed**. The two former Batch 2 pin defect assertions now require
review invalidation and successful response-owned reads. Pinned manifest, source
HTML/text bytes, original fixtures and historical validation evidence were not
edited. Source integrity and unchanged-package checks pass; existing frozen
research and trading hash regressions pass.

Coverage includes persistent/closing connections, short and bounded reads,
chunked completion/truncation, declared and undeclared oversize bodies, cleanup
failures, cumulative deadlines at every phase, every budget-setting mutation,
shared and concurrent accounting, missing model/pricing evidence, exact and
one-unit-over cost/token/request/report/response limits, and all analyze evidence
gates. Additional stdlib HTTPResponse tests decode real chunk framing from
BytesIO through a memory-only socket facade; no socket is created or connected.
Network and credential helpers are denied by test guards.

Broader repository tests requiring external data or services were not run.
No live tests or operational measurements were attempted.

## Remaining operational requirements

- A socket timeout and checks around synchronous calls do not guarantee a hard
  wall-clock deadline. DNS resolution, TLS, repeated header/chunk framing reads,
  cleanup, parsing, scheduling and a stuck call can exceed such a deadline before
  control returns. Fake tests prove local deadline decisions, not universal
  stdlib interruption or a production response/socket ownership guarantee. A
  future design needs verified bounded cancellation/isolation and lifecycle
  evidence before live readiness. No such path is introduced here.
- The ledger is in-memory and bound to a shared review object. It is neither
  durable nor cross-process, cannot survive restart or serialization, and is not
  authenticated against hostile mutation inside the same Python process. A
  future live design needs durable atomic authorization identity, reservations,
  recovery and reconciliation for ambiguous attempts. Restarting must never be
  treated as permission to reset a live budget. Live remains blocked meanwhile.
- No concrete model snapshot, official price, verified tokenizer/framing bound,
  model/account availability or entitlement is established. The existing UTF-8
  estimate and OfflineTestPricing are offline assumptions, not operational
  evidence. Returned usage is not proof of billing; full reservations are not
  claimed to guarantee the real billed charge. Production evidence stays absent.
- The Responses contract remains the scoped Batch 1 no-tools profile, not the
  complete official union or a certification of server/model behavior.

## Exact files changed in Batch 2

Modified:

- `ai_research/real_transport.py`
- `ai_research/tests/test_real_transport.py` (allow the local threading import)
- `ai_research/contracts/responses-v1/test_contract_pin.py`

Added:

- `ai_research/tests/test_transport_batch2.py`
- `ai_research/AI_R3A_R2_BATCH2.md`

No files outside ai_research were modified. Trading source and frozen evidence
were only read by existing integrity checks. No credentials, .env, StageB/C data
or intraday data acquisition was used. No network access, paid calls, orders,
commits, pushes or Git-history changes occurred.
