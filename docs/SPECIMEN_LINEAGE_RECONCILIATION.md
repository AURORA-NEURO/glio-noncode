# Specimen lineage receipt reconciliation

This document specifies the cross-view reconciliation layer for the Domain 03
C09–C12 specimen-lineage release surface. It describes the receipt index, its
address rules, the audit checks, the command contract, and the release policy.
The layer is deliberately narrow: it joins already evaluated fixture records
to sanitized result receipts without exporting the fixture payload again.

## Purpose

The C09–C12 modules answer four related questions:

1. Can a specimen context be resolved into a structural lineage graph?
2. Can observations be linked across time without inventing a missing link?
3. Can primary, recurrence, and interval phases be classified from explicit
   evidence rather than inferred from ordering alone?
4. Can treatment exposure be assigned to a pre-treatment, on-treatment, or
   post-treatment window when the required temporal facts are present?

Each question has a fixture record, an evaluator result, a source receipt, and
one or more release checks. Those views are intentionally separate. The
fixture catalog contains the scenario inputs; the evaluator contains the
sanitized output; the source catalog contains public-data receipts; and the
quality gate contains the acceptance decision. Separation prevents a compact
summary from silently becoming a substitute for the evidence that produced
it.

The receipt index is the join point between those views. It gives every record
one stable row with enough information to verify identity, context, source
coverage, output state, and content addresses. It is not a new clinical data
model and it is not a replacement for the underlying evaluator. It is a
release integrity surface.

## Scope and non-goals

The reconciliation surface covers:

- the public aggregate fixture in
  `examples/specimen-lineage-public-aggregate.json`;
- the four C09–C12 operation identifiers;
- twelve fixture records, including four positive cases and eight review
  controls;
- evaluator output addresses and expected fixture states;
- source IDs and the exact six-part context key;
- deterministic content addresses for entries, the index, and the report;
- a recursive boundary check over the serialized index projection; and
- the command and continuous-integration invocation used for release checks.

It does not cover:

- private records, identifiers, or re-identification workflows;
- treatment recommendations or clinical decision support;
- an external database connection;
- statistical performance claims about a patient population;
- replacement of source-provider validation; or
- conversion of a review result into an accepted result by configuration.

The implementation consumes public-data-shaped, aggregate fixture material.
It carries no direct subject identifier and no raw fixture record in the
serialized index or report.

## Evidence boundary

The fixture has one exact context key:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The context is an addressable declaration, not a claim that every public
record has those values. The evaluator requires the declaration to remain
stable across all twelve records. If a record carries a different context,
the catalog validation or reconciliation audit must surface it as drift.

The public source receipts are retained in the fixture catalog. The current
source set is:

| Source ID | Use in the evidence surface |
| --- | --- |
| `gdc-biospecimen-submission` | documents case-to-sample and specimen hierarchy fields |
| `gdc-biospecimen-data` | documents sample, portion, analyte, and aliquot relationships |
| `gdc-tcga-barcode` | documents the hierarchical identity convention |
| `gdc-api-available-fields` | documents sample, collection, preservation, and clinical field availability |

The index records source IDs as a set-preserving tuple. The source-set check
compares that tuple to the catalog source set. An implementation may order the
source IDs deterministically, but it may not drop a receipt or add a receipt
outside the catalog without failing reconciliation.

## Data flow

The release path is:

```text
fixture catalog
    |
    +--> evaluator --------------------> sanitized result receipts
    |                                          |
    +--> record content addresses              |
                                               v
                                    receipt-index builder
                                               |
                                               v
                                      receipt index
                                               |
                                               v
                                    reconciliation audit
                                               |
                         +---------------------+---------------------+
                         |                                           |
                    quality gate                              release bundle
```

The builder evaluates the catalog once, maps each result receipt by
`record_id`, and creates one index entry per catalog record. It copies only
stable scalar fields and addresses. It never places the original record body
inside an entry.

The audit starts a fresh evaluator run. This is intentional. Reconciliation
must compare the stored index with an independently constructed result view;
otherwise a mutated index could be used to manufacture the result it is then
asked to verify.

## Receipt index schema

The index envelope contains:

| Field | Type | Rule |
| --- | --- | --- |
| `fixture_id` | string | must match the loaded fixture |
| `context_key` | string | must match the catalog’s exact context |
| `source_ids` | tuple of strings | must cover the catalog source set |
| `entries` | tuple | exactly one entry per fixture record |
| `content_address` | string | `sha256:` address of the canonical body |
| `entry_count` | integer | derived count in the serialized projection |
| `operation_ids` | sorted strings | derived set of covered operations |

Each entry contains:

