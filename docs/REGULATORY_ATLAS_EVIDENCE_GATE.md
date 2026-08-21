# Regulatory atlas evidence gate

This document defines the public aggregate evidence boundary for Domain 05
capabilities C01-C04:

- C01: cCRE track parsing;
- C02: brain cell-type cCRE profile queries;
- C03: adult glioma cCRE profile queries;
- C04: pediatric glioma cCRE profile queries.

The implementation is a research-use annotation boundary. It does not make a
patient-level assertion, expression call, activity call, causal claim, or
clinical decision.

## Public source boundary

The checked-in source receipts point to official public ENCODE and SCREEN pages:

| Source | Purpose | URI |
| --- | --- | --- |
| SCREEN overview | cCRE registry background and class vocabulary | <https://screen.encodeproject.org/index/about> |
| ENCODE cCRE release | GRCh38 released cCRE file receipt | <https://www.encodeproject.org/files/ENCFF272QXW/> |
| ENCODE pipeline | cCRE v2 pipeline receipt | <https://www.encodeproject.org/pipelines/ENCPL751FOQ/> |
| ENCODE annotations | annotation catalog boundary | <https://www.encodeproject.org/data/annotations/> |
| ENCODE portal | public source landing page | <https://www.encodeproject.org/> |

The fixture does not download or vendor the release archive. It contains
compact aggregate rows shaped to the public track contract so parsing,
context-gating, ambiguity, and quarantine behavior remain deterministic. The
source receipts identify scope and release; they do not claim that the
synthetic fixture rows occur verbatim on a source page.

## Fixture identity

The public descriptor is:

```json
{
  "fixture": "default_regulatory_atlas_fixture"
}
```

The stable fixture version is `2026.08.d05-c01-c04.v1`. Its context key is:

```text
GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown
```

The evidence boundary is `public_aggregate_non_patient`. The fixture retains
five public source receipts, sixteen records, four positive records, and
twelve controls. Every record has one or more declared source IDs and a
content address. No record payload contains subject, patient, or sample
identifiers.

## C01 parser contract

The parser accepts TSV/BED-shaped or JSON-shaped rows. BED coordinates are
converted from zero-based half-open intervals to one-based closed intervals.
The normalized cCRE record retains chromosome, coordinates, registry class,
profile, cell state, disease class, age group, strand, score, source version,
and raw hash. The parser returns a batch input hash and content address.

Malformed rows are quarantined with `invalid_ccre_row`. Invalid JSON produces
`invalid_ccre_json` and an abstained parse receipt. A score outside the allowed
range is not silently clipped. Parse receipts contain counts and hashes, never
the original input text.

## C02-C04 profile contracts

Each profile uses the same overlap and context gate:

1. select records from the requested profile;
2. require interval overlap;
3. require compatible genome build, disease, age, and cell state fields;
4. return one of `supported`, `absent`, `out_of_domain`, or `ambiguous`.

`supported` means one compatible cCRE record overlaps the requested interval.
`absent` means there is no compatible overlap. It is not a biological negative.
`out_of_domain` means overlapping rows exist but their context is incompatible.
`ambiguous` means more than one compatible row overlaps and no row is selected.

The positive profile records are:

| Capability | Positive state | Context dimension |
| --- | --- | --- |
| C02 brain cell type | supported | brain / astrocyte |
| C03 adult glioma | supported | adult diffuse glioma / stem-like |
| C04 pediatric glioma | supported | pediatric diffuse glioma / stem-like |

Controls exercise age mismatch, disease mismatch, absent intervals, and
duplicate compatible overlaps. These controls are part of the acceptance
boundary and are not discarded from the evaluation report.

## Execution and quality floors

The accepted fixture executes the following deterministic floors:

| Artifact | Floor |
| --- | ---: |
| Evaluation receipts | 16 |
| Evaluation checks | 120 |
| Independent scenarios | 13 |
| Replay checks | 13 |
| Policy rules | 12 |
| Quality checks | 25 |
| Lineage nodes | 157 |
| Lineage edges | 157 |
| Accepted-only bundle entries | 4 |
| Runtime stages | 9 |
| Release checks | 12 |

The evaluation has one receipt per fixture record and six record-level checks
per record in addition to three fixture checks. Receipt summaries preserve
state, counts, issue codes, context, profile, match IDs, and content hashes.
They omit `input_text`, `payload`, `records`, and other executable collections.

## Policy rules

The policy module checks:

- public aggregate scope;
- exact fixture and record context;
- source closure;
- no subject-level identifiers;
- positive support;
- visible controls;
- no source fetch during parsing;
- profile context gating;
- absence is not a biological negative;
- ambiguity does not select a record;
- no activity or causal inference field;
- sanitized receipts.

Any failed rule remains visible in the policy report. A release can publish only
when the evaluation, quality gate, replay, bundle, and all release checks pass.

## Reproduction commands

```powershell
python -m glio_noncode audit-regulatory-atlas-data examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-data.json
python -m glio_noncode evaluate-regulatory-atlas-fixture examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-fixture.json
python -m glio_noncode replay-regulatory-atlas-fixtures examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-replay.json
python -m glio_noncode regulatory-atlas-quality-gate examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-quality.json
python -m glio_noncode regulatory-atlas-metrics examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-metrics.json
python -m glio_noncode regulatory-atlas-lineage examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-lineage.json
python -m glio_noncode regulatory-atlas-reconciliation examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-reconciliation.json
python -m glio_noncode run-regulatory-atlas-pipeline examples/regulatory-atlas-pipeline-accepted.json --output regulatory-atlas-pipeline.json
python -m glio_noncode build-regulatory-atlas-release examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-release.json
```

The same command family is executed by the repository workflow. The JSON
descriptor is the only input required for the built-in public aggregate path.
