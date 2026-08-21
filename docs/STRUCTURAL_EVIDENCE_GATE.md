# Domain 02 structural evidence gate

This document describes the verified C01-C04 evidence boundary. It is an
implementation contract for reproducible structural observations, not a
clinical interpretation protocol and not a claim that a small fixture is a
complete public callset.

## Scope

The gate covers four operations that form one structural observation plane:

| Capability | Operation | Input boundary | Output boundary |
| --- | --- | --- | --- |
| GNC-D02-C01 | reconstruction | deferred symbolic, breakend, and phased records | typed events and addressable issues |
| GNC-D02-C02 | consensus | caller TSV/JSON observations | caller-preserving clusters and disagreement |
| GNC-D02-C03 | complex resolution | typed structural events | connected components, paths, and ambiguity |
| GNC-D02-C04 | copy-number harmonization | caller segments | atomic intervals and visible disagreement |

The implementation modules are intentionally separate from the evidence
surfaces. Existing adapter behavior remains usable through the low-level CLI;
the evidence gate adds source receipts, fixture identity, controls, replay,
contracts, quality reconciliation, and compact publication metadata.

## Public aggregate fixture

The checked-in fixture is
`examples/structural-public-aggregate.json`. It declares the exact context
key:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

All source receipts set `patient_level` to false. The payloads use aggregate
validation records and public identifiers needed to prove mechanics. They do
not include a participant identifier, a subject identifier, a donor identifier,
or direct contact data. A source receipt identifies the public source and
release version used to frame the fixture; it does not imply that the fixture
is an exhaustive download of that source.

The source boundary includes:

1. NCBI dbVar Clinical Structural Variants (`nstd102`) through the public
   Structural Variation Data Hub;
2. NCBI dbVar Curated Common Structural Variants (`nstd186`);
3. the public gnomAD Structural Variants v4 release description; and
4. an NCBI dbVar public placement summary used to exercise copy-number
   interval mechanics.

The URLs and declared versions live in the fixture so an evaluator can inspect
the source set without guessing which release was intended. Data scope is
explicitly public and aggregate. No network call is required for local replay.

## Fixture schema

The root object contains:

| Field | Type | Requirement |
| --- | --- | --- |
| `fixture_id` | string | stable identity for replay |
| `schema_version` | string | exactly `structural-evidence-v1` |
| `context_key` | string | six pipe-delimited context fields |
| `provenance` | string | aggregate provenance declaration |
| `patient_level` | boolean | must be false |
| `sources` | array | one or more public source receipts |
| `positives` | array | at least four executable records |
| `controls` | array | at least eight review controls |
| `notes` | array | human-readable scope and limitation notes |

Each source receipt contains `source_id`, `title`, `url`, `version`, `license`,
`data_scope`, `patient_level`, `retrieved_at`, and optional notes. URLs must
use an explicit web scheme. A source with `patient_level: true` is rejected at
construction time rather than merely producing a warning.

Each executable record contains `record_id`, `operation`,
`expected_state`, `expected_result_state`, `context_key`, `source_id`, and a
typed operation `payload`. Optional `required_issue_codes`, `expected_counts`,
and a description make the assertion explicit. Positive records default to
`accepted`; controls default to `review`, but the parsed value is still
validated and cannot be silently changed by the evaluator.

## C01 reconstruction

`StructuralReconstructor` receives `RawVariantRecord` values. The fixture
exercises three distinct paths in one positive record:

- a symbolic `<DEL>` with an integer `END` becomes a typed deletion with two
  breakends;
- reciprocal VCF breakends with `MATEID` metadata become one breakend-pair
  event, retaining both alleles and orientations; and
- two records sharing sample and `PS` metadata become an ordered haplotype
  path. The phased records are consumed by the haplotype path rather than
  being mislabeled as unsupported structural rows.

The following invariants are enforced:

- record IDs are unique before pairing;
- a breakend must carry `MATEID`;
- the mate record must be present;
- both records must reference each other;
- both ALT strings must satisfy the supported bracket grammar;
- symbolic records require an integer `END` not smaller than `POS`;
- unsupported symbolic types produce an explicit issue; and
- a phased group with one record remains a warning rather than a fabricated
  path.

The C01 controls cover missing mate metadata and non-reciprocal mate metadata.
Both return an error state with retained record IDs. No event is guessed from
an incomplete pair.

## C02 caller consensus

`SVConsensusImporter` parses TSV or JSON rows and normalizes chromosome,
interval, event type, support, caller version, source line, raw hash, and
event key. Support values may be expressed as a fraction or a percentage. A
row that cannot be parsed becomes an issue with a raw hash and source line;
valid neighboring rows remain available for review.

