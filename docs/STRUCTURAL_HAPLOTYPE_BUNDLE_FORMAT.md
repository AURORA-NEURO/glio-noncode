# Structural haplotype bundle format

The C09-C12 evidence bundle is a compact release projection of the public
aggregate fixture. It is designed for review, archival comparison, and
downstream report rendering. It is not a replacement for the typed operation
reports and does not carry raw operation payloads.

## Builder contract

The builder is exposed as:

```python
from glio_noncode.structural_haplotype_bundle import (
    StructuralHaplotypeBundleFormat,
    StructuralHaplotypeEvidenceBundleBuilder,
)

bundle = StructuralHaplotypeEvidenceBundleBuilder().build(
    "examples/structural-haplotype-public-aggregate.json",
    bundle_id="reviewable-haplotype-bundle",
)
text = bundle.render(StructuralHaplotypeBundleFormat.JSON)
```

The builder performs these actions in order:

1. parse and validate the fixture catalog;
2. run the 20-check quality gate;
3. refuse failed quality unless `allow_review=True`;
4. execute the twelve fixture records;
5. build the sanitized 29-node/36-edge lineage graph;
6. run the independent scenario matrix;
7. collect contract metadata and component summaries;
8. create twelve sorted bundle entries;
9. calculate a deterministic content address;
10. render JSON, CSV, or Markdown.

The default builder is strict. A review bundle is an explicit diagnostic
artifact and retains `state: review`; it must not be treated as a release.

## Top-level JSON

The canonical JSON projection has this shape:

```json
{
  "bundle_id": "structural-haplotype-public-aggregate-2026-08-21-bundle",
  "fixture_id": "structural-haplotype-public-aggregate-2026-08-21",
  "fixture_version": "structural-haplotype-evidence-v1",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "source_ids": [],
  "entries": [],
  "component_summaries": {},
  "contract_manifest": {},
  "quality_summary": {},
  "lineage_address": "sha256:...",
  "content_address": "sha256:...",
  "state": "accepted",
  "accepted": true,
  "entry_count": 12,
  "positive_entry_count": 4,
  "review_entry_count": 8
}
```

The example omits source and entry values only to keep the schema readable.
The actual renderer emits stable sorted JSON with all fields.

### Identity fields

`bundle_id` is caller-selectable but must be non-empty. `fixture_id` and
`fixture_version` come from the catalog. `context_key` and `source_ids` are
copied from the audited catalog. The content address covers the structural
bundle body before convenience counts are added.

`lineage_address` points to the sanitized lineage graph address. It gives a
reviewer a stable handle for comparing source-to-result topology without
embedding the graph twice in the bundle.

### Component summaries

The summary object contains four named components:

```json
{
  "fixture": {
    "check_count": 72,
    "passed_count": 72,
    "positive_count": 4,
    "review_control_count": 8
  },
  "scenarios": {
    "scenario_count": 12,
    "positive_count": 4,
    "review_count": 8,
    "passed": true
  },
  "quality": {
    "check_count": 20,
    "passed_count": 20,
    "state": "accepted"
  },
  "lineage": {
    "node_count": 29,
    "edge_count": 36,
    "state": "accepted",
    "content_address": "sha256:..."
  }
}
```

The summaries are reconciliation values, not new evidence. A consumer that
needs individual issue codes or record checks should load the evaluator or
quality report directly.

### Quality summary

`quality_summary` records the gate state, pass value, count, failed check IDs,
evidence boundary, quality address, and lineage address:

```json
{
  "state": "accepted",
  "passed": true,
  "check_count": 20,
  "failed_check_ids": [],
  "evidence_boundary": "public aggregate C09-C12 structural haplotype, allele, graph, and repeat observations",
  "quality_address": "sha256:...",
  "lineage_address": "sha256:..."
}
```

## Entry schema

Each entry is a sanitized summary of one fixture record.

| Field | Type | Description |
| --- | --- | --- |
| `entry_id` | string | `positive:<record_id>` or `review:<record_id>` |
| `entry_class` | enum | `positive` or `review` |
| `capability_id` | string | GNC-D02-C09 through GNC-D02-C12 |
| `operation` | string | registered operation name |
| `state` | string | observed fixture state |
| `result_state` | string | adapter result state |
| `structural_identifier` | string | stable record identifier |
| `source_id` | string | source receipt identity |
| `evidence_address` | string | operation receipt address |
| `summary` | string | bounded human-readable result detail |

Every evidence address starts with `sha256:`. Entries are sorted by entry
class, capability ID, and entry ID. Sorting removes source-file ordering as a
cause of bundle drift.

The bundle contains exactly four positive entries and eight review entries for
the canonical fixture. A consumer should use `entry_class` to distinguish
positive evidence from controls; `state` alone is not sufficient because a
review control can have a detector result such as `ambiguous`, `partial`, or
`contradictory`.

## Sanitization policy

The following are deliberately excluded from entries, summaries, contract
manifests, and lineage nodes:

