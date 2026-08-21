# Domain 04 C01-C04 reference-coordinate evidence gate

This document defines the release boundary for the first four Domain 04
reference capabilities. The boundary is designed for reproducible research
software: it makes assembly identity, pairwise coordinate conversion,
liftover ambiguity, and pangenome path containment explicit without turning a
coordinate result into sequence equivalence, clinical interpretation, or
patient-level evidence.

The implementation is split into two planes:

1. The adapter plane contains bounded coordinate operations: alias resolution,
   equal-length mapping segment parsing, mapping candidate scoring, and
   declared pangenome path lookup.
2. The evidence plane contains public source receipts, aggregate fixture rows,
   typed operation contracts, deterministic execution receipts, replay floors,
   scenarios, bundles, lineage, reconciliation, and runtime publication.

The evidence plane is the release contract. A green adapter unit test is useful
but is not enough to publish a fixture projection when source closure, context,
candidate retention, or downstream addresses disagree.

## Capability scope

| Capability | Operation | Adapter | Required decision surface |
| --- | --- | --- | --- |
| GNC-D04-C01 | `reference_registry` | `ReferenceRegistry` | resolve aliases without conflating species or releases |
| GNC-D04-C02 | `liftover_chain` | `LiftoverChainManager` and `ReferenceProjector` | project only through supplied explicit segments |
| GNC-D04-C03 | `liftover_ambiguity` | `LiftoverAmbiguityScorer` | retain absent, unique, and competing candidates |
| GNC-D04-C04 | `pangenome_coordinate` | `PangenomeCoordinateMapper` | retain every declared path candidate |

The fixture contains 16 rows: four positive rows and twelve controls. There
are three controls for each capability so that a result cannot pass merely by
handling the positive example. The controls are part of the release evidence;
they are not discarded test data.

## Public source boundary

The fixture is aggregate and contains no subject, participant, specimen, or
medical record identifier. Public sources provide vocabulary, scope, and
resource references. The checked-in coordinate vectors are bounded verification
inputs; they do not claim to be a complete downloaded assembly or chain file.

The source receipt set is:

| Source ID | Public scope | URI |
| --- | --- | --- |
| `SRC-NCBI-GRC-FAQ` | assembly names, aliases, and accessions | `https://www.ncbi.nlm.nih.gov/grc/help/faq/` |
| `SRC-NCBI-GRCH38-DATA` | assembly and chromosome metadata | `https://www.ncbi.nlm.nih.gov/grc/human/data?asm=GRCh38` |
| `SRC-UCSC-LIFTOVER` | LiftOver workflow and chain-file access | `https://genome.ucsc.edu/FAQ/FAQdownloads` |
| `SRC-UCSC-CHAIN` | pairwise chain vocabulary | `https://www.genome.ucsc.edu/goldenPath/help/chain.html` |
| `SRC-HPRC-DATA` | pangenome release and public data-use scope | `https://humanpangenome.org/data-use/` |
| `SRC-HPRC-ALIGNMENTS` | public alignment catalog and path labels | `https://data.humanpangenome.org/alignments` |

Every source receipt contains a source ID, title, HTTPS URI, declared scope,
aggregate flag, access date, license note, and a content address computed from
those fields. The content address is recalculated during parsing; a checked-in
address is not trusted as an opaque assertion.

The data audit checks that:

- exactly six source receipts are present;
- source IDs are unique;
- every source is non-patient-level;
- every URI uses HTTPS;
- every scope and license note is non-empty;
- every source receipt has a content address; and
- every record source ID belongs to the closed source set.

A missing permission or a source outside the declared public scope is a review
condition. Source presence does not certify the quality of an underlying
resource or a particular coordinate conversion.

## Exact context

The fixture context is the ordered six-part key:

```text
GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline
```

The six positions are retained as text rather than parsed into independent
defaults inside the evidence plane. This preserves exactness across data
audit, operation receipts, replay, lineage, reconciliation, and runtime.
Every record must repeat the exact fixture key. A context with the right
assembly but a different disease, age, material, plane, or phase is not a
near-match; it is a different context and must be reviewed.

The context key is a scope label for software evidence. It does not assert
that a bulk tumor represents a particular person, that a glioma label is a
diagnosis, or that a baseline coordinate is suitable for a clinical decision.

## Typed input record

Each record has these fields:

