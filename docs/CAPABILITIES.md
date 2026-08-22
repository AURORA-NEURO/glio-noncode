# Capability coverage

GLIO-NONCODE is measured against the approved product blueprint, not against
the number of Python files or workflow roles. The checked-in catalog at
`schemas/capability_catalog.csv` contains:

| Measure | Denominator | Meaning |
| --- | ---: | --- |
| Product capabilities | 256 | 16 domains × 16 ordered capabilities |
| MVP capabilities | 64 | The first four capabilities in each domain |
| Delivery surfaces | 4 per capability | Core, API, CLI, and review/operations surfaces |
| Feature instances | 1,024 | 256 capabilities × 4 delivery surfaces |
| Control-plane roles | 48 | Bounded workflow responsibilities |
| Typed tool contracts | 96 | Two contracts per bounded role |

The 48-role and 96-contract figures describe orchestration coverage. They are
not a substitute for product implementation coverage. A capability is counted
as implemented only when the ledger names its modules; it is counted as
verified only when tests and the stated evidence boundary support that claim.
The registry reports planned, partial, implemented, and verified counts
separately so a single percentage cannot hide unfinished work.

The frontier expansion waves add partial, test-backed coverage for all C13-C16
capabilities in Domains 01-16. The repository ledger now has 256 of 256
capabilities started (100%); 100 capabilities have deterministic fixture-backed
verification and 156 remain partial. The frontier surfaces are bounded research
infrastructure. Current verified coverage is 39.06% of the 256-capability
catalog; MVP implementation coverage is 31.25%. The surfaces retain
source receipts, uncertainty, policy checks, and
review states rather than converting missing evidence into a scientific or
clinical conclusion.

Inspect the current ledger locally:

```powershell
glio-noncode capabilities
```

## Domain 01 intake boundary

The first vertical slice covers the source boundary for case material:

- VCF, gVCF, TSV, JSON, and binary BCF intake preserve source hashes,
  headers, typed fields, genotype decisions, deferred symbolic records, and
  malformed-record issues;
- BED and narrowPeak coordinates are converted from zero-based half-open to
  one-based closed intervals, while GFF3 remains one-based closed;
- regulatory-track rows are converted to context-qualified candidate
  elements only when their source accounting remains intact; unresolved
  targets are explicitly marked rather than inferred;
- supported SNV/indel identities receive a VRS-shaped allele representation;
  missing reference digests, repeat ambiguity, and unsupported breakend/CNV/
  haplotype forms remain visible as limitations or abstentions.

These adapters are a research-use boundary. They do not assert clinical
interpretation, and a VRS-shaped local representation is not presented as a
RefGet-equivalent digest unless a sequence digest is supplied.

The command-line equivalents are:

```powershell
glio-noncode intake variants.vcf --output intake.json
glio-noncode parse-track regulatory.bed --output track.json
glio-noncode normalize 7:140453136:A>T --genome-build GRCh38
```

The Domain 01 frontier boundary adds four deeper data controls:

- `ConsentPolicyAttacher` binds each intake record to policy ID/version,
  purpose, permitted uses, consent status, expiry, and exact context. Inactive
  or mismatched records are blocked with structured reasons.
- `InputAnomalyQuarantine` retains duplicate IDs, coordinate errors, context
  mismatches, missing fields, and unsupported bases in a quarantine report;
  rows are not silently discarded.
- `DataCompletenessScorer` calculates weighted required-field coverage while
  separating present, missing, and invalid fields.
- `IntakeBundleExporter` creates deterministic content-addressed bundles and
  refuses blocked, quarantined, or review-state rows when acceptance is on.

```powershell
glio-noncode attach-consent-policy consent.json --output consent-report.json
glio-noncode quarantine-input-anomalies intake-records.json --output anomaly-report.json
glio-noncode score-data-completeness completeness.json --output completeness-report.json
glio-noncode export-intake-bundle accepted-intake.json --output intake-bundle.json
```

The C13-C16 slice is verified through the public policy/aggregate fixture at
`examples/intake-public-aggregate.json`. It supplies one positive record for
each adapter plus eight review controls covering withdrawn and mismatched
policy, duplicate and invalid-sequence input, missing and invalid completeness,
and blocked or cross-context export. The independent evidence gate performs a
public-source audit, executes 33 fixture checks, replays the exact
source/context contract, runs 12 state-transition scenarios, validates four
operation contracts, and emits a compact JSON/CSV/Markdown bundle. See
`docs/INTAKE_EVIDENCE_GATE.md` and `docs/INTAKE_BUNDLE_FORMAT.md` for the
complete schema and limitations.

```powershell
python -m glio_noncode audit-intake-data examples/intake-public-aggregate.json --output intake-data.json
python -m glio_noncode evaluate-intake-fixture examples/intake-public-aggregate.json --output intake-fixture.json
python -m glio_noncode replay-intake-fixtures examples/intake-public-aggregate.json --output intake-replay.json
python -m glio_noncode intake-quality-gate examples/intake-public-aggregate.json --output intake-quality.json
python -m glio_noncode evaluate-intake-scenarios examples/intake-public-aggregate.json --output intake-scenarios.json
python -m glio_noncode intake-contracts --output intake-contracts.json
python -m glio_noncode build-intake-bundle examples/intake-public-aggregate.json --output intake-bundle.json
python -m glio_noncode run-intake-pipeline examples/intake-pipeline-accepted.json --output intake-pipeline.json
```

The pipeline command composes C13 policy attachment, C14 anomaly quarantine,
C15 completeness scoring, and C16 export into one deterministic batch boundary.
Its report carries a receipt for every stage, separates accepted, review, and
blocked record IDs, omits raw records from the published receipt, and returns a
non-zero exit code unless every input row reaches an accepted bundle. The batch
fixture in `examples/intake-pipeline-batch.json` deliberately demonstrates a
partial manifest and review state; the accepted fixture is used by CI as the
success path.

## Domain 02 structural frontier

The structural frontier preserves the uncertainty that is usually lost when
copy number or breakpoint observations are flattened:

- `TandemRepeatInterpreter` validates motifs and intervals and compares
  observed and reference copy estimates against explicit uncertainty.
- `CompoundHaplotypeEvaluator` retains required versus observed alleles,
  missingness, completeness, and unresolved phase instead of fabricating cis
  or trans relationships.
- `BreakpointUncertaintyPropagator` carries both breakpoint intervals into a
  propagated uncertainty width with a confidence gate.
- `StructuralVariantEvidenceExporter` emits sorted, context-bound evidence
  bundles with source IDs and content addresses.

```powershell
glio-noncode interpret-tandem-repeats repeats.json --output repeats-report.json
glio-noncode evaluate-compound-haplotypes haplotypes.json --output haplotype-report.json
glio-noncode propagate-breakpoint-uncertainty breakpoints.json --output breakpoint-report.json
glio-noncode export-structural-evidence structural-evidence.json --output structural-bundle.json
```

The Domain 02 C01-C04 structural evidence gate verifies the deeper boundary
with a public aggregate fixture at
`examples/structural-public-aggregate.json`:

- `StructuralReconstructor` preserves symbolic intervals, reciprocal breakends,
  and explicit phased paths. Missing or non-reciprocal mates remain errors.
- `SVConsensusImporter` retains caller versions, source-line/raw hashes,
  malformed rows, bounded clusters, and beyond-tolerance disagreement.
- `ComplexRearrangementResolver` builds shared-locus components and exposes
  alternative path ambiguity without selecting a canonical rearrangement.
- `CopyNumberSegmentHarmonizer` sweeps caller boundaries into atomic intervals
  and keeps caller disagreement visible beside its median view.

The evidence surfaces are independently executable and cross-checked:

```powershell
python -m glio_noncode audit-structural-data examples/structural-public-aggregate.json --output structural-data.json
python -m glio_noncode evaluate-structural-fixture examples/structural-public-aggregate.json --output structural-fixture.json
python -m glio_noncode replay-structural-fixtures examples/structural-public-aggregate.json --output structural-replay.json
python -m glio_noncode structural-quality-gate examples/structural-public-aggregate.json --output structural-quality.json
python -m glio_noncode evaluate-structural-scenarios examples/structural-public-aggregate.json --output structural-scenarios.json
python -m glio_noncode structural-contracts --output structural-contracts.json
python -m glio_noncode build-structural-bundle examples/structural-public-aggregate.json --output structural-bundle.json
python -m glio_noncode run-structural-pipeline examples/structural-pipeline-accepted.json --output structural-pipeline.json
python -m glio_noncode structural-lineage examples/structural-public-aggregate.json --output structural-lineage.json
```

The fixture contains four positive operation records and eight review controls.
Its source receipts point to public dbVar clinical/common structural-variation
collections, a public gnomAD SV v4 release summary, and a public dbVar
copy-number placement summary. The records are aggregate validation payloads,
not patient-level data. See `docs/STRUCTURAL_EVIDENCE_GATE.md` and
`docs/STRUCTURAL_BUNDLE_FORMAT.md` for the exact schema and limitations.

The structural bundle also carries a sanitized source-to-result lineage graph:
four public source nodes, one fixture node, twelve record nodes, and twelve
result nodes connected by 36 typed edges. Its graph address is independently
audited for exact context, source coverage, record/result pairing, and endpoint
integrity. Raw operation payloads remain outside the compact lineage receipt.

The C05-C08 structural beta gate extends Domain 02 with a second, independently
replayable evidence plane at `examples/structural-beta-public-aggregate.json`:

- focal amplification requires thresholded copy number and caller-supported
  boundaries; low-copy and invalid-copy controls abstain or enter review;
- chromothripsis retains breakpoint span, orientation switches, and supplied
  copy-number oscillation while missing state and far-gap patterns remain
  partial or abstained;
- ecDNA requires circularity, junction support, and amplification evidence;
  high copy number alone is not sufficient and conflicting linear evidence is
  retained as review;
- enhancer hijacking requires exact six-field context, an explicit structural
  bridge, and declared activity/contact channels; missing bridges and context
  drift remain review states.

The beta evidence plane executes 63 fixture assertions across four positives and
eight controls, a 12-case scenario matrix, four operation contracts, a 20-check
quality gate, a 29-node/36-edge lineage graph, and a four-stage runtime. The
compact bundle contains twelve sanitized entries and independently addressable
quality and lineage receipts. Its public source receipts point to aggregate
dbVar and gnomAD structural-variation material; the fixture is a mechanics and
boundary contract, not a patient callset or clinical truth set. See
`docs/STRUCTURAL_BETA_EVIDENCE_GATE.md` and
`docs/STRUCTURAL_BETA_BUNDLE_FORMAT.md` for the full schema, state semantics,
source scope, limitations, and verification rules.

```powershell
python -m glio_noncode audit-structural-beta-data examples/structural-beta-public-aggregate.json --output structural-beta-data.json
python -m glio_noncode evaluate-structural-beta-fixture examples/structural-beta-public-aggregate.json --output structural-beta-fixture.json
python -m glio_noncode replay-structural-beta-fixtures examples/structural-beta-public-aggregate.json --output structural-beta-replay.json
python -m glio_noncode structural-beta-quality-gate examples/structural-beta-public-aggregate.json --output structural-beta-quality.json
python -m glio_noncode evaluate-structural-beta-scenarios examples/structural-beta-public-aggregate.json --output structural-beta-scenarios.json
python -m glio_noncode structural-beta-contracts --output structural-beta-contracts.json
python -m glio_noncode build-structural-beta-bundle examples/structural-beta-public-aggregate.json --output structural-beta-bundle.json
python -m glio_noncode structural-beta-lineage examples/structural-beta-public-aggregate.json --output structural-beta-lineage.json
python -m glio_noncode run-structural-beta-pipeline examples/structural-beta-pipeline-accepted.json --output structural-beta-pipeline.json
```

## Domain 03 specimen frontier

Specimen context is now represented as a linked, reviewable envelope. The
preanalytic assessor applies declared metric thresholds; the protocol tracker
retains parent-node and operator relationships; the identity adjudicator
reports modal agreement, ties, and conflicts; and the context publisher binds
lineage, quality, and identity receipts before publication.

```powershell
glio-noncode assess-preanalytic-quality specimen-qc.json --output specimen-qc-report.json
glio-noncode track-assay-lineage assay-lineage.json --output lineage-report.json
glio-noncode adjudicate-identity-conflicts identity-observations.json --output identity-report.json
glio-noncode publish-specimen-context specimen-envelope.json --output specimen-envelope.json
```

### Domain 03 C01-C04 aggregate evidence gate

The first four specimen capabilities now have a separate, deterministic
aggregate evidence plane. It is independent from the older specimen-context
examples so that each capability has its own source receipts, positive
controls, review controls, replay contract, quality gate, bundle, and lineage
graph.

The four adapters are:

- `SpecimenOntologyMapper` maps aggregate sample rows to a declared ontology
  and keeps missing identifiers, conflicting subject keys, and invalid rows as
  structured issues.
- `MatchedNormalResolver` resolves a unique normal for a pseudonymous subject
  only when the relationship is explicit; missing and multiple normals are
  review states rather than guessed links.
- `PurityPloidyImporter` ingests tabular or JSON measurements, preserves
  caller/version and row receipts, normalizes percentage values, and
  quarantines malformed measurements.
- `ContaminationSwapDetector` compares declared and observed fingerprint
  summaries, retains mismatch and contamination signals, and abstains when
  required metrics are incomplete.

The evidence catalog at
`examples/specimen-frontier-public-aggregate.json` has four accepted positive
records and eight review controls. The fixture contains aggregate, synthetic
records only. It uses pseudonymous subject keys and six exact context fields;
it contains no patient-level payloads. Its source receipts are metadata-shaped
references to the NCBI BioSample documentation, the GDC data model and data
dictionary, and the ENA browser guides. The receipts describe source scope;
they are not claims that the source pages contain the synthetic fixture rows.

The complete command surface is:

```powershell
python -m glio_noncode audit-specimen-frontier-data examples/specimen-frontier-public-aggregate.json --output specimen-data.json
python -m glio_noncode evaluate-specimen-frontier-fixture examples/specimen-frontier-public-aggregate.json --output specimen-fixture.json
python -m glio_noncode replay-specimen-frontier-fixtures examples/specimen-frontier-public-aggregate.json --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" --output specimen-replay.json
python -m glio_noncode specimen-frontier-quality-gate examples/specimen-frontier-public-aggregate.json --output specimen-quality.json
python -m glio_noncode evaluate-specimen-frontier-scenarios examples/specimen-frontier-public-aggregate.json --output specimen-scenarios.json
python -m glio_noncode specimen-frontier-contracts --output specimen-contracts.json
python -m glio_noncode build-specimen-frontier-bundle examples/specimen-frontier-public-aggregate.json --output specimen-bundle.json
python -m glio_noncode specimen-frontier-lineage examples/specimen-frontier-public-aggregate.json --output specimen-lineage.json
python -m glio_noncode run-specimen-frontier-pipeline examples/specimen-frontier-pipeline-accepted.json --output specimen-pipeline.json
```

The accepted path executes 72 fixture assertions, 21 quality checks, 12
independent scenarios, four operation contracts, and a four-stage runtime.
The bundle contains 12 sanitized entries. The lineage graph contains 29 nodes
and 36 typed edges. A second pipeline example at
`examples/specimen-frontier-pipeline-review.json` keeps review issue codes and
does not publish the run as an accepted result.

