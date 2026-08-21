# Reference annotation release manifest format

This format describes the final publication projection for Domain 04 C05–C08.
It is separate from the raw adapter result, the fixture, the bundle, and the
lineage graph. The separation keeps a release decision auditable and prevents
a convenience count from replacing operation evidence.

## Envelope

```json
{
  "release_id": "reference-annotation-c05-c08",
  "fixture_id": "reference-annotation-public-aggregate",
  "fixture_version": "2026.08.c05-c08.v1",
  "context_key": "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
  "state": "published",
  "source_ids": ["..."],
  "capability_ids": ["GNC-D04-C05", "GNC-D04-C06", "GNC-D04-C07", "GNC-D04-C08"],
  "entry_count": 4,
  "accepted_count": 4,
  "review_count": 0,
  "checks": [],
  "content_address": "sha256:..."
}
```

The envelope has no input text, parser rows, ontology definitions, or query
payloads. Those remain in the fixture and adapter-specific evidence layers.

## Required fields

| Field | Type | Rule |
|---|---|---|
| `release_id` | string | stable release projection ID |
| `fixture_id` | string | must match evaluation, quality, and bundle |
| `fixture_version` | string | must match every release input |
| `context_key` | string | exact ordered six-part context |
| `state` | enum | `published`, `review`, or `blocked` |
| `source_ids` | array | five declared public receipt IDs |
| `capability_ids` | array | four Domain 04 IDs in registry order |
| `entry_count` | integer | accepted plus review counts |
| `accepted_count` | integer | supported entries in the publication bundle |
| `review_count` | integer | review entries in the publication bundle |
| `checks` | array | addressed release checks |
| `content_address` | string | hash over all other envelope fields |

## Release checks

The default manifest emits fourteen release checks:

1. fixture identity closure;
2. fixture version closure;
3. context closure;
4. accepted evaluation;
5. accepted quality gate;
6. accepted replay;
7. verified bundle;
8. accepted-only bundle state;
9. four positive entries;
10. zero review entries;
11. four registered contracts;
12. five source receipts;
13. capability closure; and
14. one accepted entry per contract.

Each check contains an ID, Boolean result, detail, and content address. A
published manifest requires every check to pass.

## State transitions

```text
quality accepted + replay accepted + accepted-only bundle verified
        |                         |
        | all release checks pass |
        v                         v
    published                 review or blocked
```

The state is `published` only if every check passes. If evaluation and quality
are accepted but the publication projection is incomplete, the state is
`review`. If a core evidence gate fails, the state is `blocked`.

## Count invariants

The following identities are checked before writing:

```text
accepted_count + review_count = entry_count
accepted_count = 4 for the accepted-only release
review_count = 0 for the accepted-only release
len(capability_ids) = 4
len(source_ids) = 5
```

The verifier also checks every check address, the manifest address, nonnegative
counts, and the rule that a published state cannot contain a failed check.

## Source closure

The release manifest carries source IDs only. Source URI, release, license, and
scope remain in the public-data fixture receipt layer. This means a release
comparison can detect a source-set change without copying a source document into
the release output.

The current closure is:

```text
GNC-D04-C05 -> gencode-human, gencode-format
GNC-D04-C06 -> ncbi-mane, gencode-human
GNC-D04-C07 -> obo-ro
GNC-D04-C08 -> obo-mondo
```

The full five-source receipt set also includes `gencode-format` and
`gencode-human` for the transcript boundary. A source can support more than
one capability, but an undeclared source cannot be introduced by a bundle
projection.

## Write protocol

The write function performs these operations:

1. verify source and capability closure;
2. verify count reconciliation;
3. verify every check address;
4. verify the manifest address;
5. reject an invalid manifest; and
6. write sorted, indented JSON with a terminal newline.

Writing is therefore a release action after all evidence objects have been
constructed. It does not fetch data, mutate the fixture, or recalculate adapter
results.

## Review behavior

A review manifest is useful when a bundle is built with all sixteen records or
when a context mismatch is intentionally inspected. Review output is preserved
for diagnosis but cannot be passed to the publication path by changing a
Boolean convenience field.

Examples of review conditions include:

- one source receipt is missing;
- one record points to an undeclared source;
- a MANE gene query returns two rows;
- a regulatory alias resolves to two terms;
- a disease source term has two target namespaces;
- an evaluation state differs from the fixture expectation;
- a bundle contains a control entry; or
- the context key is not exact.

Each condition remains visible as a failed check or review state. No condition
is silently converted to supported.

## Compatibility

The release ID, fixture version, capability IDs, field names, state values, and
check IDs are compatibility surfaces. A breaking change requires a new fixture
version and a documentation update. Additive check detail can be introduced
when the existing check ID and pass semantics remain stable.

The release format intentionally stores operation IDs instead of adapter class
names. This keeps the public projection stable when an internal implementation
is refactored while preserving the capability contract.