| Field | Meaning | Boundary |
| --- | --- | --- |
| `record_id` | stable fixture row identity | unique across positives and controls |
| `operation` | one of the four operation IDs | must be in the contract registry |
| `role` | `positive` or `control` | controls must name expected issues |
| `expected_state` | adapter result state | positive rows require `supported` |
| `context_key` | exact six-part scope | must equal the fixture key |
| `source_ids` | source receipts used by the row | must be non-empty and closed |
| `expected_issue_codes` | exact diagnostic vocabulary | compared to the execution receipt |
| `payload` | operation-specific aggregate input | recursively checked for restricted keys |
| `content_address` | typed address of the row | recomputed from the canonical fields |

The parser reconstructs a typed record from JSON and ignores any supplied
content address while computing its own address. This prevents an input file
from making an invalid row appear immutable by copying a stale address.

Restricted key checks are recursive. Patient, subject, participant, individual,
person, medical-record, contact, token, key, and secret-like fields are not
permitted in fixture payloads or release projections. The boundary is key-based
and conservative so a release projection does not depend on a future caller
interpreting a value correctly.

## C01 canonical reference registry

The registry resolves explicit aliases to a `ReferenceAssembly`. The checked-in
registry includes the two human assemblies used by the coordinate adapters:

| Assembly | Common alias | Species | Release metadata |
| --- | --- | --- | --- |
| `GRCh38` | `hg38`, `GRCh38.p14` | *Homo sapiens* | `GCA_000001405.15` major reference accession |
| `GRCh37` | `hg19`, `GRCh37.p13` | *Homo sapiens* | `GCA_000001405.1` major reference accession |

An alias is not an accession parser. The positive fixture uses `hg38`, which
resolves to `GRCh38`. Controls use GenBank-like and RefSeq-like accession
strings and a future assembly label. These controls remain invalid because
the registry has not declared those strings as aliases. A future extension may
add accession aliases, but it must add an explicit assembly record, source
coverage, and collision tests at the same time.

C01 returns a bounded summary containing the resolved assembly ID, canonical
name, species, release, and alias count. The summary does not copy the source
receipt or a full registry dump into every record. An unknown query returns
`invalid` with `reference_alias_unknown`; it is not coerced to the nearest
assembly by case, prefix, or version similarity.

## C02 explicit chain segment liftover

The chain operation accepts a tabular segment vector with these fields:

```text
mapping_id
source_chrom
source_start
source_end
target_chrom
target_start
target_end
strand
version
```

The adapter normalizes chromosome labels, converts numeric fields, and creates
an equal-length `MappingSegment`. Equal length is required by this bounded
operation so interval projection is deterministic. A complete UCSC chain file
contains more structure and alignment blocks; this fixture does not claim to
implement every chain-file feature.

The positive row maps a short GRCh38 chromosome 7 interval to a supplied
GRCh37 segment. The controls cover a malformed unequal segment, a breakend
requiring a graph-aware mate mapping, and a valid chain with no segment
containing the requested chromosome.

The result summary retains parsed segment count, parse issue count, projection
status, mapping ID, target build, target chromosome, and target coordinates. It
does not expose raw chain text. The state mapping is:

| Adapter status | Evidence state | Meaning |
| --- | --- | --- |
| `mapped` or `identity` | `supported` | one declared projection completed |
| `partial` | `partial` | more than one segment competes |
| `abstained` | `abstained` | no safe projection, breakend, or missing segment |
| parser or input failure | `invalid` | typed input could not be accepted |

Reverse-strand allele handling remains in the adapter test surface. It is not
silently converted into a forward-strand claim by the evidence plane.

## C03 liftover ambiguity

C03 takes a query interval and a list of typed mapping segments. It first
requires full-interval containment and then passes every candidate to
`LiftoverAmbiguityScorer`.

| Candidate count | State | Score | Decision |
| ---: | --- | ---: | --- |
| 0 | `abstained` | absent | no coordinate selected |
| 1 | `supported` | 1.0 | unique candidate retained |
| 2 or more | `ambiguous` | `1 / count` | all candidate IDs retained |

The score is a bounded description of candidate multiplicity. It is not a
posterior probability, mapping quality, or reason to choose one segment. The
fixture includes one unique positive and three controls: two candidates, a
different chromosome, and a segment that does not contain the entire interval.

C03 summaries retain query coordinates, candidate mapping IDs, candidate
count, score, and scorer state. They do not retain full source rows in the
release bundle. The lineage graph still links the record to its sanitized
result so a reviewer can see which control path was evaluated.

## C04 pangenome path coordinates

C04 accepts declared `PangenomePath` records. A path contains path ID and name,
chromosome and one-based inclusive interval, strand, sequence ID, public source
ID, release version, and bounded attributes such as coordinate reference and
pipeline label.

