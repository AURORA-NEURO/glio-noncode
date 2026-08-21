# Structural beta evidence bundle format

## Overview

The structural beta bundle is the compact publication projection for Domain 02
C05-C08. It is built by `StructuralBetaEvidenceBundleBuilder` from the public
aggregate fixture. The builder executes the complete quality gate first. A
failing gate raises a validation error unless the caller explicitly requests a
review bundle with `allow_review=True` or `--allow-review`.

The bundle is a receipt and index, not a replacement for the detector output.
It retains stable identities, states, summaries, source IDs, component
addresses, and quality results. It deliberately excludes raw detector records,
subject identifiers, patient identifiers, and sensitive operation payloads.

## Supported projections

| Projection | Extension | Intended use | Address verification |
| --- | --- | --- | --- |
| JSON | `.json` | canonical machine-readable bundle | supported |
| CSV | `.csv` | flat entry review table | rows only; verify the JSON root |
| Markdown | `.md` or `.markdown` | compact human review | display projection |

Use the CLI:

```powershell
python -m glio_noncode build-structural-beta-bundle examples/structural-beta-public-aggregate.json --output beta-bundle.json
python -m glio_noncode build-structural-beta-bundle examples/structural-beta-public-aggregate.json --output beta-bundle.csv --format csv
python -m glio_noncode build-structural-beta-bundle examples/structural-beta-public-aggregate.json --output beta-bundle.md --format markdown
```

The Python API is:

```python
from glio_noncode.structural_beta_bundle import StructuralBetaEvidenceBundleBuilder

bundle = StructuralBetaEvidenceBundleBuilder().build(
    "examples/structural-beta-public-aggregate.json",
    bundle_id="local-beta-bundle",
)
assert bundle.accepted
assert bundle.verify(bundle.to_dict())
```

## JSON root

The JSON root contains the following stable fields:

| Field | Type | Rule |
| --- | --- | --- |
| `bundle_id` | string | caller-selected or fixture-derived identity |
| `fixture_id` | string | source fixture identity |
| `fixture_version` | string | fixture schema version |
| `context_key` | string | exact six-field context |
| `source_ids` | array of strings | sorted public source receipt IDs |
| `entries` | array | twelve sanitized entry objects |
| `component_summaries` | object | fixture, scenario, quality, and lineage summaries |
| `contract_manifest` | object | four-operation contract manifest |
| `quality_summary` | object | gate state, check counts, and addresses |
| `lineage_address` | string | address of the 29-node/36-edge graph |
| `content_address` | string | address of the complete canonical body |
| `state` | enum | `accepted` or `review` |
| `accepted` | boolean | convenience field derived from state |
| `entry_count` | integer | convenience count derived from entries |
| `positive_entry_count` | integer | convenience count derived from entries |
| `review_entry_count` | integer | convenience count derived from entries |

The five convenience fields are not part of the content address. This lets a
verifier detect mutation of the substantive body while avoiding false failure
from a recomputed display count. The substantive root fields are included in
the hash body in the order-independent JSON representation used by the local
serialization helper.

## Entry object

Every entry is a `StructuralBetaBundleEntry` with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `entry_id` | string | `positive:<record_id>` or `review:<record_id>` |
| `entry_class` | enum | `positive` or `review` |
| `capability_id` | string | one of GNC-D02-C05 through GNC-D02-C08 |
| `operation` | string | detector operation name |
| `state` | string | fixture receipt state, usually accepted/review |
| `result_state` | string | detector result state |
| `structural_identifier` | string | sanitized record identity |
| `source_id` | string | public source receipt identity |
| `evidence_address` | string | detector output address |
| `summary` | string | bounded operation detail |

Entries are sorted by `(entry_class, capability_id, entry_id)`. With the
canonical fixture, all four positive entries sort before all eight review
entries. This ordering is part of the addressed body and prevents filesystem
or JSON insertion order from changing the bundle.

The entry class describes the fixture expectation, not the detector result
strength. A review entry may carry a useful partial or ambiguous detector
state. A positive entry is included only after its positive fixture checks pass.

## Component summaries

`component_summaries` contains four bounded summaries:

### Fixture summary

The fixture summary includes the number of evaluator checks, the number that
passed, the positive record count, and the review-control count. The canonical
values are 63, 63, 4, and 8.

### Scenario summary

The scenario summary includes twelve scenarios, four positive scenarios, eight
review scenarios, and the matrix pass state. It does not include raw scenario
payloads.

### Quality summary

The quality summary includes:

- gate state;
- pass boolean;
- twenty-check count;
- failed check IDs;
- evidence boundary text;
- quality report address;
- lineage address.

The quality address points to the complete quality report, while the lineage
address points to the complete sanitized graph. Both addresses are retained so
a reviewer can compare the bundle to independently generated components.

### Lineage summary

The lineage summary includes 29 nodes, 36 edges, graph state, and graph content
address. It is a shape summary only; node and edge payloads are available from
the separate lineage command and are still sanitized.

## Contract manifest

The contract manifest is the output of
`default_structural_beta_contract_registry().manifest()`. It contains four
contracts, one per operation, with capability ID, accepted result states,
review result states, required input fields, output fields, provenance fields,
and safety notes. The bundle embeds the manifest so the interpretation of
`state` and `result_state` is versioned with the entries.

The manifest does not authorize a scientific conclusion. It defines the local
adapter boundary and the states that must remain visible when evidence is
missing, conflicting, out of domain, or structurally invalid.

## Quality and lineage relationship

The bundle cannot be accepted without a passing quality gate. The quality gate
itself builds and audits the lineage graph using the same evaluation report.
The builder then reuses that evaluation to construct entries and recomputes the
lineage address. A verifier can therefore compare:

