# Domain 03 C09-C12 specimen lineage evidence gate

This document defines the executable release boundary for the four longitudinal
specimen operations. It is a research-software contract for declared aggregate
observations. It is not a clinical adjudication, a patient registry, a chain of
custody assertion, or proof of biological ancestry.

## 1. Scope and evidence boundary

The gate covers four adapters already present in the specimen context plane:

| Capability | Adapter | Question answered | Release state |
| --- | --- | --- | --- |
| GNC-D03-C09 | `MultiRegionLineageResolver` | Which declared region edges form a subject-local graph? | verified |
| GNC-D03-C10 | `LongitudinalSpecimenLinker` | Which same-subject specimens have an explicit or ordered link? | verified |
| GNC-D03-C11 | `PrimaryRecurrencePhaseMapper` | Which phase labels are supported by explicit evidence? | verified |
| GNC-D03-C12 | `TreatmentExposureContextualizer` | How does a collection time relate to a declared treatment interval? | verified |

The gate proves deterministic behavior over a checked-in aggregate fixture. It
does not prove that a specimen came from a named person, that a region is a
biological clone, that a later specimen is a recurrence, or that a therapy
caused a molecular response. Those claims require evidence outside this
software boundary and remain unavailable to these adapters.

The fixture is intentionally shaped as aggregate synthetic observations. Its
`case_id` values are cohort keys used to test graph and temporal joins; they do
not identify a person. Direct identifier field names are rejected recursively
by the data audit.

## 2. Public source receipts

The fixture uses documentation as a source receipt. The receipt establishes the
data-model vocabulary and the permitted aggregate scope; it does not claim that
the synthetic rows were copied from the documentation.

