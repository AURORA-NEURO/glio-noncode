# Domain 05 C09-C12 evidence gate

The C09-C12 layer verifies four research-use-only adapter families against a
deterministic public aggregate fixture:

| Capability | Adapter | Positive boundary | Review controls |
| --- | --- | --- | --- |
| C09 | `OpenChromatinTrackHarmonizer` | two concordant ATAC-seq replicates | malformed signal, replicate disagreement, context mismatch |
| C10 | `MethylationTrackHarmonizer` | covered replicate fractions | zero coverage, fraction disagreement, context mismatch |
| C11 | `EnhancerPromoterSilencerClassifier` | complete declared role channels | missing channels, multi-role ambiguity, context mismatch |
| C12 | `SuperEnhancerCandidateAtlas` | ranked constituents with declared activity | constituent-floor abstention, missing activity, context mismatch |

The fixture is intentionally aggregate and non-patient. It preserves source IDs,
source versions, exact context, raw-row hashes, replicate identity, coverage,
target-gene declarations, and content addresses. It does not claim that the
synthetic rows appear in the cited source releases.

## Public source boundary

The implementation uses public source contracts and source receipts only:

- ENCODE's [ATAC-seq standards and processing overview](https://www.encodeproject.org/atac-seq/) defines the accessibility assay and replicated processing boundary.
- ENCODE's [pipeline catalog](https://www.encodeproject.org/pipelines/) identifies the public processing families for accessibility and methylation assays.
- ENCODE's [annotation catalog](https://www.encodeproject.org/data/annotations/) supplies the open-chromatin, DNA-methylation, and regulatory annotation vocabulary.
- [ENCODE SCREEN](https://screen.encodeproject.org/index/about) supplies the candidate cis-regulatory-element boundary.
- The [NCI adult CNS tumor reference](https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq) supplies disease-context vocabulary only.

No network fetch occurs during fixture execution. Source receipts are HTTPS
identities with access dates, release labels, license notes, and scope notes.

## Acceptance floors

The accepted fixture contains four positive records and twelve controls. The
evaluator emits 120 checks, one sanitized receipt per record, deterministic
replay checks, a scenario matrix, source-to-receipt lineage, reconciliation
checks, operation metrics, and a release manifest. Receipts exclude input text
and do not contain subject-level identifiers.

The view layer turns those receipts into four operation views, a twelve-row
priority-ordered review queue, and a five-source participation matrix. The
observability layer emits nine ordered stage receipts and nine sanitized stage
events. CSV and Markdown exports are generated from those sanitized objects;
they do not expose the fixture's input text.

Interpretation is deliberately bounded:

- accessibility is not activity or causality;
- methylation fraction is not silencing without additional role evidence;
- a high methylation value creates only a silencer candidate;
- a grouped super-enhancer candidate is not a causal regulatory claim;
- ambiguous, partial, abstained, and out-of-domain states remain visible.

## Commands

```powershell
glio-noncode audit-atlas-alpha-evidence-data --output atlas-alpha-audit.json
glio-noncode evaluate-atlas-alpha-evidence --output atlas-alpha-evaluation.json
glio-noncode atlas-alpha-evidence-quality-gate --output atlas-alpha-quality.json
glio-noncode atlas-alpha-evidence-schema --output atlas-alpha-schema.json
glio-noncode run-atlas-alpha-evidence-pipeline --run-id c09-c12-local --output atlas-alpha-run.json
glio-noncode build-atlas-alpha-evidence-release --run-id c09-c12-release --output atlas-alpha-release.json
```

The Python surface exposes `build_atlas_alpha_evidence_view`,
`filter_atlas_alpha_evidence_review_queue`, `build_atlas_alpha_evidence_trace`,
`compare_atlas_alpha_evidence_runs`, and the CSV/Markdown export functions for
downstream review surfaces.

To use a serialized fixture, pass its path as the optional positional input.
The parser validates the fixture content address before execution.
