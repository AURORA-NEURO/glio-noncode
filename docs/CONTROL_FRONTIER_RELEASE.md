# Control frontier release procedure

This procedure describes how to produce and inspect a Domain 16 C05-C12
release receipt. It is designed for a public aggregate runtime and a clean
replayable build.

## Preconditions

The working tree must contain the typed control frontier package, its focused
tests, and the CI commands. The fixture must report the exact context
`GRCh38|glioma|adult|stem_like|core|untreated`, the boundary
`public_aggregate_control_runtime`, nine source receipts, eight positive rows,
and twenty-four controls.

Run the data audit first:

```powershell
python -m glio_noncode control-frontier-data-audit --output /tmp/control-data.json
```

The audit must pass source count, record count, role count, context closure,
boundary, HTTPS source, and unique-source checks.

## Evaluation sequence

Run the functional evaluation and runtime:

```powershell
python -m glio_noncode control-frontier-evaluate --output /tmp/control-evaluation.json
python -m glio_noncode control-frontier-pipeline --output /tmp/control-runtime.json
```

The evaluation must contain 160 checks and accept the positive paths while
keeping all controls non-positive. The runtime must contain 24 ordered stages
and a passing depth report.

## Depth sequence

The depth projections are separate files so failures can be located without
opening the complete runtime receipt:

```powershell
python -m glio_noncode control-frontier-depth --output /tmp/control-depth.json
python -m glio_noncode control-frontier-thresholds --output /tmp/control-thresholds.json
python -m glio_noncode control-frontier-validation-matrix --output /tmp/control-validation.json
python -m glio_noncode control-frontier-handoff --output /tmp/control-handoff.json
python -m glio_noncode control-frontier-access --output /tmp/control-access.json
```

The expected depth counts are 32 threshold probes, 128 validation cells, and
192 evidence cells. The handoff and access manifests must retain the exact
fixture ID and public aggregate boundary.

## Review and release projections

Create review and report outputs from the same fixture:

```powershell
python -m glio_noncode control-frontier-review-csv --output /tmp/control-review.csv
python -m glio_noncode control-frontier-report --output /tmp/control-report.md
python -m glio_noncode control-frontier-data-dictionary --output /tmp/control-dictionary.json
```

The CSV is for bounded review and contains controls. The Markdown report is a
summary, not a replacement for JSON receipts. Any downstream consumer must
carry `fixture_id`, `context_key`, and `evidence_boundary` forward.

## Release gate

A release is acceptable only when all of the following are true:

- data audit accepted;
- evaluation accepted;
- every positive row accepted;
- every control row remains visible and non-positive;
- runtime stages are ordered and accepted;
- integrity and content-address checks pass;
- replay agrees with the original evaluation;
- policy, claim-boundary, and access audits pass;
- threshold, validation, and evidence matrices pass;
- failure injections are detected; and
- the report states the aggregate boundary.

If any requirement fails, retain the output as a failed rehearsal, route the
issue to the review queue, and do not publish it as an accepted release.

## CI expectations

Continuous integration runs the data audit, functional evaluation, runtime,
depth projections, focused unit tests, and CLI tests. The full repository test
suite remains the final regression pass. CLI output must be deterministic for
the default fixture so receipt diffs identify actual code or contract changes.

## Change control

Changes to operation names, context key, state vocabulary, issue codes, row
counts, or serialized fields require a fixture version update and a migration
note. Changes to implementation internals that preserve receipts still require
focused tests and an updated content address in generated output. No release
step permits unreviewed expansion of source, network, mutation, or claim scope.