| Field | Type | Rule |
| --- | --- | --- |
| `record_id` | string | unique fixture identity |
| `operation` | string | one of the four C09–C12 operations |
| `fixture_state` | string | expected catalog state |
| `result_state` | string | evaluator-observed state |
| `context_key` | string | exact catalog context |
| `source_ids` | tuple of strings | non-empty subset of catalog sources |
| `record_address` | string | fixture record content address |
| `result_address` | string | evaluator output address |
| `content_address` | string | canonical address of the entry body |

The `content_address` of an entry is computed from all fields except the
entry’s own content address. The index address is computed from the fixture,
context, source set, and entries, again excluding the index address itself.
The report address is computed from the fixture, state, and check objects.
This avoids a recursive hash while retaining tamper evidence for every
release surface.

## State semantics

`accepted` means that all reconciliation checks passed and that the state is
safe for the downstream release bundle. It does not mean that all twelve
scenarios are positive. The eight controls are expected to remain visible and
are expected to remain in review or blocked states according to their
operation contract.

`review` means at least one cross-view check failed. It is a release stop. The
caller must inspect `failed_check_ids`, locate the changed address or field,
and regenerate the index only after determining why the change occurred.
Regeneration is not a way to hide drift: the fresh audit still compares the
new index to a fresh evaluator run.

The reconciliation report exposes:

- `fixture_id`;
- `state`;
- the ordered check tuple;
- a report `content_address`;
- `passed`; and
- `failed_check_ids`.

Consumers should use `passed` and `failed_check_ids` rather than treating a
non-empty check list as proof of acceptance.

## Audit checks

The audit currently evaluates sixteen checks in a stable order.

| Order | Check ID | Assertion |
| ---: | --- | --- |
| 1 | `fixture-id` | index fixture identity equals catalog identity |
| 2 | `context` | index context equals catalog context |
| 3 | `source-set` | index source set equals catalog source set |
| 4 | `entry-floor` | entry count equals catalog record count |
| 5 | `record-identity` | entry identities equal catalog record identities |
| 6 | `record-uniqueness` | no entry identity is duplicated |
| 7 | `operation-coverage` | all four operation IDs are represented |
| 8 | `context-consistency` | every entry carries the catalog context |
| 9 | `source-consistency` | every entry source set is covered by the catalog |
| 10 | `record-addresses` | every record address matches the catalog record |
| 11 | `result-addresses` | every result address matches the fresh evaluation |
| 12 | `state-alignment` | every result state matches the fresh evaluation |
| 13 | `entry-addresses` | every entry address matches its canonical body |
| 14 | `index-address` | index address matches its canonical body |
| 15 | `address-uniqueness` | every result address is unique |
| 16 | `sanitized-index` | serialized index contains no forbidden raw fields |

The checks are independent enough to provide useful diagnosis. For example,
an output address mutation should fail `result-addresses` and usually
`entry-addresses`, while leaving `fixture-id`, `context`, and the record floor
untouched. A duplicate record ID should fail identity and uniqueness checks;
it must not be silently collapsed into a dictionary.

## Sanitization boundary

The index projection is intentionally aggregate. The recursive key boundary
rejects the following names wherever they occur:

```text
records, raw_records, payload, patient_id, subject_id,
medical_record_number, sample_patient_id, participant_id,
case_uuid, individual_id, person_id
```

This is a field-name boundary, not a claim that arbitrary free text can be
made safe by serialization. The source fixture remains local to the evaluator
and its public-data-shaped scenario definitions. The index and report expose
only record identities designed for the fixture, operation/state labels,
context, source IDs, and content addresses.

Future fields must be reviewed against the boundary before they are added to
the public projection. A field that can contain a direct identifier belongs in
the evaluator’s private working input, not in the receipt index.

## Drift scenarios

The tests exercise the most important failure modes:

1. Result address drift changes a result address while retaining the record
   identity. The evaluator comparison must catch it.
2. Context drift changes one entry’s context. The entry consistency check must
   catch it even if all content addresses remain syntactically valid.
3. Duplicate record identity replaces one entry ID with another entry ID. The
   uniqueness check must catch it without raising a lookup failure.
4. Missing record removes an entry. The entry floor and identity checks must
   catch the omission.
5. Entry address drift changes an entry address without changing its fields.
   The canonical entry-body check must catch it.
6. Source drift changes the catalog-to-index source relationship. The source
   set and source consistency checks must identify the mismatch.
7. State drift changes a result state while retaining its result address. The
   fresh evaluator comparison must catch the mismatch.
8. Index address drift changes only the envelope address. The canonical index
   body check must catch the mismatch.

These are integrity tests, not clinical validation tests. A passing result
means that the release surfaces agree with each other and the declared public
fixture. It does not establish biological, diagnostic, or treatment efficacy.

## Command contract

