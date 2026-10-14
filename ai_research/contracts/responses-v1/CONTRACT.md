# Responses contract reference v1

Version: `AI-R3A-R1-RESPONSES-CONTRACT-1`. Retrieved **2026-10-14 UTC**.
This pin supports offline AI-R3A-R2 implementation. It does not change runtime
compatibility flags or grant execution authority. It is a scoped reference,
not a complete OpenAPI schema or a promise of model/account compatibility.

## Sources and integrity

| ID | Official source | What was verified |
| --- | --- | --- |
| C | [Create a model response](https://developers.openai.com/api/reference/resources/responses/methods/create) | REST body and returned Response definitions, item unions, usage and statuses |
| S | [Structured Outputs, Responses mode](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) | Strict format, refusals, incomplete output and supported schema subset |
| R | [Reasoning models](https://developers.openai.com/api/docs/guides/reasoning) | Reasoning items, token accounting and incomplete generations |
| M | [Migration to Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses) | Responses versus Chat Completions shapes and reasoning-before-message example |

`manifest.json` records URLs, retrieval timestamps and SHA256 of the **actual
retained bytes**. `sources/*.html` are downloaded originals; corresponding `.txt`
files are readable derivatives made by `extract_sources.py`, without executing
embedded scripts. No hashes of snippets, inaccessible pages or assumed server
versions are claimed. Sources contain navigation, multiple language examples and
some Chat Completions examples; use the Responses-specific sections. The web
reader failed to open C, but direct public HTTPS retrieval succeeded and its full
field definitions were inspected locally. No SDK/OpenAPI package was fetched.

## Documented request contract [C, S, M]

The endpoint is `POST https://api.openai.com/v1/responses` with a JSON body.
The local candidate sends model, two input messages, max_output_tokens and
store=false. For those fields and the needed format:

| Property | Reference type / optionality | Verified meaning |
| --- | --- | --- |
| `model` | optional ResponsesModel (string or documented IDs) | Selects model; no concrete model selected in this audit |
| `input` | optional string or array of input items | Plain string or typed input; easy messages accept string content and system/developer/user/assistant roles |
| easy message `role`, `content` | not labelled optional | Role and string or input-content array; `type: "message"` is optional |
| `max_output_tokens` | optional number or null, minimum 16 | Bounds generated tokens, including reasoning, visible output and non-visible formatting tokens [R] |
| `store` | optional boolean or null | Defaults true when omitted; false disables storage for later response retrieval, not a universal data-retention guarantee |
| `text` / `text.format` | optional objects | Default format is plain text; select JSON Schema explicitly |
| JSON Schema format `type`, `name`, `schema` | not labelled optional | `type="json_schema"`; name uses letters/digits/underscore/dash, at most 64 characters; schema is a JSON Schema object |
| format `description` | optional string | Description for the model |
| format `strict` | optional boolean or null | Set true for strict adherence within the supported subset |
| `stream`, `background` | optional boolean or null | Streaming/background are separate modes; this pin's implementation target is synchronous, non-streaming, no tools |
| `truncation` | optional auto/disabled/null | Disabled is default and excessive context fails with HTTP 400; auto may drop earlier conversation items |

The reference labels model and input optional. This does **not** establish that
an empty standalone request is valid: reusable prompts/conversations are other
documented request options. R2 should retain explicit model and input as local
requirements. Requiredness, nullability and local policy are distinct.

Documentation-only format example (not an outbound payload or report schema):

```json
{"text":{"format":{"type":"json_schema","name":"offline_example","strict":true,"schema":{"type":"object","properties":{"result":{"type":"string"}},"required":["result"],"additionalProperties":false}}}}
```

`response_format` is the Chat Completions shape, not the Responses format above.
Prompting for JSON or `json_object` mode alone does not enforce the report schema.
Generating the snapshot-specific AI-R1 report schema is future R2 work.

## Documented envelope and statuses [C]

Here “not optional” means the returned reference definition does not label the
field optional; it is not inferred from a single example. C is authoritative for
the complete union and all other properties; this table covers relevant fields.

| Returned property | Reference presence / type |
| --- | --- |
| `id` | not optional, string |
| `object` | not optional, literal `response` |
| `created_at` | not optional, number, Unix timestamp in seconds |
| `model` | not optional, string / documented model union |
| `output` | not optional, array of output items; length and order depend on generation |
| `error` | not optional, error object or null; object has code and message, optional misalignment details |
| `incomplete_details` | not optional, object or null; its `reason` is optional |
| `instructions` | not optional, string/input-item array or null |
| `access_programs` | not optional, object or null |
| `metadata` | not optional, metadata map or null |
| `parallel_tool_calls` | not optional, boolean |
| `temperature`, `top_p` | not optional, number or null |
| `tools`, `tool_choice` | not optional, documented tool array / choice union |
| `status` | optional enum: completed, failed, in_progress, cancelled, queued, incomplete |
| `usage` | optional usage object or null |
| `completed_at` | optional number or null; documented as present only for completed status |
| `background`, `max_output_tokens`, `max_tool_calls` | optional boolean/number or null respectively |
| `conversation`, `previous_response_id`, `reasoning`, `text`, `service_tier` | optional; see C for their object/string unions and nullability |

Additional documented properties include prompt/cache configuration, moderation,
truncation, safety identifiers and deprecated user fields. Do not infer that the
current eight-field envelope allowlist covers the official response.

Response status and item status are separate. R2 may require an explicitly
completed response for success even though C labels status optional. Missing,
unknown, failed, cancelled and incomplete statuses must never produce commentary
under that local policy. Queued/in_progress are not completed reports; polling
would require a separately designed budget and is outside this offline scope.

C lists incomplete reasons `max_output_tokens`, `max_messages`, `content_filter`
and `steered`; the latter describes WebSocket steering. R documents that token
or context exhaustion can yield incomplete **before visible text exists**, while
still consuming billable input/reasoning tokens. Refusal and incomplete output
are not schema-conforming report successes. Do not retry automatically merely
because a report is unavailable. Documentation does not settle every cross-field
status/error/incomplete-details invariant; R2 should define a conservative local
acceptance policy and label it as such.

## Documented output items and content [C, M, R]

The API returns a typed item array, not a one-message/one-content guarantee.
M demonstrates reasoning followed by an assistant message. SDK `output_text` is
a convenience accessor; a raw HTTP consumer must inspect typed output itself.

| Item / content | Required versus optional fields in C |
| --- | --- |
| `message` | id:string, type:message, role:assistant, status:in_progress/completed/incomplete, content:array; optional phase:commentary/final_answer/null |
| `output_text` content | type:output_text, text:string, annotations:array, logprobs:array are not labelled optional |
| `refusal` content | type:refusal, refusal:string, neither labelled optional |
| `reasoning` item | id:string, type:reasoning, summary:array are not labelled optional; content:array, encrypted_content:string/null, status:item-status are optional |
| summary entries | type:summary_text and text:string |
| reasoning content entries | type:reasoning_text and text:string |

Empty annotations/logprobs/summary arrays are legitimate documented shapes;
C and M include `logprobs: []` examples. Logprob entries contain token:string,
bytes:number array, logprob:number and top_logprobs:array. Annotation variants
include file citations, URL citations, container file citations and file paths.

C's wider union includes function/tool calls and outputs, search/computer/code
interpreter/image items, programs, compaction, shell/apply-patch and MCP items.
Their existence in the official contract grants no local authority to execute
them. R2's no-tools profile must explicitly reject unsupported item types.
Reasoning metadata is not the report, and must not become executable content.
C currently says encrypted reasoning is populated by default on POST; older
include-based guidance and the optional field definition do not justify requiring
it unconditionally. Preserve this ambiguity when designing synthetic fixtures.

## Documented usage [C, R]

When usage is present/non-null, C defines numeric input_tokens, output_tokens,
total_tokens plus input_tokens_details and output_tokens_details objects.
Input details now contain **cache_write_tokens and cached_tokens**; output
details contain reasoning_tokens. C uses “number” rather than a universally
enforced integer constraint; integral, finite, nonnegative counts and arithmetic
checks are proposed local safeguards, not invented API schema requirements.
Reasoning consumes output budget. Usage is not proof of the final billed charge.
The UTF-8 byte heuristic does not establish model tokenization or framing bounds.

## Supported strict schema subset [S]

- Types: string, number, integer, boolean, object, array; enums and nested anyOf.
- Root must be an object, not anyOf. Every object property must be required;
  optional semantics can use a union with null. Every object must set
  additionalProperties=false. Definitions, references and recursion are supported.
- Documented limits: 5,000 total object properties, 10 nesting levels, 120,000
  characters across names/enum/const strings, 1,000 total enum values. A string
  enum with more than 250 values has a 15,000-character aggregate limit.
- Supported constraints include string pattern and listed formats (date-time,
  time, date, duration, email, hostname, ipv4, ipv6, uuid); numeric multipleOf,
  minimum/maximum and exclusive bounds; array minItems/maxItems.
- Unsupported composition: allOf, not, dependentRequired, dependentSchemas,
  if/then/else. Fine-tuned models have additional exclusions for string, numeric,
  object and array constraints; consult S before using one. Strict unsupported
  schemas result in an API error.

These limits are this retrieval's values, not the older commonly cited 100-property
and five-level limits. The guide does not provide an exhaustive acceptance rule
for every unlisted JSON Schema keyword. Avoid relying on unlisted keywords or
model-specific support. Server schema conformance does not replace AI-R1's local
metric equality, provenance, exact-template and disclaimer validation.

## Unresolved assumptions and boundaries

No concrete model snapshot, price, tokenizer, framing allowance, account access,
retention entitlement, DNS/header hard deadline or authorization-wide ledger is
verified. Public general API docs cannot establish those operational guarantees.
Missing versus nullable status/usage, evolving metadata, phase selection,
encrypted reasoning and unlisted schema keywords require explicit local policy.
No fixture in this pin is a captured paid API response. All live locks and the
empty verified-pricing registry remain unchanged. See the audit handoff for R2
acceptance work and validation evidence.
