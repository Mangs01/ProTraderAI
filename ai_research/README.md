# AI-R1 offline foundation

This package has no integration with the trading entry point, research modules,
broker, environment variables, external providers, or files. Standard library only.
No network or credential configuration exists. No raw prompts are persisted.

Run the synthetic-only demonstration from the repository root:

```powershell
python -B -m ai_research --approve-synthetic
python -B -m pytest -q -p no:cacheprovider ai_research/tests
```

The switch approves the built-in demonstration only. There is no file, URL,
directory, stdin, or arbitrary JSON loading option. The Python API accepts an
explicitly supplied dictionary, validates it, and requires a fresh explicit
approval bound to its canonical SHA256. Review that the data is authorized and
contains no personal information before calling `approve_snapshot`.

Snapshot version: `AI-R1-SNAPSHOT-1`. Required fields: schema_version,
research_label, source_description, evaluation_period (start/end ISO dates),
evidence_limitations (up to eight entries). Optional metrics: number_of_trades,
gross_pnl, charges, net_pnl, maximum_drawdown, profit_factor. Missing metrics stay
missing. Booleans, nulls, non-finite numbers, unknown/nested fields, unsupported
text, paths, identifiers, credentials, sealed references and instructions fail
closed. Text is deliberately restricted to short alphabetic prose and limited
punctuation. Numeric-looking strings are never coerced.

Report version: `AI-R1-REPORT-1`. Facts are labelled FACT_FROM_INPUT;
interpretations AI_INTERPRETATION; hypotheses UNVERIFIED_HYPOTHESIS. "Verified"
means schema-valid and equal to the submitted metrics, not independently proven.
No advice, trading commands, strategy changes, or execution authority exists.
AI-R1 permits only the exact built-in mock provider and fixed output templates.

Approval is an operator attestation, not authentication or a data classification
oracle. Validation cannot detect secret information disguised as ordinary prose
or sealed metrics deliberately relabelled by an operator. This boundary depends
on honest explicit operator selection. Python private methods are conventions,
not a sandbox against hostile code already running in the same interpreter.

Future AI-R2 work requires separate authorization: provider policy, sanitized
payload review, adapter design, bounded timeout/retries and rate limits, validated
report output and mocked tests. Live adapters are absent. Frozen protocols and
trading logic must remain independent. AI-R1 introduces no dependencies.
