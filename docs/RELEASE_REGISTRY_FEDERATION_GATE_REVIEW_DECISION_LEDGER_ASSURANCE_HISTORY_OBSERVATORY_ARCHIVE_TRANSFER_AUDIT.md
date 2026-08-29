# Assurance-history observatory archive-transfer audit

The archive-transfer audit is the operator-facing integrity report for a
complete or partial chunk receiver. It is deliberately separate from the
transfer manifest and from the nested observatory archive. The report is
derived from those objects and cannot promote an incomplete transfer.

## Audit states

| State | Meaning |
| --- | --- |
| `complete` | Every declared chunk is present, the nested ZIP reassembles, and all eight checks pass. |
| `incomplete` | The transfer manifest and available chunks are valid, but one or more chunks remain missing. |

An incomplete report is not a malformed transfer. It is useful while a
receiver is waiting for object-store or upload retries. It remains explicitly
non-complete until the assembler receives every chunk and the nested archive
verifier accepts the reassembled bytes.

## Checks

Every report contains exactly eight ordered checks:

| Check | Assertion |
| --- | --- |
| `transfer-address` | The transfer content address reproduces from its public projection. |
| `range-conservation` | Chunk indices, offsets, sizes, and total archive bytes conserve. |
| `public-boundary` | The transfer projection contains no forbidden attribution or private-path fields. |
| `manifest-address` | The canonical manifest address reproduces from its fields. |
| `chunk-receipts` | Every received chunk matches the declared size and hash. |
| `progress-conservation` | Received and missing index sets partition the declared chunk range. |
| `nested-archive` | Complete bytes reload as the declared archive address. |
| `assembly-complete` | No chunk remains missing and finalization is available. |

Each check has a bounded detail, an evidence address, and its own content
address. The report conserves check counts:

```text
check_count = passed_count + failed_count = 8
```

For a complete transfer, `nested-archive` and `assembly-complete` must pass.
For a partial transfer, they remain false with a detail that says verification
is deferred. The other checks can still detect a bad manifest, invalid range,
or tampered received chunk before the transfer is complete.

## Python use

```python
complete = audit_transfer_directory("review-output/transfer")
partial = audit_partial_transfer_directory("review-output/partial-transfer")
assert complete.state == "complete"
assert partial.state == "incomplete"
```

The complete-directory audit reloads the exact transfer and verifies the
nested archive. The partial-directory audit loads a full manifest with only
the received chunk files, validates every received receipt, and returns an
incomplete report without trying to construct an invalid ZIP. An in-memory
`TransferAssembler` can be audited during upload and emits the same progress
semantics.

Mapping rehydration is public-projection-only and validates every check
address, check order, count, state, and completion relationship. It does not
claim that the mapped report has access to the source bytes.

## CLI and API

The command is nested below the archive-transfer command:

```powershell
python -m glio_noncode <archive-transfer-command>-audit \
  --input review-output/transfer \
  --format summary

python -m glio_noncode <archive-transfer-command>-audit \
  --input review-output/partial-transfer \
  --partial \
  --format markdown
```

The HTTP route is:

```text
.../decision-ledger/assurance-history/observatory/archive/transfer/audit
```

It exposes `/`, `/schema`, `/check-schema`, and `/capabilities`. JSON and
Markdown are projections of the same report. The CLI and API return a valid
incomplete report with success status because the transfer is structurally
valid; downstream release logic must inspect `state`, `complete`, and failed
checks before accepting the handoff.

## Recovery loop

```text
load full transfer manifest
          |
          v
receive any subset of chunks
          |
          v
write partial transfer directory
          |
          v
audit incomplete state and missing indices
          |
          v
reload and add retried chunks idempotently
          |
          v
audit complete state
          |
          v
finalize and verify nested archive address
```

Identical duplicate chunks are accepted as idempotent retries. A different
byte sequence for an already received index is rejected, even when it has the
right length. A missing chunk cannot be replaced by a changed manifest entry.
The receiver repairs the transport copy from the original source and reruns
the loader.

## Negative controls

The audit rejects non-typed values, unknown fields, wrong check order,
duplicate check IDs, invalid pass-state types, changed check addresses,
tampered counts, state/completion disagreement, missing or extra partial
directory members, non-canonical manifests, conflicting duplicate chunks,
invalid chunk receipts, and incomplete finalization. A report containing a
local path or forbidden attribution key fails its public-boundary check.

The audit does not edit the transfer, write a replacement manifest, or infer
that incomplete data is safe. It is a read-oriented diagnostic and release
handoff surface.

The audit report itself is content addressed, so a copied report can be
compared without trusting its filename or delivery channel. Its check receipts
are stable for equal transfer state, while a new received chunk changes the
progress, completion, and report addresses in a visible sequence.

For release review, retain the audit beside the transfer manifest and the
nested archive address. Treat a failed check as a request to inspect the
transport source, not as permission to weaken the receiving policy.

The report is suitable for an offline review queue because its public evidence
is bounded and its state is explicit.

## Handoff interpretation

An audit with `state=complete` and `failed_count=0` confirms the transport
contract only. It does not certify the scientific, clinical, licensing, or
domain meaning of the nested records. An audit with `state=incomplete` is a
valid operational checkpoint and should be retained until the receiver either
resumes it or discards it under the local retention policy.

## Demonstration

The transfer demonstration can be followed by the audit command:

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_demo.py \
  --input review-output/observatory.zip \
  --destination review-output/transfer \
  --resource progress \
  --format json

python -m glio_noncode <archive-transfer-command>-audit \
  --input review-output/transfer \
  --format markdown
```

The current-format downloaded-data tests cover both the complete path and the
partial-write/resume path. They assert address reproducibility and the absence
of local paths, agent fields, language fields, and other attribution metadata
from public output.