Rows cluster when their explicit event key agrees or when chromosome, event
type, and both breakpoints fall within the declared tolerance. A median start
and end are reported as a consensus view. They are not substituted for the
caller coordinates. The output retains:

- every normalized observation;
- caller IDs and versions;
- observation IDs and raw hashes;
- breakpoint disagreement in base pairs;
- support summary; and
- transformation provenance.

The positive record uses two callers within five base pairs and produces a
`supported` result. Controls cover a malformed coordinate and callers whose
breakpoints disagree beyond tolerance. The malformed input is `review` with a
stable issue code. The disagreement input is `review` with an `ambiguous`
result and no hidden error.

## C03 complex resolution

`ComplexRearrangementResolver` converts each event breakend into a normalized
`chromosome:position` node and computes connected components. A component can
contain more than one event identity. The resolver creates a path receipt that
lists event IDs and breakpoint nodes, but it does not select a biological
identity or supersede any source event.

The positive record contains two events sharing a breakpoint locus. The
operation is accepted because the graph was constructed without a technical
error, while its result state is `ambiguous`. This distinction is important:
an accepted computation is not the same as a resolved biological conclusion.

The controls cover an event with no explicit breakpoints and an invalid typed
event. The first returns `event_without_breakpoints` and no graph resolution.
The second fails at the typed event boundary with `validation_error`.

## C04 copy-number harmonization

`CopyNumberSegmentHarmonizer` sweeps every start and `end + 1` boundary from
all callers. Each atomic interval records the active caller set, source
segment IDs, median total copy number, spread, state, provenance, and content
address. Adjacent intervals merge only when chromosome, copy number, caller
set, and state are identical.

The positive record contains three input segments and produces two atomic
intervals. The first interval is supported; the second retains caller
disagreement as `ambiguous`. The operation is accepted because all source
segments are valid and the disagreement is represented, not because the
median is treated as a truth label.

Controls cover a malformed start coordinate and a negative copy number. Both
remain review-bound with a stable validation issue and no harmonized claim.

## State semantics

There are two state layers:

1. `StructuralFixtureState` describes whether the fixture assertion passed or
   remains under review.
2. `StructuralEvidenceState` describes the domain output, such as `supported`,
   `partial`, or `ambiguous`.

An ambiguous domain result can be part of an accepted fixture when the
ambiguity is the expected and preserved output. A malformed input cannot be
accepted merely because another operation in the same fixture passed.

The evaluator compares both layers. It checks expected state, expected result
state, required issue codes, declared counts, and a content address for every
record. Positive and control IDs are checked for disjointness.

## Quality gate

`evaluate_structural_quality_gate` reconciles seventeen checks:

1. public aggregate data audit;
2. complete positive and control execution;
3. fixture assertion floor;
4. replay identity and address stability;
5. independent scenario matrix;
6. positive operation floor;
7. review control floor;
8. operation coverage;
9. four registered contracts;
10. exact context agreement;
11. source receipt agreement;
12. repeated execution determinism;
13. unique positive identities;
14. unique control identities;
15. each operation has a positive executable record;
16. aggregate source scope; and
17. content-addressed operation receipts.

The current positive fixture produces 95 operation checks, 17 quality checks,
and 12 scenario results. The gate is accepted only when every check passes.
There is no coercion from review to accepted during rendering.

## Replay

The replay expectation binds fixture ID, exact context, sorted source IDs,
minimum check count, positive floor, and control floor. Replaying the same
fixture path twice is rejected as duplicate fixture identity and duplicate
content address. Replaying the fixture twice in the evaluator yields the same
evaluation address and the same per-operation addresses.

Replay is offline. It validates the checked-in fixture and does not fetch the
source URLs. A future network adapter can add a retrieval receipt, but it must
not change the local replay contract or silently replace a source version.

## Scenario matrix

The independent scenario matrix executes each positive and control record
separately. It does not reuse the evaluator's stored receipt. Every scenario
records the declared state, observed state, declared result state, observed
result state, required issue codes, observed issue codes, content address, and
detail. The matrix currently contains four positive scenarios and eight review
scenarios.

## Batch pipeline

`StructuralPipelineRequest` provides one typed boundary for the four operations.
`StructuralPipeline` runs reconstruction, consensus, complex resolution, and
copy-number harmonization in that order. Each `StructuralStageReceipt` records
capability ID, input count, accepted count, review count, result state, issue
codes, output address, and detail. The count invariant is enforced:

