# Validation-release frontier operations

This document describes the D13 C13-C16 validation-release surface. It is a
local, deterministic research-planning boundary for four operations:

1. off-target risk estimation;
2. validation value-of-information planning;
3. experiment package construction; and
4. result-to-claim update ingestion.

The checked-in fixture is
`examples/validation-release-public-aggregate.json`. It contains public
portal receipts and synthetic aggregate planning measurements. It does not
contain participant rows, site-local raw data, clinical outcomes, or secret
material.

## C13 off-target risk

Each target declares an exact context, an on-target score, candidate
off-target scores, and candidate weights. The operation calculates maximum
burden, weighted burden, descriptive specificity, candidate count, and a risk
tier. A maximum at or above `0.60` blocks the target. A weighted burden at or
above `0.25` routes the target to review. Context mismatch is blocking and a
malformed score is rejected.

The positive fixture row contains a low weighted burden. Its controls isolate
high maximum burden, foreign context, and malformed score parsing. The output
does not call a target effective, safe, or suitable for a person.

## C14 validation value of information

Each experiment declares cost, information gain, risk reduction, and optional
prerequisites. The planner validates identity uniqueness, rejects missing
dependencies, detects cycles, and selects a dependency-safe set by transparent
value density under a numeric budget. Selected IDs, total cost, information,
risk reduction, and remaining budget are retained.

The positive row schedules a baseline, a functional follow-up, and a replicate
when the dependency and budget constraints permit. Controls isolate an
insufficient budget, a prerequisite cycle, and a foreign context. Value of
information is a planning heuristic, not a statistical guarantee or a claim
that an experiment will succeed.

## C15 experiment packages

Packages retain an identity, exact context, experiment IDs, control IDs,
protocol IDs, and one content address for each non-empty manifest file. The
operation rejects an empty experiment set, keeps cross-file identity collisions
in review, and blocks foreign context. It emits a manifest projection rather
than writing or executing a protocol.

The positive package has two experiment rows, two control rows, and one public
protocol receipt. The manifest is sufficient for downstream review and replay;
it is not an experimental authorization.

## C16 result-to-claim updates

Results may update only a known claim, under the exact context, with a
SHA-256-style evidence address. Unknown claims, missing evidence addresses,
and foreign contexts remain visible in review or blocked state. Updated IDs,
review IDs, result count, claim count, and issue codes are retained.

The positive row updates one declared hypothesis with a result receipt. The
controls isolate unknown claim identity, context mismatch, and missing evidence
address. A `supported` result state is a declared research record, not proof of
causality, efficacy, treatment response, or clinical validity.

## Execution architecture

The implementation is split into contracts, source receipts, operations,
schema, adapters, evaluation, metrics, lineage, reconciliation, policy,
quality, replay, release, artifacts, review, depth, evidence, failure,
recovery, compliance, exports, and runtime modules. The runtime emits 50
ordered stages. Each stage has a sequence, state, elapsed duration, output
address, detail, and stage address.

The evaluation emits five checks per row: state, issue coverage, role boundary,
content address, and safe output projection. The depth audit adds a 16-cell
scenario matrix, a 96-cell validation matrix, and a 96-cell evidence matrix.
The accepted runtime additionally requires replay determinism, source-linked
lineage, a quality gate, integrity, control coverage, operational actions,
failure injection, recovery, release checks, and bundle closure.

## Commands

```powershell
python -m glio_noncode validation-release-frontier-data-audit --output validation-release-data.json
python -m glio_noncode validation-release-frontier-evaluate --output validation-release-evaluation.json
python -m glio_noncode validation-release-frontier-quality --output validation-release-quality.json
python -m glio_noncode validation-release-frontier-pipeline --output validation-release-runtime.json
python -m glio_noncode validation-release-frontier-depth --output validation-release-depth.json
python -m glio_noncode validation-release-frontier-thresholds --output validation-release-thresholds.json
python -m glio_noncode validation-release-frontier-review-csv --output validation-release-review.csv
python -m glio_noncode validation-release-frontier-report --output validation-release-report.md
```

## Evidence boundary

This surface proves deterministic input handling, declared arithmetic,
dependency checks, content-addressed manifests, exact-context gating, and
review routing. It does not prove off-target absence, assay performance,
biological effect, causal mechanism, therapeutic benefit, prognosis, or
clinical safety. Those claims require external validation and institutional
governance.
