# D06 Sequence Architecture Depth

## Scope

D06 is the cross-family sequence boundary for GLIO-NONCODE. It composes four public aggregate tranches and exposes one deterministic contract for sequence grammar, variant effect, regulatory sequence behavior, and frontier evidence.

The boundary is deliberately narrow:

```text
fixture: sequence-grammar-variant-effect-public-aggregate
context: GRCh38|diffuse_glioma|adult|bulk_tumor|sequence|baseline
sources: public aggregate receipts only
operations: D06-C01 through D06-C16
```

The layer owns composition, context controls, source joins, receipt normalization, review routing, lineage, validation, compliance, depth accounting, and release state. Family tranches remain responsible for their own positive evidence records and family-specific calculations.

## Depth matrix

| Surface | Target | Observed | Closure rule |
| --- | ---: | ---: | --- |
| Public sources | 17 | 17 | every source is addressed and marked public aggregate |
| Operations | 16 | 16 | every operation has a dependency node and source join |
| Cases | 64 | 64 | four scenarios per operation |
| Family tranches | 4 | 4 | effect, grammar, regulation, and frontier are represented |
| Evaluation checks | 458 | 458 | seven checks per case plus ten global checks |
| Validation cells | 80 | 80 | five planes by sixteen operations |
| Review controls | 48 | 48 | foreign, malformed, and identity controls remain held |
| Ledger events | 64 | 64 | one hash-linked event per case |
| Runtime stages | 24 | 24 | ordered stages from fixture load to final runtime |
| Release artifacts | 6 | 6 | fixture, evaluation, review, lineage, metrics, validation |
| Quality checks | 12 | 12 | evaluation, plan, review, lineage, artifact, release, stage, source, check, state, context, compliance |
| Result states | 6 | 6 | supported, accepted, published, out_of_domain, invalid, contradictory |

The depth percentage is the mean of the five structural targets: source count, operation count, case count, family count, and evaluation check count. A complete D06 fixture reports `100.0`.

## Operation families

| IDs | Family | Primary concern | Controls |
| --- | --- | --- | --- |
| C01-C04 | sequence effect frontier | context encoding, foundation receipt, long context, regulatory ensemble | context and receipt boundaries |
| C05-C08 | sequence grammar frontier | motif loss, motif gain, spacing, cooperative grammar | grammar contract and mismatch controls |
| C09-C12 | sequence regulation frontier | nucleosome, splice, UTR, promoter behavior | regulatory interpretation boundaries |
| C13-C16 | sequence frontier | enhancer, saturation, disagreement, publication | frontier evidence and release boundaries |

Every operation has one positive scenario and three controls. The positive scenario may delegate to its family fixture. Controls stop at the aggregate boundary and carry an explicit issue code.

## Runtime stages

The twenty-four stages are deterministic and content-addressed:

1. `fixture-loaded`
2. `sources-audited`
3. `plan-compiled`
4. `policy-scored`
5. `ingestion-closed`
6. `effect-family-ready`
7. `grammar-family-ready`
8. `regulation-family-ready`
9. `frontier-family-ready`
10. `cases-executed`
11. `review-routed`
12. `lineage-linked`
13. `metrics-materialized`
14. `validation-matrix-closed`
15. `schema-closed`
16. `artifacts-materialized`
17. `access-closed`
18. `replay-closed`
19. `depth-accounted`
20. `compliance-closed`
21. `release-gated`
22. `quality-gated`
23. `observability-closed`
24. `runtime-finalized`

Each stage has an ordinal, one predecessor address, one output address, one check count, and its own content address. A release state of `published` is insufficient by itself; the runtime must also have no blocked stage, accepted compliance, accepted depth, and a passed quality gate.

## Receipt normalization

Positive family output is reduced to a public summary before it enters the aggregate receipt. Raw input markers are removed from the summary boundary. The retained summary includes the delegated context key, aggregate context key, family result state, issue codes, bounded counts, and an output address.

Control summaries are intentionally smaller. They retain the control disposition, issue code, detail, aggregate context key, and delegated context key. They do not enter family execution.

The seven case-level checks are:

1. observed aggregate state;
2. observed family result state;
3. exact issue code tuple;
4. bounded count map;
5. receipt address and pass state;
6. sanitized summary boundary;
7. delegated context retention and foreign mismatch.

The ten global checks close receipt count, positive count, control count, pass count, operation coverage, family coverage, source joins, operation balance, foreign context controls, and result-state coverage.

## Compliance boundary

Compliance verifies all nested case payloads, not only top-level fields. The public aggregate surface rejects direct identity fields, individual-level identifiers, clinical decision fields, treatment recommendation fields, and hidden provenance markers. Every source must carry both `scope=public_aggregate` and `public_aggregate=true`.

Compliance also requires:

- exact declared aggregate or control contexts;
- explicit delegated context keys;
- addressed source and case identities;
- review state for all controls;
- hold-first operation policies.

The report exposes every failing nested path so a malformed fixture can be repaired without guessing which payload caused the block.

## Verification commands

```powershell
python -m unittest tests.test_sequence_architecture tests.test_sequence_architecture_cli tests.test_sequence_architecture_exports tests.test_sequence_architecture_reporting
python -m glio_noncode sequence-architecture-fixture --output .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-runtime --input .artifacts/sequence-fixture.json --output .artifacts/sequence-runtime.json
python -m glio_noncode sequence-architecture-depth --input .artifacts/sequence-fixture.json --output .artifacts/sequence-depth.json
python -m glio_noncode sequence-architecture-compliance --input .artifacts/sequence-fixture.json --output .artifacts/sequence-compliance.json
python -m glio_noncode sequence-architecture-bundle --input .artifacts/sequence-fixture.json --output .artifacts/sequence-bundle
```

The accepted runtime JSON contains `depth`, `quality`, and `compliance` objects. The bundle contains `fixture.json`, `runtime.json`, `release.json`, and `report.json`; the release projection includes the six artifacts and the three closure reports.
