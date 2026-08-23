# D01 runbook

This runbook is for the public aggregate intake boundary. It is intentionally
offline-capable after source receipts and fixture material are available.

## Preflight

1. Confirm the repository is on the intended commit and the working tree has
   no unreviewed changes.
2. Confirm every source receipt uses HTTPS and has `public_aggregate` scope.
3. Confirm the exact context key is
   `GRCh38|glioma|adult|aggregate|public_reference|pre_treatment`.
4. Confirm the fixture has 16 operations and 64 cases.
5. Confirm the payload audit reports no private subject keys.

Commands:

```powershell
glio-noncode intake-architecture-fixture --output intake-architecture.json
glio-noncode intake-architecture-data-audit --input intake-architecture.json
glio-noncode intake-architecture-plan --input intake-architecture.json
```

## Execute

Run the runtime and save the addressed JSON receipt:

```powershell
glio-noncode intake-architecture-runtime --input intake-architecture.json --output intake-runtime.json
glio-noncode intake-architecture-quality --input intake-architecture.json --output intake-quality.json
glio-noncode intake-architecture-validation --input intake-architecture.json --output intake-validation.json
```

The runtime must report 20 stages, 64 evaluated cases, 48 review items, 64
ledger events, five artifacts, and an accepted release. The positive cases are
accepted; foreign, malformed, and duplicate controls remain held.

## Review procedure

Export the review queue:

```powershell
glio-noncode intake-architecture-review-csv --input intake-architecture.json --output intake-review.csv
```

Reviewers should resolve the source or identity issue outside the runtime,
record the decision in the appropriate governed system, and create a new
content-addressed fixture version. Do not edit a result into acceptance. A
foreign-context row must be re-contextualized or excluded by a new manifest.
A malformed row must be corrected at source. A duplicate row must retain both
source records until the reconciliation decision is explicit.

## Replay and failure rehearsal

```powershell
glio-noncode intake-architecture-replay --input intake-architecture.json
glio-noncode intake-architecture-failures
glio-noncode intake-architecture-invariants --input intake-architecture.json
```

Replay is accepted only when both evaluation addresses match. Failure probes
must observe `review` for each negative control and must preserve the expected
issue code. Invariants enforce 64 results, 48 held controls, contiguous ledger
cardinality, and positive/control separation.

## Release and rollback

Release is accepted only when all five offline artifacts are present, every
artifact is offline-capable, and the rollback version is non-empty. If the
quality gate fails, hold the release at review, retain the existing accepted
version, and use the stored rollback pointer. Never promote a failed runtime by
changing the output JSON.

## Boundary reminders

This runtime reports deterministic intake and identity control evidence. It
does not establish a specimen chain of custody, validate individual consent,
make a diagnostic claim, infer a mechanism, or authorize a clinical or
institutional action.
