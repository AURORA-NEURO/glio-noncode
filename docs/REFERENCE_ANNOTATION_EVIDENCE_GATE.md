# Domain 04 C05–C08 reference annotation evidence gate

This document defines the executable boundary for the next four Domain 04
capabilities:

| Capability | Operation | Primary adapter | Accepted result |
|---|---|---|---|
| GNC-D04-C05 | GENCODE transcript catalog | `GencodeTranscriptAdapter` | exact transcript identity resolves |
| GNC-D04-C06 | MANE transcript catalog | `ManeTranscriptAdapter` | one exact cross-identifier resolves |
| GNC-D04-C07 | regulatory ontology catalog | `RegulatoryOntologyAdapter` | one declared term resolves |
| GNC-D04-C08 | disease ontology mapping | `DiseaseOntologyMapper` | one declared target resolves |

The implementation is a local, deterministic research boundary. It does not
vendor an external release, fetch bytes during evaluation, assign clinical
meaning, choose between competing rows, or convert a terminology match into a
clinical conclusion.

## 1. Public source boundary

The checked-in fixture carries source receipts, not full release archives. The
receipts record the authority, URI, release description, access date, license
statement, and scope used by the fixture.

The current receipt set is:

| Source ID | Authority | URI | Boundary |
|---|---|---|---|
| `gencode-human` | GENCODE human release index | [gencodegenes.org/human](https://www.gencodegenes.org/human/) | release identity and assembly vocabulary |
| `gencode-format` | GENCODE GTF format specification | [gencodegenes.org/pages/data_format](https://www.gencodegenes.org/pages/data_format.html) | nine-column GTF and attribute shape |
| `ncbi-mane` | NCBI/EMBL-EBI MANE documentation | [ncbi.nlm.nih.gov/refseq/MANE](https://www.ncbi.nlm.nih.gov/refseq/MANE/) | matched RefSeq and Ensembl identifiers |
| `obo-ro` | OBO Relation Ontology | [obofoundry.org/ontology/ro](https://obofoundry.org/ontology/ro.html) | declared relation IDs, labels, and aliases |
| `obo-mondo` | OBO Mondo Disease Ontology | [obofoundry.org/ontology/mondo](https://obofoundry.org/ontology/mondo.html) | declared disease terminology targets |

These links describe the public vocabulary and format scope. The fixture uses
release-shaped examples and records the boundary explicitly; it must not be
read as a complete release mirror.

## 2. Exact context

Every fixture record has the same ordered context key:

```text
GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline
```

The six fields are interpreted as follows:

| Position | Field | Required value in this fixture |
|---:|---|---|
| 1 | assembly | `GRCh38` |
| 2 | disease context | `diffuse_glioma` |
| 3 | age band | `adult` |
| 4 | material scope | `bulk_tumor` |
| 5 | coordinate plane | `reference_plane` |
| 6 | comparison state | `baseline` |

Context is part of identity. A report with a different assembly, disease
context, material scope, coordinate plane, or comparison state is a review
result until it is evaluated against a fixture with that exact context.

## 3. Fixture topology

The aggregate fixture is versioned as `2026.08.c05-c08.v1` and has the stable
ID `reference-annotation-public-aggregate`.

It contains five source receipts and sixteen executable records:

| Operation | Positive | Controls | Total |
|---|---:|---:|---:|
| GENCODE transcript catalog | 1 | 3 | 4 |
| MANE transcript catalog | 1 | 3 | 4 |
| regulatory ontology catalog | 1 | 3 | 4 |
| disease ontology mapping | 1 | 3 | 4 |
| **Total** | **4** | **12** | **16** |

Positive records must resolve to `supported`. Controls must remain
`ambiguous` or `abstained`. A control that resolves as supported is a gate
failure because it demonstrates silent selection or an over-broad match.

Every record contains:

- a stable record ID;
- one declared operation;
- one positive/control role;
- the exact context key;
- one or more source IDs;
- a release-shaped text or JSON input;
- one explicit query;
- an expected state;
- zero or more expected issue codes;
- a human-readable boundary description; and
- a content address over the complete record declaration.

The evaluator consumes the payload but emits only a sanitized projection. Raw
input text is not copied into operation receipts, bundles, lineage nodes, or
quality reports.

## 4. C05 GENCODE transcript catalog

The GENCODE adapter accepts GTF/GFF3 or JSON-shaped transcript rows. The
fixture intentionally uses both forms so parser behavior is exercised across
the declared boundary.

### Positive path

`C05-POS-001` contains a versioned transcript identifier, gene identifier,
chromosome, interval, strand, biotype, and assembly. The query uses the
versioned transcript ID. The result is supported with one match.

### Control paths

`C05-CTRL-001` contains a malformed GTF row. The parser quarantines the row as
`invalid_gencode_row`; the unknown query also produces
`transcript_not_resolved`.

`C05-CTRL-002` contains two transcript rows for one exact gene identifier.
The result is `ambiguous` with `ambiguous_transcript_match`. Both transcript
records remain in the adapter result.

`C05-CTRL-003` contains a valid catalog and an unknown transcript identifier.
The result is `abstained` with `transcript_not_resolved`.

The adapter preserves transcript version, gene identity, assembly,
coordinates, strand, biotype, source identity, source version, attributes,
row hashes, and catalog addresses. It does not choose a canonical transcript
from a gene-only query when more than one record matches.

## 5. C06 MANE transcript catalog

The MANE adapter accepts TSV, CSV, and JSON-shaped matched transcript rows. A
record retains RefSeq and Ensembl identifiers, MANE status, gene identity,
assembly, optional coordinates, source version, and row attributes.

### Positive path

`C06-POS-001` contains a MANE Select row and resolves by its RefSeq identifier.
The result is supported with one match and retains the MANE status.

### Control paths

`C06-CTRL-001` has two rows for one gene, one MANE Select and one MANE Plus
Clinical. A gene query returns both and produces `ambiguous_mane_match`.

`C06-CTRL-002` has no usable cross-identifier and is queried by an identifier
not present in the row. The result is `abstained` with
`mane_not_resolved`.

`C06-CTRL-003` has a valid row but an unknown query identifier. It also
abstains with `mane_not_resolved`.

No field named status is treated as a ranking function. A MANE status filters
or describes declared records; it does not silently discard competing rows.

## 6. C07 regulatory ontology catalog

The regulatory adapter accepts a declared term catalog with IDs, labels,
namespace, definition, parents, aliases, source identity, and source version.
Matching is limited to an exact term ID, a declared label, or a declared
alias.

### Positive path

`C07-POS-001` queries `RO:0001` and resolves one declared Relation Ontology
term.

### Control paths

`C07-CTRL-001` uses an alias shared by two terms. The result is `ambiguous`
with `term_match_ambiguous`; both term IDs are retained.

`C07-CTRL-002` uses an unlisted label. The result is `abstained` with
`term_not_resolved`.

`C07-CTRL-003` contains a duplicate term ID. The duplicate is quarantined as
`invalid_regulatory_term`; the query remains `abstained` with
`term_not_resolved`.

The adapter does not infer a relationship from spelling, tokenize a label into
new ontology IDs, or use a neighboring term as a substitute.

## 7. C08 disease ontology mapping

The disease mapper accepts source terms and explicit target mappings. Each
mapping retains source ID, source label, target ID, target namespace, target
label when provided, relationship, source identity, source version, row hash,
and attributes.

### Positive path

`C08-POS-001` maps one declared source ID to one Mondo target. The result is
supported and contains one mapping.

### Control paths

`C08-CTRL-001` maps the same source ID to both a Mondo and a DOID target. The
result is `ambiguous` with `disease_mapping_ambiguous`; both target IDs remain
visible.

`C08-CTRL-002` uses an unknown source ID and abstains with
`disease_not_resolved`.

`C08-CTRL-003` uses an unknown source label and abstains with
`disease_not_resolved`.

The operation is terminology identity mapping only. It is not a diagnosis,
prognosis, treatment recommendation, or disease-state assertion.

## 8. Typed contract registry

`default_reference_annotation_contracts()` returns four ordered contracts. A
contract declares:

- capability ID and operation name;
- required input fields;
- output dimensions;
- accepted states;
- review states;
- permitted issue codes; and
- the safety boundary for interpretation.

The registry rejects duplicate capability IDs and duplicate operation names.
Payload validation runs before an adapter is invoked. This keeps an absent
input field distinct from a valid adapter result of `abstained`.

## 9. Evaluation receipts

`evaluate_reference_annotation_fixture()` performs these steps for every
record:

1. Resolve the operation contract.
2. Check required payload fields.
3. Parse the release-shaped input with the existing adapter.
4. Execute the explicit query.
5. Derive catalog and result states.
6. Preserve adapter issue codes.
7. Check expected state and issue-code floors.
8. Check positive/control role boundaries.
9. Check count and sanitized summary shape.
10. Address the resulting receipt.

The main fixture emits 120 checks: three fixture checks and 7 checks for each
of the 16 records, plus four closure checks. The report is accepted only when
every check passes.

Receipt fields are deliberately operational rather than raw:

| Field | Purpose |
|---|---|
| `catalog_state` | parser-level support or partial state |
| `catalog_count` | number of parsed rows, terms, or mappings |
| `resolution_state` | supported, ambiguous, or abstained |
| `match_count` | number of retained matches |
| `observed_issue_codes` | explicit review reasons |
| `summary` | sanitized operation-specific dimensions |
| `content_address` | deterministic receipt identity |

## 10. Replay and scenario matrix

The replay expectation checks fixture ID, version, context, catalog address,
positive floor, control floor, record floor, evaluation check floor, accepted
status, role boundaries, and receipt addresses.

The default check floor is 120 evaluation checks. Lowering that floor is a
contract change and requires a documented fixture version change.

The scenario matrix has 16 rows and repeats the declared expected states. A
scenario passes only when state, issue-code inclusion, and role boundary all
agree. Scenario output is addressed separately from evaluation output so a
state transition cannot be hidden by a summary count.

## 11. Evidence bundle

`ReferenceAnnotationBundleBuilder` creates two useful projections:

| Mode | Entries | Published |
|---|---:|---|
| review bundle | 16 | false |
| accepted-only bundle | 4 | true |

The bundle contains no input text. Each entry contains record identity,
capability, operation, role, exact context, result state, issue codes, match
count, source IDs, evidence boundary, and entry address.

The builder supports JSON, CSV, and Markdown. JSON is the canonical structured
projection. CSV is row-oriented for inspection. Markdown is intended for a
human review packet and retains addresses and issue codes.

`verify()` checks entry identity, entry addresses, bundle address, evidence
boundary, and the rule that a published bundle cannot contain a review entry.

## 12. Lineage and reconciliation

The canonical graph contains:

- 5 source nodes;
- 1 fixture node;
- 16 record nodes;
- 16 result nodes;
- 5 source-to-fixture declaration edges;
- 16 fixture-to-record containment edges;
- 22 source-to-record declaration edges; and
- 16 record-to-result production edges.

That produces 38 nodes and 59 edges. The lineage audit checks unique IDs,
context closure, source/record/result counts, fixture presence, edge counts,
and address retention.

Reconciliation compares evaluation receipt IDs, fixture record IDs, bundle
entry IDs, lineage record IDs, lineage result IDs, context, boundary, state
roles, operation closure, and address presence. It does not treat one view as
authoritative when the other view disagrees; disagreement remains a failed
check.

## 13. Quality gate and release decision

`evaluate_reference_annotation_quality_gate()` runs:

1. public-data audit;
2. contract registry checks;
3. fixture evaluation;
4. replay;
5. scenario matrix;
6. accepted-only bundle verification;
7. lineage audit; and
8. reconciliation.

The integrated gate emits 23 checks. It verifies 38/59 graph topology, a
120-check evaluation floor, 17 reconciliation checks, 16 scenarios, 4
publishable entries, exact context closure, and raw-input exclusion from
receipts.

`build_reference_annotation_release_manifest()` adds a final release layer.
It requires an accepted evaluation, accepted quality gate, accepted replay,
an accepted-only verified bundle, four contracts, five source receipts, and
one bundle entry per contract. The states are:

| State | Meaning |
|---|---|
| `published` | all release checks pass and four positive entries are publishable |
| `review` | evaluation and quality are valid but the publication projection is not complete |
| `blocked` | one or more core evidence gates fail |

The release manifest is independently content addressed and can be written as
JSON only after address and count verification.

## 14. Commands

The command surface is:

```text
python -m glio_noncode audit-reference-annotation-data examples/reference-annotation-public-aggregate.json
python -m glio_noncode evaluate-reference-annotation-fixture examples/reference-annotation-public-aggregate.json
python -m glio_noncode replay-reference-annotation-fixtures examples/reference-annotation-public-aggregate.json
python -m glio_noncode reference-annotation-quality-gate examples/reference-annotation-public-aggregate.json
python -m glio_noncode evaluate-reference-annotation-scenarios examples/reference-annotation-public-aggregate.json
python -m glio_noncode reference-annotation-contracts
python -m glio_noncode build-reference-annotation-bundle examples/reference-annotation-public-aggregate.json --output /tmp/reference-annotation-bundle.json --accepted-only
python -m glio_noncode reference-annotation-lineage examples/reference-annotation-public-aggregate.json
python -m glio_noncode reference-annotation-reconciliation examples/reference-annotation-public-aggregate.json
python -m glio_noncode run-reference-annotation-pipeline examples/reference-annotation-pipeline-accepted.json
python -m glio_noncode build-reference-annotation-release examples/reference-annotation-public-aggregate.json --output /tmp/reference-annotation-release.json
```

The accepted pipeline request publishes four entries. The review request uses
the same fixture with a GRCh37 context key and returns a nonzero status without
publishing.

## 15. Change rules

A change to any of the following requires fixture, test, documentation, and
address review:

- source URI, release, license, or access date;
- context key or evidence boundary;
- record payload, expected state, issue code, or role;
- adapter routing or summary fields;
- contract required fields, states, or issue codes;
- replay floors;
- bundle publication rule;
- lineage topology or edge identity;
- reconciliation closure; or
- release check count.

Do not remove a control to make a positive path pass. Add a new fixture version
when the public source grammar changes. Keep rejected, ambiguous, and
unresolved states explicit so downstream work can distinguish missing evidence
from contradictory evidence.

## 16. Verification checklist

Before a commit:

- the data audit is accepted;
- all 16 receipts are present;
- all four positives are supported;
- all 12 controls remain review states;
- the 120-check floor is met;
- replay is accepted;
- all 16 scenarios pass;
- review and accepted-only bundles verify;
- lineage is 38 nodes and 59 edges;
- reconciliation is accepted;
- the quality gate emits 23 passing checks;
- the release manifest is publishable;
- JSON, CSV, and Markdown projections render;
- the focused and full test suites pass; and
- added repository content contains no restricted authorship or tool metadata.