```text
bundle.quality_summary.quality_address
bundle.quality_summary.lineage_address
bundle.lineage_address
component_summaries.lineage.content_address
```

The two lineage address fields and the component summary address must agree.
The quality address must be a `sha256:` content address. An address mismatch is
review-worthy even if the visible entry table looks unchanged.

## State semantics

The root state is derived from the quality gate:

| Root state | Meaning | Default write behavior |
| --- | --- | --- |
| `accepted` | all 20 quality checks pass | written normally |
| `review` | one or more quality checks fail | rejected unless override |

`--allow-review` is an inspection override. It does not turn a review bundle
into an accepted bundle, change the failed check IDs, or change the root state.
Review bundles are useful for examining drift and controls, but they must not be
promoted without repairing the failed fixture or updating its declared contract
with an independent review decision.

The bundle builder does not define a `blocked` root state because blocked
pipeline execution is represented by the runtime report before bundle
publication. A request with no executable stage input does not produce a beta
evidence bundle.

## Address rules

All operation evidence addresses, lineage node addresses, lineage edge
addresses, lineage graph addresses, quality component addresses, and bundle
addresses begin with `sha256:` followed by a 64-character hexadecimal digest.

The JSON verifier is intentionally narrow:

```python
from glio_noncode.structural_beta_bundle import StructuralBetaEvidenceBundleBuilder

payload = json.loads(Path("beta-bundle.json").read_text())
if not StructuralBetaEvidenceBundleBuilder.verify(payload):
    raise ValueError("bundle body or address changed")
```

The verifier removes only convenience fields before hashing. It does not trust
the `accepted` boolean or entry counts. Mutation of an entry state, source ID,
summary, quality address, lineage address, contract manifest, or root state
invalidates the content address. Mutation of only a convenience count leaves
the substantive address check unchanged, after which a consumer may recompute
the count and flag presentation drift separately.

CSV and Markdown are projections. A consumer requiring cryptographic integrity
should retain the JSON root and verify it before using either projection.

## Raw payload boundary

The following classes of information are excluded from the bundle:

- raw detector records;
- raw issue objects and implementation-specific exception text;
- patient or subject identifiers;
- sample identifiers;
- unbounded source rows;
- opaque input blobs;
- private coordinates not included in the aggregate fixture contract.

The bundle retains only the record identity, operation, expected class, observed
states, public source ID, output address, and short summary. A caller requiring
raw diagnostic detail should inspect the local detector invocation under its
own access controls; it should not add the payload to the public bundle.

## CSV projection

The CSV header is fixed and contains ten columns:

```text
entry_id,entry_class,capability_id,operation,state,result_state,structural_identifier,source_id,evidence_address,summary
```

There is one row per entry, so the canonical file has thirteen lines: one header
and twelve entries. CSV field quoting is handled by the standard writer. The
CSV does not repeat the root context, source list, contract manifest, quality
address, or lineage address; those remain in the JSON root.

## Markdown projection

The Markdown projection contains:

1. a title and bundle identity;
2. fixture version and exact context;
3. root state and content address;
4. a twelve-row entry table;
5. an evidence-boundary section;
6. a public source ID list.

Markdown is for inspection and issue discussion. It is not an interchange
format and is not independently address-verified.

## Review workflow

When a bundle build is rejected:

1. run the data audit to distinguish source/scope drift from detector drift;
2. run the fixture evaluator and inspect failed record check IDs;
3. run the scenario matrix to classify expected state-transition drift;
4. run the quality gate to identify cross-surface disagreement;
5. inspect the lineage audit for context, source, endpoint, or pairing errors;
6. repair the fixture or adapter contract;
7. rerun the complete command sequence;
8. build without `--allow-review` only after the gate passes.

Do not repair a failed result by deleting a control, removing an issue code from
the declaration, or changing a result to accepted without examining the
adapter behavior. Controls are part of the release boundary and their review
states are intentionally preserved.

## Runtime handoff

The accepted runtime fixture produces four stage receipts and a manifest that
contains only stage IDs, stage addresses, request identity, source IDs, context,
and schema version. The runtime manifest is not the same object as the evidence
bundle. The normal handoff is:

```text
pipeline request
  -> stage receipts
  -> sanitized runtime manifest
  -> public aggregate fixture evaluation
  -> quality gate
  -> evidence bundle
```

The runtime report may be accepted while the separate public fixture bundle is
being evaluated in another process. Consumers should retain both addresses and
not treat the runtime manifest as proof that the quality gate passed.

## Compatibility and extension rules

Any schema revision must:

- change the fixture or contract schema version;
- add a migration note;
- preserve old parser behavior or reject it explicitly;
- update the content-addressed test vectors;
- add positive and review fixtures for new fields;
- update the quality check count and documentation;
- keep aggregate-only scope explicit;
- update the Actions command sequence.

New operation fields should be added to the typed contract, evaluator, bundle
entry or component summary only when the field has a stable meaning and a
negative-control behavior. An untyped passthrough field is not considered a
verified extension.

## Bundle verification checklist

Before sharing a JSON bundle, verify:

- the root `state` is accepted;
- `accepted` agrees with `state`;
- `entry_count` recomputes to twelve;
- four entries are positive and eight are review;
- capability IDs cover C05, C06, C07, and C08;
- every evidence address has the expected prefix and length;
- the quality check count is twenty with no failed IDs;
- the lineage summary is 29 nodes and 36 edges;
- the lineage address fields agree;
- the source IDs are public aggregate receipts;
- `StructuralBetaEvidenceBundleBuilder.verify` returns true;
- the serialized content contains no raw operation or subject fields.
