# Domain 05 C13-C16 frontier atlas evidence gate

This gate covers four bounded regulatory-atlas operations:

| Capability | Operation | Accepted output | Required review behavior |
| --- | --- | --- | --- |
| C13 | insulator boundary atlas | supported boundary observations | retain low support, malformed intervals, and context drift |
| C14 | regulatory hotspot atlas | multi-source concordant hotspot observations | retain insufficient source count, direction disagreement, and context drift |
| C15 | evidence-tier adjudication | declared high-tier evidence label | retain low tier, missing sources, and context drift |
| C16 | atlas snapshot publication | context-bound content-addressed snapshot | abstain on empty records, quarantine drift, reject invalid metadata |

## Evidence boundary

The checked-in fixture is synthetic aggregate validation material. It is not a
patient table, does not contain subject identifiers, and does not establish a
clinical, causal, mechanistic, or treatment conclusion. The fixed context is:

```text
GRCh38|diffuse_glioma|adult|stem_like|core|untreated
```

The evidence boundary is `public_aggregate_non_patient`. Every record has one
or more source receipt IDs, and every receipt resolves to an HTTPS source
receipt. The source list is intentionally small and public:

- https://www.encodeproject.org/hic/
- https://www.encodeproject.org/pipelines/ENCPL839OAB/
- https://www.encodeproject.org/pipelines/
- https://screen.encodeproject.org/index/about
- https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq

These sources define the public vocabulary and processing context. The local
fixture remains a compact reproducibility boundary rather than a mirror of
external records.

## Fixture balance

`examples/frontier-atlas-evidence-pipeline-accepted.json` contains 16 records:
one positive path and three controls for each operation. The positive paths
are C13 accepted, C14 accepted, C15 accepted, and C16 published. Controls cover
low support, malformed intervals, insufficient source count, direction
disagreement, low or absent tier evidence, empty snapshots, context drift, and
invalid snapshot metadata.

The evaluator emits 120 checks. Each receipt retains record identity,
operation, role, context, expected state, observed state, counts, issue codes,
summary fields, and a content address. Raw `input_text` is consumed locally
and is not copied into receipts, exports, lineage transformations, trace
events, or release manifests.

## Gate layers

The quality gate runs these layers in order:

1. public aggregate data audit;
2. adapter evaluation;
3. deterministic replay of states, issues, and receipt addresses;
4. positive and negative scenario matrix;
5. twelve-rule policy evaluation;
6. source-to-receipt lineage closure;
7. expected/observed reconciliation;
8. operation metrics and address checks;
9. typed schema validation;
10. immutable bundle assembly.

The runtime wraps the gate in a nine-stage trace. Review records remain visible
in metrics and views. A strict runtime can reject any run with visible review
records using `--fail-on-review`; the default runtime accepts the batch only
when the evidence gate and requested context pass.

## Local verification

```powershell
python -m pytest tests/test_frontier_atlas_evidence.py tests/test_frontier_atlas_evidence_cli.py -q
python -m glio_noncode frontier-atlas-quality-gate examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-quality.json
python -m glio_noncode run-frontier-atlas-pipeline examples/frontier-atlas-evidence-pipeline-accepted.json --run-id frontier-atlas-local --output frontier-atlas-runtime.json
```

The quality report must be accepted, contain 120 passing evaluation checks,
and include a passing schema check. The runtime release is descriptive
research infrastructure and must not be read as a clinical decision.