The accepted bundle requires an exact fixture identity, source membership,
context agreement, record-address agreement, operation coverage, positive and
control floors, and sanitized output. Review bundles require explicit opt-in.
Replay rejects duplicate record IDs, duplicate addresses, source drift,
context drift, and changed expected floors. Lineage rejects missing endpoints,
unknown relations, orphan results, and content-address mismatches. These are
mechanical evidence controls; they do not establish specimen identity,
diagnostic truth, or clinical validity.

See `docs/SPECIMEN_FRONTIER_EVIDENCE_GATE.md` for the record schema, source
boundary, control design, replay rules, and failure semantics. See
`docs/SPECIMEN_FRONTIER_BUNDLE_FORMAT.md` for the JSON, CSV, Markdown,
lineage, and runtime receipt formats.

## Domain 04 reference frontier

Reference governance now has explicit provenance, drift, bundle, and release
boundaries. Source checks compare declared and observed checksums and require
license/context receipts; annotation drift compares substantive fields while
ignoring retrieval-only fields; reproducible bundles sort records and retain a
schema hash; and the release gate denies publication when any required check
is absent or false.

```powershell
glio-noncode check-source-provenance source-records.json --output provenance.json
glio-noncode detect-annotation-drift annotation-delta.json --output drift.json
glio-noncode build-reference-bundle references.json --output reference-bundle.json
glio-noncode gate-reference-release release-checks.json --output release-decision.json
```

The C01-C04 reference-coordinate vertical slice adds a public aggregate
fixture with six official source receipts, four positive records, and twelve
controls. It resolves canonical assembly aliases, parses explicit chain-like
segments, scores unique/competing/absent mappings, and retains every declared
HPRC path candidate. The release plane adds 26 data-boundary checks, 134
operation checks, 16 scenario transitions, 16 replay checks, 24
reconciliation checks, a 39-node/38-edge lineage graph, a sanitized bundle,
and five conserved runtime stages.

```powershell
glio-noncode audit-reference-coordinate-data examples/reference-coordinate-public-aggregate.json --output reference-coordinate-data.json
glio-noncode evaluate-reference-coordinate-fixture examples/reference-coordinate-public-aggregate.json --output reference-coordinate-fixture.json
glio-noncode replay-reference-coordinate-fixtures examples/reference-coordinate-public-aggregate.json --output reference-coordinate-replay.json
glio-noncode reference-coordinate-quality-gate examples/reference-coordinate-public-aggregate.json --output reference-coordinate-quality.json
glio-noncode evaluate-reference-coordinate-scenarios examples/reference-coordinate-public-aggregate.json --output reference-coordinate-scenarios.json
glio-noncode reference-coordinate-contracts --output reference-coordinate-contracts.json
glio-noncode build-reference-coordinate-bundle examples/reference-coordinate-public-aggregate.json --output reference-coordinate-bundle.json --format markdown
glio-noncode reference-coordinate-lineage examples/reference-coordinate-public-aggregate.json --output reference-coordinate-lineage.json
glio-noncode reference-coordinate-reconciliation examples/reference-coordinate-public-aggregate.json --output reference-coordinate-reconciliation.json
glio-noncode run-reference-coordinate-pipeline examples/reference-coordinate-pipeline-accepted.json --output reference-coordinate-pipeline.json
```

The C05-C08 annotation slice verifies the GENCODE, MANE, Relation Ontology,
and Mondo-shaped boundaries with five public source receipts, four positive
records, and twelve controls. The accepted fixture emits 120 execution checks,
12 replay checks, 16 scenario transitions, 17 reconciliation checks, a
38-node/59-edge lineage graph, a 23-check quality gate, a four-entry accepted
bundle, and an independently verified publication manifest. Receipts exclude
input text and preserve ambiguity or abstention rather than selecting rows.
See `docs/REFERENCE_ANNOTATION_EVIDENCE_GATE.md` and
`docs/REFERENCE_ANNOTATION_RELEASE_FORMAT.md` for the full schema and change
rules.

```powershell
glio-noncode audit-reference-annotation-data examples/reference-annotation-public-aggregate.json --output reference-annotation-data.json
glio-noncode evaluate-reference-annotation-fixture examples/reference-annotation-public-aggregate.json --output reference-annotation-fixture.json
glio-noncode replay-reference-annotation-fixtures examples/reference-annotation-public-aggregate.json --output reference-annotation-replay.json
glio-noncode reference-annotation-quality-gate examples/reference-annotation-public-aggregate.json --output reference-annotation-quality.json
glio-noncode evaluate-reference-annotation-scenarios examples/reference-annotation-public-aggregate.json --output reference-annotation-scenarios.json
glio-noncode reference-annotation-contracts --output reference-annotation-contracts.json
glio-noncode build-reference-annotation-bundle examples/reference-annotation-public-aggregate.json --output reference-annotation-bundle.json --accepted-only
glio-noncode reference-annotation-lineage examples/reference-annotation-public-aggregate.json --output reference-annotation-lineage.json
glio-noncode reference-annotation-reconciliation examples/reference-annotation-public-aggregate.json --output reference-annotation-reconciliation.json
glio-noncode run-reference-annotation-pipeline examples/reference-annotation-pipeline-accepted.json --output reference-annotation-pipeline.json
glio-noncode build-reference-annotation-release examples/reference-annotation-public-aggregate.json --output reference-annotation-release.json
```

The C09-C12 reference-governance plane now turns the existing identity,
frequency, snapshot, and permission adapters into a deeply checked public
aggregate release surface. It uses five public source receipts, four positive
records, and twelve controls under
`GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline`:

- C09 resolves declared HGNC-shaped IDs, symbols, aliases, versions, and
  assemblies while retaining ambiguity and unknown identity controls.
- C10 retains population, ancestry, AC, AN, homozygote count, declared or
  derived AF, build, and source versions. Missing counts and conflicting rows
  remain review evidence.
- C11 builds sorted content-addressed reference manifests, checks expected
  hashes, rejects duplicate resource identities, and marks another assembly
  as out of context. It does not fetch resource bytes.
- C12 evaluates explicit SPDX-shaped permission rows for use, attribution,
  redistribution, commercial terms, and expiry. Missing or conflicting
  permission blocks use.

The aggregate emits 23 public-data checks, 120 execution checks, 13 replay
checks, 14 named state scenarios, a 157-node/155-edge lineage graph, 16
reconciliation checks, a 25-check quality gate plus a 12-rule policy report, a four-entry accepted-only
bundle, a metrics report, an explicit 12-rule policy report, and a publication manifest. Receipts are sanitized
and retain state, counts, issue codes, and addresses without copying input
collections.

```powershell
glio-noncode audit-reference-governance-data examples/reference-governance-public-aggregate.json --output reference-governance-data.json
glio-noncode evaluate-reference-governance-fixture examples/reference-governance-public-aggregate.json --output reference-governance-fixture.json
glio-noncode replay-reference-governance-fixtures examples/reference-governance-public-aggregate.json --output reference-governance-replay.json
glio-noncode reference-governance-quality-gate examples/reference-governance-public-aggregate.json --output reference-governance-quality.json
glio-noncode evaluate-reference-governance-scenarios examples/reference-governance-public-aggregate.json --output reference-governance-scenarios.json
glio-noncode reference-governance-contracts --output reference-governance-contracts.json
glio-noncode reference-governance-metrics examples/reference-governance-public-aggregate.json --output reference-governance-metrics.json
glio-noncode build-reference-governance-bundle examples/reference-governance-public-aggregate.json --output reference-governance-bundle.json --accepted-only
glio-noncode reference-governance-lineage examples/reference-governance-public-aggregate.json --output reference-governance-lineage.json
glio-noncode reference-governance-reconciliation examples/reference-governance-public-aggregate.json --output reference-governance-reconciliation.json
glio-noncode run-reference-governance-pipeline examples/reference-governance-pipeline-accepted.json --output reference-governance-pipeline.json
glio-noncode build-reference-governance-release examples/reference-governance-public-aggregate.json --output reference-governance-release.json
```

The complete schema and release rules are documented in
`docs/REFERENCE_GOVERNANCE_EVIDENCE_GATE.md` and
`docs/REFERENCE_GOVERNANCE_RELEASE_FORMAT.md`.

The same frontier wave extended the atlas, sequence, chromatin, and cell-state
boundaries through Domains 05-08. Those modules remain part of the current
256-capability ledger, with the individual capability records retaining their
own partial or verified status.

Domain 05 includes an insulator/boundary atlas, independent-source regulatory
hotspot aggregation, evidence-tier adjudication, and versioned atlas snapshot
publication. Domain 06 includes motif-spacing grammar, declared alternate
allele saturation, ensemble spread quantification, and model/sequence evidence
publication. Domain 07 includes confidence-aware context imputation, assay
coverage gates, cross-assay concordance, and chromatin evidence publication.
Domain 08 includes cell-state abundance intervals, score/margin reference
mapping, out-of-domain support checks, and a receipt-bound cell-state context
envelope.

The frontier command boundary is:

```powershell
glio-noncode build-insulator-boundary-atlas boundary.json --output boundary-report.json
glio-noncode build-regulatory-hotspot-atlas hotspots.json --output hotspot-report.json
glio-noncode adjudicate-atlas-evidence-tier atlas-evidence.json --output tier-report.json
glio-noncode publish-atlas-snapshot atlas-records.json --output atlas-snapshot.json
glio-noncode evaluate-enhancer-grammar grammar.json --output grammar-report.json
glio-noncode simulate-allele-saturation saturation.json --output saturation-report.json
glio-noncode quantify-ensemble-disagreement ensemble.json --output disagreement-report.json
glio-noncode publish-sequence-evidence sequence-evidence.json --output sequence-bundle.json
glio-noncode impute-context-confidence context-imputation.json --output imputation-report.json
glio-noncode gate-assay-support assay-support.json --output assay-gate.json
glio-noncode adjudicate-assay-concordance concordance.json --output concordance-report.json
glio-noncode publish-chromatin-evidence chromatin-evidence.json --output chromatin-bundle.json
glio-noncode estimate-cell-state-abundance cell-counts.json --output abundance-report.json
glio-noncode map-single-cell-reference cell-reference-scores.json --output mapping-report.json
glio-noncode detect-cell-state-ood cell-ood.json --output cell-ood-report.json
glio-noncode publish-cell-state-context cell-context.json --output cell-context-envelope.json
```

These modules are descriptive and research-use only. They do not claim that a
hotspot is causal, that a sequence model is calibrated, that an imputed assay
is measured, or that a mapped cell state is clinically definitive.

The D09-D12 frontier established the next four inference domains in the
256-capability ledger. The topology layer models ecDNA contacts, compartment
switches, uncertainty-aware
signal transport, and 3D publication. The link layer corrects dependence,
ranks target genes, calibrates and abstains, and publishes source-bound links.
The causal layer decomposes posteriors, ranks regulatory-driver hypotheses,
selectively abstains, and publishes research-only dossiers. The cohort layer
stratifies subgroup rates, estimates source/target transportability, aggregates
privacy-floored federated summaries, and publishes aggregate discovery bundles.

```powershell
glio-noncode model-ecdna-contacts ecdna-contacts.json --output ecdna-report.json
glio-noncode estimate-compartment-switch compartments.json --output compartment-report.json
glio-noncode transport-topology-uncertainty topology-paths.json --output transport-report.json
glio-noncode publish-3d-evidence topology-evidence.json --output topology-bundle.json
glio-noncode correct-link-dependence link-evidence.json --output dependence-report.json
glio-noncode rank-target-genes target-links.json --output gene-rank-report.json
glio-noncode calibrate-link-abstention link-calibration.json --output calibration-report.json
glio-noncode publish-link-evidence link-evidence.json --output link-bundle.json
glio-noncode decompose-posterior posterior-components.json --output posterior-report.json
glio-noncode infer-regulatory-driver-posterior driver-hypotheses.json --output driver-report.json
glio-noncode selective-causal-prediction causal-predictions.json --output selective-report.json
glio-noncode publish-causal-dossier causal-dossier.json --output dossier.json
glio-noncode stratify-subgroup-fairness cohort-labels.json --output fairness-report.json
glio-noncode estimate-transportability transportability.json --output transportability-report.json
glio-noncode analyze-federated-summary federated-summary.json --output federated-report.json
glio-noncode publish-cohort-discovery cohort-discovery.json --output cohort-bundle.json
```

These inference surfaces keep dependence correction, calibration error,
uncertainty, subgroup gaps, feature overlap, privacy floors, and abstentions
visible. None of them turns an association or posterior score into a clinical
decision.

The D13-D16 frontier completes all 256 catalog capability code paths with
partial, test-backed implementations. The current ledger reports 256 of 256
capabilities started (100%); 100 controls are verified against the checked-in
aggregate fixtures, while 156 capabilities remain partial. Partial
means the bounded code and tests exist. Verified means the local deterministic
fixture and negative-control boundary pass; external validation, calibration,
and institutional release evidence remain separate.

Domain 13 now includes off-target risk estimation, prerequisite-safe validation
value-of-information selection, content-addressed experiment packages, and
result-driven claim updates. Domain 14 includes evidence reclassification,
cycle-checked deprecation/supersession, audit reproducibility bundles, and
HMAC-signed research dossiers with audience and expiry verification. Domain 15
includes structured review forms, deterministic JSON/Markdown/CSV-oriented
reports, global search and command matching, and accessibility/human-factors
checks. Domain 16 includes deny-by-default privacy/security policy evaluation,
offline deployment manifests, site-local federated coordination, and explicit
release/rollback gates.

Run the full frontier evidence gate locally or in CI:

```powershell
glio-noncode evaluate-frontier-fixture examples/frontier-glioma-case.json --output frontier-fixture-report.json
glio-noncode audit-frontier-data examples/frontier-glioma-case.json --output frontier-data-report.json
glio-noncode replay-frontier-fixtures examples/frontier-glioma-case.json --output frontier-replay-report.json
glio-noncode frontier-contracts --output frontier-contracts.json
glio-noncode evaluate-frontier-scenarios examples/frontier-glioma-case.json --output frontier-scenario-report.json
glio-noncode frontier-quality-gate examples/frontier-glioma-case.json --output frontier-quality-report.json
```

The contract registry covers 79 operations across data, context, inference,
release, hardening, and end-to-end surfaces. The 17 release operations map to
the 16 D13-D16 capability receipts; signed-dossier publication and verification
share one lifecycle capability by design.

The scenario matrix replays all four positive pipeline payloads and every
negative control in the fixture. It independently checks the accepted/review
boundary and verifies that each declared blocked stage remains present. This
gives the repository a state-transition proof in addition to individual
operation checks.

The quality gate reconciles those component receipts into one deterministic
verdict. It requires the 49-check fixture floor, accepted public-data audit,
identity/context/source-consistent replay, eight passing state-transition
scenarios, the 79-operation registry, sixteen release capability mappings,
stable repeated evaluation, and a secret-output boundary.

The fixture contains public research identifiers and declared reproducibility
measurements only. It contains no patient-level data. Its four negative controls
must remain in review: context mismatch, evidence-cycle detection,
accessibility failure, and deny-by-default deployment policy.

