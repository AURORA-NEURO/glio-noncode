# D06 Sequence Grammar and Variant Effect Architecture

## Boundary

D06 composes four public aggregate sequence families into one deterministic boundary:

```text
boundary: public_aggregate_sequence_grammar_variant_effect
context: GRCh38|diffuse_glioma|adult|bulk_tumor|sequence|baseline
version: 2026.08.d06-sequence-architecture.v1
```

The family tranches remain the execution authorities. The D06 layer owns the cross-family source joins, operation order, exact context boundary, conservative controls, receipt normalization, lineage, review, validation, and release state.

| Operations | Family | Plane |
| --- | --- | --- |
| C01-C04 | sequence effect frontier | effect |
| C05-C08 | sequence grammar frontier | grammar |
| C09-C12 | sequence regulation frontier | regulation |
| C13-C16 | sequence frontier evidence | frontier |

## Operation map

1. Context encoding
2. Foundation-model adapter receipt
3. Long-context variant effect
4. Regulatory track delta ensemble
5. Motif disruption
6. Motif creation
7. Motif spacing grammar
8. Cooperative transcription-factor grammar
9. Nucleosome propensity
10. Splice regulation
11. UTR regulation
12. Promoter grammar
13. Enhancer grammar
14. Allele saturation
15. Ensemble disagreement
16. Sequence evidence publication

Every operation has one public positive and three explicit controls: foreign context, malformed input, and identity conflict. The aggregate contains 17 source receipts, 64 cases, 16 positive paths, and 48 held controls.

## Runtime

The runtime closes twenty-four stages from fixture loading through release finalization. It materializes six artifacts: fixture, evaluation, review, lineage, metrics, and validation. The quality gate requires:

- 458 passed evaluation checks: seven per case plus ten global closure checks;
- 80 passed validation cells across ingestion, effect, grammar, regulation, and frontier planes;
- 48 controls remaining in review;
- 64 hash-linked ledger events;
- four represented family tranches and six observed result states;
- deterministic replay;
- six addressed artifacts;
- twelve quality checks and accepted public-scope compliance;
- a published release state.

Family outputs are preserved in positive receipt summaries. The D06 layer does not reinterpret a motif hit, sequence index, delta, disagreement value, or grammar match as calibrated probability, clinical consequence, binding, expression, or causality.

## CLI

```powershell
python -m glio_noncode sequence-architecture-fixture --output .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-data-audit --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-plan --input .artifacts/sequence-fixture.json
python -m glio_noncode evaluate-sequence-architecture --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-runtime --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-quality --input .artifacts/sequence-fixture.json
```

Inspect controls and release artifacts:

```powershell
python -m glio_noncode sequence-architecture-query --state review --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-scenarios --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-bundle --input .artifacts/sequence-fixture.json --output .artifacts/sequence-bundle
```

Deep provenance and public-scope checks are also available:

```powershell
python -m glio_noncode sequence-architecture-dictionary --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-compliance --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-sources --input .artifacts/sequence-fixture.json
python -m glio_noncode sequence-architecture-report --input .artifacts/sequence-fixture.json --format markdown --output .artifacts/sequence-report.md
```

The dictionary covers 32 fields across seven persisted entities. Compliance walks nested family payloads for restricted identity and decision fields and verifies public scope markers, exact context boundaries, delegated contexts, addressed identities, and held controls. The source registry keeps catalog-only source receipts visible while requiring all operational sources to join cases.