The mapper normalizes chromosome aliases for containment and returns every path
containing the complete query interval. It does not infer missing paths,
translate sequence IDs, or collapse alternate and primary paths.

The positive vector uses the public HPRC alignment vocabulary for a GRCh38
path. Controls cover two overlapping paths, a path on another chromosome, and
a query that crosses the declared path boundary. The multiple-path result
retains both path IDs and both sequence IDs. It remains `ambiguous` even when
one path is named primary and another is named alternate.

Containment is not sequence equivalence. A path label is public metadata, not
a claim that the checked-in interval matches a downloaded graph sequence.

## Operation contracts and evaluation

The contract registry exposes four contracts with required input fields,
sanitized output fields, safety boundaries, issue codes, and supported states.
The manifest is content-addressed and ordered by the operation enum. A change
to a required field or issue code must update the contract test, fixture
control, replay expectation, and this document.

Every operation receipt additionally carries record ID, role, issue codes,
source IDs, exact context, and a content address. That common envelope allows
downstream views to reconcile results without copying raw operation payloads.

The canonical fixture evaluation produces 134 checks: eight checks per record
for contract fields, state, issue codes, receipt address, source retention,
context retention, sanitization, and execution; plus receipt count, operation
coverage, positive state, control state, receipt identity, and report
sanitization checks. The expected issue tuple is exact, not a subset. A control
that fails for an unlisted reason is fixture drift even if its state is still
non-supported.

## Replay and scenarios

Replay compares fixture ID and version, exact context, sorted source set,
ordered record set, operation set, minimum check count, positive floor, and
control floor. The checked-in expectation requires at least 130 evaluation
checks, four positive rows, and twelve controls. Replay also requires one
receipt per input row, supported positive receipts, non-supported controls,
addressed receipts, and exact context retention.

The scenario matrix turns every row into a named transition. A scenario passes
only when both state and exact issue-code tuple match the record expectation.
The current matrix has sixteen passing transitions: four supported positives,
three invalid registry controls, three chain controls, three ambiguity paths,
and three pangenome paths. A control may not be removed because a positive
operation remains green.

## Evidence bundle

The verification bundle includes all sixteen sanitized receipts by default.
This is the audit view: it includes review controls and is not published. The
`--accepted-only` view includes the four supported positives and may be marked
published when all upstream gates pass. JSON, CSV, and Markdown renderings
share the same entry addresses and source/context fields.

The bundle verifier checks fixture ID and version, exact context, unique entry
identity, entry membership, record and receipt address retention, context
retention, absence of raw chain text, truthful control inclusion, and bundle
content addressing. Review controls may be rendered for inspection, but
rendering them does not make them publishable.

## Lineage graph

The lineage graph has 39 nodes and 38 edges for the canonical fixture: six
source nodes, one fixture node, sixteen record nodes, and sixteen sanitized
result nodes. Edges are typed: six `declares` edges connect sources to the
fixture, sixteen `contains` edges connect the fixture to records, and sixteen
`produces` edges connect records to results.

Every node and edge has a content address. The graph audit checks unique IDs,
valid endpoints, exact node and edge floors, contextual consistency, source
declaration edges, record containment, result production, address presence,
and recomputed graph address. Removing one result edge fails both the typed
edge count and the result-edge check; it cannot disappear into a final count.

## Reconciliation

Reconciliation joins the data catalog, evaluation receipts, verification
bundle, and lineage graph without mutating any component. The current report
contains 24 checks covering evaluation state and count, receipt identity,
context, source closure, operation set, expected states, expected issues,
record addresses, bundle membership/context/receipt addresses, bundle
sanitization, lineage state/count/context/address, positive support, control
review state, raw-record boundary, source closure, and cross-view address
completeness.

The first failed boundary is the repair starting point. Downstream views are
regenerated after a repair so their addresses describe repaired inputs.
Patching only a final report is not an accepted repair.

## Runtime pipeline

The runtime request references a fixture path, exact context, accepted-only
mode, review opt-in, and output format. It executes five stages:

| Stage | Input count | Output count | Gate |
| --- | ---: | ---: | --- |
| `public_data` | 16 records | 16 records | 26 data checks |
| `fixture_evaluation` | 16 records | 16 receipts | 134 operation checks |
| `replay` | 16 records | 16 receipts | 16 replay checks |
| `reconciliation` | 16 receipts | 16 receipts | 24 cross-view checks |
| `bundle` | 16 receipts | 4 accepted-only entries | publication mode |