Run the command from the repository root:

```powershell
python -m glio_noncode specimen-lineage-reconciliation `
  examples/specimen-lineage-public-aggregate.json `
  --output lineage-reconciliation.json
```

The JSON projection contains an `index` object, an `audit` object, and
convenience fields for `entry_count`, `operation_ids`, and `passed`. The
command returns exit code `0` for an accepted audit and a non-zero code for a
review result or invalid input. The output path is optional; when omitted,
the projection is written to standard output.

The direct Python API is:

```python
catalog = SpecimenLineageFixtureCatalog.from_file(path)
index = build_specimen_lineage_receipt_index(catalog)
audit = audit_specimen_lineage_receipt_index(catalog, index)
```

The `index` object is immutable and the report is immutable. This makes it
safe to pass the objects between the quality gate, bundle builder, and tests
without hidden mutation of a shared receipt.

## Quality-gate integration

The C09–C12 quality gate includes the reconciliation audit as one of its
checks. The quality report carries both `receipt_index_address` and
`receipt_reconciliation_address`, so a bundle consumer can link from the
quality result to the exact index and audit content without embedding the
index rows in every artifact.

The integrated gate has twenty-two checks:

- fixture and source integrity checks;
- four operation coverage checks;
- evaluator check conservation;
- replay agreement;
- scenario-matrix agreement;
- contract agreement;
- lineage graph agreement;
- runtime-stage agreement; and
- the sixteen receipt-index reconciliation checks as one grouped gate result.

The grouped quality check retains the reconciliation report address in the
quality report. A consumer that needs per-check detail can call the dedicated
command or inspect the report object returned by the API.

## Bundle and CI policy

The accepted bundle may include the index address, audit address, and their
summary states. It must not inline raw fixture records. A review audit may be
written for debugging, but it cannot be published as an accepted bundle.

Continuous integration runs the following command against the checked-in
public aggregate fixture:

```text
python -m glio_noncode specimen-lineage-reconciliation examples/specimen-lineage-public-aggregate.json --output /tmp/glio-specimen-lineage-reconciliation.json
```

The workflow also runs the complete unit-test discovery command, compilation,
lint checks, the evaluator, the public-data audit, replay, quality gate,
scenario matrix, contract projection, bundle builder, lineage graph, and the
four-stage runtime. A release is eligible only when every command and the
full suite pass.

## Change rules

When adding a record:

1. Add the record to the public aggregate fixture with a clear operation and
   expected state.
2. Keep the exact context key unless the entire fixture version is being
   intentionally revised.
3. Ensure the record has source IDs covered by the catalog source set.
4. Add or update the operation-specific evaluator expectation.
5. Add a scenario assertion or an explicit control test when behavior changes.
6. Regenerate derived addresses through the typed builders, not by editing
   hashes manually.
7. Update the evidence and capability ledgers with the new count.
8. Run the complete verification commands before publishing.

When changing the schema:

1. Update the dataclass and canonical address body together.
2. Add a migration note to this document and the bundle format document.
3. Add a positive round-trip test and at least one drift test.
4. Recheck the sanitization boundary for every new field.
5. Keep check IDs stable when the assertion meaning is unchanged.
6. Add a new check ID rather than reusing an old ID for a different meaning.

When changing a source receipt:

1. Confirm the URL and source purpose remain authoritative.
2. Preserve the source ID when the receipt meaning is unchanged.
3. Update the source snapshot or fixture version when the meaning changes.
4. Re-run the source-set, source-consistency, and evidence audits.

## Review checklist

Before merging a C09–C12 change, reviewers should be able to answer yes to
each question below:

- Does the public fixture still contain four positive and eight control
  records, or is the changed count documented?
- Does every record map to exactly one evaluator receipt?
- Are all four operation IDs covered?
- Is the context key identical at the catalog, entry, index, and result
  surfaces?
- Are record, result, entry, index, and report addresses deterministic?
- Does a mutated result address fail the audit?
- Does a duplicated record identity fail the audit?
- Does a missing entry fail the audit?
- Does the serialized index pass the forbidden-key boundary?
- Does the quality gate report the reconciliation address?
- Does the CLI return the expected exit code?
- Does the full test suite pass without weakening prior module coverage?

## Current release snapshot

The checked-in aggregate fixture currently has twelve records across four
operations. The index contains twenty-nine address-bearing values when the
record, result, entry, index, and report surfaces are considered together;
the graph surface independently exposes twenty-nine nodes and twenty-eight
edges. The reconciliation audit has sixteen checks and is included in the
twenty-two-check quality gate.

These counts are release facts for the checked-in fixture, not universal
properties of future data. Any fixture expansion must update the counts,
tests, evidence ledger, and release notes in the same build.