| Source ID | Public receipt | Receipt role |
| --- | --- | --- |
| `gdc-biospecimen-submission` | [GDC Data Submission Walkthrough](https://docs.gdc.cancer.gov/Data_Submission_Portal/Users_Guide/Data_Submission_Walkthrough/) | case-linked sample, portion, analyte, aliquot, and read-group hierarchy |
| `gdc-biospecimen-data` | [GDC Biospecimen Data](https://docs.gdc.cancer.gov/Encyclopedia/pages/Biospecimen_Data/) | sample-to-portion-to-analyte relationships and retrieval boundary |
| `gdc-tcga-barcode` | [GDC TCGA Barcode](https://docs.gdc.cancer.gov/Encyclopedia/pages/TCGA_Barcode/) | hierarchical biospecimen identity shape |
| `gdc-api-available-fields` | [GDC Available Fields](https://docs.gdc.cancer.gov/API/Users_Guide/Appendix_A_Available_Fields/) | sample type, tissue collection, preservation, and clinical field vocabulary |

Every receipt has an absolute URL, a scope statement, an aggregate-only flag,
and a patient-level false flag. Source IDs are part of every record address and
are reconciled by the quality gate.

## 3. Exact context

Every positive and control record uses this six-dimension context:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The six positions are intentionally kept as a single exact key. A record with a
different key is excluded by the adapter and becomes an explicit context issue;
the evaluator never silently reassigns it to the catalog context.

## 4. Fixture schema

The root object is `specimen-lineage-evidence-v1`:

```json
{
  "schema_version": "specimen-lineage-evidence-v1",
  "fixture_id": "specimen-lineage-public-aggregate-v1",
  "aggregate_only": true,
  "context_key": "...six dimensions...",
  "sources": [],
  "positives": [],
  "controls": []
}
```

Each record contains:

| Field | Meaning |
| --- | --- |
| `record_id` | stable row identity within the fixture |
| `operation` | one of the four operation enum values |
| `source_ids` | declared public receipts shaping the row |
| `context_key` | exact six-dimension context |
| `expected_fixture_state` | `accepted` for a positive or `review` for a control |
| `expected_result_state` | adapter state expected for that row |
| `expected_issue_codes` | exact sorted issue-code set |
| `expected_counts` | exact aggregate count assertions |
| `payload` | synthetic rows passed to the adapter |
| `parameters` | explicit adapter thresholds or flags |
| `content_address` | SHA-256 address over the preceding contract fields |

The catalog requires at least four positive rows, at least eight controls, all
four operation values, four public sources, and a six-position context key. The
checked-in catalog has exactly four positives and eight controls.

## 5. C09 region lineage

### Input contract

The region adapter accepts a sequence of objects with `region_id`, `sample_id`,
and `case_id`. Optional `parent_region_id` or `parent_region_ids`,
`region_label`, `relationship`, collection time, context, source ID, source
version, and order index are retained where present.

The implementation reads `case_id` through the existing subject alias parser.
The public fixture uses only aggregate case keys. No direct identifier field is
accepted by the fixture audit.

### Algorithm

1. Materialize the input once and compute an input content address.
2. Parse rows into typed `RegionObservation` values.
3. Reject non-object rows, invalid required fields, context mismatches, and
   duplicate region IDs as row-addressable issues.
4. Group valid observations by case key.
5. Convert every declared parent into a `RegionLineageEdge`.
6. Mark an edge partial if its parent is absent from the snapshot.
7. Find roots from known regions that are never an edge child.
8. Find leaves from known regions that are never an edge parent.
9. Traverse parent edges to retain every cycle node.
10. Mark the subject graph contradictory for cycles, partial for missing parents
    or a singleton graph, and supported only when two or more known regions form
    a complete acyclic declaration.

No edge is manufactured from labels, collection time, sample names, or spatial
proximity. A missing parent remains a missing graph node.

### Release cases

The positive case has one root and two derived leaves. The controls include one
missing-parent graph and one two-node cycle. Their expected states are,
respectively, `partial` and `contradictory`.

## 6. C10 longitudinal linking

### Input contract

The linker accepts `specimen_id`, `sample_id`, `case_id`, `tissue`,
`collection_time`, and `timepoint`. `predecessor_specimen_id` is optional.
Time values may be ISO dates, ISO datetimes, or numeric time values supported by
the base adapter. Source, version, phase hint, and context are retained.

### Ordering rules

Within each case key, observations are sorted by parsed collection time and then
specimen ID. Explicit predecessor declarations are authoritative for the
successor that carries them. If a group has no predecessor declarations, the
adapter creates adjacent ordered-time links. A singleton is unlinked unless
`link_singleton` is explicitly enabled.

Each link retains:

- the case key;
- predecessor and successor specimen IDs;
- `declared_predecessor` or `ordered_time` as the ordering basis;
- an absolute gap label or `unknown_gap`;
- both source IDs;
- a supported or partial state; and
- a content address.

Different tissue labels on an inferred adjacent link produce a visible warning.
They do not invalidate the link, but the link remains partial when time is
missing. A missing declared predecessor creates an unlinked successor and a
warning. Cross-case links are not attempted.

### Release cases

The positive chain has three observations and two explicit supported links. One
control has a missing collection time and retains a partial ordered link. The
other has a missing declared predecessor, zero links, one unlinked specimen, and
one diagnostic issue.

## 7. C11 phase mapping

### Vocabulary

The mapper normalizes the following declared labels:

| Phase | Accepted labels |
| --- | --- |
| primary | `primary`, `diagnosis`, `initial`, `new_diagnosis` |
| recurrence | `recurrence`, `recurrent`, `relapse`, `progression`, `secondary` |
| interval | `interval`, `maintenance`, `surveillance`, `follow_up` |
| unknown | no supported explicit label or primary predecessor evidence |

### Evidence precedence

1. A conflicting set of labels is contradictory and maps to unknown with the
   conflict preserved.
2. One supported explicit label is supported.
3. An observation whose declared predecessor is an explicitly primary specimen
   is recurrence with evidence `declared_predecessor_is_primary`.
4. Everything else is unknown and partial.

The mapper emits a warning when multiple primary declarations occur for one
case. It does not use later collection date as a recurrence shortcut. A phase
assignment is a research context label, not clinical disease status.

The positive case covers primary, recurrence by declared primary predecessor,
and interval. Controls cover later-only unknown observations and a conflicting
primary/recurrence declaration.

## 8. C12 treatment context

### Interval contract

Treatment exposures require `exposure_id`, `case_id`, `therapy_id`,
`therapy_class`, and a parseable `start_time`. `end_time` is optional but, when
present, must not precede the start. Status, context, source, and source version
are retained.

### Temporal relation rules

For a same-case specimen collection time:

- before the exposure start is `pre_treatment`;
- at or after start and before or at end is `on_treatment`;
- after a declared end is `post_treatment`;
- an open-ended exposure remains `on_treatment` after its start.

When multiple same-case exposures cover the same specimen time, every matching
context is retained. If another exposure is also on treatment, the context is
ambiguous and carries the overlapping exposure IDs. Missing specimen time is
uncontextualized with a `missing_specimen_time` warning. Exposures from another
case are never joined.

The positive case produces one pre-, one on-, and one post-treatment relation.
Controls cover overlapping exposures and a missing specimen time.

## 9. Evaluation surface

`SpecimenLineageFixtureEvaluator` executes all twelve rows and returns a typed
receipt for each. Each receipt checks:

1. adapter result state;
2. exact sorted issue-code set;
3. every declared expected count;
4. SHA-256 input address;
5. SHA-256 output address;
6. sanitized output boundary; and
7. explicit accepted/review fixture role.

The checked-in fixture produces 159 checks. The output projection contains
bounded result summaries, counts, IDs, issue codes, and addresses. It does not
include the raw `records` collection or direct identifier fields.

An evaluation is accepted only when the data audit passes and every check
passes. A review control is expected to produce a review state; its passing
check means that the adapter retained the anomaly correctly, not that the
anomaly disappeared.

## 10. Replay and scenario matrix

The replay runner reloads one or more fixture files and compares each against an
expectation containing fixture ID, exact context, source set, minimum check
count, positive floor, and control floor. It reports identity, context, source,
evaluation, and floor drift as explicit issue codes.

The scenario matrix calls the operation dispatcher independently for every row
and compares state, issue set, and expected counts without reusing the aggregate
evaluation report. This catches a quality-gate implementation that could pass
from a stale cached report.

The matrix has twelve scenarios: four positive transitions and eight review
transitions. It preserves the distinction among supported, partial, ambiguous,
and contradictory states.

## 11. Quality gate

The quality gate reconciles:

- data audit acceptance;
- aggregate evaluation acceptance;
- the 159-check floor;
- independent scenario acceptance;
- four-positive and eight-control floors;
- four-operation coverage;
- four operation contracts;
- exact context and source agreement;
- deterministic evaluation address;
- fixture identity and aggregate scope;
- receipt uniqueness;
- positive and control roles;
- contract-state coverage;
- sanitized output checks;
- graph audit and 29-node/28-edge shape;
- graph content address; and
- receipt-index identity, state, context, source, uniqueness, and address reconciliation.

The gate has 22 release checks. A bundle cannot be built in accepted state until
the gate passes. `allow_review` is an explicit inspection escape hatch and is
never enabled by the normal CI command.

## 12. Source-to-result lineage graph

The graph has four source nodes, one fixture node, twelve record nodes, and
twelve result nodes. It contains:

- four `declares` edges from source receipts to the fixture;
- twelve `contains` edges from the fixture to records; and
- twelve `produces` edges from records to sanitized result receipts.

This is 29 nodes and 28 edges. Every node has the exact fixture context and a
content address. Every edge has a deterministic ID and references existing
nodes. Raw payloads are not copied into the graph.

The receipt index is a second, flatter reconciliation surface. It contains one
entry per fixture record and joins the fixture record address to the fresh
execution result address. Its audit detects omitted records, duplicate IDs,
operation coverage drift, source or context drift, result-state drift, address
drift, and raw-payload leakage without opening the raw fixture in a review
consumer.

## 13. Bundle and runtime

The bundle builder publishes twelve entries containing operation, fixture state,
result state, issue codes, source IDs, context, record address, and result
address. JSON, CSV, and Markdown projections are supported. The bundle format
is specified in `docs/SPECIMEN_LINEAGE_BUNDLE_FORMAT.md`.

The runtime executes operations in this fixed order:

```text
region_lineage -> longitudinal_linking -> phase_mapping -> treatment_context
```

Each stage records input, accepted, review, and blocked counts with conservation
checked at construction. A blocked stage captures a bounded error type and
prevents publication. Any review stage prevents publication but keeps all four
stage receipts. The accepted example publishes a sanitized stage manifest; the
review example does not.

## 14. Commands

```powershell
python -m glio_noncode audit-specimen-lineage-data examples/specimen-lineage-public-aggregate.json --output lineage-data.json
python -m glio_noncode evaluate-specimen-lineage-fixture examples/specimen-lineage-public-aggregate.json --output lineage-fixture.json
python -m glio_noncode replay-specimen-lineage-fixtures examples/specimen-lineage-public-aggregate.json --output lineage-replay.json
python -m glio_noncode specimen-lineage-quality-gate examples/specimen-lineage-public-aggregate.json --output lineage-quality.json
python -m glio_noncode evaluate-specimen-lineage-scenarios examples/specimen-lineage-public-aggregate.json --output lineage-scenarios.json
python -m glio_noncode specimen-lineage-contracts --output lineage-contracts.json
python -m glio_noncode build-specimen-lineage-bundle examples/specimen-lineage-public-aggregate.json --output lineage-bundle.json
python -m glio_noncode specimen-lineage-lineage examples/specimen-lineage-public-aggregate.json --output lineage-graph.json
python -m glio_noncode specimen-lineage-reconciliation examples/specimen-lineage-public-aggregate.json --output lineage-reconciliation.json
python -m glio_noncode run-specimen-lineage-pipeline examples/specimen-lineage-pipeline-accepted.json --output lineage-pipeline.json
```

## 15. Release checklist

Before changing a C09-C12 ledger state or fixture:

1. retain public source receipts and verify their URLs;
2. keep all fixture rows aggregate-only;
3. preserve the exact context key unless the release contract changes;
4. add both positive and review controls for new behavior;
5. update the operation contract and issue/state expectation;
6. update the independent scenario matrix expectations;
7. update bundle and lineage shape assertions when the schema changes;
8. run focused tests and the complete repository suite;
9. run every CI command locally; and
10. inspect staged additions for direct identifiers and restricted metadata.

The evidence gate is a software verification boundary. It is deliberately
conservative: absence, conflict, temporal ambiguity, and missing parents remain
visible instead of being converted into a stronger scientific claim.
