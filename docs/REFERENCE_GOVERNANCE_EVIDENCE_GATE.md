# Domain 04 C09–C12 reference governance evidence gate

This slice makes four reference-boundary capabilities executable:

| Capability | Operation | Supported evidence | Review evidence |
|---|---|---|---|
| C09 | gene alias/version resolution | exact declared ID, symbol, alias, assembly, and version | ambiguity, unknown identity, assembly mismatch |
| C10 | population frequency adaptation | bounded AF or AC/AN-derived AF with population and build | conflicting rows, missing counts, build mismatch |
| C11 | reference snapshot manager | sorted content-addressed manifest with checksum, size, source, and license | hash drift, duplicate identity, out-of-context assembly |
| C12 | license/use restriction registry | explicit permission for requested use | absent, expired, commercial, redistribution, or conflicting terms |

The fixture is a public aggregate evidence boundary. It is not a downloaded
release, a subject-level dataset, a clinical interpretation, or a permission
to fetch bytes. The five source receipts identify public authorities and the
scope of each boundary:

- [HGNC downloads](https://www.genenames.org/download/) for public gene data
  files, aliases, and release-shaped records.
- [HGNC](https://hgnc.genenames.org/) for nomenclature authority context.
- [NCBI RefSeq](https://www.ncbi.nlm.nih.gov/refseq/) for reference-sequence
  identity and assembly context.
- [SPDX License List](https://spdx.org/licenses/) for canonical license IDs.
- [SPDX MIT identifier](https://spdx.org/licenses/MIT) for a canonical
  permission and attribution boundary.

## Evidence boundary

The fixture uses the exact context key:

```text
GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline
```

The fixture version is `2026.08.c09-c12.v1`. All records use the
`public_aggregate_non_patient` boundary. The payloads contain declared source
fields and deterministic controls, but no subject identifier, patient
identifier, or sample identifier.

There are 16 records:

- four positive records, one for each operation;
- twelve controls, three for each operation;
- one source receipt per declared public boundary, with source URI, release,
  access date, license, scope, and content address;
- one record content address per executable payload.

The fixture loader accepts the descriptor below. The full executable records
are defined in the public-data module so the checked-in example remains small
and stable.

```json
{
  "fixture": "default_reference_governance_fixture"
}
```

## C09 gene alias/version resolver

The C09 adapter is intentionally identifier-bounded. A record may contain a
gene ID, symbol, aliases, version, assembly, source ID, and source version.
The resolver indexes each declared identity value and retains the exact match
basis in every match receipt.

The positive case queries `GLIO-1` and resolves a single record with a declared
HGNC-shaped ID and version. The ambiguity control gives two records the same
symbol. The unknown control queries an unlisted alias. The assembly control
supplies a complete record from GRCh37 while requesting GRCh38.

The resolver does not infer identity from a description. It does not decide
that two records from different releases are equivalent. A versionless query
may remain ambiguous when multiple versions are declared. That ambiguity is a
valid result and is not collapsed by sorting or by choosing the newest row.

Representative result fields:

```json
{
  "query_id": "gene-positive",
  "state": "supported",
  "match_basis": ["alias"],
  "versioned_id": "HGNC:1234.2",
  "assembly": "GRCh38",
  "source_version": "2026.08"
}
```

Review states include `ambiguous`, `partial`, and `out_of_domain`. The
execution receipt keeps the state, record count, match count, issue codes, and
versioned IDs while excluding the source payload.

## C10 population frequency adapter

C10 retains population scope rather than flattening all observations into one
number. Each observation preserves variant ID, population ID, ancestry, AC,
AN, homozygote count, declared or derived AF, genome build, source identity,
source version, and raw row address.

When AF is absent and AC and AN are present, AF is derived as `AC / AN` after
the adapter verifies that AN is positive. Frequencies are bounded to `[0, 1]`.
Missing counts remain missing. They are not converted to zero and are not
silently imputed from another population.

The positive case derives `0.04` from AC `4` and AN `100`. The conflict control
has two different AF values for one variant and population. The missing-count
control produces a partial summary. The build control remains outside the
requested GRCh38 context.

Population frequency is descriptive reference evidence. It is not a clinical
classification, pathogenicity decision, or diagnostic conclusion. The
receipt reports minimum, maximum, mean, population IDs, and issue codes only.

## C11 reference snapshot manager

C11 turns declared resources into a sorted manifest. Each resource retains:

- resource ID and kind;
- URI or path;
- normalized checksum with an explicit `sha256:` prefix;
- optional byte size;
- source ID and source version;
- optional license ID;
- a stable resource identity.

The manifest address covers snapshot ID, assembly, source, source version, and
sorted resource entries. An expected manifest hash is checked exactly. A
duplicate resource ID is an error and is not overwritten by the later row.
The manager compares snapshots by added, removed, changed, and unchanged
resource IDs. A change in checksum or source version is a changed resource.

The manager does not fetch resource bytes. A valid manifest means that the
declared metadata is internally coherent; it does not prove that a remote URI
is reachable or that the bytes at that URI currently match the digest.

The positive fixture has two resources. One control supplies an expected hash
that cannot match. One repeats an identity with different URI and checksum.
One complete GRCh37 snapshot is retained as an out-of-context control.

## C12 license/use restriction registry

C12 evaluates a requested use against explicit restriction rows. It does not
treat a missing row as permission. For each resource it can retain:

- license ID;
- allowed uses;
- prohibited uses;
- attribution text;
- redistribution permission;
- commercial permission;
- expiry date;
- source and source version.

The positive record explicitly permits research and redistribution. The missing
record blocks use. The expired record blocks a request made after its expiry.
The conflict record has two different restriction signatures and is marked
contradictory without selecting one.

Attribution remains attached to an allowed decision. A requested use that is
not listed is rejected when the allowed-use declaration is non-empty. An
explicit prohibition takes precedence over a general allowed-use declaration.

## Execution receipts

`evaluate-reference-governance-fixture` executes all records through the
existing typed adapters. The default result has:

| Metric | Value |
|---|---:|
| execution receipts | 16 |
| execution checks | 120 |
| positive receipts | 4 |
| control receipts | 12 |
| operation families | 4 |
| public-data checks | 23 |
| quality-gate checks | 25 |

Each receipt contains the capability ID, operation, role, exact context,
adapter state, two bounded counts, observed and expected issue-code sets,
check IDs, a sanitized summary, and a content address. Input collections are
not copied into receipts, quality reports, or release bundles.

## Replay and scenario floors

The replay module captures stable record IDs, expected states, issue-code
floors, positive/control counts, and addresses. It then re-executes the
fixture and compares the new output. Replay checks include exact record order,
state identity, issue floors, receipt addresses, whole-report address, and
positive/control state floors.

The scenario matrix keeps named state transitions independently visible:

1. exact alias support;
2. alias ambiguity;
3. assembly boundary;
4. AC/AN frequency derivation;
5. population conflict;
6. missing frequency counts;
7. snapshot manifest support;
8. expected hash drift;
9. duplicate resource identity;
10. snapshot assembly boundary;
11. explicit license permission;
12. missing permission;
13. expired permission;
14. conflicting permission.

## Lineage and reconciliation

The lineage graph has source, record, receipt, and check nodes. It is
constructed from sanitized summaries and public source receipt metadata. The
default graph has 157 nodes and 155 edges. Every edge endpoint is checked,
node identities are unique, positive receipt states are supported, and no
input collections are copied into graph attributes.

Reconciliation compares the fixture, source audit, execution report, replay,
scenario matrix, and lineage graph. It verifies identity, version, context,
catalog order, operation coverage, role counts, source closure, replay address,
and graph receipt coverage.

## Bundle and release

The accepted-only bundle contains four positive entries. JSON is the default;
CSV and Markdown are also available. The bundle verifier checks entry
addresses, bundle address, positive support, accepted-only filtering, and
input-collection exclusion.

The release manifest is `published` only when execution, quality, replay,
bundle, identity, count, address, and sanitization checks pass. Otherwise it
is `review` or `blocked`. A published manifest cannot contain a failed check.

## Commands

Run the public-data audit:

```text
glio-noncode audit-reference-governance-data examples/reference-governance-public-aggregate.json --output governance-data.json
```

Run execution and replay:

```text
glio-noncode evaluate-reference-governance-fixture examples/reference-governance-public-aggregate.json --output governance-evaluation.json
glio-noncode replay-reference-governance-fixtures examples/reference-governance-public-aggregate.json --output governance-replay.json
```

Run the integrated gate and metrics:

```text
glio-noncode reference-governance-quality-gate examples/reference-governance-public-aggregate.json --output governance-quality.json
glio-noncode reference-governance-metrics examples/reference-governance-public-aggregate.json --output governance-metrics.json
```

Build the accepted-only bundle:

```text
glio-noncode build-reference-governance-bundle examples/reference-governance-public-aggregate.json --output governance-bundle.json --accepted-only
```

Build lineage, reconciliation, and release evidence:

```text
glio-noncode reference-governance-lineage examples/reference-governance-public-aggregate.json --output governance-lineage.json
glio-noncode reference-governance-reconciliation examples/reference-governance-public-aggregate.json --output governance-reconciliation.json
glio-noncode build-reference-governance-release examples/reference-governance-public-aggregate.json --output governance-release.json
```

Run the full runtime request:

```text
glio-noncode run-reference-governance-pipeline examples/reference-governance-pipeline-accepted.json --output governance-pipeline.json
```

The release step is intentionally strict. A local adapter result is not a
publication result until the independent data, replay, lineage,
reconciliation, and bundle checks close.
