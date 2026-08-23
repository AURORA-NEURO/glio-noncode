# D05 Glioma Regulatory Atlas Architecture

## Scope

D05 composes four evidence families into one deterministic public aggregate:

1. Regulatory atlas: cCRE tracks, brain-cell profiles, adult glioma profiles, and pediatric glioma profiles.
2. Molecular atlas: IDH-mutant, IDH-wildtype, H3K27-altered, and histone-mark harmonization.
3. Alpha evidence: open chromatin, methylation, regulatory-role classification, and super-enhancer candidates.
4. Frontier atlas: boundary territory, hotspot detection, evidence tiering, and snapshot publication.

The composed boundary is deliberately narrow:

```text
fixture boundary: public_aggregate_glioma_regulatory_atlas
context: GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown
version: 2026.08.d05-atlas-architecture.v1
```

The fixture contains 20 public source receipts, 16 operations, and 64 cases. Every operation has one positive case and three held controls: foreign context, malformed input, and identity conflict. A positive case may carry an issue receipt from its family adapter; the composed architecture preserves it while requiring a supported result. Controls are never promoted by the aggregate runtime.

## Operation inventory

| ID | Operation | Plane | Family |
| --- | --- | --- | --- |
| D05-C01 | cCRE track parse | regulatory | regulatory |
| D05-C02 | brain cell profile | regulatory | regulatory |
| D05-C03 | adult glioma profile | regulatory | regulatory |
| D05-C04 | pediatric glioma profile | regulatory | regulatory |
| D05-C05 | IDH-mutant atlas | molecular | molecular |
| D05-C06 | IDH-wildtype atlas | molecular | molecular |
| D05-C07 | H3K27-altered atlas | molecular | molecular |
| D05-C08 | histone harmonization | molecular | molecular |
| D05-C09 | open chromatin evidence | evidence | alpha evidence |
| D05-C10 | methylation evidence | evidence | alpha evidence |
| D05-C11 | regulatory role evidence | evidence | alpha evidence |
| D05-C12 | super-enhancer candidate | evidence | alpha evidence |
| D05-C13 | boundary territory | frontier | frontier |
| D05-C14 | hotspot detection | frontier | frontier |
| D05-C15 | evidence tier | frontier | frontier |
| D05-C16 | snapshot publication | frontier | frontier |

The operation order is the dependency order used by the plan compiler. It is also the stable order used by runtime stages, metrics, and replay.

## Runtime surface

The runtime closes twenty ordered stages:

1. fixture loaded
2. sources audited
3. plan compiled
4. policy scored
5. ingestion closed
6. regulatory family ready
7. molecular family ready
8. alpha evidence family ready
9. frontier family ready
10. cases executed
11. review routed
12. lineage linked
13. metrics materialized
14. validation matrix closed
15. schema closed
16. artifacts materialized
17. access closed
18. replay closed
19. release gated
20. runtime finalized

The published state requires all checks to pass. The six runtime artifacts are the fixture digest, evaluation receipts, review queue, lineage ledger, metrics, and validation matrix. The release receipt records the artifact addresses and the final quality state.

## Conservative controls

Controls are explicit cases rather than implicit error paths. The architecture holds them before a family adapter is called:

- foreign context -> `out_of_domain` / `context_mismatch`
- malformed input -> `invalid` / `malformed_input`
- identity conflict -> `contradictory` / `identity_conflict`

This makes a boundary decision inspectable, replayable, and testable without treating a control as an adapter failure. The default fixture therefore has 16 accepted positive receipts and 48 review receipts.

## CLI examples

Emit the canonical public aggregate:

```powershell
python -m glio_noncode atlas-architecture-fixture --output .artifacts/atlas-fixture.json
```

Run the core gates:

```powershell
python -m glio_noncode atlas-architecture-data-audit --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-plan --input .artifacts/atlas-fixture.json
python -m glio_noncode evaluate-atlas-architecture --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-runtime --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-quality --input .artifacts/atlas-fixture.json
```

Inspect the held boundary and release bundle:

```powershell
python -m glio_noncode atlas-architecture-query --state review --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-bundle --input .artifacts/atlas-fixture.json --output .artifacts/atlas-bundle
```

All emitted JSON is deterministic for a fixed fixture and run identifier. Payload-bearing fixture output is suitable for local reproduction; query output is intended for sanitized receipt inspection.

## Deep inspection surfaces

The architecture also exposes field-level, provenance, scenario, and reporting modules:

```powershell
python -m glio_noncode atlas-architecture-dictionary --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-sources --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-scenarios --input .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-report --input .artifacts/atlas-fixture.json --format markdown --output .artifacts/atlas-report.md
python -m glio_noncode atlas-architecture-receipts-csv --input .artifacts/atlas-fixture.json --output .artifacts/receipts.csv
```

The dictionary covers 31 fields across source, operation, case, receipt, review, ledger, and artifact entities. The scenario matrix has 64 rows and eight closure checks. The source registry binds all 20 public source receipts to operations and cases. Reports omit case payloads and are safe for release-level review.