- raw operation records;
- sequence strings and graph node sequences;
- sample-level identifiers;
- patient, subject, or medical-record identifiers;
- unbounded source payloads;
- internal exception text that could echo an input payload.

The builder checks output objects through a verification boundary. It does not
assume that convenience fields such as `accepted` or `entry_count` are
trustworthy when verifying a serialized payload; the check removes those
fields and recomputes the structural body address.

The exclusion is intentionally conservative. A future field should be added
only when it has a bounded schema, an explicit source/provenance meaning, and
tests proving that it cannot echo a raw row.

## JSON verification

`StructuralHaplotypeEvidenceBundleBuilder.verify` accepts a parsed mapping and
checks the minimum release structure:

```python
payload = json.loads(bundle_path.read_text(encoding="utf-8"))
assert StructuralHaplotypeEvidenceBundleBuilder.verify(payload)
```

Verification requires:

- schema version and state;
- non-empty fixture, context, and source IDs;
- exactly twelve entries;
- four positive and eight review entries;
- valid operation-to-capability mapping;
- unique entry IDs;
- addressed evidence and lineage values;
- quality summary with twenty checks;
- component summary counts;
- no disallowed raw fields;
- content address matching the normalized structural body.

The verifier does not rerun the operation adapters. For a full release gate,
run the quality command first and then verify the emitted bundle.

## CSV projection

CSV contains one row per entry and the following header in a stable order:

```text
entry_id,entry_class,capability_id,operation,state,result_state,structural_identifier,source_id,evidence_address,summary
```

CSV is intended for flat review tables. It intentionally omits component
summaries, contracts, source receipt details, and the bundle address. Use JSON
for archival interchange. Values are escaped with the standard CSV writer,
and rows use UTF-8 with a final newline.

## Markdown projection

Markdown begins with:

```markdown
# Structural haplotype evidence bundle
```

The header records bundle identity, fixture/version, exact context, state,
content address, and entry count. A table then lists all twelve entries with
class, capability, operation, state, result, structural identifier, and
evidence address. The final sections expose the evidence boundary and source
IDs.

Markdown is a human-readable view. It should not be parsed as the canonical
machine format, and it does not repeat raw payloads.

## Address model

All addresses are deterministic SHA-256 content addresses of normalized typed
data. The address inputs are:

| Address | Covered body |
| --- | --- |
| entry `evidence_address` | one sanitized operation receipt |
| `lineage_address` | typed lineage nodes and edges |
| `quality_address` | quality checks and reconciliation metadata |
| `content_address` | bundle identity, entries, summaries, contracts, and state |

Changing a source ID, context, result state, issue code, entry ordering after
normalization, or quality result changes the corresponding address. Renderer
choice does not change the JSON body address.

## Review and publication workflow

```text
public fixture
      |
      v
data audit -----> operation evaluation -----> quality gate
                                                   |
                              +--------------------+-------------------+
                              |                                        |
                         accepted                             review/failed
                              |                                        |
                       strict bundle                        diagnostic bundle only
```

For an accepted release:

```powershell
python -m glio_noncode structural-haplotype-quality-gate examples/structural-haplotype-public-aggregate.json --output quality.json
python -m glio_noncode build-structural-haplotype-bundle examples/structural-haplotype-public-aggregate.json --format json --output bundle.json
python -c "import json; from glio_noncode.structural_haplotype_bundle import StructuralHaplotypeEvidenceBundleBuilder as B; p=json.load(open('bundle.json')); assert B.verify(p)"
```

For a review artifact:

```powershell
python -m glio_noncode build-structural-haplotype-bundle examples/structural-haplotype-public-aggregate.json --allow-review --format markdown --output review-bundle.md
```

The `--allow-review` flag does not turn a failed gate into accepted evidence;
it permits inspection of the bounded review projection.

## Compatibility and evolution

The current schema version is `structural-haplotype-evidence-v1`. A compatible
change may add optional summary fields while retaining existing meaning and
address rules. A breaking change includes any of the following:

- changing the exact context grammar;
- changing entry identity or sort order;
- changing the meaning of `positive` or `review`;
- embedding raw operation payloads;
- changing operation-to-capability mapping;
- changing the address normalization contract;
- removing a required summary or quality field.

Breaking changes require a new schema version, a new fixture ID, migration
notes, and a fresh quality-gate report. Old bundles remain valid historical
artifacts and must not be rewritten in place.

## Source and scientific limitations

The bundle records source receipts from public aggregate resources, including
[NCBI dbVar](https://www.ncbi.nlm.nih.gov/dbvar/) and the
[gnomAD-SV v4 release description](https://gnomad.broadinstitute.org/news/2023-11-v4-structural-variants/).
Those receipts do not make the compact fixture complete, clinical, or
population representative.

The bundle cannot establish long-read phasing, allele assignment at the
molecule level, graph sequence homology, complete repeat annotation,
transposition, pathogenicity, prognosis, or treatment response. It is a
deterministic software evidence projection with explicit review controls.
