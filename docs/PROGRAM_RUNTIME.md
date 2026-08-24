# Sixteen-domain architecture program runtime

The program runtime is the repository-wide execution surface for the sixteen
architecture domains. It resolves one canonical public fixture and one
canonical runtime function for every domain, executes them, normalizes their
heterogeneous receipts, checks the public boundary, and preserves a compact
cross-domain report.

## Closed denominators

The runtime uses an explicit `D01` through `D16` domain denominator. Each
domain contributes ten checks and the program contributes twelve global checks,
for `16 * 10 + 12 = 172` checks. A clean run also records the stage, evaluation,
and artifact counts exposed by every domain runtime.

The checked-in closure is
`data/architecture-program-runtime-closure.json`. It contains the complete
twelve-stage runtime, the normalized domain receipts, all 172 checks, the
eighteen-check independent quality gate, the domain matrix, deterministic
replay evidence, and missing-reference controls.

## Runtime stages

`run_program_runtime()` closes these ordered stages:

1. `catalog-loaded`
2. `specifications-resolved`
3. `fixtures-resolved`
4. `domain-runtimes-executed`
5. `receipts-normalized`
6. `domain-acceptance-closed`
7. `public-boundary-closed`
8. `reconciliation-closed`
9. `report-closed`
10. `quality-closed`
11. `query-surface-closed`
12. `runtime-finalized`

Each stage is independently addressed and carries its predecessor address,
output address, state, ordinal, and execution detail.

## Public-boundary rule

The orchestrator projects only stable receipt fields. It scans the serialized
runtime projection for private subject keys before accepting a domain. D08 also
redacts subject-level keys from delegated family summaries at the architecture
boundary while preserving the internal research APIs that still require those
fields. A private-key finding is a review state, not a warning that can be
silently ignored.

## Python and CLI surface

The Python surface provides:

- `run_architecture_program()` for the normalized sixteen-domain report;
- `run_program_runtime()` for the complete twelve-stage runtime;
- `run_program_runtime_quality_gate()` for the independent eighteen-check gate;
- `architecture_program_domain_matrix()` and `query_architecture_program()` for
  dashboard and review filtering;
- `replay_architecture_program()` for deterministic report/runtime addresses;
- `run_program_runtime_failure_injections()` for missing fixture/runtime
  reference controls; and
- JSON, summary JSON, receipts CSV, checks CSV, domain CSV, and Markdown
  projections.

From the repository root:

```powershell
python -m glio_noncode architecture-program-report
python -m glio_noncode architecture-program-report --format markdown
python -m glio_noncode architecture-program-runtime
python -m glio_noncode architecture-program-summary
python -m glio_noncode architecture-program-receipts-csv
python -m glio_noncode architecture-program-checks-csv
python -m glio_noncode architecture-program-domains-csv
python -m glio_noncode architecture-program-query --domain-id D08
python -m glio_noncode architecture-program-replay
python -m glio_noncode architecture-program-failures
```

Commands return `0` for an accepted projection and `2` when a reference,
runtime, quality, or public-boundary control is held for review.

## Extension rules

To add or change a domain adapter:

1. update the ordered specification table and keep the `D01`–`D16` identity
   contract explicit;
2. ensure the fixture and runtime resolve through the bounded reference resolver;
3. preserve addressed stage, evaluation, artifact, and runtime outputs;
4. add a focused public-boundary and failure-control test;
5. regenerate the closure artifact and inspect the complete 172-check report;
6. run the replay and CLI tests; and
7. commit source, tests, documentation, and closure together.

The program report is repository execution evidence. It is not a biological,
clinical, or treatment claim.
