# D04 reference architecture

The D04 reference architecture is the composition boundary for public aggregate reference operations in `glio-noncode`. It connects four existing typed families—coordinate, annotation, governance, and release—behind one exact-context contract. The composition provides deterministic joins, scenario controls, sanitized receipts, review routing, lineage, replay, and release artifacts without replacing the family adapters.

## Boundary

The default fixture uses this exact context:

```text
GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline
```

The boundary identifier is `public_aggregate_reference_context_and_release`. Every positive case must use the exact context and cite one or more public aggregate source receipts. A case from the foreign context below is held before adapter dispatch:

```text
GRCh37|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline
```

The fixture contains 20 source receipts, 16 operation specifications, and 64 case contracts. Each operation has one positive case and one case for each of three controls:

| Scenario | Boundary result | Adapter dispatch |
| --- | --- | --- |
| `positive` | `accepted` when the family result is supported, accepted, or published | allowed |
| `foreign_context` | `out_of_domain` | held |
| `malformed_input` | `invalid` | held |
| `identity_conflict` | `contradictory` | held |

Controls are not simulated adapter failures. They are explicit boundary decisions that protect the exact reference context and keep ambiguous input visible to review.

## Operation families

The 16 operations are grouped into four adapter families:

| Family | Operations | Primary output |
| --- | --- | --- |
| Coordinate | `reference_registry`, `liftover_chain`, `liftover_ambiguity`, `pangenome_coordinate` | coordinate receipt, chain interpretation, ambiguity outcome, or pangenome mapping summary |
| Annotation | `gencode_transcript_catalog`, `mane_transcript_catalog`, `regulatory_ontology_catalog`, `disease_ontology_mapping` | catalog state and bounded match counts |
| Governance | `gene_alias_version_resolution`, `population_frequency_adaptation`, `reference_snapshot_manifest`, `license_use_restriction` | resolved catalog counts and restriction outcome |
| Release | `source_provenance_check`, `annotation_drift_detection`, `reproducible_reference_bundle`, `reference_release_gate` | release state, provenance result, or bundle output fields |

Each positive payload is derived from a verified public fixture in the corresponding family. The aggregate fixture preserves only the fields required to re-create the family record: operation, context, source joins, bounded payload, expected result, expected issue codes, expected counts, and a content address.

## Runtime sequence

`run_reference_architecture` closes the composition in 24 ordered stages:

1. Load the fixture.
2. Audit source receipts and scope.
3. Compile the operation dependency plan.
4. Score the scenario policy.
5. Close the ingestion boundary.
6. Prepare the coordinate family.
7. Prepare the annotation family.
8. Prepare the governance family.
9. Prepare the release family.
10. Execute all cases.
11. Route held controls to review.
12. Link the hash chain.
13. Materialize metrics.
14. Close the plane-by-operation validation matrix.
15. Close the interchange schema.
16. Materialize six artifacts.
17. Close public access policy.
18. Replay evaluation and compare addresses.
19. Account for operation, case, family, check, state, and lineage depth.
20. Close public aggregate compliance and forbidden-field checks.
21. Apply release checks.
22. Apply the 12-check quality gate.
23. Close observability projections.
24. Finalize the runtime.

The runtime publishes only when evaluation, plan, review queue, lineage, artifacts, access, replay, invariants, schema, runbook, observability, and quality checks all pass. The published state does not mean that controls were accepted; it means the controls were held and accounted for according to the contract.

## Public data boundary

`examples/reference-architecture-public-aggregate.json` is a checked-in, sanitized fixture. It includes source title, public URI, version, scope, license description, content address, and bounded operation payloads. It does not include direct subject identifiers, clinical records, or individual-level measurements. The data audit checks:

- exact fixture version and architecture boundary;
- exact context and foreign-context separation;
- a minimum public-source floor;
- public aggregate scope for every source;
- source and operation join closure;
- four cases for each operation;
- one case per scenario for each operation;
- content addressing on sources, cases, and fixture;
- aggregate-only payload scope;
- a direct-identity field scan.
- explicit public aggregate markers on all sources;
- delegated context keys on all cases;
- foreign-context separation between case and delegated context.

The fixture is loaded through `default_reference_architecture_fixture()` or `ReferenceArchitectureFixture.from_file()`. `reference_architecture_fixture_json()` returns the canonical serialized representation for reproducibility checks and bundle exports.

## Receipts and checks

Every case creates one `ReferenceArchitectureCaseReceipt`. A receipt compares expected and observed architecture state, family result state, issue codes, bounded counts, and content-addressed output identity.

There are seven checks per case and ten global checks, producing 458 evaluation checks. Positive coordinate results can include informative issue codes such as chain parsing or unique ambiguity outcomes. Those codes are retained and compared; they do not demote a successful family result. Control issue codes are one-for-one with their declared policy scenario. The expanded checks also close sanitized summaries, delegated contexts, family coverage, source joins, operation balance, foreign-context controls, and result-state coverage.

## Review and lineage

The review queue contains all 48 controls. Priority is deterministic: identity conflicts are most urgent, foreign-context controls follow, and malformed input is routed with a lower default priority. No control is silently discarded.

The ledger contains 64 hash-linked events. Each event joins a case, operation, input address, output address, previous address, state, and event address. The first event links to `sha256:genesis`; every later event links to the preceding event. Release checks require the entire chain to be valid and complete.

## Artifacts and retention

Six content-addressed artifacts are materialized:

1. fixture JSON;
2. evaluation JSON;
3. review JSON;
4. lineage JSON;
5. metrics JSON;
6. release notes.

The access policy exposes only public aggregate artifacts, permits JSON and Markdown media types, requires versioned public retention, and requires every artifact to retain upstream addresses. The CLI bundle command writes `runtime.json`, `release.json`, and `fixture.json` for local inspection while the typed runtime retains the complete release manifest.

## Quality gates

The release quality gate requires 20 public sources, 16 operations, 64 cases, 64 passing receipts, 458 evaluation checks, 16 plan nodes, 48 review items, 64 ledger events, six addressed artifacts, 24 stages, six result states, accepted public aggregate compliance, and a published release. The depth report exposes a 100.0% default completion score. Independent validation, replay, schema, invariant, failure, access, and observability checks are also retained in the runtime computation.

## CLI examples

```powershell
python -m glio_noncode reference-architecture-fixture --output .\out\fixture.json
python -m glio_noncode reference-architecture-data-audit --input .\out\fixture.json
python -m glio_noncode evaluate-reference-architecture --input .\out\fixture.json
python -m glio_noncode reference-architecture-runtime --input .\out\fixture.json
python -m glio_noncode reference-architecture-quality --input .\out\fixture.json
python -m glio_noncode reference-architecture-compliance --input .\out\fixture.json
python -m glio_noncode reference-architecture-report --input .\out\fixture.json
python -m glio_noncode reference-architecture-receipts-csv --input .\out\fixture.json
python -m glio_noncode reference-architecture-review-csv --input .\out\fixture.json
python -m glio_noncode reference-architecture-query --state review --input .\out\fixture.json
python -m glio_noncode reference-architecture-bundle --input .\out\fixture.json --output .\out\bundle
```

Commands return zero only when their requested contract is closed. A failing audit, evaluation, runtime, validation, quality, compliance, depth, replay, review, access, invariant, or failure command returns a nonzero result so it can be used directly in CI. The bundle additionally writes JSON and Markdown summaries plus receipt and review CSV projections.
