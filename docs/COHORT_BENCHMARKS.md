# Cohort benchmark suite

The cohort benchmark suite is the aggregate-only evaluation boundary for
reproducible cohort comparisons. It accepts rows that describe a declared
cohort, source domain, context, score, uncertainty, binary outcome, and
optional feature and lineage keys. It never accepts direct subject, sample,
patient, contact, credential, model, agent, or language attribution fields.

The suite is descriptive research infrastructure. An accepted report is not
external validation, clinical performance, transportability, or a patient-level
conclusion.

## What it does

`run_cohort_benchmark` produces one content-addressed report with four linked
planes:

1. deterministic train/validation/test partitioning using group, source,
   context, record-hash, or temporal assignment;
2. leakage auditing for duplicate record identifiers, cross-split lineage,
   optional source/context overlap, split construction, and temporal order;
3. held-out calibration metrics including Brier score, log loss, expected and
   maximum calibration error, and a descriptive calibration slope/intercept;
4. held-out selective-risk coverage curves plus declared source-to-target
   transport comparisons for feature overlap, positive-rate shift, score shift,
   and Brier shift.

Every plane is explicit about `accepted`, `review`, `blocked`, and `abstained`.
Insufficient labels or scores abstain. Leakage errors block the complete suite.
Transport comparisons remain reviewable when shifts exceed policy; feature
overlap alone never implies transportability.

## Input contract

JSON can be a list of rows or an object containing `records`/`rows`. JSONL,
CSV, and TSV are also accepted. A minimal row is:

```json
{
  "record_id": "aggregate-001",
  "cohort_id": "cohort-a",
  "domain_id": "source",
  "source_id": "public-source-a",
  "context_key": "GRCh38|glioma|adult|stem_like|unknown|unknown",
  "label": 1,
  "score": 0.82,
  "uncertainty": 0.08,
  "group_id": "cohort-a-group-1",
  "lineage_key": "public-receipt-001",
  "feature_keys": ["feature-a", "feature-b"],
  "collected_at": "2026-01-01T00:00:00+00:00"
}
```

`label` and `score` may be absent for rows that are retained for split and
transport accounting but excluded from calibration and selective-risk metrics.
`context_key` is the six-dimension GLIO context lattice key.

## CLI

```powershell
python -m glio_noncode.cli cohort-benchmark aggregate.json `
  --dataset-id glio-cohort-run `
  --split-strategy temporal `
  --minimum-records-per-split 5 `
  --source-domain source `
  --target-domain target `
  --output cohort-benchmark.json

python -m glio_noncode.cli cohort-benchmark-schema --output cohort-benchmark-schema.json
python -m glio_noncode.cli cohort-benchmark-capabilities --output cohort-benchmark-capabilities.json
```

The command exits `0` only for an accepted complete suite and `2` for review,
blocked, or abstained output. The report is still written for non-accepted
states so review workflows retain the evidence.

## API

`GET /v1/cohort/benchmark/schema` and
`GET /v1/cohort/benchmark/capabilities` expose the contract without source
rows. `POST /v1/cohort/benchmark` accepts `{dataset_id, records, config}` and
returns the complete addressed report. Accepted reports return `200`; review,
blocked, and abstained reports return `422` with the report body.

The API is local-first and follows the same deployment authentication and
public-boundary controls as the rest of the service.

## Reproducibility and limits

Assignments hash the declared seed and grouping key, and temporal ordering is
stable on collection timestamp plus record identifier. Reports and component
receipts carry content addresses. Input is bounded to one million records,
100 calibration bins, 101 selective-risk points, and 1,000 transport domains.