```powershell
glio-noncode estimate-off-target-risk off-targets.json --output off-target-report.json
glio-noncode optimize-validation-voi validation-options.json --output voi-plan.json
glio-noncode export-experiment-package experiment-package.json --output experiment-package.json
glio-noncode ingest-result-update-claims result-ingestion.json --output claim-updates.json
glio-noncode reclassify-evidence reclassification.json --output reclassification-report.json
glio-noncode manage-deprecation-supersession supersession.json --output supersession-report.json
glio-noncode build-audit-reproducibility-bundle audit-sections.json --output audit-bundle.json
glio-noncode publish-signed-dossier dossier.json --output signed-dossier.json
glio-noncode evaluate-structured-review review-form.json --output review-result.json
glio-noncode build-export-report report-sections.json --output report.json
glio-noncode search-command-palette search.json --output search-results.json
glio-noncode evaluate-accessibility-human-factors accessibility.json --output accessibility-report.json
glio-noncode evaluate-privacy-security-policy security-requests.json --output security-report.json
glio-noncode build-local-deployment-bundle deployment.json --output deployment-bundle.json
glio-noncode coordinate-federated-execution federated-plan.json --output federated-plan.json
glio-noncode decide-release-rollback release.json --output release-decision.json
```

These are research and platform-control receipts. A signed dossier is not a
clinical authorization, federated eligibility is not permission to access raw
data, and a release or rollback decision does not assert scientific validity.

The frontier controls also compose into four end-to-end pipelines. These
pipelines preserve every stage receipt and stop at the first reviewable gate:

- `ValidationFrontierPipeline` combines off-target risk, value-of-information
  selection, package export, execution readiness, and result-to-claim updates.
- `EvidenceLifecyclePipeline` combines graph integrity, lineage, reclassification,
  supersession, audit bundling, and signed dossier publication.
- `WorkbenchQualityPipeline` combines structured review, report export, search,
  accessibility, and human-factors event simulation.
- `DeploymentGovernancePipeline` combines policy admission, service dependency
  resolution, federated privacy accounting, deployment readiness, site-local
  coordination, and release/rollback gates.

```powershell
glio-noncode run-validation-frontier-pipeline validation-pipeline.json --output validation-pipeline-report.json
glio-noncode run-evidence-lifecycle-pipeline evidence-pipeline.json --output evidence-pipeline-report.json
glio-noncode run-workbench-quality-pipeline workbench-pipeline.json --output workbench-pipeline-report.json
glio-noncode run-deployment-governance-pipeline deployment-pipeline.json --output deployment-pipeline-report.json
```

The Domain 01 beta extensions deepen the variation contract without silently
coercing unresolved data:

