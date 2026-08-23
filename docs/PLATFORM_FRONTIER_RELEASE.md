# Platform frontier release procedure

## Preconditions

The current fixture must expose the exact platform context and public aggregate
boundary. It must contain five HTTPS source receipts, 16 records, four
positive rows, and twelve controls. The data audit must pass before evaluation.

```powershell
python -m glio_noncode platform-frontier-data-audit
```

## Functional evaluation

```powershell
python -m glio_noncode platform-frontier-evaluate
python -m glio_noncode platform-frontier-pipeline
```

The evaluation must contain 80 passing checks and exactly four accepted
positive executions. The pipeline must contain 24 ordered stages and a passing
depth report.

## Depth projections

```powershell
python -m glio_noncode platform-frontier-depth
python -m glio_noncode platform-frontier-thresholds
python -m glio_noncode platform-frontier-validation-matrix
python -m glio_noncode platform-frontier-handoff
python -m glio_noncode platform-frontier-access
```

Expected counts are 16 scenario cells, 16 threshold probes, 64 validation
cells, and 96 evidence cells. These counts are operational evidence of
coverage, not scientific performance metrics.

## Release gate

A release is accepted only when data audit, evaluation, quality, reconciliation,
integrity, replay, depth, claim boundary, compliance, artifact inventory,
performance, benchmark, package, and bundle checks pass. The release manifest
must retain fixture ID, version, context, boundary, evaluation address,
quality address, lineage address, and replay address.

Controls are part of the release evidence. They are not filtered out of the
review CSV or Markdown report. A consumer that sees only accepted positives is
not a complete consumer of this package.

## Reproducibility

Run manifests join input addresses, registry address, policy address, plan
address, reference build, command, and all 24 stage IDs. Idempotency locks
identify replay versus new admission. A changed fixture version creates an
explicit migration receipt. Prior release addresses remain available for
comparison and rollback planning.

## Scope

The package is public aggregate operational infrastructure. It does not expose
private row-level data, clinical fields, treatment suitability, diagnostic
labels, or biological measurements. Passing this release procedure proves the
declared platform-control behavior only.