```text
accepted_count + review_count = input_count
```

The report contains stage receipts and a manifest receipt. It does not copy raw
records, caller tables, or event payloads into the manifest. The accepted
fixture is `examples/structural-pipeline-accepted.json`. The review fixture is
`examples/structural-pipeline-batch.json`; it has one missing-mate operation,
so the final pipeline is `review` while the other stages remain inspectable.

The pipeline states are:

- `accepted`: all four operations produced valid stage outputs;
- `review`: at least one stage retained an issue while work was still
  executable; and
- `blocked`: no operation produced an executable input boundary.

The CLI exits zero only for `accepted` and exits two for `review` or
`blocked`. A review manifest can be emitted for inspection, but it is not
presented as an accepted release.

## Bundle boundary

`StructuralEvidenceBundleBuilder` requires a passing quality gate unless
`--allow-review` is explicitly supplied. The bundle has twelve sorted entries:
four positive operation summaries and eight review-control summaries. It
contains source IDs, contract manifest, component summaries, quality receipt,
lineage receipt, and content address. It does not contain raw records, caller
TSV text, or event payloads.

## Source-to-result lineage

`StructuralLineageBuilder` creates a sanitized graph over the same fixture and
evaluation report. The graph has four node kinds:

| Node kind | Identity | Addressed content |
| --- | --- | --- |
| `source` | public source receipt ID | title, version, scope, context |
| `fixture` | fixture ID | complete fixture catalog address |
| `record` | positive or control record ID | operation and expected-state metadata |
| `result` | record ID plus result role | operation receipt address |

The graph does not copy the operation payload into a node. A source declares a
record, the fixture contains the record, and the record produces one result.
The canonical fixture therefore produces 29 nodes and 36 edges: four source
nodes, one fixture node, twelve record nodes, twelve result nodes, and three
edges for each executable record. The graph preserves review results rather
than dropping them from the lineage.

Each edge is typed as `declares`, `contains`, or `produces`. Node IDs and edge
IDs are unique, all endpoints must exist, all nodes must share the exact
context key, and the graph address covers the sorted node and edge sets. The
independent audit checks source coverage, fixture presence, record/result
pairing, context agreement, source membership, and address integrity.

The CLI emits the graph and its audit receipt together:

```powershell
python -m glio_noncode structural-lineage examples/structural-public-aggregate.json --output structural-lineage.json
```

The bundle carries the lineage address in `lineage_address`,
`quality_summary.lineage_address`, and `component_summaries.lineage`. These
three references are a compact cross-check; the full graph remains available
from the lineage command and is independently verifiable.

JSON bundles can be verified offline with
`StructuralEvidenceBundleBuilder.verify`. CSV and Markdown are projections of
the same entry ordering. The JSON content address is computed over the
canonical bundle body before convenience fields such as `accepted` and entry
counts are appended.

## Local verification

```powershell
python -m compileall -q src tests
python -m glio_noncode audit-structural-data examples/structural-public-aggregate.json
python -m glio_noncode evaluate-structural-fixture examples/structural-public-aggregate.json
python -m glio_noncode replay-structural-fixtures examples/structural-public-aggregate.json
python -m glio_noncode structural-quality-gate examples/structural-public-aggregate.json
python -m glio_noncode evaluate-structural-scenarios examples/structural-public-aggregate.json
python -m glio_noncode structural-contracts
python -m glio_noncode build-structural-bundle examples/structural-public-aggregate.json --output structural-bundle.json
python -m glio_noncode run-structural-pipeline examples/structural-pipeline-accepted.json
python -m glio_noncode structural-lineage examples/structural-public-aggregate.json --output structural-lineage.json
python -m unittest discover -s tests -t .
```

The commands write JSON to stdout when `--output` is omitted. The Actions
workflow runs the same surfaces with temporary output paths on Python 3.11,
3.12, and 3.13.

## Limitations and release boundary

This gate proves deterministic mechanics and preservation of explicit
uncertainty. It does not prove caller sensitivity, breakpoint truth, clinical
pathogenicity, tumor clonality, mechanistic rearrangement identity, or
cross-study transport. Public dbVar and gnomAD summaries are not a substitute
for specimen-level consent, raw-read evidence, orthogonal assay confirmation,
or an institutional release review.

The verified state therefore means that the declared operation contracts,
fixtures, controls, replay behavior, and bundle boundaries work together. It
does not change the domain result semantics and does not convert an ambiguous
result into a supported biological conclusion.
