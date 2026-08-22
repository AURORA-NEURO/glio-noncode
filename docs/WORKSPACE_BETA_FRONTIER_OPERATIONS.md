# Workspace beta frontier operations

## Local checks

```powershell
python -m glio_noncode beta-frontier-data-audit
python -m glio_noncode beta-frontier-evaluate
python -m glio_noncode beta-frontier-quality-gate
python -m glio_noncode beta-frontier-runtime
python -m glio_noncode beta-frontier-invariants
```

The default fixture is deterministic and contains no person-level rows.

## Runtime outputs

The runtime report is the primary operational object. It includes stage order,
fixture and contract addresses, evaluation checks, descriptive metrics,
reconciliation items, quality checks, release bundle addresses, and final
acceptance.

## Observability

`observe_beta_frontier` emits events for run start, each runtime stage, each
projection result, each retained issue, and run completion. Each event carries
an address, operation when applicable, state, severity, and detail.

Recommended counters are total projection events, count by operation, count by
state, retained issue count, failed stage count, and release hold count.

## Review queue

The queue omits rows already marked ready and sorts the remainder by priority,
operation, and record ID. Blocking rows include foreign context, contradiction,
and invalid input. High-priority rows include partial and incomplete output.
Abstained rows remain in the queue with a normal priority.

## Artifact retention

The inventory contains fixture, evaluation, metrics, quality, runtime, bundle,
and release artifacts. Every item carries a media type, receipt, size hint, and
retention class. A missing kind blocks inventory acceptance.

## Source boundary

The package uses public HTTPS receipt URLs and aggregate-only payloads. Any
future external fixture loader must preserve the same boundary field, source
receipt shape, exact context, and control matrix.