The accepted example publishes only the four supported positive entries. The
review example deliberately supplies a different context and returns state
`review`, `published=false`, and a sanitized report. A non-publishing result
is successful behavior for a review path; the CLI returns a non-zero status so
automation cannot mistake it for a release.

## Failure and repair matrix

| Boundary | Failure | Repair | Shortcut that is not allowed |
| --- | --- | --- | --- |
| Assembly alias | unknown or undeclared label | add an explicit registry record and source receipt | choose nearest assembly by prefix |
| Source receipt | missing, duplicate, or non-public source | correct source declaration | mark row trusted without receipt |
| Context | one field differs | correct or intentionally version fixture | transport a nearby context |
| Chain parse | malformed or unequal segment | repair source vector and replay | drop malformed row silently |
| Chain mapping | no complete segment | add explicit mapping or keep abstained | map a partial interval as complete |
| Breakend | mate mapping not supplied | add graph-aware contract later | force a single breakend coordinate |
| Ambiguity | multiple candidates | retain all candidates and review | select the highest arbitrary score |
| Pangenome | multiple paths | retain path and sequence IDs | prefer primary path without evidence |
| Bundle | review entries in publish view | use accepted-only mode or keep review | relabel review entries as accepted |
| Lineage | missing node or edge | regenerate typed graph | patch edge count only |
| Reconciliation | cross-view address drift | repair first divergent component | edit final report in isolation |
| Runtime | context mismatch or failed stage | keep review and rerun after repair | bypass a stage with a manual receipt |

## CLI and CI

The complete command surface is:

```powershell
python -m glio_noncode audit-reference-coordinate-data examples/reference-coordinate-public-aggregate.json --output data.json
python -m glio_noncode evaluate-reference-coordinate-fixture examples/reference-coordinate-public-aggregate.json --output evaluation.json
python -m glio_noncode replay-reference-coordinate-fixtures examples/reference-coordinate-public-aggregate.json --output replay.json
python -m glio_noncode reference-coordinate-quality-gate examples/reference-coordinate-public-aggregate.json --output quality.json
python -m glio_noncode evaluate-reference-coordinate-scenarios examples/reference-coordinate-public-aggregate.json --output scenarios.json
python -m glio_noncode reference-coordinate-contracts --output contracts.json
python -m glio_noncode build-reference-coordinate-bundle examples/reference-coordinate-public-aggregate.json --output bundle.json
python -m glio_noncode reference-coordinate-lineage examples/reference-coordinate-public-aggregate.json --output lineage.json
python -m glio_noncode reference-coordinate-reconciliation examples/reference-coordinate-public-aggregate.json --output reconciliation.json
python -m glio_noncode run-reference-coordinate-pipeline examples/reference-coordinate-pipeline-accepted.json --output pipeline.json
```

CI runs all ten commands, compilation, and the full unit-test discovery on
Python 3.11, 3.12, and 3.13. The review pipeline example is tested locally
because it intentionally returns status 2. The accepted pipeline is the CI
path and must return zero.

## Change rules

When adding a source, use an HTTPS public URI, state its scope, mark it
non-patient-level, add a source receipt test, and update source-count and
source-closure floors. When adding a positive row, keep exact context, name
source IDs, provide contract-required fields, state exact issue codes, add a
scenario assertion, and update replay floors and the capability note.

When adding a control, state the failure meaning in an issue code, keep the
control in the verification bundle, ensure it cannot become supported, add a
mutation test for issue drift, and document its invalid, abstained, partial,
or ambiguous state. When changing a projection field, update the operation
contract, decide whether it is safe for a result summary, add an address test,
add a malformed control, and regenerate downstream expectations.

## Verification checklist

Before release, verify that data audit reports 26 checks; six sources are
public, HTTPS, unique, and addressed; exact context is retained; there are
four positives and twelve controls; all four contracts are present; evaluation
reports 134 checks; every positive is supported; every control retains an
exact non-supported issue; replay reports 16 checks; scenarios report 16
transitions; lineage has 39 nodes and 38 edges; reconciliation reports 24
checks; the verification bundle has 16 entries; accepted-only mode has four
publishable entries; runtime has five stages; no raw chain text or restricted
key appears in projections; focused tests pass; the full suite passes; and all
three Python versions pass CI.

Passing this gate proves consistency of the declared public aggregate fixture
and its typed software boundaries. It does not prove assembly completeness,
chain-file completeness, graph sequence identity, population
representativeness, diagnostic validity, treatment response, or clinical
readiness.