- Cat-VRS-shaped categorical definitions can be loaded from versioned JSON,
  TSV, or CSV catalogs. Matching is limited to declared category IDs, aliases,
  ontology terms, and member variation IDs; a scientific label by itself never
  creates membership. The shape follows the [GA4GH Cat-VRS project](https://github.com/ga4gh/cat-vrs),
  while external schema validation remains a release gate.
- VA-Spec-shaped annotation envelopes retain subject, context, method,
  statement, evidence-line, source-version, and raw-hash provenance. Missing
  evidence, subject/context mismatch, and conflicting supported values are
  explicit states. The shape follows [GA4GH VA-Spec](https://va-spec.ga4gh.org/en/latest/core-information-model/index.html)
  and is not a clinical interpretation.
- Literal multi-allelic records become indexed child identities that retain the
  parent input hash, source version, original alternate, and allele-specific
  genotype projection. Symbolic structural alternates abstain and phasing is
  never inferred.
- Literal SNVs and indels can be replayed against a supplied local reference
  window to enumerate equivalent placements in homopolymers and short repeats.
  Reference mismatches, unsupported classes, and window limits abstain; global
  repeat equivalence is not claimed.
- `VariantEquivalenceResolver` compares normalized build, contig, interval,
  allele, and kind keys across source records and supports explicit aliases.
  Same-key records remain separate, and competing keys or out-of-scope context
  remain visible.
- `DuplicateAliasReconciler` groups duplicate normalized identities and emits
  explicit alias-collision groups without selecting a preferred source record.
- `BatchSampleIdentityChecker` checks declared batch, sample, and subject
  mappings, retaining missing fields, cross-subject sample conflicts, source
  versions, and line-addressable issues. It does not authenticate a specimen.
- `ChainOfCustodyCapture` records artifact event order, predecessor links,
  input/output hash continuity, per-artifact digests, and broken-chain issues.
  The receipt is not a signature or institutional custody attestation.

The beta command boundaries are:

```powershell
glio-noncode normalize-categorical variant.json --catalog categories.tsv --output category.json
glio-noncode build-annotation annotation.json --context-key "GRCh38|glioma|adult|unknown|unknown|unknown" --output annotation.json
glio-noncode decompose-multiallelic multiallelic.json --output alleles.json
glio-noncode normalize-repeat repeat.json --output repeat.json
glio-noncode resolve-variant-equivalence variants.json --query legacy-v1 --output equivalence.json
glio-noncode reconcile-variant-aliases variants.json --output reconciliation.json
glio-noncode check-batch-sample-identity samples.json --require-subject --output sample-identity.json
glio-noncode capture-chain-of-custody custody-events.json --output custody.json
```

The checked-in public aggregate variation fixture exercises the five deeper
Domain 01 adapters together. It uses NCBI ClinVar and GRCh38 assembly receipts,
public identifiers, a fixed local reference window, and no patient-level data.
The fixture proves supported VRS-shaped normalization, declared categorical
membership, provenance-complete annotation envelopes, lossless two-allele
decomposition, and repeat ambiguity without silent placement selection. Five
negative controls prove symbolic abstention, label-only categorical abstention,
annotation context rejection, symbolic multi-allelic rejection, and reference
mismatch rejection.

Run its independent data, operation, replay, and combined gates:

```powershell
glio-noncode audit-variation-data examples/variation-public-aggregate.json --output variation-data.json
glio-noncode evaluate-variation-fixture examples/variation-public-aggregate.json --output variation-fixture.json
glio-noncode replay-variation-fixtures examples/variation-public-aggregate.json --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" --output variation-replay.json
glio-noncode evaluate-variation-scenarios examples/variation-public-aggregate.json --output variation-scenarios.json
glio-noncode variation-contracts --output variation-contracts.json
glio-noncode variation-quality-gate examples/variation-public-aggregate.json --output variation-quality.json
```

The combined variation gate requires 29 fixture checks, five positive record
kinds, five negative controls, an independent ten-scenario state matrix, a
five-operation contract registry, exact source/context consistency, deterministic
content addresses, and a restricted-output boundary. Verified here means the
local public aggregate software contract passes; external RefGet equivalence,
Cat-VRS schema validation, VA-Spec interchange validation, global repeat truth
sets, and structural normalization remain separate validation work.

The checked-in public aggregate identity fixture exercises the next four Domain
01 adapters as one independently auditable slice:

- `VariantEquivalenceResolver` resolves a declared public alias across two
  normalized source records while preserving source IDs, variants, methods,
  competing-key visibility, and exact build/context filtering.
- `DuplicateAliasReconciler` retains duplicate normalized records and explicit
  alias collisions as separate groups. It never selects a preferred record and
  turns duplicate input IDs into a validation abstention.
- `BatchSampleIdentityChecker` proves a complete declared mapping and retains
  missing fields, cross-subject conflicts, batch/sample summaries, source
  versions, and stable issue codes without authenticating a specimen.
- `ChainOfCustodyCapture` proves a three-event artifact chain and exposes
  predecessor-link gaps, hash continuity gaps, cross-artifact links, event
  ordering, per-artifact digests, and invalid-timestamp abstention.

The fixture is public aggregate data only. It uses the same exact glioma context
and public NCBI source receipts as the variation fixture; it does not contain
patient-level values or claim biological identity, consent, clinical meaning,
digital signatures, or institutional custody attestation. Eight controls cover
out-of-domain build, absent query, ambiguous alias, duplicate input ID, a
cross-subject sample, a missing subject, a broken custody link, and an invalid
timestamp.

Run the independent identity boundaries and combined gate:

```powershell
glio-noncode audit-identity-data examples/identity-public-aggregate.json --output identity-data.json
glio-noncode evaluate-identity-fixture examples/identity-public-aggregate.json --output identity-fixture.json
glio-noncode replay-identity-fixtures examples/identity-public-aggregate.json --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" --output identity-replay.json
glio-noncode evaluate-identity-scenarios examples/identity-public-aggregate.json --output identity-scenarios.json
glio-noncode identity-contracts --output identity-contracts.json
glio-noncode identity-quality-gate examples/identity-public-aggregate.json --output identity-quality.json
glio-noncode build-identity-bundle examples/identity-public-aggregate.json --output identity-bundle.json
```

The combined identity gate requires 37 fixture checks, four positive operation
records, eight negative controls, an independent twelve-scenario matrix, a
four-operation contract registry, exact source/context consistency, replay
count floors, deterministic content addresses, and a restricted-output
boundary. Verified here means the local public aggregate software contract
passes; RefGet-backed identity truth, specimen authentication, consent review,
signatures, and institutional custody systems remain separate validation work.

## Domain 02 structural beta extensions

The structural beta plane adds four bounded detector contracts:

- `FocalAmplificationBoundaryMapper` thresholds copy-number segments, merges
  only observed neighboring intervals, and retains left/right boundary support
  from every caller. It does not impute uncovered sequence or make a gene-level
  amplification claim.
- `ChromothripsisPatternDetector` measures bounded breakpoint clustering,
  orientation switches, and supplied copy-number oscillation. Its evidence
  index is descriptive, not a probability, and missing copy-number state keeps
  the result partial.
- `ExtrachromosomalDnaCandidateDetector` requires explicit circular evidence,
  junction support, and amplification evidence before returning a stronger
  candidate state. High copy number by itself never creates an ecDNA result,
  and conflicting linear evidence remains ambiguous.
- `EnhancerHijackingCandidateDetector` requires an exact `ReferenceContext.key`,
  an explicit structural bridge, and declared evidence channels. It keeps
  alternative target genes and does not substitute nearest-gene proximity for
  a regulatory link.

The beta command boundaries are:

```powershell
glio-noncode map-focal-amplification segments.json --output focal.json
glio-noncode detect-chromothripsis breakpoints.json --output chromothripsis.json
glio-noncode detect-ecdna structural-evidence.json --output ecdna.json
glio-noncode detect-enhancer-hijacking links.json --context-key "GRCh38|glioma|adult|unknown|unknown|unknown" --output hijacking.json
```

The Domain 02 phased and graph extensions deepen structural representation:

- `PhasedHaplotypeAssembler` creates ordered paths only from explicit phased
  genotype fields. It retains phase sets, allele calls, source hashes, missing
  alleles, and unphased observations; it does not infer read-backed phase or
  reconstruct sequence.
- `AlleleAwareSvRepresenter` retains structural event coordinates per allele,
  genotype dosage, zygosity, copy number, support, and contradictory caller
  records. It does not collapse allele-specific events into a single event.
- `PangenomeGraphProjector` maps bounded intervals to supplied graph nodes and
  paths with exact, contained, spanning, overlapping, and unmapped states.
  Multiple paths remain visible, and coordinate overlap is not sequence
  homology.
- `RepeatMobileElementAnnotator` uses an indexed, source-versioned interval
  catalogue to return repeat family, class, subfamily, strand, mobile status,
  overlap fraction, and no-hit queries. It does not derive transposition from
  sequence or claim annotation completeness.

```powershell
glio-noncode assemble-haplotype phased-variants.json --context-key "GRCh38|glioma|adult|unknown|unknown|unknown" --output haplotypes.json
glio-noncode represent-allele-aware-sv structural-events.json --output allele-aware.json
glio-noncode project-pangenome projection-queries.json --nodes graph-nodes.json --output graph-projection.json
glio-noncode annotate-repeat-mobile structural-events.json --annotations repeats.json --mobile-only --output repeat-annotations.json
```

## Domain 02 structural haplotype evidence boundary

The C09-C12 extension turns the four structural haplotype adapters into one
independently auditable release family. The boundary is organized around four
operations and one exact aggregate context:

- C09 phased haplotypes preserve explicit `GT`, phase-set, allele, and source
  observations. A missing phase is retained as an ambiguous control rather
  than being filled by inference.
- C10 allele-aware structural events preserve allele index, dosage, phase,
  copy number, support, and contradictory observations. A coordinate conflict
  is review evidence, not a silent merge.
- C11 pangenome projection maps bounded queries to supplied path nodes and
  keeps ambiguous and unmapped candidates visible. Coordinate overlap is not
  sequence homology.
- C12 repeat/mobile annotation joins bounded intervals to a supplied,
  source-versioned catalogue and retains class, family, strand, mobile status,
  and overlap. A context mismatch stays in review.

The checked-in aggregate contains four positive records and eight controls,
all scoped to
`GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment`.
It is built from public aggregate receipts for NCBI dbVar, the dbVar Human
Structural Variation Data Hub, the dbVar Study Browser, the dbVar FTP manifest,
and gnomAD-SV. No patient-level values are required by the fixture.

The execution stack is deliberately layered:

- the fixture evaluator produces 72 individual checks and sanitized operation
  receipts;
- the replay runner proves fixture identity, exact context, source set,
  record floors, and deterministic addresses;
- the scenario matrix independently exercises 12 positive/review transitions;
- the quality gate reconciles 20 checks, including contracts, lineage, and
  the sanitized output boundary;
- the lineage graph contains 29 typed nodes and 36 typed edges from sources
  through fixture records to result receipts;
- the bundle builder publishes 12 compact entries in JSON, CSV, or Markdown;
- the runtime executes C09, C10, C11, and C12 in order and returns accepted,
  review, or blocked aggregate state with a stage manifest.

Run the complete C09-C12 surface locally:

```powershell
python -m glio_noncode audit-structural-haplotype-data examples/structural-haplotype-public-aggregate.json --output haplotype-data.json
python -m glio_noncode evaluate-structural-haplotype-fixture examples/structural-haplotype-public-aggregate.json --output haplotype-fixture.json
python -m glio_noncode replay-structural-haplotype-fixtures examples/structural-haplotype-public-aggregate.json --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" --output haplotype-replay.json
python -m glio_noncode evaluate-structural-haplotype-scenarios examples/structural-haplotype-public-aggregate.json --output haplotype-scenarios.json
python -m glio_noncode structural-haplotype-contracts --output haplotype-contracts.json
python -m glio_noncode structural-haplotype-quality-gate examples/structural-haplotype-public-aggregate.json --output haplotype-quality.json
python -m glio_noncode build-structural-haplotype-bundle examples/structural-haplotype-public-aggregate.json --output haplotype-bundle.json
python -m glio_noncode structural-haplotype-lineage examples/structural-haplotype-public-aggregate.json --output haplotype-lineage.json
python -m glio_noncode run-structural-haplotype-pipeline examples/structural-haplotype-pipeline-accepted.json --output haplotype-pipeline.json
```

The evidence gate is local software verification, not clinical validation. It
does not establish read-backed phase, long-read molecule assignment, graph
sequence homology, repeat annotation completeness, transposition, pathogenicity,
or treatment response. The full schema, issue taxonomy, release rules, and
tamper checks are documented in `docs/STRUCTURAL_HAPLOTYPE_EVIDENCE_GATE.md`
and `docs/STRUCTURAL_HAPLOTYPE_BUNDLE_FORMAT.md`.

Every future capability wave must add implementation modules, fixtures,
negative or abstention cases, and review-facing evidence before its ledger
state is advanced.

## Domain 03 specimen context

The specimen-context plane keeps sample and specimen labels project-local and
declarative. It maps conflicting ontology rows as ambiguous, resolves a
matched normal only when the same subject has exactly one declared normal,
imports purity/ploidy tables with caller receipts, and flags declared
fingerprint conflicts while abstaining on incomplete contamination evidence.
These are local partial capabilities until locked canonical fixtures and
external calibration benchmarks are available.

The Domain 03 scientific-beta extensions add four conservative measurement
surfaces:

- `SomaticGermlineOriginClassifier` keeps tumor/normal presence, allele
  fractions, normal read evidence, and declared population frequency as
  separate channels. Conflicting channels remain uncertain.
- `MosaicismPosteriorEstimator` measures repeated low-fraction observations
  across distinct tissues and exposes calibration metadata. Without a declared
  calibration identifier, its posterior-shaped value is explicitly uncalibrated.
- `CancerCellFractionEstimator` uses purity, total copy number, alternate copy
  number, and VAF in a transparent model. Raw values outside the model range
  are retained and marked partial rather than clamped silently.
- `SubcloneAssigner` creates relative within-sample CCF clusters and keeps
  distance-to-cluster and boundary ambiguity. It does not infer phylogeny,
  mutation order, or named biological clones.

The beta command boundaries are:

```powershell
glio-noncode classify-origin origin-observations.json --output origin.json
glio-noncode estimate-mosaicism tissue-observations.json --output mosaicism.json
glio-noncode estimate-ccf ccf-input.json --output ccf.json
glio-noncode assign-subclones ccf-estimates.json --output subclones.json
```

### Domain 03 C05-C08 aggregate evidence gate

The four beta adapters now have an independent aggregate evidence plane at
`examples/specimen-beta-frontier-public-aggregate.json`. It uses public
ClinVar classification and submission documentation plus GDC VCF and DNA
sequencing documentation as metadata-shaped source receipts. The checked-in
records are synthetic aggregate validation payloads; the receipts define
source vocabulary and scope rather than claiming that the source pages contain
these rows.

The four verified operations are:

- C05 origin classification: tumor and normal observations remain separate;
  population-frequency evidence is retained as its own channel, and conflicts
  remain uncertain.
- C06 mosaicism evidence: repeated low-fraction observations are grouped by
  distinct aggregate tissues; contamination flags reduce the evidence surface,
  and uncalibrated posterior-shaped values remain labeled as uncalibrated.
- C07 cancer-cell fraction: purity, VAF, total copy number, alternate copy
  number, and optional depth intervals are retained; out-of-range raw values
  are not silently clamped.
- C08 relative subclones: CCF observations are clustered within sample scope;
  distance and boundary ambiguity remain visible, and cluster IDs make no
  biological ancestry claim.

The evidence gate contains four accepted positive records and eight review
controls. It executes 72 fixture checks, a 12-scenario matrix, four operation
contracts, 21 quality checks, a 29-node/36-edge lineage graph, a 12-entry
sanitized bundle, and a four-stage runtime. The controls cover conflicting
origin evidence, malformed fractions, single-tissue and contaminated
mosaicism, out-of-range and zero-purity CCF, boundary clustering, and invalid
CCF rows.

```powershell
python -m glio_noncode audit-specimen-beta-frontier-data examples/specimen-beta-frontier-public-aggregate.json --output beta-data.json
python -m glio_noncode evaluate-specimen-beta-frontier-fixture examples/specimen-beta-frontier-public-aggregate.json --output beta-fixture.json
python -m glio_noncode replay-specimen-beta-frontier-fixtures examples/specimen-beta-frontier-public-aggregate.json --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" --output beta-replay.json
python -m glio_noncode specimen-beta-frontier-quality-gate examples/specimen-beta-frontier-public-aggregate.json --output beta-quality.json
python -m glio_noncode evaluate-specimen-beta-frontier-scenarios examples/specimen-beta-frontier-public-aggregate.json --output beta-scenarios.json
python -m glio_noncode specimen-beta-frontier-contracts --output beta-contracts.json
python -m glio_noncode build-specimen-beta-frontier-bundle examples/specimen-beta-frontier-public-aggregate.json --output beta-bundle.json
python -m glio_noncode specimen-beta-frontier-lineage examples/specimen-beta-frontier-public-aggregate.json --output beta-lineage.json
python -m glio_noncode run-specimen-beta-frontier-pipeline examples/specimen-beta-frontier-pipeline-accepted.json --output beta-pipeline.json
```

The accepted pipeline reaches `published`; the review pipeline retains stage
review states and does not publish. Review bundles require explicit opt-in.
The complete source boundary, issue taxonomy, replay rules, and bundle schema
are documented in `docs/SPECIMEN_BETA_FRONTIER_EVIDENCE_GATE.md` and
`docs/SPECIMEN_BETA_FRONTIER_BUNDLE_FORMAT.md`.

### Domain 03 C09-C12 longitudinal specimen evidence gate

The longitudinal and exposure adapters now have a complete aggregate evidence
plane at `examples/specimen-lineage-public-aggregate.json`. The fixture is
shaped by public GDC biospecimen documentation and contains synthetic
aggregate observations only. Its exact context is
`GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment`.

The four verified operation families are:

- C09 region lineage: declared parent edges produce subject-local roots and
  leaves, while missing parents and cycles remain partial or contradictory.
- C10 longitudinal linking: declared predecessors and deterministic collection
  ordering produce same-case links with gap labels, tissue changes, and missing
  dates retained.
- C11 phase mapping: primary, recurrence, interval, and unknown states require
  explicit labels or a declared primary predecessor; later time alone does not
  become recurrence.
- C12 treatment context: specimen collection times are compared with declared
  exposure intervals to preserve pre/on/post relations, overlap ambiguity, and
  missing times without claiming response or resistance.

The release surface contains four positive records and eight review controls,
159 deterministic fixture assertions, a 12-row independent scenario matrix,
four operation contracts, a 22-check quality gate, a 29-node/28-edge typed
lineage graph, a 12-entry sanitized bundle, a receipt-index reconciliation, and
a four-stage runtime. The
public source receipts are the GDC biospecimen submission walkthrough, GDC
biospecimen data model, TCGA barcode hierarchy, and GDC available-fields
documentation. The receipts establish schema vocabulary and scope; they do
not claim that the checked-in synthetic rows were copied from those pages.

Run the complete C09-C12 surface locally:

```powershell
python -m glio_noncode audit-specimen-lineage-data examples/specimen-lineage-public-aggregate.json --output lineage-data.json
python -m glio_noncode evaluate-specimen-lineage-fixture examples/specimen-lineage-public-aggregate.json --output lineage-fixture.json
python -m glio_noncode replay-specimen-lineage-fixtures examples/specimen-lineage-public-aggregate.json --required-context-key "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment" --output lineage-replay.json
python -m glio_noncode evaluate-specimen-lineage-scenarios examples/specimen-lineage-public-aggregate.json --output lineage-scenarios.json
python -m glio_noncode specimen-lineage-contracts --output lineage-contracts.json
python -m glio_noncode specimen-lineage-quality-gate examples/specimen-lineage-public-aggregate.json --output lineage-quality.json
python -m glio_noncode build-specimen-lineage-bundle examples/specimen-lineage-public-aggregate.json --output lineage-bundle.json
python -m glio_noncode specimen-lineage-lineage examples/specimen-lineage-public-aggregate.json --output lineage-graph.json
python -m glio_noncode specimen-lineage-reconciliation examples/specimen-lineage-public-aggregate.json --output lineage-reconciliation.json
python -m glio_noncode run-specimen-lineage-pipeline examples/specimen-lineage-pipeline-accepted.json --output lineage-pipeline.json
```

The accepted runtime publishes all four stages; the review runtime keeps the
missing-parent, missing-predecessor, conflicting-phase, and overlapping-
exposure states visible and does not publish. Review bundles require explicit
opt-in. The full contract is implemented in the `specimen_lineage_*` modules
and covered by the `tests/test_specimen_lineage_*` suite.

The Domain 03 longitudinal and exposure extensions deepen specimen context:

- `MultiRegionLineageResolver` builds subject-local region graphs from
  declared parent edges and retains roots, leaves, missing parents, cycles,
  relationship labels, and source receipts. It does not authenticate a
  specimen or infer clonal ancestry.
- `LongitudinalSpecimenLinker` links same-subject specimens through declared
  predecessors or deterministic collection-time ordering. Tissue changes,
  missing dates, gap labels, and the ordering basis remain visible; temporal
  order is not biological evolution.
- `PrimaryRecurrencePhaseMapper` maps explicit primary, recurrence, interval,
  and unknown labels. A later collection date alone remains unknown, and
  conflicting phase declarations remain contradictory.
- `TreatmentExposureContextualizer` compares same-subject specimen times with
  declared therapy intervals and returns pre-treatment, on-treatment, or
  post-treatment context, including overlapping exposures and missing times.
  It does not infer response, resistance, or causality.

```powershell
glio-noncode resolve-multi-region-lineage regions.json --output region-lineage.json
glio-noncode link-longitudinal-specimens specimens.json --output longitudinal.json
glio-noncode map-primary-recurrence specimens.json --output phase-map.json
glio-noncode contextualize-treatment specimens.json --exposures treatments.json --output treatment-context.json
```

### Domain 03 C13-C16 preanalytic and context release gate

The C13-C16 specimen capabilities now have their own aggregate evidence plane.
It wraps the preanalytic quality, assay protocol lineage, identity conflict,
and specimen-context envelope adapters with a public source manifest, an exact
six-part context key, twelve aggregate fixture records, and explicit
positive/review controls. The fixture is shaped by public GDC and NCI
biospecimen documentation; it is synthetic aggregate validation material and
does not copy patient-level rows.

The four operations are:

- C13 `BiospecimenPreanalyticQualityAssessor`: applies declared ischemia,
  storage-temperature, and RNA-integrity thresholds while retaining missing and
  failed metrics, scores, source IDs, and review issue codes.
- C14 `AssayLineageProtocolTracker`: retains specimen, protocol, assay,
  operator, start-time, parent-node, root, duplicate-node, and missing-parent
  relationships in a deterministic graph view.
- C15 `IdentityConflictAdjudicator`: computes modal agreement and preserves
  ties and conflicting observations as review results. It does not authenticate
  a specimen or select a preferred source identity below the threshold.
- C16 `SpecimenContextEnvelopePublisher`: binds specimen IDs and the three
  constituent receipt addresses into a publication envelope. Missing or
  context-drifted receipts remain review and do not publish.

```powershell
python -m glio_noncode audit-specimen-preanalytic-data examples/specimen-preanalytic-public-aggregate.json --output preanalytic-data.json
python -m glio_noncode evaluate-specimen-preanalytic-fixture examples/specimen-preanalytic-public-aggregate.json --output preanalytic-fixture.json
python -m glio_noncode replay-specimen-preanalytic-fixtures examples/specimen-preanalytic-public-aggregate.json --output preanalytic-replay.json
python -m glio_noncode specimen-preanalytic-quality-gate examples/specimen-preanalytic-public-aggregate.json --output preanalytic-quality.json
python -m glio_noncode evaluate-specimen-preanalytic-scenarios examples/specimen-preanalytic-public-aggregate.json --output preanalytic-scenarios.json
python -m glio_noncode specimen-preanalytic-contracts --output preanalytic-contracts.json
python -m glio_noncode build-specimen-preanalytic-bundle examples/specimen-preanalytic-public-aggregate.json --output preanalytic-bundle.json
python -m glio_noncode specimen-preanalytic-lineage examples/specimen-preanalytic-public-aggregate.json --output preanalytic-lineage.json
python -m glio_noncode specimen-preanalytic-reconciliation examples/specimen-preanalytic-public-aggregate.json --output preanalytic-reconciliation.json
python -m glio_noncode run-specimen-preanalytic-pipeline examples/specimen-preanalytic-pipeline-accepted.json --output preanalytic-pipeline.json
```

The accepted path executes 131 fixture checks, 16 receipt-index checks, 25
quality-gate checks, twelve state-transition scenarios, four operation
contracts, a 29-node/28-edge typed graph, a twelve-entry sanitized bundle,
and four conserved runtime stages. The review fixture retains a missing
identity receipt and returns a non-publishing runtime state. See
`docs/SPECIMEN_PREANALYTIC_EVIDENCE_GATE.md` and
`docs/SPECIMEN_PREANALYTIC_BUNDLE_FORMAT.md` for the full schema, source
boundary, change rules, and release checks.

## Domain 04 reference coordinates

The reference plane resolves assembly aliases separately from mapping
evidence. Chain-like tables are imported as explicit equal-length segments;
liftover scoring reports absent, unique, or competing mappings; and
pangenome coordinates retain every declared path candidate. The resolver
never treats a coordinate conversion as proof of sequence equivalence.

The C01-C04 evidence gate is explicit at each boundary:

- C01 `ReferenceRegistry` resolves `GRCh38`/`hg38` and `GRCh37`/`hg19` aliases
  while retaining species, release, accession, and source metadata. Unknown
  accessions and future assembly labels remain invalid rather than being
  guessed from a string pattern.
- C02 `LiftoverChainManager` imports equal-length mapping segments with source
  hashes, preserves malformed rows, and projects only through one supplied
  segment. Missing mappings, competing segments, reverse-strand alleles, and
  breakends retain explicit outcomes.
- C03 `LiftoverAmbiguityScorer` emits a bounded score over all candidates.
  Unique, competing, and absent candidates are different states, and the
  score never selects a coordinate or discards alternatives.
- C04 `PangenomeCoordinateMapper` keeps path ID, sequence ID, source, version,
  strand, and interval for every declared path candidate. HPRC path labels are
  public reference metadata; containment is not a claim of graph equivalence.

The fixture source receipts point to NCBI GRC assembly documentation, NCBI
GRCh38 assembly data, UCSC LiftOver and chain-format documentation, and HPRC
public data and alignment catalogs. The fixture records are bounded coordinate
vectors, not patient records and not a substitute for downloading or validating
the complete underlying reference resources. C01-C04 changes must preserve
source closure, exact context, candidate retention, content addresses, and
non-publishing review controls.

The Domain 04 scientific-beta adapters add versioned annotation governance.
The C05-C08 evidence plane now verifies these adapters through the public
aggregate fixture, replay, bundle, graph, reconciliation, quality, and release
layers:

- `GencodeTranscriptAdapter` parses GTF/JSON transcript snapshots, splits
  versioned Ensembl identifiers, retains attributes and coordinates, and
  reports gene-level one-to-many transcript ambiguity.
- `ManeTranscriptAdapter` preserves MANE Select/Plus Clinical status and
  RefSeq/Ensembl cross-identifiers without selecting a preferred record when
  the catalog remains one-to-many.
- `RegulatoryOntologyAdapter` matches only declared regulatory term IDs,
  labels, and aliases. Ambiguous aliases remain ambiguous and no scientific
  label-based ontology inference is performed.
- `DiseaseOntologyMapper` maps declared source terms to explicit target
  namespaces and relationships, retaining multiple targets. It is an identity
  mapping surface, not a disease diagnosis.

The beta command boundaries are:

```powershell
glio-noncode parse-gencode gencode.gtf --output gencode.json
glio-noncode parse-mane mane.tsv --output mane.json
glio-noncode normalize-regulatory-term term.json --catalog regulatory-ontology.json --output term-normalized.json
glio-noncode map-disease-term disease.json --catalog disease-mappings.json --output disease-mapped.json
```

The Domain 04 reference-governance extensions deepen identity, population,
snapshot, and permission boundaries:

- `GeneAliasVersionResolver` resolves declared gene IDs, symbols, aliases,
  assemblies, and versions while retaining exact match bases and one-to-many
  results. Free-text functional descriptions are not identity evidence.
- `PopulationFrequencyAdapter` preserves population and ancestry scope,
  allele counts, homozygote counts, genome build, source versions, and either
  declared or AC/AN-derived frequency. It is not a clinical classification.
- `ReferenceSnapshotManager` builds sorted, content-addressed manifests of
  reference resources and compares snapshots by checksum and source version.
  It does not fetch or validate resource bytes.
- `LicenseUseRestrictionRegistry` evaluates explicit allowed/prohibited uses,
  attribution, redistribution, commercial terms, expiry, and conflicts.
  Missing permission blocks use rather than granting it.

```powershell
glio-noncode resolve-gene-alias gene-queries.json --catalog gene-catalog.json --assembly GRCh38 --output gene-resolution.json
glio-noncode adapt-population-frequency frequencies.json --genome-build GRCh38 --output frequencies-adapted.json
glio-noncode build-reference-snapshot resources.json --snapshot-id ref-2026-08 --assembly GRCh38 --source-id local-reference --output snapshot.json
glio-noncode evaluate-license-use resources.json --restrictions licenses.json --requested-use research --output license-evaluation.json
```

## Domain 05 regulatory atlases

The atlas extension parses ENCODE SCREEN-style cCRE records and supports
brain-cell, adult-glioma, and pediatric-glioma profiles over a bounded local
snapshot. Queries preserve source versions and raw hashes, gate on declared
cell state, disease, and age context, and distinguish supported overlap from
absence, ambiguity, and out-of-domain context. Atlas overlap is an annotation
observation, not proof of activity or causality.

### Domain 05 C01-C04 public cCRE evidence gate

The first four regulatory-atlas capabilities now have a dedicated, executable
public aggregate boundary. The fixture at
`examples/regulatory-atlas-public-aggregate.json` is shaped from official
ENCODE SCREEN/cCRE release documentation and keeps the local rows compact,
versioned, and non-subject-level. The official source receipts are:

- [SCREEN cCRE overview](https://screen.encodeproject.org/index/about)
- [ENCODE cCRE release ENCFF272QXW](https://www.encodeproject.org/files/ENCFF272QXW/)
- [ENCODE cCRE v2 pipeline](https://www.encodeproject.org/pipelines/ENCPL751FOQ/)
- [ENCODE annotations catalog](https://www.encodeproject.org/data/annotations/)
- [ENCODE portal](https://www.encodeproject.org/)

The executable slice includes `CcreTrackParser` for BED/TSV/JSON conversion
and malformed-row quarantine, plus context-gated brain-cell, adult-glioma, and
pediatric-glioma profile queries. Four positive rows and twelve controls cover
valid parsing, malformed coordinates, malformed JSON, context mismatch,
absence, and overlap ambiguity. The profile layer preserves the distinction
between a supported overlap and a biological conclusion.

The integrated boundary contains 120 evaluation checks, 13 independent
scenarios, 13 replay checks, 12 policy rules, a 157-node/157-edge sanitized
lineage graph, 25 quality checks, balanced operation metrics, accepted-only
JSON/CSV/Markdown bundles, a nine-stage runtime, and a twelve-check release
manifest. Receipts omit input text and executable payload collections.

```powershell
python -m glio_noncode audit-regulatory-atlas-data examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-data.json
python -m glio_noncode evaluate-regulatory-atlas-fixture examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-fixture.json
python -m glio_noncode replay-regulatory-atlas-fixtures examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-replay.json
python -m glio_noncode regulatory-atlas-quality-gate examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-quality.json
python -m glio_noncode evaluate-regulatory-atlas-scenarios examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-scenarios.json
python -m glio_noncode regulatory-atlas-contracts --output regulatory-atlas-contracts.json
python -m glio_noncode regulatory-atlas-metrics examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-metrics.json
python -m glio_noncode build-regulatory-atlas-bundle examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-bundle.json --accepted-only
python -m glio_noncode regulatory-atlas-lineage examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-lineage.json
python -m glio_noncode regulatory-atlas-reconciliation examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-reconciliation.json
python -m glio_noncode run-regulatory-atlas-pipeline examples/regulatory-atlas-pipeline-accepted.json --output regulatory-atlas-pipeline.json
python -m glio_noncode build-regulatory-atlas-release examples/regulatory-atlas-public-aggregate.json --output regulatory-atlas-release.json
```

See `docs/REGULATORY_ATLAS_EVIDENCE_GATE.md` and
`docs/REGULATORY_ATLAS_RELEASE_FORMAT.md` for the complete source boundary,
state semantics, receipt fields, policy rules, and release schema.

### Domain 05 C05-C08 molecular-state and histone evidence gate

The next four atlas capabilities now have a separate public aggregate evidence
plane. The fixture at `examples/molecular-atlas-public-aggregate.json` covers:

- `MolecularStateAtlasAdapter` for IDH-mutant state evidence;
- `MolecularStateAtlasAdapter` for IDH-wildtype state evidence;
- `MolecularStateAtlasAdapter` for H3K27-altered state evidence;
- `HistoneMarkTrackHarmonizer` for replicate-aware H3K27ac interval summaries.

The state profiles require exact state and `ReferenceContext.key` matches.
Supported, absent, out-of-domain, and ambiguous results remain distinct. The
histone path splits intervals at observed boundaries, retains replicate and
caller identity, reports median signal and spread, and keeps invalid rows,
single replicates, and disagreement as review states. Histone signal remains a
descriptive observation rather than an activity or causal estimate.

The public source receipts use [ENCODE histone standards](https://www.encodeproject.org/chip-seq/histone/), the [ENCODE histone pipeline](https://www.encodeproject.org/pipelines/ENCPL272XAE/), the [NCI adult CNS tumor reference](https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq), the [NCI childhood cancer data boundary](https://www.cancer.gov/research/areas/childhood/childhood-cancer-data-initiative), and the [NCI GDC lower-grade glioma publication](https://gdc.cancer.gov/about-data/publications/lgg_2015). These receipts describe the public vocabulary and processing boundary; the checked-in rows are compact aggregate fixture records.

The accepted path executes 120 evaluation checks, 15 independent scenarios,
13 replay checks, 12 policy rules, a 157-node/158-edge sanitized lineage
graph, 25 quality checks, four balanced operation metrics, accepted-only
JSON/CSV/Markdown bundles, a nine-stage runtime, and a twelve-check release
manifest.

```powershell
python -m glio_noncode audit-molecular-atlas-data examples/molecular-atlas-public-aggregate.json --output molecular-atlas-data.json
python -m glio_noncode evaluate-molecular-atlas-fixture examples/molecular-atlas-public-aggregate.json --output molecular-atlas-fixture.json
python -m glio_noncode replay-molecular-atlas-fixtures examples/molecular-atlas-public-aggregate.json --output molecular-atlas-replay.json
python -m glio_noncode molecular-atlas-quality-gate examples/molecular-atlas-public-aggregate.json --output molecular-atlas-quality.json
python -m glio_noncode evaluate-molecular-atlas-scenarios examples/molecular-atlas-public-aggregate.json --output molecular-atlas-scenarios.json
python -m glio_noncode molecular-atlas-contracts --output molecular-atlas-contracts.json
python -m glio_noncode molecular-atlas-metrics examples/molecular-atlas-public-aggregate.json --output molecular-atlas-metrics.json
python -m glio_noncode build-molecular-atlas-bundle examples/molecular-atlas-public-aggregate.json --output molecular-atlas-bundle.json --accepted-only
python -m glio_noncode molecular-atlas-lineage examples/molecular-atlas-public-aggregate.json --output molecular-atlas-lineage.json
python -m glio_noncode molecular-atlas-reconciliation examples/molecular-atlas-public-aggregate.json --output molecular-atlas-reconciliation.json
python -m glio_noncode run-molecular-atlas-pipeline examples/molecular-atlas-pipeline-accepted.json --output molecular-atlas-pipeline.json
python -m glio_noncode build-molecular-atlas-release examples/molecular-atlas-public-aggregate.json --output molecular-atlas-release.json
```

See `docs/MOLECULAR_ATLAS_EVIDENCE_GATE.md` and
`docs/MOLECULAR_ATLAS_RELEASE_FORMAT.md` for source scope, state semantics,
histone handling, policy rules, receipt fields, and release verification.

The Domain 05 scientific-beta extensions keep molecular states separate:

- `MolecularStateAtlasAdapter` supports IDH-mutant, IDH-wildtype, and
  H3K27-altered state records with exact state and `ReferenceContext.key`
  matching. Evidence from another state or context is not transported.
- `HistoneMarkTrackHarmonizer` converts histone-mark observations into atomic
  intervals at observed boundaries, reports median signal and replicate spread,
  and keeps one-replicate and high-disagreement intervals partial or ambiguous.
  Signal remains descriptive and is not a calibrated activity call.

The beta command boundaries are:

```powershell
glio-noncode query-state-atlas state-atlas.json --molecular-state "IDH-mutant" --chromosome 7 --start 100 --end 200 --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output state-query.json
glio-noncode harmonize-histone histone.tsv --output histone.json
```

The Domain 05 atlas-alpha tranche deepens track and regulatory-role
boundaries without merging assay semantics. C09-C12 are now verified through a
public aggregate, non-patient fixture with 4 positive records, 12 review
controls, 120 evaluation checks, deterministic replay, source lineage,
reconciliation, policy, metrics, quality-gated runtime, and release artifacts.
See `docs/ATLAS_ALPHA_EVIDENCE_GATE.md` and
`docs/ATLAS_ALPHA_EVIDENCE_RELEASE_FORMAT.md` and
`docs/ATLAS_ALPHA_EVIDENCE_SCHEMA.md` for the evidence boundary, release
manifest, and typed output schema.

- `OpenChromatinTrackHarmonizer` splits ATAC/DNase-style observations at
  every observed boundary and retains replicate, caller, source, context,
  signal spread, and ambiguity. Accessibility is not activity.
- `MethylationTrackHarmonizer` derives fractions from methylated/total counts
  when available and keeps coverage, replicate spread, zero-coverage partial
  states, source hashes, and exact context attached to each interval.
- `EnhancerPromoterSilencerClassifier` evaluates declared role channels and
  reports multi-role ambiguity, missing channels, and methylation-based
  silencer candidates without inferring silencing or causality.
- `SuperEnhancerCandidateAtlas` ranks enhancer constituents, groups selected
  intervals by chromosome and proximity, preserves declared target genes, and
  labels candidates partial when activity evidence is absent.

```powershell
glio-noncode harmonize-open-chromatin atac.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output atac-harmonized.json
glio-noncode harmonize-methylation methylation.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output methylation-harmonized.json
glio-noncode classify-regulatory-role regulatory-elements.json --role-threshold 0.5 --output regulatory-roles.json
glio-noncode build-super-enhancer-atlas enhancers.json --minimum-constituents 3 --merge-gap-bp 100 --output super-enhancer-candidates.json
glio-noncode audit-atlas-alpha-evidence-data --output atlas-alpha-audit.json
glio-noncode evaluate-atlas-alpha-evidence --output atlas-alpha-evaluation.json
glio-noncode atlas-alpha-evidence-quality-gate --output atlas-alpha-quality.json
glio-noncode run-atlas-alpha-evidence-pipeline --run-id c09-c12-local --output atlas-alpha-run.json
glio-noncode build-atlas-alpha-evidence-release --run-id c09-c12-release --output atlas-alpha-release.json
```

### Domain 05 C13-C16 frontier atlas evidence gate

The C13-C16 frontier completes the deeper regulatory-atlas evidence plane for
insulator boundaries, regulatory hotspots, evidence-tier adjudication, and
snapshot publication. The checked-in fixture at
`examples/frontier-atlas-evidence-pipeline-accepted.json` is a public,
non-patient aggregate boundary with four positive paths and twelve visible
controls. It uses exact context `GRCh38|diffuse_glioma|adult|stem_like|core|untreated`
and never treats aggregate evidence as a patient-level or clinical claim.

The public source receipts define the data vocabulary and processing boundary:

- [ENCODE Hi-C standards](https://www.encodeproject.org/hic/)
- [ENCODE Hi-C pipeline](https://www.encodeproject.org/pipelines/ENCPL839OAB/)
- [ENCODE pipeline catalog](https://www.encodeproject.org/pipelines/)
- [ENCODE SCREEN overview](https://screen.encodeproject.org/index/about)
- [NCI adult CNS tumor reference](https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq)

The four operations preserve distinct outcomes:

- C13 `InsulatorBoundaryAtlas` retains interval validity, insulation score,
  support, orientation, exact context, and low-support or malformed-interval
  review states.
- C14 `RegulatoryHotspotAtlas` retains source count, evidence types, direction
  concordance, support, and disagreement; direction is not a mechanism claim.
- C15 `AtlasEvidenceTierAdjudicator` emits evidence labels from declared source
  and reproducibility floors; a tier is not a calibrated probability.
- C16 `AtlasSnapshotPublisher` binds schema, version, context, record address,
  and manifest address. Empty snapshots abstain, context drift is quarantined,
  and invalid metadata cannot publish.

The evidence plane executes 120 fixture checks, 12 policy rules, 23 schema
checks, deterministic replay, scenario evaluation, source-to-receipt lineage,
expected/observed reconciliation, operation metrics, a nine-stage runtime
trace, sanitized review views, CSV/Markdown/JSON exports, and a release
manifest. Receipts exclude raw input text and aggregate payload collections.

```powershell
python -m glio_noncode audit-frontier-atlas-data examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-data.json
python -m glio_noncode evaluate-frontier-atlas-fixture examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-fixture.json
python -m glio_noncode replay-frontier-atlas examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-replay.json
python -m glio_noncode frontier-atlas-quality-gate examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-quality.json
python -m glio_noncode evaluate-frontier-atlas-scenarios examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-scenarios.json
python -m glio_noncode frontier-atlas-contracts --output frontier-atlas-contracts.json
python -m glio_noncode frontier-atlas-schema examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-schema.json
python -m glio_noncode frontier-atlas-metrics examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-metrics.json
python -m glio_noncode build-frontier-atlas-bundle examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-bundle.json
python -m glio_noncode frontier-atlas-lineage examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-lineage.json
python -m glio_noncode frontier-atlas-reconciliation examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-reconciliation.json
python -m glio_noncode frontier-atlas-policy examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-policy.json
python -m glio_noncode run-frontier-atlas-pipeline examples/frontier-atlas-evidence-pipeline-accepted.json --run-id frontier-atlas-release --output frontier-atlas-runtime.json
python -m glio_noncode build-frontier-atlas-release examples/frontier-atlas-evidence-pipeline-accepted.json --run-id frontier-atlas-release --output frontier-atlas-release.json
python -m glio_noncode frontier-atlas-review-view examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-review.json
python -m glio_noncode frontier-atlas-trace examples/frontier-atlas-evidence-pipeline-accepted.json --run-id frontier-atlas-trace --output frontier-atlas-trace.json
python -m glio_noncode export-frontier-atlas-receipts-csv examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-receipts.csv
python -m glio_noncode export-frontier-atlas-review-csv examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-review.csv
python -m glio_noncode export-frontier-atlas-review-markdown examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-review.md
python -m glio_noncode export-frontier-atlas-metrics-csv examples/frontier-atlas-evidence-pipeline-accepted.json --output frontier-atlas-metrics.csv
```

See `docs/ATLAS_FRONTIER_EVIDENCE_GATE.md`,
`docs/ATLAS_FRONTIER_RELEASE_FORMAT.md`, and
`docs/ATLAS_FRONTIER_SCHEMA.md` for source scope, state transitions, receipt
fields, output restrictions, and release verification.

## Domain 06 sequence and model adapters

The sequence plane emits deterministic context features separately from
external model outputs. Foundation-model and long-context adapters require
model/version and context-window metadata, validate reported deltas, retain
source hashes, and quarantine inconsistent rows. The delta ensemble reports
mean and disagreement by variant; it does not convert model output into a
probability or clinical interpretation.

The Domain 06 scientific-beta extensions make sequence grammar inspectable:

- `MotifDisruptionScanner` and `MotifCreationScanner` compare reference and
  alternate windows against declared IUPAC consensus motifs. Hits retain
  one-based coordinates, strand, match score, motif source/version, sequence
  hashes, exact context, and alternate-only or reference-only evidence.
- `MotifSpacingGrammarAnalyzer` evaluates declared motif-pair spacing and
  orientation rules, retains every compatible pair, and reports unmatched
  rules instead of selecting a preferred pair silently.
- `CooperativeTFGrammarModel` applies versioned weighted interactions to
  compatible motif hits and returns per-interaction contributions, required
  missing interactions, and a reproducible descriptive score. Its result is
  explicitly not a probability, binding claim, clinical interpretation, or
  calibrated regulatory-effect estimate.

The beta command boundaries are:

```powershell
glio-noncode scan-motif-disruption motif-window.json --output motif-losses.json
glio-noncode scan-motif-creation motif-window.json --output motif-gains.json
glio-noncode analyze-motif-grammar motif-grammar.json --output grammar.json
glio-noncode score-cooperative-grammar motif-grammar.json --model-id declared-grammar --model-version 2026.1 --output grammar-score.json
```

The Domain 06 sequence-alpha tranche adds four bounded sequence-regulatory
contracts:

- `NucleosomeSequencePropensityModel` emits a transparent phase-aware
  dinucleotide and GC-balance index with length and ambiguity states. It is a
  sequence proxy, not calibrated nucleosome occupancy.
- `SpliceRegulatoryNoncodingScanner` scans declared donor, acceptor,
  branchpoint, polypyrimidine, or other splice motifs on reference and
  optional alternate windows, retaining strand, score, source version, and
  created/disrupted hits without inferring splice consequence.
- `UtrRegulatoryScanner` keeps 5-prime and 3-prime UTR motif evidence
  separate and reports bounded start/stop patterns in 5-prime UTRs as
  sequence observations rather than translation or expression predictions.
- `PromoterCoreGrammarModel` evaluates declared core-promoter motif pairs by
  spacing, orientation, and weighted rule coverage, preserving all compatible
  pairs and unmatched rules instead of selecting one grammar silently.

```powershell
glio-noncode predict-nucleosome-propensity sequence-windows.json --minimum-length 147 --output nucleosome-index.json
glio-noncode scan-splice-regulatory splice-windows.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output splice-evidence.json
glio-noncode scan-utr-regulatory utr-windows.json --minimum-uorf-codons 2 --output utr-evidence.json
glio-noncode evaluate-promoter-grammar promoter-grammar.json --minimum-coverage 0.5 --output promoter-grammar.json
```

### Domain 06 C13-C16 sequence frontier evidence gate

The Domain 06 C13-C16 tranche makes four sequence-regulatory boundaries
executable against a checked-in public aggregate fixture. The fixture contains
four positive records, twelve visible controls, five source receipts, exact
GRCh38 context, and a `public_aggregate_non_patient` evidence boundary. It
stores source summaries and content addresses without embedding raw external
payloads or subject-level identifiers.

- C13 `enhancer_grammar` wraps motif-pair spacing, orientation, coverage, and
  compatible-pair evidence. Missing motif hits, insufficient coverage, and
  context mismatch are distinct outcomes; grammar compatibility is descriptive.
- C14 `allele_saturation` wraps reference-to-alternate score deltas with point
  counts, uncertainty floors, positive-effect identifiers, and explicit review
  states. A score delta is not effect proof.
- C15 `ensemble_disagreement` retains prediction IDs, mean, spread, interval,
  range disagreement, and completeness checks. Disagreement is reported as a
  model comparison and is not converted into probability or clinical meaning.
- C16 `sequence_evidence_publish` binds sequence IDs, model receipt IDs,
  context, record addresses, bundle addresses, and publication state. Empty
  records abstain and invalid metadata is quarantined rather than published.

The evidence plane includes 120 deterministic evaluation checks, 23 schema
checks, 12 review-queue entries, four out-of-domain controls, a seven-rule
review budget, nine trace stages, lineage and reconciliation reports, replay
expectations, sanitized CSV/Markdown exports, and a release manifest. Every
positive and control record is evaluated through the same contract path.

```powershell
glio-noncode evaluate-sequence-frontier-fixture examples/sequence-frontier-evidence-pipeline-accepted.json --output sequence-frontier-evaluation.json
glio-noncode sequence-frontier-quality-gate examples/sequence-frontier-evidence-pipeline-accepted.json --output sequence-frontier-quality.json
glio-noncode run-sequence-frontier-pipeline examples/sequence-frontier-evidence-pipeline-accepted.json --run-id d06-local --output sequence-frontier-run.json
glio-noncode build-sequence-frontier-release examples/sequence-frontier-evidence-pipeline-accepted.json --run-id d06-release --output sequence-frontier-release.json
glio-noncode export-sequence-frontier-review-markdown examples/sequence-frontier-evidence-pipeline-accepted.json --output sequence-frontier-review.md
```

See `docs/SEQUENCE_FRONTIER_EVIDENCE_GATE.md`,
`docs/SEQUENCE_FRONTIER_RELEASE_FORMAT.md`, and
`docs/SEQUENCE_FRONTIER_SCHEMA.md` for fixture scope, state transitions,
receipt fields, schema restrictions, release checks, and output handling.

## Domain 07 chromatin context

The chromatin plane keeps accessibility and histone observations tied to a
source snapshot and exact reference context. ATAC, DNase, histone, and H3K27ac
BED-like TSV/JSON rows preserve one-based normalized coordinates, assay kind,
replicate identifiers, signal values, raw hashes, and malformed-row issues.
Retriever queries require both interval overlap and an exact
`ReferenceContext.key`; an overlap from another disease, age, cell state, or
territory is reported as out-of-domain rather than reused.

Accessibility deltas are measured reference-to-alternate comparisons with
missing-value abstention and zero-baseline guards. H3K27ac is summarized as an
observation with replicate spread and ambiguity retained. Neither signal nor
delta is promoted to a causal effect, enhancer truth label, target-gene link,
or calibrated probability without external truth sets and assay-specific
validation.

The command-line boundary is:

```powershell
glio-noncode parse-chromatin accessibility.tsv --track-kind atac --output accessibility.json
```

The Domain 07 scientific-beta extensions make methylation context explicit:

- `MethylationRecordParser` and `MethylationContextRetriever` preserve
  one-based or BED-like coordinates, beta values, coverage, assay/sample and
  replicate metadata, source versions, raw hashes, exact context keys, and
  replicate disagreement. Records from another context are reported as
  out-of-domain rather than borrowed.
- `CpGCreationLossAnalyzer` compares equal-length allele windows and emits
  reference-only or alternate-only CpG dinucleotides with genomic coordinates.
  It can attach exact measured methylation when supplied; length-changing
  windows are explicitly out of domain for this coordinate-safe beta operation.
- `MethylationSensitiveMotifAnalyzer` evaluates declared IUPAC motif hits and
  reports beta values at zero-based sensitive motif offsets, retaining missing
  and ambiguous methylation states without imputing neighbors.
- `IdhHypermethylationContextModel` summarizes a declared IDH-mutant panel
  against an IDH-wildtype comparator with minimum-site gates, coverage-weighted
  beta, panel threshold, and comparator delta. The output is descriptive
  context evidence, not a diagnostic or genome-wide epigenetic classifier.

The beta command boundaries are:

```powershell
glio-noncode parse-methylation methylation.tsv --output methylation.json
glio-noncode query-methylation-context methylation.tsv --chromosome 7 --start 100 --end 200 --context-key "GRCh38|glioma|adult|stem_like|tumor|unknown" --output methylation-query.json
glio-noncode analyze-cpg-change cpg-window.json --output cpg-changes.json
glio-noncode analyze-methylation-motifs methylation-motifs.json --output methylation-motifs.json
glio-noncode model-idh-hypermethylation idh-panel.json --model-id idh-panel --model-version 2026.1 --context-key "GRCh38|glioma|adult|stem_like|tumor|unknown" --output idh-context.json
```

The Domain 07 chromatin-alpha tranche adds assay-control depth:

- `ChromatinStateSegmentationAdapter` splits overlapping observations at all
  observed boundaries and retains open/intermediate/closed labels, signal
  spread, replicate/sample support, mixed-state ambiguity, and source hashes.
- `AlleleSpecificChromatinAnalyzer` summarizes reference-versus-alternate
  signals by variant and assay, retaining replicate deltas, directions,
  missingness, mixed directions, and exact context.
- `EpigenomicPurityDeconvolver` solves a bounded one-dimensional mixture
  proportion from declared observed, tumor-reference, and normal-reference
  marker signals. Out-of-range marker estimates remain visible and the
  aggregate is not a clinical purity call.
- `BatchCellCompositionCorrector` applies declared batch offsets and
  cell-composition coefficients while retaining raw signal, both adjustment
  terms, target composition, and missing-parameter partial states.

```powershell
glio-noncode segment-chromatin-state chromatin-intervals.json --low-signal 0.25 --high-signal 0.75 --output chromatin-segments.json
glio-noncode analyze-allele-specific-chromatin allele-chromatin.json --ambiguity-tolerance 0.25 --output allele-chromatin.json
glio-noncode deconvolve-epigenomic-purity purity-markers.json --minimum-markers 3 --output epigenomic-purity.json
glio-noncode correct-batch-cell-composition corrected-signals.json --output batch-corrected.json
```

### Domain 07 C13-C16 chromatin frontier evidence gate

The Domain 07 C13-C16 tranche wraps the chromatin-alpha adapters in a public
aggregate evidence plane. The checked-in fixture contains four positive records,
twelve controls, five public source receipts, exact
`GRCh38|glioma|adult|stem_like|tumor|unknown` context, and a
`public_aggregate_non_patient` boundary. Raw assay rows are retained only in the
fixture input payload; execution receipts expose typed counts, state labels,
issue codes, and content addresses without raw input text.

- C13 `chromatin_segmentation` splits overlapping accessibility intervals at all
  observed boundaries, preserves replicate and sample support, and distinguishes
  supported, ambiguous, partial, and out-of-domain outcomes.
- C14 `allele_specific_chromatin` compares reference and alternate signal by
  variant and assay, retains each replicate delta and direction, and leaves
  mixed directions ambiguous rather than averaging disagreement away.
- C15 `epigenomic_purity` computes bounded marker-level mixture estimates from
  declared observed, tumor-reference, and normal-reference signals. Out-of-range
  values are visible, zero denominators remain partial or abstained, and the
  aggregate is not a clinical purity call.
- C16 `batch_composition_correction` retains raw signal, batch adjustment,
  composition adjustment, target composition, corrected signal, and missing or
  invalid covariate states. Corrections remain descriptive assay normalization.

The evidence plane emits 120 deterministic evaluation checks, 23 schema checks,
12 review rows, four out-of-domain controls, four operation metrics, a nine-stage
trace, source-to-receipt lineage, expected-versus-observed reconciliation,
replay expectations, a 12-check quality gate, and a content-addressed release
manifest. The same typed evaluator runs positive and control records so review
states cannot be promoted silently.

```powershell
glio-noncode evaluate-chromatin-frontier-fixture --output chromatin-frontier-evaluation.json
glio-noncode chromatin-frontier-quality-gate --output chromatin-frontier-quality.json
glio-noncode run-chromatin-frontier-pipeline --run-id d07-local --output chromatin-frontier-run.json
glio-noncode build-chromatin-frontier-release --run-id d07-release --output chromatin-frontier-release.json
glio-noncode export-chromatin-frontier-review-markdown --output chromatin-frontier-review.md
```

See `docs/CHROMATIN_FRONTIER_EVIDENCE_GATE.md`,
`docs/CHROMATIN_FRONTIER_RELEASE_FORMAT.md`, and
`docs/CHROMATIN_FRONTIER_SCHEMA.md` for source boundaries, state transitions,
receipt fields, schema restrictions, release checks, and sanitized outputs.

## Domain 08 cell state, disease class, and territory

The biological-context plane parses subject-scoped disease ontology, age-route,
molecular-class, molecular-state, and malignant-microenvironment territory
observations. Each row retains its source version, raw hash, confidence,
evidence state, and exact `ReferenceContext.key`. Resolvers exclude other
subjects, report out-of-domain context rather than transporting a taxonomy
silently, and preserve one-to-many territory candidates as ambiguous.

Adult/pediatric routing uses the declared age group and abstains for unknown or
unsupported routes. Molecular class and molecular state remain separate
dimensions, so an observed class cannot fill a missing state. The assembled
`GliomaStateContext` carries the weakest component state, source IDs, an
uncertainty summary, and explicit research-use limitations. It does not make a
clinical diagnosis, prognosis, pathogenicity, treatment, or actionability
claim.

The parser boundary is:

```powershell
glio-noncode parse-context context-observations.tsv --output context.json
```

The Domain 08 scientific-beta extensions add bounded context priors:

- `DevelopmentalLineagePrior` aggregates versioned developmental-lineage
  observations only for the declared glioma age routes, preserving candidate
  alternatives, source/evidence tiers, uncertainty, and ambiguity margins.
- `GlioblastomaMalignantStatePrior` has an explicit glioblastoma/GBM disease
  gate before summarizing stem-like, cycling, mesenchymal-like, hypoxic, or
  related malignant-state candidates.
- `IdhMutantLineageStatePrior` and
  `H3K27AlteredDevelopmentalStatePrior` require their declared molecular-state
  gates, so IDH-wildtype or unsupported-state observations are not silently
  transported into another prior family.

All four emit bounded support summaries, not calibrated probabilities. Missing
observations, exact-context mismatches, contradictory rows, and close
candidate scores remain visible as abstained, out-of-domain, contradictory, or
ambiguous states. The beta command boundaries are:

```powershell
glio-noncode parse-context-prior lineage-prior.tsv --output lineage-prior.json
glio-noncode estimate-developmental-lineage-prior lineage-prior.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output lineage-result.json
glio-noncode estimate-glioblastoma-state-prior gbm-prior.json --context-key "GRCh38|glioblastoma|adult|stem_like|core|unknown" --output gbm-result.json
glio-noncode estimate-idh-lineage-prior idh-prior.json --context-key "GRCh38|glioma|adult|proneural|core|unknown" --molecular-state "IDH-mutant" --output idh-result.json
glio-noncode estimate-h3k27-developmental-prior h3-prior.json --context-key "GRCh38|glioma|pediatric|stem_like|midline|unknown" --molecular-state "H3K27-altered" --output h3-result.json
```

The Domain 08 context-alpha tranche adds four exact-context priors:

- `SpatialNichePrior` ranks declared niche candidates within a subject and
  context while retaining sample support, close-candidate margins, and
  alternatives.
- `CoreMarginTerritoryPrior` compares declared core and margin scores with an
  explicit ambiguity tolerance, preserving mixed and one-sided evidence.
- `RecurrenceStatePrior` ranks primary, recurrence, and progression candidates
  without transporting one phase into another or collapsing close scores.
- `TreatmentInducedStatePrior` compares baseline and post-treatment support
  for a declared state and treatment phase, preserving induced, stable, or
  reduced labels as descriptive changes.

```powershell
glio-noncode estimate-spatial-niche-prior spatial-niches.json --context-key "GRCh38|glioma|adult|stem_like|tumor|unknown" --output spatial-niche-prior.json
glio-noncode estimate-core-margin-prior core-margin.json --ambiguity-tolerance 0.1 --output core-margin-prior.json
glio-noncode estimate-recurrence-state-prior recurrence-states.json --ambiguity-margin 0.1 --output recurrence-prior.json
glio-noncode estimate-treatment-induced-state-prior treatment-states.json --induction-threshold 0.1 --output treatment-state-prior.json
```

## Domain 09 3D topology

The topology plane imports long-form Hi-C and Micro-C contacts and TAD-boundary
candidates with assay labels, one-based normalized coordinates, source
versions, raw hashes, replicate/caller metadata, and quarantined malformed
rows. Contact-pair lookup is order-independent but still requires an exact
reference context; other-context overlap is not reused.

Matrix QC reports duplicate canonical pairs, zero-signal rows, signal ranges,
and partial states. Mean/max normalization is available as a transparent
descriptive transform with explicit limitations; it is not hidden ICE balancing
or a correction for assay bias. TAD boundary ensembles group calls only within
a declared tolerance and retain competing clusters. Insulation-score deltas
retain alternate-minus-reference direction, missingness, replicate count, and
zero-baseline guards. These are topology observations, not proof of causality,
enhancer activity, target-gene linkage, or clinical actionability.

The parser boundaries are:

```powershell
glio-noncode parse-contacts contacts.tsv --assay hi-c --output contacts.json
glio-noncode parse-boundaries boundaries.tsv --assay micro-c --output boundaries.json
```

The Domain 09 scientific-beta extensions add topology-specific adapters and
scorers:

- `LoopStripeAdapter` parses loop and stripe features with two normalized
  anchors, feature kind, signal, resolution, replicate/caller metadata,
  source versions, hashes, and row-level quarantine.
- `PromoterCaptureContactAdapter` preserves promoter and target-element
  identity, bait metadata, coordinates, signal, exact context, and source
  receipts for promoter-capture snapshots.
- `EnhancerPromoterContactScorer` summarizes exact-context contact observations
  with replicate spread and a declared bounded signal transform. It retains
  all observations and does not turn contact into a link claim.
- `ActivityByContactScorer` combines measured activity and contact components
  under explicit scales, retaining both component states, model/version, and
  missingness. The product is descriptive evidence, not a probability or
  causal regulatory effect.

The beta command boundaries are:

```powershell
glio-noncode parse-loop-stripe loops.tsv --output loops.json
glio-noncode parse-promoter-capture promoter-capture.json --coordinate-system one_based --output promoter-capture-normalized.json
glio-noncode score-enhancer-promoter-contact contact-evidence.json --enhancer-id enh-1 --promoter-id GENE1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output contact-score.json
glio-noncode score-activity-by-contact activity-contact.json --enhancer-id enh-1 --promoter-id GENE1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id abc-model --model-version 2026.1 --output abc-score.json
```

The Domain 09 topology-alpha tranche adds four explicit structural contracts:

- `BoundaryMotifOrientationAnalyzer` compares left/right motif strands and
  preserves convergent, divergent, tandem, and mixed-orientation labels.
- `CTCFCohesinDisruptionModel` keeps CTCF and cohesin reference/alternate
  channels separate before emitting bounded stable, gained, or disrupted
  descriptive labels.
- `IDHInsulatorDysfunctionModel` compares IDH-mutant and IDH-wildtype
  insulator observations by region while retaining methylation as a separate
  channel.
- `SVTopologyRewiringSimulator` applies declared SV edge deletions, gains, and
  rewires to a contact-edge set, preserving every simulated outcome and
  affected node.

```powershell
glio-noncode analyze-boundary-motif-orientation boundary-motifs.json --minimum-score 0.5 --output boundary-orientation.json
glio-noncode model-ctcf-cohesin-disruption ctcf-cohesin.json --disruption-threshold 0.2 --output ctcf-cohesin-model.json
glio-noncode model-idh-insulator-dysfunction idh-insulators.json --dysfunction-threshold 0.2 --output idh-insulator-model.json
glio-noncode simulate-sv-topology-rewiring sv-topology.json --output sv-rewiring.json
```

## Domain 10 candidate link graph

The link plane produces context-qualified candidate relationships among
variants, regulatory elements, and genes. Coordinate-overlap links require
exact element context. Gene intervals are imported with source receipts and
support a nearest-gene baseline that retains distance ties and can abstain
outside a declared distance window. Neither overlap nor proximity is treated
as a regulatory mechanism.

cCRE assignment retains every overlapping context-matched element and exposes
one-to-many ambiguity. Enhancer-gene consensus groups method-specific evidence
by variant, element, and gene, reports confidence-weighted support, keeps
alternative genes, and marks single-method evidence partial. Contradictory
evidence is not averaged away, and context-mismatched evidence is not
transported. Candidate graphs are research evidence structures, not causal,
clinical, pathogenicity, or actionability claims.

The gene-source boundary is:

```powershell
glio-noncode parse-genes genes.tsv --output genes.json
```

The Domain 10 scientific-beta extensions add evidence-path linkers:

- `ActivityByContactLinkAdapter` preserves activity and contact components,
  declared scales, variant-element-gene identity, confidence, source versions,
  and raw hashes before any graph edge is produced.
- `CoaccessibilityLinker` and `MolecularQtlLinker` create candidate graph
  edges with method identity, effect metadata, exact context, alternatives,
  and single-method partial state. Molecular-QTL p/q values use a declared
  bounded transform and are not treated as causal evidence by themselves.
- `AlleleSpecificLinkEvidenceIntegrator` keeps allele-direction evidence and
  reports gain/loss conflicts as contradictory graph state instead of averaging
  them into a selected target gene.

The beta command boundaries are:

```powershell
glio-noncode parse-activity-contact-link activity-contact.tsv --output activity-contact.json
glio-noncode link-coaccessibility coaccessibility.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output coaccessibility-links.json
glio-noncode link-molecular-qtl molecular-qtl.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output qtl-links.json
glio-noncode integrate-allele-specific-links allele-links.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output allele-integrated-links.json
```

The external-alpha link extensions add four deeper contracts:

- `CRISPRPerturbationLinkAdapter` and `CRISPRPerturbationLinker` preserve
  perturbation mode, direction, effect size and scale, guides, replicates,
  exact context, and opposing-direction contradiction before producing a
  candidate edge.
- `ThreeDContactLinkAdapter` and `ThreeDContactLinker` preserve raw contact
  signal, declared normalization scale, assay kind, resolution, replicate
  identity, source version, and candidate-edge limitations.
- `PromoterTetheringModel` computes a bounded descriptive baseline from
  distance, contact, promoter activity, element activity, and overlap channels,
  retaining alternative genes and abstaining when components are missing.
- `MultiGeneElementGraphBuilder` builds a context-qualified graph slice with
  multi-gene alternatives, node degrees, connected components, evidence paths,
  source lineage, and support-threshold receipts.

These models preserve ambiguity and missingness. They do not convert contact,
perturbation, proximity, or graph connectivity into a causal, clinical,
pathogenicity, or actionability conclusion.

```powershell
glio-noncode parse-crispr-perturbation-links crispr-links.tsv --source-id crispr-atlas --effect-scale 1.0 --output crispr-links.json
glio-noncode link-crispr-perturbations crispr-links.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output crispr-candidates.json
glio-noncode parse-3d-contact-links contacts.tsv --source-id hic-atlas --assay-kind hic --resolution-bp 5000 --output contact-links.json
glio-noncode link-3d-contacts contact-links.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --variant-id v1 --output contact-candidates.json
glio-noncode model-promoter-tethering tethering.json --minimum-score 0.35 --minimum-components 2 --output tethering-model.json
glio-noncode build-multi-gene-element-graph link-evidence.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --minimum-support 0.2 --output multi-gene-graph.json
```

## Domain 11 causal evidence structures

The causal-evidence plane builds immutable factor-graph snapshots with parent
lineage, supersession history, active-factor views, orphan diagnostics,
contradictory-edge detection, and deterministic replay. Superseded factors are
never erased from history. A typed `RegulatoryCausalHypothesis` records its
factor graph, missing evidence, prior/likelihood proxies, and contradiction
state.

Context-conditioned priors use exact context profiles and bounded feature
contributions; missing or out-of-support features abstain. Measurement
likelihoods group dependent channels before aggregation and retain missing or
contradictory measurements. Both are explicitly proxies, not calibrated
probabilities, causal effects, diagnoses, prognoses, treatment recommendations,
or actionability claims.

The Domain 11 scientific-beta extensions make the three mediator steps and the
allele comparison explicit:

- `SequenceToElementCausalMediator` evaluates sequence-to-element evidence only
  when source and target nodes, exact context, and mediator kind match. It
  requires independent source paths for `supported`, keeps against-direction
  and negative-control evidence, and reports bounded uncertainty and sensitivity.
- `ElementToGeneCausalMediator` and `GeneToStateCausalMediator` apply the same
  source/version, context, contradiction, and abstention gates to downstream
  mediator edges. A single positive source remains partial and a context-only
  mismatch is out of domain.
- `CounterfactualAlleleStateSimulator` compares declared reference and
  alternate state observations, reports the alternate-minus-reference delta,
  retains replicate ambiguity, and carries model/version receipts. The delta
  is descriptive and is not proof of causality or clinical effect.

The beta command boundaries are:

```powershell
glio-noncode parse-causal-evidence causal-evidence.json --output causal-evidence-parsed.json
glio-noncode evaluate-sequence-element-mediator causal-evidence.json --source-node variant:v1 --target-node element:enh-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id seq-element-beta --model-version 1 --output sequence-element.json
glio-noncode evaluate-element-gene-mediator causal-evidence.json --source-node element:enh-1 --target-node gene:GENE1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id element-gene-beta --model-version 1 --output element-gene.json
glio-noncode evaluate-gene-state-mediator causal-evidence.json --source-node gene:GENE1 --target-node state:stem_like --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id gene-state-beta --model-version 1 --output gene-state.json
glio-noncode simulate-counterfactual-allele-state allele-state.json --state-id state:open --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id allele-state-beta --model-version 1 --output allele-state-delta.json
```

The replayable factor boundary is:

```powershell
glio-noncode factor-graph factors.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output graph.json
```

The external-alpha causal controls add four deeper contracts:

- `MediationSensitivityAnalyzer` reruns a typed mediator after omitting each
  source, retaining base and leave-one-out states, support deltas, source
  influence, model versions, and robustness tolerance.
- `ConfoundingChecklistAdjudicator` records addressed, unresolved, missing,
  and not-applicable confounders with severity, adjustment method, source
  lineage, and exact-context gates.
- `EvidenceDependenceCorrector` groups declaredly dependent evidence paths,
  selects one representative per group, and retains excluded IDs, group
  counts, source families, uncertainty, and contradiction state.
- `NegativeEvidenceIntegrator` keeps positive paths, negative controls, and
  measured-negative observations separate, reporting coverage and conflict
  instead of erasing negative evidence or treating it as proof of absence.

All four are bounded research controls. They do not establish causal
identification, calibrated posteriors, diagnoses, treatment recommendations,
or actionability.

```powershell
glio-noncode analyze-mediation-sensitivity causal-evidence.json --mediator-kind sequence_to_element --source-node variant:v1 --target-node element:enh-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-id seq-alpha --model-version 1 --output sensitivity.json
glio-noncode adjudicate-confounding confounders.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --required-confounder batch --required-confounder purity --output confounding.json
glio-noncode correct-evidence-dependence dependence.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --minimum-independent-groups 2 --output dependence-corrected.json
glio-noncode integrate-negative-evidence negative-evidence.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --minimum-negative-controls 1 --output negative-integrated.json
```

## Domain 12 cohort discovery and controls

The cohort plane builds exact-context queries with variant-kind, origin, sample,
chromosome, and callable-space criteria. It returns selected records together
with exclusion reasons and never treats an empty or context-mismatched cohort
as negative evidence. The local background model reports observed variants per
callable base, target-space expectation, source intervals, and small-sample
uncertainty without emitting an unvalidated significance claim.

Sequence-context controls use bounded Hamming distance; chromatin controls use
declared feature ranges and RMS distance. Both retain candidate pools,
distances, source IDs, cutoff criteria, partial/absent states, and exact-context
out-of-domain behavior. These are negative-control constructions for research,
not causal null proofs, clinical risk estimates, or treatment evidence.

The Domain 12 scientific-beta extensions add four convergence surfaces:

- `RegulatoryRecurrenceTester` deduplicates variant and sample observations,
  applies callable and exact-context gates, identifies recurrence in distinct
  samples, and clusters nearby distinct variants into thresholded hotspots.
- `RegionalBurdenTester` reports callable-base burden, a declared background
  comparator, expected count, and excess ratio for one exact-context region.
  Missing comparator data remains partial, and the result is not a significance
  test.
- `FunctionalConvergenceTester` aggregates declared feature support by variant,
  contrasts observed and control pools, retains leading-feature ties, and keeps
  feature direction counts and source lineage.
- `PathwayRegulonConvergenceTester` aggregates gene-set membership for pathway
  and regulon namespaces, reports observed/control contrasts and gene coverage,
  and marks opposing activation/repression evidence contradictory.

The beta command boundaries are:

```powershell
glio-noncode parse-regulatory-recurrence recurrence.tsv --output recurrence.json
glio-noncode test-regulatory-recurrence recurrence.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output recurrence-test.json
glio-noncode test-regional-burden regional-burden.json --region-id reg-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --background-rate 0.001 --output regional-burden-test.json
glio-noncode parse-functional-convergence functional.tsv --output functional.json
glio-noncode test-functional-convergence functional.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output functional-test.json
glio-noncode parse-pathway-regulon pathway-regulon.json --output pathway-regulon-parsed.json
glio-noncode test-pathway-regulon-convergence pathway-regulon.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --set-kind pathway --output pathway-test.json
```

The external-alpha cohort controls add four deeper contracts:

- `ClonalityTimingIntegrator` retains CCF values, pseudonymous sample IDs,
  phase labels, timepoint ordering, and missingness while emitting bounded
  clonal/subclonal labels.
- `PrimaryRecurrenceComparator` compares matching loci across primary,
  recurrence, and progression phases with explicit sample coverage and delta
  thresholds.
- `TreatmentSelectionSignalDetector` compares declared pre-treatment and
  post-treatment frequencies while preserving treatment, response, sample, and
  exposure timing metadata.
- `CrossCohortReplicationEngine` retains cohort-specific effect sizes,
  support, sample counts, direction concordance, and minimum cohort coverage.

These summaries are descriptive research outputs. They do not establish clonal
evolution, treatment response or resistance, causal selection, transportability,
statistical significance, or clinical utility.

```powershell
glio-noncode integrate-clonality-timing clonality.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --clonal-threshold 0.85 --output clonality-timing.json
glio-noncode compare-primary-recurrence phases.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --change-threshold 0.2 --output primary-recurrence.json
glio-noncode detect-treatment-selection treatment-phases.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --change-threshold 0.2 --output treatment-selection.json
glio-noncode replicate-cross-cohort replication.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --minimum-cohorts 2 --minimum-concordance 0.75 --output replication.json
```

The query boundary is:

```powershell
glio-noncode cohort-query cohort.json --output cohort-selection.json
```

## Domain 13 validation planning

The validation plane converts typed hypothesis gaps into ranked review items
without filling missing evidence. Assay eligibility routes check declared
model systems, insert bounds, controls, and readouts, and retain blocked
alternatives plus sensitivity notes.

MPRA and STARR-seq planners validate target context and reference alleles,
generate reference/alternate constructs, enforce construct budgets, and attach
required controls and readouts. Context mismatch, allele mismatch, unsupported
length, and missing inventory remain blocked or abstained. Construct generation
does not establish expression, effect size, assay success, safety, or causal
validation; expert review and institutional approvals remain required.

The Domain 13 scientific-beta extensions add intervention and allele-specific
design packages:

- `CRISPRiDesignPlanner` and `CRISPRaDesignPlanner` generate deterministic,
  context-gated guide candidates with declared overlap, PAM, heuristic
  on-target, specificity, off-target, control, readout, and budget receipts.
- `BaseEditingDesignPlanner` restricts candidates to declared single-base edit
  substitutions and editing windows, retaining unsupported chemistry and
  bystander-edit blockers.
- `PrimeEditingDesignPlanner` adds explicit PBS, RTT, edit-length, and flank
  gates. These sequences are design placeholders and require editor-specific
  validation.
- `AlleleSpecificReporterPlanner` keeps reference and alternate constructs
  paired under the same context, control, readout, and construct-budget
  contract. A reporter package is not an endogenous causal claim.

The beta command boundaries are:

```powershell
glio-noncode plan-crispri validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output crispri.json
glio-noncode plan-crispra validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output crispra.json
glio-noncode plan-base-editing validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output base-editing.json
glio-noncode plan-prime-editing validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 20 --output prime-editing.json
glio-noncode plan-allele-specific-reporter validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --max-guides 2 --output allele-reporter.json
```

The Domain 13 external-alpha planning extensions deepen model and assay
readiness without converting planning metadata into biological conclusions:

- `ModelSystemEligibilityMatcher` matches exact context to declared model
  systems, cell states, evidence strength, and explicit eligibility blockers.
- `GuideOligoDesignAdapter` losslessly adapts TSV or JSON guide/oligo designs,
  retaining sequence roles, design and target identifiers, strand, offsets,
  PAMs, versions, row hashes, and quarantined malformed rows.
- `ControlsRandomizationPlanner` produces deterministic content-addressed
  control assignments across biological and technical replicates, with
  reproducible seeds, context gates, and execution-review warnings.
- `PowerReplicationEstimator` calculates a transparent normal-approximation
  replicate requirement and achieved-power proxy while exposing effect,
  variance, alpha, blocking, shortfall, and assumptions.

These alpha outputs are bounded research-planning records. They do not prove
model fidelity, guide efficacy, off-target safety, assay success, statistical
guarantees, causal effects, clinical utility, or institutional approval.

The external-alpha command boundaries are:

```powershell
glio-noncode match-model-system-eligibility eligibility.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --model-system organoid --output eligibility-match.json
glio-noncode parse-guide-oligo-design guides.tsv --source-id guide-design --output guides-adapted.json
glio-noncode plan-controls-randomization validation-targets.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --biological-replicates 3 --technical-replicates 1 --output controls-plan.json
glio-noncode estimate-power-replication power.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output power.json
```

## Domain 14 evidence lifecycle

The evidence-lifecycle plane resolves versioned citation manifests and retains
source version, URI, checksum, raw record, and retrieval metadata for every
accepted citation. TSV, CSV, and JSON rows that lack a URI, title, or citation
text are quarantined with a row hash instead of being silently dropped.

Versioned evidence claims are assembled into immutable graph snapshots. Parent
lineage, supersession, missing citations, citation-context mismatch, active
claim IDs, and historical claim IDs are all retained. A replay reconstructs the
same content address, while appending creates a new graph version without
erasing prior claims.

Edge validation checks exact graph context, active lineage, source coverage,
and disagreement state. The contradiction tracker keeps positive, negative,
contradictory, and declared-value alternatives separate; it never averages
conflicting evidence into a false consensus. A research-only dossier envelope
records a deterministic integrity digest and remains review-required. The
digest is a content-addressed reproducibility aid, not a cryptographic identity
signature, clinical conclusion, or treatment recommendation.

The Domain 14 scientific-beta extensions add operational evidence views:

- `EvidenceTierAdjudicator` keeps every declared tier and support/against
  direction, reports the highest tier without deleting lower-tier alternatives,
  and marks unresolved or contradictory claims for review.
- `ProvenanceLineageViewer` projects parent claims, supersession history,
  active state, source versions, citation nodes, and content hashes without
  mutating the immutable graph.
- `UncertaintyLedgerBuilder` records measurement, context, provenance,
  transport, calibration, dependence, and review drivers with conservative
  per-claim maxima. It is not a calibrated probability.
- `ReviewerAssignmentRouter` routes active claims to explicit domain,
  provenance, statistical, assay, computational, and context roles using
  contradiction, tier, uncertainty, and context blockers.

The beta command boundaries are:

```powershell
glio-noncode adjudicate-evidence-tier tier-observations.json --context-key "GRCh38|glioma|adult|stem_like|core|untreated" --output tier-adjudication.json
glio-noncode view-provenance-lineage graph-input.json --claim-id claim-2 --output lineage.json
glio-noncode build-uncertainty-ledger uncertainty.json --context-key "GRCh38|glioma|adult|stem_like|core|untreated" --output uncertainty-ledger.json
glio-noncode route-reviewers graph-input.json --roles data_provenance domain_expert --output review-queue.json
```

The lifecycle boundaries are:

```powershell
glio-noncode parse-citations citations.tsv --source-id source-1 --source-version v1 --output citations.json
glio-noncode evidence-graph graph-input.json --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output dossier.json
```

The Domain 14 external-alpha extensions add explicit review operations around
the immutable graph:

- `BlindedAdjudicationWorkflow` creates deterministic masked cases with
  evidence digests, masked claim/source receipts, reviewer tokens, and exact
  context. Consensus, abstention, and split decisions remain distinct.
- `ReviewerCommentChangeLogger` stores immutable comments plus before/after
  content-addressed changes and supports append-only review snapshots.
- `ReleaseDecisionRecorder` records research-only gate results, required and
  completed reviewer roles, failed conditions, decision rationale, and an
  optional comment-log address. Approval is never clinical authorization.
- `EvidenceDeltaDetector` compares graph snapshots and classifies claim,
  citation, graph-state, and context changes with before/after hashes and
  review severity. It does not resolve disagreements by averaging evidence.

The external-alpha command boundaries are:

```powershell
glio-noncode plan-blinded-adjudication adjudication-observations.json --context-key "GRCh38|glioma|adult|stem_like|core|untreated" --reviewer-count 2 --output blinded-plan.json
glio-noncode adjudicate-blinded-evidence blinded-decision-bundle.json --output adjudication-result.json
glio-noncode record-review-log review-log.json --context-key "GRCh38|glioma|adult|stem_like|core|untreated" --output review-log-result.json
glio-noncode record-release-decision release-input.json --requested-decision approved --output release-decision.json
glio-noncode detect-evidence-delta graph-delta.json --expected-context-key "GRCh38|glioma|adult|stem_like|core|untreated" --output evidence-delta.json
```

## Domain 15 research workspaces

The workspace plane is a deterministic read model for future CLI, API,
notebook, or graphical clients. Immutable records carry typed section identity,
exact reference context, source IDs, coordinates, tags, searchable fields, and
research state. Bounded queries support text search, chromosome/interval
overlap, source and state filters, tag conjunctions, pagination, facets, and a
command-palette surface. A context mismatch returns out-of-domain rather than
transporting records silently.

Case workspaces expose manifest variants and candidate regulatory elements, and
optionally add dossier hypotheses, evidence claims, and validation routes.
Cohort workspaces keep selected records, local callable/background summaries,
and matched controls in separate sections. The variant explorer resolves a
single variant and only declared relationships. The regulatory track browser
turns parsed intervals into source-accounted overlap-searchable records while
keeping parse issues and the annotation-only limitation visible.

The Domain 15 scientific-beta projections add four deep research surfaces:

- `TopologyViewer` builds a bounded two-anchor topology viewport from
  loop/stripe observations, promoter-capture contacts, contact scores, and
  activity-by-contact summaries. Interval focus, exact context, source
  versions, observation IDs, replicate metadata, deterministic node/edge
  limits, and out-of-context withholding are retained. The viewport does not
  convert contact into activity or causality.
- `CausalChainExplorer` joins sequence-to-element, element-to-gene, and
  gene-to-state mediator results. It keeps alternative paths, negative
  evidence, missing mediator kinds, contradictory edges, context mismatch,
  support, uncertainty, and source receipts visible rather than collapsing
  them into one chain score.
- `PosteriorDecompositionViewer` exposes the declared prior, exact-context
  support components, normalized descriptive shares, calibration status, and
  an unexplained residual. Components are never invented to reconcile a
  declared support value, and the result remains a research proxy rather than
  a calibrated clinical probability.
- `EvidenceTableAndFilters` provides text, context, channel, tier, state,
  source, confidence, pagination, and deterministic facet filters over saved
  workspace records. Partial, ambiguous, and unresolved evidence remains in
  the table, and filtering never changes the underlying evidence state.

These are research navigation artifacts. They do not infer activity, causality,
diagnosis, prognosis, actionability, or treatment.

The Domain 15 external-alpha extensions add coordination and sharing records:

- `ValidationExperimentBoardBuilder` groups exact-context experiment cards by
  declared status, priority, dependencies, blockers, owners, readouts, and
  accessible board-column metadata. It is a planning read model and does not
  execute or approve experiments.
- `NotebookSDKLauncher` produces bounded notebook or SDK launch descriptors
  with runtime, artifact, parameter, resource, source, and network-policy
  receipts. It never executes user code, and requested network access remains
  review-required.
- `ShareableSnapshotPublisher` emits research-only shareable snapshot
  envelopes with payload addresses, audiences, expiry, key IDs, and HMAC
  verification. Shared-secret integrity is not public-key identity or
  scientific validation.
- `RoleBasedCollaborationEvaluator` applies a deny-by-default role matrix to
  view, comment, edit, launch, share, and approve requests while retaining
  exact-context decisions and policy receipts.

These coordination artifacts do not replace identity, data-governance,
institutional, security, accessibility, or scientific review controls.

```powershell
glio-noncode workspace-case manifest.json --output case-workspace.json
glio-noncode workspace-track regulatory.bed --context-key "GRCh38|glioma|adult|stem_like|unknown|unknown" --output track-workspace.json
glio-noncode view-topology topology.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output topology-view.json
glio-noncode explore-causal-chain causal-results.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output causal-chain.json
glio-noncode view-posterior-decomposition posterior.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output posterior-view.json
glio-noncode filter-evidence-table case-workspace.json --channel sequence --min-confidence 0.8 --output evidence-table.json
glio-noncode build-validation-board validation-experiments.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output validation-board.json
glio-noncode plan-notebook-launch launch-requests.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output launch-plan.json
glio-noncode publish-shareable-snapshot workspace.json --snapshot-id workspace-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --key-id review-key --signing-secret "$env:GLIO_SNAPSHOT_SECRET" --output shared-snapshot.json
glio-noncode verify-shareable-snapshot shared-snapshot.json --signing-secret "$env:GLIO_SNAPSHOT_SECRET" --output snapshot-verification.json
glio-noncode evaluate-collaboration-access access.json --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output access-report.json
```

## Domain 16 typed mission runtime

The mission runtime combines the declared control-plane registry with workflow
compilation. A mission request names its research boundary and requested roles;
planning expands only declared dependencies, checks claim ceilings and review
requirements, and records a registry content address. Workflow compilation
returns a topological order, aggregate resource envelope, and explicit
network/nondeterminism warnings. An empty request abstains without compiling
hidden work.

The typed tool facade exposes owner-checked input/output contracts, safety
class, deterministic flag, network sources, mutation scope, and review
requirements. The execution sandbox adds a local/network isolation contract
and requires a registered handler for every invocation. The underlying executor
then applies policy, data-scope, sensitive-key, resource, provenance, event-log,
typed-output, human-review, and idempotency controls. Unregistered or disallowed
work is rejected; it is never treated as an abstention-free success.

The Domain 16 scientific-beta control projections deepen those boundaries:

- `PolicyClaimAuditor` produces a pre-execution receipt for claim ceilings,
  source allowlists, mutation scope, data scope, sensitive-key paths, policy
  violations, warnings, and policy version without copying sensitive values.
- `BudgetResourceScheduler` orders dependency-aware work deterministically and
  accounts for invocation, network, wall-time, cost, CPU, memory, GPU, storage,
  capacity rejection, and deferred work before execution.
- `DeterministicFallbackRouter` evaluates only declared alternatives after a
  retryable failure. It records rejection reasons for repeated operations,
  missing inputs, network restrictions, nondeterministic candidates, output
  contract mismatch, and cost limits.
- `HumanReviewQueueRouter` creates a bounded stable review queue from
  abstentions, blocked outcomes, non-retryable failures, and explicit reasons.
  Reviewer roles, blockers, source IDs, priority, and omitted candidates stay
  visible; queue construction never adjudicates or releases an outcome.

The mission boundary is:

```powershell
glio-noncode mission-plan mission.json --output mission-plan.json
glio-noncode audit-policy-claim control-request.json --output policy-audit.json
glio-noncode schedule-budget work-items.json --max-cost-units 1000 --output budget-schedule.json
glio-noncode route-fallback fallback.json --output fallback-route.json
glio-noncode queue-human-review review-items.json --roles domain_expert statistical_review --output review-queue.json
```

The Domain 16 external-alpha runtime controls add four inspectable registry
and quality surfaces:

- `EventSourcedExecutionLedger` replays typed requested, planned, admitted,
  started, checkpoint, completed, failed, rejected, and cancelled events with
  contiguous sequence and transition checks.
- `ModelRegistry` resolves versioned artifacts against exact context,
  input/output contracts, lifecycle status, license, source, and evaluation
  receipts, retaining compatibility blockers.
- `DataReferenceRegistry` resolves versioned data and reference records while
  preserving URI, checksum, schema, coordinate system, license, retrieval,
  context, and lifecycle gates.
- `DriftAndOODMonitor` computes declared mean-delta, PSI, KS-proxy, or
  missingness signals with watch/drift thresholds and explicit support-boundary
  states. These are monitoring signals, not model-failure findings.

The external-alpha command boundaries are:

```powershell
glio-noncode replay-execution-ledger execution-events.json --execution-id execution-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output execution-ledger.json
glio-noncode resolve-model-registry models.json --model-id model-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output model-resolution.json
glio-noncode resolve-data-reference references.json --dataset-id reference-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output reference-resolution.json
glio-noncode monitor-drift drift-observations.json --monitor-id monitor-1 --context-key "GRCh38|glioma|adult|stem_like|core|unknown" --output drift-report.json
```

This runtime is for bounded research orchestration. It does not authorize a
clinical claim, treatment decision, or release beyond the existing review and
research-use policy.
