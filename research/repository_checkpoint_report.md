# Repository Recovery Checkpoint

## Research state

Cycle: NSE_PUBLIC_STKEQ_24_CYCLE_001

Phase 26:
2bc4fbf72477f1c7d634a8851522c2086e0e7625e92c9abebea2611192878aaa

Phase 27:
9f3903d1e82f0e5d1cc3fd0d9f727ef66b1c367717ccc6b60addd74bcfa88815

## Git baseline

Branch: main

Starting HEAD: 254f7c87bb16d84e4009bae5643e4d510398123c

Starting message: Phase 11 complete

## Recovery reason

Codex unified execution could not initialize because of its workspace
deny-read ACL helper. Independent Windows PowerShell tests confirmed
that the repository itself is readable and writable.

No repository ACL reset, takeown, icacls repair, clean, reset, revert,
research execution, market-data acquisition, or SmartAPI operation was
performed.

## Repository policy

Completed source, tests, research code, protocols, governance,
manifests, reports, audits and reproducibility evidence are candidates
for controlled Git preservation.

Existing historical research datasets/evidence are not deleted or
silently ignored by this checkpoint.

Future Phase 28A bulk bhavcopies are local-only:

research/data/new_cycle_001/raw/bhavcopy/

Future large regenerated derived payloads are local-only:

research/data/new_cycle_001/derived/

Small metadata, hashes, provenance, schemas and acquisition reports
remain trackable.

.env remains ignored and must never be staged.

## Staging policy

No git add .
No git add -A.
No bulk staging without staged-diff inspection.

This preparation step performs no staging and no commit.

## Integrity recovery incident

During manual Phase 27H checkpoint preparation, a whitespace/newline
normalization command unintentionally changed byte representations of
several previously frozen research files.

For research/phase16_forensics.py:

- Historical expected SHA256:
  8e1fd099e98f61caaeed0a1710415f7b89574039c24a92a20c0dec3ebe712d8e
- Checkpoint SHA256:
  5aea877cb2c0a9bfd93bcba8a04aa6929b6f0fc370a41cc1bae4dcd8321d14e8
- The byte-exact historical representation could not be recovered from
  the Git object database, Git index, available backup, or inspected
  editor history.
- Current source logical lines match the available staged representation.
- Comparison with the pre-existing CPython 3.12 pyc found matching
  executable instructions and constants.
- Historical preservation hashes were not rewritten to conceal the
  mismatch.
- Validation result: 462 passed, 3 failed. All three failures are
  preservation SHA assertions for research/phase16_forensics.py.

Other accidentally normalized files with recorded historical SHA
mismatches were identified during recovery. Their historical hashes
remain unchanged; no byte-exact version was fabricated.

Controlled explicit-path staging has now been performed. No `git add .`
or `git add -A` was used.

Phase 28A remains unauthorized and has not started.

## Integrity recovery incident

During manual Phase 27H checkpoint preparation, a whitespace/newline
normalization command unintentionally changed byte representations of
several previously frozen research files.

For research/phase16_forensics.py:

- Historical expected SHA256:
  8e1fd099e98f61caaeed0a1710415f7b89574039c24a92a20c0dec3ebe712d8e
- Checkpoint SHA256:
  5aea877cb2c0a9bfd93bcba8a04aa6929b6f0fc370a41cc1bae4dcd8321d14e8
- The byte-exact historical representation could not be recovered from
  the Git object database, Git index, available backup, or inspected
  editor history.
- Current source logical lines match the available staged representation.
- Comparison with the pre-existing CPython 3.12 pyc found matching
  executable instructions and constants.
- Historical preservation hashes were not rewritten to conceal the
  mismatch.
- Validation result: 462 passed, 3 failed. All three failures are
  preservation SHA assertions for research/phase16_forensics.py.

Other accidentally normalized files with recorded historical SHA
mismatches were identified during recovery. Their historical hashes
remain unchanged; no byte-exact version was fabricated.

Controlled explicit-path staging has now been performed. No `git add .`
or `git add -A` was used.

Phase 28A remains unauthorized and has not started.
