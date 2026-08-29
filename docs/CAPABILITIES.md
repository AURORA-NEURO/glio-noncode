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

The frontier expansion waves add test-backed coverage across the sixteen
domains. The repository ledger now has 256 of 256 capabilities started (100%);
256 capabilities have deterministic fixture-backed verification and none remain
partial. The frontier surfaces are bounded research infrastructure. Current
verified coverage is 100% of the 256-capability catalog; MVP implementation
coverage is 100%. The surfaces retain
source receipts, uncertainty, policy checks, and
review states rather than converting missing evidence into a scientific or
clinical conclusion.

## Longitudinal packet-review observatory

The packet-review history observatory turns a sequence of independently
verified history archives into a deterministic, path-free timeline. Each
observation retains its history address, terminal gate address, decision,
state, acceptance, and release-readiness projection. Adjacent observations
are classified as stable, promoted, recovered, regressed, held, blocked,
superseded, or changed. Rollups conserve observation and transition counts and
the observatory carries its own independent structural checks.

The observatory loads exact-byte `manifest.json` plus `history.json` archives,
exports summary/observation/transition/check views as JSON, CSV, or Markdown,
and answers bounded queries with state, transition, acceptance, readiness, text,
and pagination filters. Directory locations are input-only and never appear in
public projections.

## Observatory runtime policy

The runtime evaluates an observatory against a bounded release policy. The
default policy requires observations, accepted histories, a ready latest
observation, and zero regressions, blocked observations, changed transitions,
or mixed-state ambiguity. The policy is explicit and replaceable; every
threshold and result is content-addressed.

Runtime closure emits five ordered stages: load, verify, policy, project, and
complete. A policy failure is preserved as a held or blocked state with
addressed checks rather than being discarded. Accepted ready runtimes can be
persisted as exact `manifest.json` plus `runtime.json` archives and queried by
stage or policy-check result.

## Cross-domain frontier release closure

The D13-D16 closure layer is a verified composition surface over the four
independent frontier handoffs. It does not replace their source contracts: it
names each source artifact under a domain-qualified identity, joins the
handoffs through six forward-only dependencies, and evaluates six release
gates for each domain.

| Aggregate plane | Verified denominator |
| --- | ---: |
| Source domains | 4 |
| Source artifacts | 155 |
| Forward dependencies | 6 |
| Release gates | 24 |
| Source receipts | 20 |
| Source records | 64 |
| Evaluation checks | 360 |
| Closure stages | 52 |
| Certification checks | 216 |
| Reconciliation checks | 158 |
| Aggregate certification checks | 48 |
| Observability events / metrics | 193 / 24 |
| Release graph nodes / edges | 189 / 191 |
| Runtime stages / plan steps | 12 / 13 |
| Exact-byte export artifacts | 13 |

The release package is accepted only when every source handoff is accepted,
all 24 gates pass, all cross-domain denominators reconcile, all eight
certification planes pass, the public schema has no forbidden terminal keys,
the negative-control mutations are rejected, and two snapshot replays have the
same content address. The public projection contains aggregate identifiers and
content addresses only; it emits no agent, model, or programming-language
attribution metadata.

The implementation is available through `frontier_release_closure_*` modules,
the `frontier-release-closure-*` CLI commands, and the
`/v1/frontier-release/closure/*` HTTP routes. The [frontier release closure
operations](FRONTIER_RELEASE_CLOSURE_OPERATIONS.md) document maps every plane
to its source, audit, query, export, and failure-control behavior.

## Top-level D01-D16 program release closure

The top-level program closure is the next aggregate layer above the accepted
architecture-program offline handoff. It reuses one source bundle and adds a
complete D01-D16 registry, ordered dependency matrix, per-domain gates,
denominator reconciliation, certification, observability, graph, negative
controls, execution plan, deterministic replay, and exact-byte export.

| Aggregate plane | Verified denominator |
| --- | ---: |
| Domains | 16 |
| Portable source artifacts | 18 |
| Forward dependencies | 120 |
| Release gates | 96 |
| Source reconciliation checks | 19 |
| Certification checks | 96 |
| Observability events / metrics | 266 / 96 |
| Connected graph nodes | 251 |
| Negative controls | 12 |
| Runtime stages / plan steps | 14 / 23 |
| Exact-byte export artifacts | 15 |

The layer is accepted only when source and aggregate denominators reconcile,
every domain gate passes, certification reaches 100%, replay addresses match,
all twelve mutations are rejected, and the export directory verifies. It is
available through `program_release_closure_*` modules, the
`program-release-closure-*` CLI commands, and `/v1/program-release/closure/*`.
See [program release closure operations](PROGRAM_RELEASE_CLOSURE_OPERATIONS.md)
for the full contract and review checklist.

## Domain 16 C01-C04 platform-control frontier

The W1 platform-control slice is implemented as a fresh public aggregate
runtime over typed planning and execution contracts. It uses the exact context
`public_platform|research|aggregate|local|v1` and the boundary
`public_aggregate_platform_runtime`. The fixture has 16 rows: one positive and
three controls for each of mission planning, workflow compilation, typed tool
registry resolution, and isolated execution.

| Capability | Positive path | Controls |
| --- | --- | --- |
| C01 Mission planner | dependency-complete plan is ready | empty request, unknown role, claim ceiling |
| C02 Workflow compiler | dependency-safe graph is ready | cycle, missing dependency, network/nondeterminism |
| C03 Typed tool registry | registered contracts are compatible | missing tool, input mismatch, cardinality |
| C04 Execution sandbox | registered local handler is admitted | unregistered handler, network denial, sensitive input |

The runtime retains 80 row checks, 24 ordered stages, 16 scenario cells, 16
threshold probes, 64 validation cells, and 96 evidence cells. It includes
policy, schema, adapters, lineage, reconciliation, quality, replay, release,
review, handoff, integrity, depth, package, benchmark, access, and bundle
projections. Positive paths are accepted only when their state and issue tuple
match the fixture. Controls remain visible and never count as positive success.

Commands:

```powershell
python -m glio_noncode platform-frontier-data-audit
python -m glio_noncode platform-frontier-evaluate
python -m glio_noncode platform-frontier-pipeline
python -m glio_noncode platform-frontier-depth
python -m glio_noncode platform-frontier-thresholds
python -m glio_noncode platform-frontier-validation-matrix
python -m glio_noncode platform-frontier-handoff
python -m glio_noncode platform-frontier-review-csv
```

The sandbox uses local-only defaults, allowlisted typed handlers, mission
provenance, event IDs, idempotency, and explicit policy denial. The fixture is
aggregate operational data and does not claim scientific validity, diagnosis,
treatment suitability, or clinical action.

## Domain 16 C05-C12 control/runtime frontier

The C05-C12 tranche is a public aggregate operational plane for eight bounded
runtime capabilities. It uses the fixed context
`GRCh38|glioma|adult|stem_like|core|untreated` and the boundary
`public_aggregate_control_runtime`. The fixture is deliberately synthetic
aggregate data with public HTTPS receipt placeholders; it contains no
patient-level rows and makes no biological, diagnostic, treatment, or outcome
claim.

Each operation has one positive path and three retained controls:

| Capability | Functional operation | Positive boundary | Control families |
| --- | --- | --- | --- |
| C05 | Policy and claim gate | declared scope admitted | sensitive path, source gap, mutation scope |
| C06 | Budget/resource scheduler | dependency-safe work ready | capacity, network limit, dependency cycle |
| C07 | Deterministic fallback | eligible local route selected | non-retryable, network-only, missing input |
| C08 | Human review router | bounded item routed | blocker, omission, empty queue |
| C09 | Execution ledger | valid event history completed | invalid transition, duplicate, foreign context |
| C10 | Model registry | exact contract compatible | foreign context, contract mismatch, missing version |
| C11 | Data/reference registry | coordinate and license compatible | foreign context, coordinate, missing reference |
| C12 | Drift/OOD monitor | in-domain feature ready | watch, drift, out-of-domain |

The depth surface retains 32 records, 160 row checks, 24 runtime stages, 32
threshold probes, 128 validation cells, and 192 evidence cells. Every receipt
is content-addressed. The runtime includes schema, adapter, execution,
metrics, lineage, policy, reconciliation, review, quality, replay, release,
package, compliance, projection, controls, performance, compatibility,
support, source, access, benchmark, audit, evidence, diagnostics, and depth
stages. Positive results are accepted only when all five row checks pass;
controls remain visible and are never counted as positive success.

Commands:

```powershell
python -m glio_noncode control-frontier-data-audit --output control-frontier-data.json
python -m glio_noncode control-frontier-evaluate --output control-frontier-evaluation.json
python -m glio_noncode control-frontier-pipeline --output control-frontier-runtime.json
python -m glio_noncode control-frontier-depth --output control-frontier-depth.json
python -m glio_noncode control-frontier-thresholds --output control-frontier-thresholds.json
python -m glio_noncode control-frontier-validation-matrix --output control-frontier-validation.json
python -m glio_noncode control-frontier-handoff --output control-frontier-handoff.json
python -m glio_noncode control-frontier-review-csv --output control-frontier-review.csv
```

The implementation is split into contracts, public fixture data, operation
adapters, evaluation, schema, policy, lineage, reconciliation, quality,
replay, release, access, reporting, failure injection, and runtime modules.
The registry marks all eight capabilities verified because these modules are
covered by focused tests, CLI execution, and the depth audit. Verification is
limited to the declared aggregate operational boundary.

## Domain 12 C05-C08 aggregate evidence frontier

The C05-C08 tranche is implemented as a separate public aggregate evidence
plane over the existing typed cohort primitives:

- C05 covers distinct-sample regulatory recurrence and local hotspot summaries;
- C06 covers callable-base regional burden and a declared descriptive
  comparator;
- C07 covers feature-level functional convergence with observed/control
  contrast;
- C08 covers pathway and regulon membership convergence while retaining
  opposing declared directions as contradictory.

The release rehearsal contains sixteen pseudonymous paths: one positive and
three controls for each operation. Every path carries an expected state,
source receipt IDs, content addresses, and a fixed exact context. The runtime
executes schema, adapters, evaluation, metrics, lineage, provenance, policy,
reconciliation, review, quality, replay, release, packaging, claim-boundary,
and operational stages. Twelve non-positive paths remain reviewable or
quarantined; only four supported paths are publishable.

Commands:

```powershell
glio-noncode cohort-beta-frontier-fixture --output c05-c08-fixture.json
glio-noncode cohort-beta-frontier-evaluate --output c05-c08-evaluation.json
glio-noncode cohort-beta-frontier-quality --output c05-c08-quality.json
glio-noncode cohort-beta-frontier-report --format markdown --output c05-c08-report.md
glio-noncode run-cohort-beta-frontier-pipeline --output c05-c08-runtime.json
```

This plane is descriptive research infrastructure. It does not emit
significance, driver, causal, treatment, prognosis, or clinical outcome
claims.

## Domain 12 C09-C12 cohort alpha depth plane

The C09-C12 tranche is now a full bounded release surface around the four
external-alpha cohort primitives. It uses a fresh public aggregate fixture and
keeps every operation under the exact context
`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`.

The implementation is intentionally layered module-by-module:

- `cohort_alpha_frontier_public_data` defines six public source receipts,
  sixteen pseudonymous aggregate records, four positive paths, and twelve
  partial, ambiguous, foreign-context, or abstained controls;
- `cohort_alpha_frontier_fixture_eval` dispatches each record to the typed
  C09, C10, C11, or C12 primitive and records expected versus observed state;
- `cohort_alpha_frontier_contracts`, `adapters`, `schema`, `field_validation`,
  `normalization`, and `operation_catalog` close the input and output surface;
- `governance` adds metrics, lineage, provenance, policy, reconciliation,
  review queue, quality gate, replay receipt, release bundle, and manifest;
- `thresholds`, `calibration`, `control_coverage`, `state_distribution`,
  `boundary_cases`, and `boundary_explanations` make evidence limits visible;
- `failure_injection`, `recovery`, `performance`, `schema_migrations`,
  `change_control`, `retention`, `freshness`, and `execution_plan` define the
  operational response to drift or incomplete evidence;
- `claim_boundary`, `claim_dictionary`, `claim_evidence`, `safety_controls`,
  `review_sla`, `review_protocol`, and `accessibility` constrain downstream
  wording and make review work inspectable;
- `package`, `artifact_index`, `export_formats`, `views`, `report`, `summary`,
  `release_notes`, `compatibility`, and `reproducibility` define handoff
  objects without publishing raw patient-level records;
- `runtime`, `observability`, `transcript`, `audit_log`, `provenance_ledger`,
  `release_checks`, and `test_vectors` close the deterministic execution loop.

The default fixture has these expected states:

| Operation | Supported | Partial or ambiguous | Foreign | Abstained |
| --- | ---: | ---: | ---: | ---: |
| C09 clonality timing | 1 | 1 partial | 1 | 1 |
| C10 primary recurrence | 1 | 1 partial | 1 | 1 |
| C11 treatment selection | 1 | 1 partial | 1 | 1 |
| C12 cross-cohort replication | 1 | 1 ambiguous | 1 | 1 |

Only the four exact-context supported records are publishable. Partial and
ambiguous records remain reviewable; foreign-context and abstained records are
quarantined. The claim ceiling is descriptive aggregate evidence only: the
surface does not establish clonal evolution, recurrence causation, prognosis,
treatment effect, resistance, benefit, significance, transportability, or
clinical validity.

Commands:

```powershell
glio-noncode cohort-alpha-frontier-fixture --output c09-c12-fixture.json
glio-noncode cohort-alpha-frontier-evaluate --output c09-c12-evaluation.json
glio-noncode cohort-alpha-frontier-quality --output c09-c12-quality.json
glio-noncode cohort-alpha-frontier-replay --output c09-c12-replay.json
glio-noncode cohort-alpha-frontier-report --format markdown --output c09-c12-report.md
glio-noncode run-cohort-alpha-frontier-pipeline --output c09-c12-runtime.json
```

The runtime currently emits 71 ordered accepted stages and 23 extended
consumer-facing receipts. The complete local focused suite is in
`tests/test_cohort_alpha_frontier.py` and
`tests/test_cohort_alpha_frontier_cli.py`; these tests assert fixture closure,
state reconciliation, policy partitions, schema and adapter behavior, query
filters, claim controls, replay determinism, CLI output, and runtime ordering.

This plane remains descriptive research infrastructure. It is not a clinical
decision system and does not convert aggregate evidence into an intervention.

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

### Domain 04 C13-C16 reference release frontier

The Domain 04 C13-C16 reference release frontier is now verified through a
separate public aggregate package. It uses five public source receipts and
sixteen records under the exact context
`GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline`: four positive
paths and twelve controls, balanced across provenance, annotation drift,
reproducible bundles, and release gating.

The four operations preserve distinct evidence boundaries:

- C13 checks URI, declared and observed checksum, license, and exact context;
  missing or mismatched receipts remain `review`.
- C14 compares versioned annotation rows, ignores retrieval-only receipt
  fields, and reports substantive changes or new identities as `drift`.
- C15 sorts available exact-context reference metadata into a schema-hashed,
  content-addressed bundle; foreign, unavailable, and unidentified rows are
  `blocked`.
- C16 applies explicit checksum, schema, license, context, and source checks;
  a missing or false required check blocks publication.

The package performs 23 data checks, 48 execution checks, 12 replay checks,
25 quality checks, 12 policy rules, a 111-node/133-edge redacted lineage graph,
16 reconciliation checks, a nine-stage runtime, an accepted bundle and
artifact inventory, an eleven-item review queue, accessibility and boundary
checks, a 16-row scenario matrix, 12 quantitative thresholds, and a four-row
validation matrix. The accepted outputs contain states, IDs, counts, issue
codes, and addresses without copying raw operation rows.

```powershell
python -m glio_noncode reference-release-data-audit
python -m glio_noncode reference-release-evaluate
python -m glio_noncode reference-release-replay
python -m glio_noncode reference-release-quality-gate
python -m glio_noncode reference-release-runtime
python -m glio_noncode reference-release-bundle
python -m glio_noncode reference-release-review-queue
python -m glio_noncode reference-release-pipeline
python -m glio_noncode export-reference-release-review-csv
```

See `docs/REFERENCE_RELEASE_FRONTIER_API.md`,
`docs/REFERENCE_RELEASE_FRONTIER_DATA_DICTIONARY.md`,
`docs/REFERENCE_RELEASE_FRONTIER_OPERATIONS.md`,
`docs/REFERENCE_RELEASE_FRONTIER_RELEASE.md`, and
`docs/REFERENCE_RELEASE_FRONTIER_VALIDATION.md` for the complete field,
runtime, release, and verification contract.

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

The D13-D16 frontier has evidence-backed code paths for all 256 catalog
capabilities. The current ledger reports 256 of 256 capabilities started and
verified (100%). Verified means the local deterministic fixture and
negative-control boundary pass; external validation, calibration, and
institutional release evidence remain separate.

Domain 13 now includes off-target risk estimation, prerequisite-safe validation
value-of-information selection, content-addressed experiment packages, and
result-driven claim updates. Domain 14 includes evidence reclassification,
cycle-checked deprecation/supersession, audit reproducibility bundles, and
HMAC-signed research dossiers with audience and expiry verification. Domain 15
includes structured review forms, deterministic JSON/Markdown/CSV-oriented
reports, global search and command matching, and accessibility/human-factors
checks. Its release handoff preserves 56 exact-byte artifacts, 49 runtime
stages, 80 evaluation checks, independent denominator indexes, public-key
auditing, and deterministic offline replay. Domain 16 includes deny-by-default privacy/security policy evaluation,
offline deployment manifests, site-local federated coordination, and explicit
release/rollback gates.

The D16 deployment closure is a separate, addressable handoff plane. It
projects 19 resources from the public source bundle: artifacts, fixture
records, executions, checks, source receipts, validation cells, evidence,
lineage edges, review views, queues, diagnostics, runtime stages, stage
indexes, operation partitions, controls, failure probes, audit events,
transcript events, and trace observations. It conserves 51 artifacts, 16
records, 80 checks, 64 validation cells, 16 evidence rows, 52 lineage edges,
38 runtime stages, 32 audit events, 33 transcript events, and 37 trace
observations. Ten address-only indexes, 47 reconciliation checks, 60
certification checks, 151 events, 24 metrics, and a connected 599-node graph
make the release decision independently inspectable. The 14-stage runtime
replays the source bundle and emits an exact-byte export packet containing 14
JSON artifacts plus its manifest.

The D13 validation-design bundle closure is independently addressable. It
checks 27 artifact identities and safe public paths, builds nine address-only
indexes, reconciles 33 cross-artifact joins, emits conserved summary counters
and operation partitions, certifies eight domains with 48 evidence-linked
checks, and exposes 158 events plus 18 aggregate metrics. The closure runtime
has 12 deterministic stages and a replay comparison against the exact bundle
address. Its query surface covers artifacts, records, executions, checks,
sources, stages, planes, operations, issues, states, and review rows.

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

### Domain 06 C01-C04 sequence effect frontier

The first four Domain 06 capabilities now have a complete public aggregate
evidence plane around the bounded sequence adapters. The fixture contains four
positive records, twelve controls, four public source receipts, exact context,
and a `public_aggregate_non_patient` boundary.

- C01 context encoding retains GC, ambiguity, k-mer, sequence hash, and source
  accounting while empty and invalid sequences remain explicit states.
- C02 foundation-model ingestion validates model/version rows, reported
  deltas, source hashes, and malformed-row controls without making a performance
  claim.
- C03 long-context ingestion enforces a 1,024-base minimum window and reports
  short-window failures as explicit controls.
- C04 regulatory-track ensembling retains model IDs, mean deltas, spread,
  single-model partial state, disagreement, and no-observations abstention.

The package provides 96 deterministic execution checks, 25 quality checks, ten
invariants, twelve scenario rows, six threshold profiles, four validation rows,
ten runtime stages, 12 review entries, a nine-node artifact inventory, source
lineage, replay, policy, accessibility, boundary, CSV/Markdown exports, and a
release pipeline. Model deltas remain descriptive research evidence and are not
converted into probabilities.

```powershell
glio-noncode sequence-effect-data-audit --output sequence-effect-data.json
glio-noncode sequence-effect-evaluate --output sequence-effect-evaluation.json
glio-noncode sequence-effect-quality-gate --output sequence-effect-quality.json
glio-noncode sequence-effect-pipeline --run-id d06-c01-c04-local --output sequence-effect-pipeline.json
```

### Domain 06 C05-C08 sequence grammar frontier

The next four Domain 06 capabilities now have a complete public aggregate
evidence plane around motif losses, motif gains, spacing/orientation rules, and
weighted cooperative interactions. The fixture contains four positive records,
twelve controls, four public source receipts, exact context, and the same
`public_aggregate_non_patient` boundary used by the sequence domain.

- C05 `motif_disruption` compares reference and alternate windows, retains every
  reference-only hit, records strand/source/version/hash data, and keeps invalid
  alphabets, empty windows, and empty catalogs explicit.
- C06 `motif_creation` retains alternate-only hits with the same provenance and
  makes catalog and sequence insufficiency visible as abstention rather than a
  negative biological finding.
- C07 `motif_spacing_grammar` evaluates every declared pair against spacing and
  orientation rules; unmatched rules and invalid intervals remain review paths.
- C08 `cooperative_tf_grammar` retains per-interaction contributions, required
  interaction gaps, model version, sequence hash, and the explicit limitation
  that a weighted score is not a probability.

The frontier executes 96 fixture checks, 25 quality checks, ten invariants,
twelve scenarios, six threshold profiles, four validation rows, ten runtime
stages, twelve review entries, a nine-artifact inventory, source lineage,
replay, policy, accessibility, boundary, CSV/Markdown exports, and a complete
release pipeline.

```powershell
glio-noncode sequence-grammar-data-audit --output sequence-grammar-data.json
glio-noncode sequence-grammar-evaluate --output sequence-grammar-evaluation.json
glio-noncode sequence-grammar-quality-gate --output sequence-grammar-quality.json
glio-noncode sequence-grammar-pipeline --run-id d06-c05-c08-local --output sequence-grammar-pipeline.json
glio-noncode export-sequence-grammar-review-csv --output sequence-grammar-review.csv
```

### Domain 06 C09-C12 sequence regulation frontier

The C09-C12 tranche now has a complete aggregate evidence plane around
nucleosome sequence propensity, splice-regulatory motif paths, UTR elements and
bounded upstream patterns, and core-promoter grammar. It uses four public source
receipts, a fixed context, four positive records, twelve controls, and the same
`public_aggregate_non_patient` boundary. Every operation runs through a typed
adapter, an expected-state comparison, policy routing, quality checks, and a
content-addressed release surface.

- C09 `nucleosome_propensity` retains phase-aware dinucleotide features,
  GC-balance, length state, ambiguity state, context mismatch, and a bounded
  sequence-only score. The score is not calibrated occupancy.
- C10 `splice_regulation` retains reference and alternate motif hits,
  created/disrupted sets, source versions, strand data, invalid alphabet
  controls, and no-change abstention. It does not infer splice consequence.
- C11 `utr_regulation` separates 5-prime and 3-prime elements, retains allele
  deltas and bounded upstream start/stop patterns, and keeps ambiguity and
  invalid-region paths visible. It does not infer binding, translation,
  stability, or expression.
- C12 `promoter_grammar` evaluates declared motif pairs by spacing, orientation,
  and weighted coverage while preserving unmatched rules and competing pairs.
  Compatibility is not promoter activity or transcription initiation evidence.

The frontier evaluates 16 record paths, 25 quality checks, ten runtime stages,
12 review items, 19 content-addressed report surfaces, four operation contracts,
four adapter specifications, source lineage, replay, accessibility, boundary,
scenario, threshold, validation, release, and bundle reports. Positive cases
remain releasable only when their expected paths match; controls stay visible in
review rather than being silently discarded.

```powershell
glio-noncode sequence-regulation-fixture --output sequence-regulation-fixture.json
glio-noncode sequence-regulation-data --output sequence-regulation-data.json
glio-noncode sequence-regulation-evaluate --output sequence-regulation-evaluation.json
glio-noncode sequence-regulation-quality --output sequence-regulation-quality.json
glio-ncode sequence-regulation-contracts --output sequence-regulation-contracts.json
glio-noncode sequence-regulation-replay --output sequence-regulation-replay.json
glio-noncode run-sequence-regulation-pipeline --output sequence-regulation-pipeline.json
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

### Domain 07 C01-C04 chromatin-context frontier evidence gate

The Domain 07 C01-C04 tranche now binds the core chromatin context primitives
to a closed public aggregate fixture. It contains four positive records and
twelve controls across ATAC/DNase track retrieval, accessibility deltas,
histone mark context, and H3K27ac activity observations. Five source receipts
retain public URLs, release labels, scope, exact context, and content
addresses. Coordinates are normalized, malformed rows are quarantined,
replicate spread remains visible, missing measurements abstain, and foreign
context is refused.

The release plane adds typed contracts, schema and aggregate-boundary checks,
source lineage and registry, expected-path reconciliation, policy decisions,
metrics, review-safe projections, a prioritized queue, structured runtime
events, deterministic replay, invariants, scenario and validation matrices,
thresholds, a runbook, content-addressed bundle and artifact inventory, and
JSON/CSV exports. H3K27ac and accessibility signals remain descriptive assay
observations. Enhancer function, target linkage, causal effect, and external
transport are not inferred from signal alone.

The bounded aggregate command surface is:

```powershell
glio-noncode chromatin-context-frontier-fixture --output chromatin-context-fixture.json
glio-noncode chromatin-context-frontier-data --output chromatin-context-data.json
glio-noncode chromatin-context-frontier-evaluate --output chromatin-context-evaluation.json
glio-noncode chromatin-context-frontier-quality --output chromatin-context-quality.json
glio-noncode chromatin-context-frontier-contracts --output chromatin-context-contracts.json
glio-noncode chromatin-context-frontier-schema --output chromatin-context-schema.json
glio-noncode chromatin-context-frontier-sources --output chromatin-context-sources.json
glio-noncode chromatin-context-frontier-replay --output chromatin-context-replay.json
glio-noncode run-chromatin-context-frontier-pipeline --output chromatin-context-pipeline.json
```

The C01-C04 surface proves the following boundaries:

- `ChromatinTrackParser` converts BED-like coordinates and JSON observations,
  retaining source version, raw row hash, replicate, mark, and context.
- `ChromatinContextRetriever` gates by assay kind, interval overlap, and exact
  context. One match is supported, multiple matches are ambiguous, and a
  foreign-context overlap is out of domain.
- `AccessibilityDeltaEstimator` reports absolute and relative measured deltas,
  blocks relative normalization at a zero baseline, and abstains on missing
  reference or alternate signal.
- `H3K27acActivityEstimator` reports replicate-aware signal while retaining the
  limitation that a track observation is not enhancer or target-gene truth.

### Domain 07 C05-C08 methylation frontier evidence gate

The Domain 07 C05-C08 tranche binds the methylation primitives to a closed
public aggregate fixture. It contains four positive records and twelve
controls across methylation context retrieval, CpG creation/loss, sensitive
motif context, and IDH hypermethylation context. Each source retains a URI,
version, checksum, and exact context key. Malformed rows, missing support,
foreign context, changed-length sequence windows, and incomplete comparator
panels stay visible as invalid, abstained, partial, or out-of-domain states.

The release plane adds typed contracts, schema and public-boundary checks,
source lineage, expected-path reconciliation, policy decisions, metrics,
review-safe rows, a prioritized review queue, structured runtime events,
accessibility checks, replay comparison, scenario and validation matrices,
thresholds, a runbook, and a content-addressed bundle. The IDH panel remains
descriptive aggregate context and is not a diagnostic classifier. Measured
beta values are preserved; missing values are not imputed.

The bounded aggregate command surface is:

```powershell
glio-noncode methylation-frontier-fixture --output methylation-frontier-fixture.json
glio-noncode methylation-frontier-data --output methylation-frontier-data.json
glio-noncode methylation-frontier-evaluate --output methylation-frontier-evaluation.json
glio-noncode methylation-frontier-quality --output methylation-frontier-quality.json
glio-noncode methylation-frontier-contracts --output methylation-frontier-contracts.json
glio-noncode methylation-frontier-schema --output methylation-frontier-schema.json
glio-noncode methylation-frontier-sources --output methylation-frontier-sources.json
glio-noncode methylation-frontier-replay --output methylation-frontier-replay.json
glio-noncode run-methylation-frontier-pipeline --output methylation-frontier-pipeline.json
```

### Domain 07 C09-C12 chromatin-alpha frontier evidence gate

The Domain 07 C09-C12 tranche binds chromatin-alpha primitives to its own
closed public aggregate fixture. It contains four positive rows and twelve
controls across chromatin interval segmentation, allele-specific chromatin,
epigenomic purity context, and batch/cell-composition correction. The five
source receipts retain public URLs, releases, scopes, exact context, and
content addresses. Foreign context, mixed replicate directions, invalid rows,
out-of-range marker estimates, and missing correction terms remain explicit
partial, ambiguous, or out-of-domain states.

The release plane covers typed contracts, schema and public-boundary checks,
expected-path reconciliation, operation metrics, source lineage, release and
review policy, a ten-stage runtime, content-addressed bundle and artifact
receipts, a sanitized review view, prioritized queue, structured trace,
accessibility and compliance checks, invariants, replay comparison, scenario
and validation matrices, thresholds, a runbook, and deterministic exports.
Chromatin labels and deltas remain descriptive evidence; purity and corrected
signals are research-use summaries, not clinical or causal conclusions.

The bounded aggregate command surface is:

```powershell
glio-noncode chromatin-alpha-frontier-fixture --output chromatin-alpha-fixture.json
glio-noncode chromatin-alpha-frontier-data --output chromatin-alpha-data.json
glio-noncode chromatin-alpha-frontier-evaluate --output chromatin-alpha-evaluation.json
glio-noncode chromatin-alpha-frontier-quality --output chromatin-alpha-quality.json
glio-noncode chromatin-alpha-frontier-contracts --output chromatin-alpha-contracts.json
glio-noncode chromatin-alpha-frontier-schema --output chromatin-alpha-schema.json
glio-noncode chromatin-alpha-frontier-sources --output chromatin-alpha-sources.json
glio-noncode chromatin-alpha-frontier-replay --output chromatin-alpha-replay.json
glio-noncode run-chromatin-alpha-frontier-pipeline --output chromatin-alpha-pipeline.json
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

### Domain 08 C01-C04 cell-context frontier evidence gate

The Domain 08 C01-C04 tranche binds disease ontology context, adult/pediatric
routing, molecular class/state resolution, and territory-aware context assembly
to a closed public aggregate fixture. It contains four positive records and
twelve controls across the four operations, with five source receipts and an
exact `ReferenceContext.key`. Malformed taxonomy rows, multiple candidates,
age conflicts, missing molecular dimensions, and foreign-context observations
remain visible as partial, ambiguous, contradictory, abstained, or
out-of-domain states.

The release plane adds typed contracts, schema and aggregate-boundary checks,
source lineage and registry, expected-path reconciliation, policy decisions,
operation metrics, a four-operation depth ledger, accessibility and integrity
reports, review-safe rows, a prioritized queue, ten runtime stages, structured
trace events, deterministic replay, scenario and validation matrices,
thresholds, a runbook, content-addressed bundle and artifact inventory, and
JSON/CSV exports. Disease terms, age routes, molecular dimensions, and
territory labels are descriptive research context. No diagnosis, prognosis,
pathogenicity, treatment, or actionability claim is inferred.

The bounded aggregate command surface is:

```powershell
glio-noncode cell-context-frontier-fixture --output cell-context-fixture.json
glio-noncode cell-context-frontier-data --output cell-context-data.json
glio-noncode cell-context-frontier-evaluate --output cell-context-evaluation.json
glio-noncode cell-context-frontier-quality --output cell-context-quality.json
glio-noncode cell-context-frontier-contracts --output cell-context-contracts.json
glio-noncode cell-context-frontier-adapters --output cell-context-adapters.json
glio-noncode cell-context-frontier-schema --output cell-context-schema.json
glio-noncode cell-context-frontier-sources --output cell-context-sources.json
glio-noncode cell-context-frontier-replay --output cell-context-replay.json
glio-noncode run-cell-context-frontier-pipeline --output cell-context-pipeline.json
```

The C01-C04 depth surface proves the following boundaries:

- `DiseaseOntologyContextualizer` retains exact-context candidate alternatives,
  source IDs, evidence IDs, confidence, and ambiguity margins.
- `AdultPediatricRouter` takes the declared route, exposes conflicting
  evidence, and abstains rather than guessing when age is unknown.
- `MolecularClassStateContextualizer` keeps molecular class and molecular state
  independent, retaining missingness, contradiction, and uncertainty.
- `CellStateContextAssembler` propagates the weakest dimension and exposes
  one-to-many territory candidates without silently selecting a label.

### Domain 08 C05-C08 beta context-prior evidence gate

The Domain 08 C05-C08 tranche binds the four scientific-beta context priors to
a fresh public aggregate fixture. It contains one positive path and three
controls for each operation: developmental-lineage context, glioblastoma
malignant-state context, IDH-mutant lineage-state context, and H3K27-altered
developmental-state context. The fixture has sixteen records, four public
source receipts, four target context families, and no subject-level payload
keys.

The adapter layer parses versioned observations, preserves source versions and
candidate evidence, and maps parser quarantine to a partial state without
discarding usable rows. The four control families prove that close candidates
remain ambiguous, wrong disease or molecular gates remain out of domain, and
bounded uncertainty is retained beside every selected or unselected candidate.
The release surface does not produce a diagnosis, prognosis, treatment claim,
or calibrated probability.

The complete command surface is:

```powershell
glio-noncode cell-context-beta-frontier-fixture --output beta-fixture.json
glio-noncode cell-context-beta-frontier-data --output beta-data.json
glio-noncode cell-context-beta-frontier-evaluate --output beta-evaluation.json
glio-noncode cell-context-beta-frontier-quality --output beta-quality.json
glio-noncode cell-context-beta-frontier-contracts --output beta-contracts.json
glio-noncode cell-context-beta-frontier-adapters --output beta-adapters.json
glio-noncode cell-context-beta-frontier-schema --output beta-schema.json
glio-noncode cell-context-beta-frontier-sources --output beta-sources.json
glio-noncode cell-context-beta-frontier-replay --output beta-replay.json
glio-noncode cell-context-beta-frontier-export --output beta-export.json
glio-noncode cell-context-beta-frontier-review --output beta-review.json
glio-noncode run-cell-context-beta-frontier-pipeline --output beta-pipeline.json
```

The C05-C08 depth surface proves the following boundaries:

- `DevelopmentalLineagePrior` runs adult and pediatric route families with
  exact-context candidates, support summaries, ambiguity margins, and parser
  issue receipts.
- `GlioblastomaMalignantStatePrior` requires an explicit GBM disease gate and
  preserves malignant-state alternatives without turning a state prior into a
  disease label.
- `IdhMutantLineageStatePrior` requires an IDH-mutant declaration and refuses
  IDH-wildtype transport while retaining source versions and evidence tiers.
- `H3K27AlteredDevelopmentalStatePrior` requires an H3K27-altered declaration,
  retains developmental alternatives, and keeps pediatric midline context
  distinct from other molecular routes.
- The public release adds candidate, gate, uncertainty, integrity, source,
  replay, policy, queue, bundle, artifact, report, accessibility, and runtime
  surfaces with a twelve-stage accepted pipeline.

### Domain 08 C09-C12 alpha context-prior evidence gate

The Domain 08 C09-C12 tranche binds four cell-context alpha priors to a closed
public aggregate fixture. It contains one positive path and three controls for
each operation: spatial niche, core-versus-margin territory, recurrence state,
and treatment-induced state. The fixture has sixteen records, four public
source receipts, a single adult glioma stem-like anchor context, and no
subject-level payload keys.

The adapter layer converts versioned JSON observations into the existing alpha
primitive contracts. Every result retains the operation, exact context,
sample-level support, candidate IDs, source versions, evidence IDs, content
addresses, issue codes, and the expected state. Invalid rows become partial,
close candidates remain ambiguous, and foreign context rows become out of
domain without being merged into the accepted context.

The four operation surfaces are intentionally distinct:

- C09 `spatial_niche_prior` ranks niche candidates by bounded support while
  retaining close-candidate margins and sample aggregation.
- C10 `core_margin_territory_prior` compares core and margin support with an
  explicit tolerance and exposes mixed or one-sided territory evidence.
- C11 `recurrence_state_prior` preserves primary, recurrence, and progression
  phase candidates with replicate counts, rank margins, and alternatives.
- C12 `treatment_induced_state_prior` compares baseline and post-treatment
  state support and records induced, stable, reduced, or mixed descriptive
  labels without making response or resistance claims.

The release has typed contracts, schema checks, source closure, fixture
evaluation, replay receipts, operational metrics, policy decisions,
reconciliation, quality gates, boundary checks, integrity invariants, depth
audits, candidate and delta audits, validation matrices, scenario matrices,
accessibility checks, catalog entries, review views, queue items, reports,
release manifests, bundles, artifact inventories, runbook steps, and a
twelve-stage runtime trace. The bundle is accepted only when the data,
evaluation, schema, quality, policy, integrity, boundary, and release floors
all pass.

The complete command surface is:

```powershell
glio-noncode cell-context-alpha-frontier-fixture --output alpha-fixture.json
glio-noncode cell-context-alpha-frontier-data --output alpha-data.json
glio-noncode cell-context-alpha-frontier-evaluate --output alpha-evaluation.json
glio-noncode cell-context-alpha-frontier-replay --output alpha-replay.json
glio-noncode cell-context-alpha-frontier-quality --output alpha-quality.json
glio-noncode cell-context-alpha-frontier-contracts --output alpha-contracts.json
glio-noncode cell-context-alpha-frontier-adapters --output alpha-adapters.json
glio-noncode cell-context-alpha-frontier-schema --output alpha-schema.json
glio-noncode cell-context-alpha-frontier-sources --output alpha-sources.json
glio-noncode cell-context-alpha-frontier-export --output alpha-export.json
glio-noncode cell-context-alpha-frontier-review --output alpha-review.json
glio-noncode run-cell-context-alpha-frontier-pipeline --output alpha-pipeline.json
```

The C09-C12 depth surface proves that descriptive priors, candidate ranking,
territory deltas, phase transitions, and treatment-state deltas remain bounded
to supplied aggregate evidence. It does not produce diagnosis, prognosis,
localization, treatment selection, response, or resistance conclusions.

### Domain 08 C13-C16 cell-state frontier evidence gate

The Domain 08 C13-C16 tranche composes four cell-state boundaries over a public
aggregate fixture. It keeps exact context, source closure, state margins,
uncertainty intervals, out-of-domain findings, upstream receipt addresses, and
review actions visible in every output.

- C13 `cell_state_abundance_interval` reports bounded binomial abundance
  intervals and retains invalid-count controls as partial.
- C14 `single_cell_reference_mapping` preserves top and second reference scores,
  margins, ambiguous controls, and context mismatch controls.
- C15 `cell_state_ood_detection` evaluates distance and support boundaries while
  keeping other territories out of the accepted context.
- C16 `cell_state_context_publication` binds aggregate cell IDs to mapping,
  abundance, and OOD receipt addresses before a release can be ready.

The fixture contains 4 positive records, 12 controls, 5 public source receipts,
120 evaluation checks, 23 schema checks, 12 quality checks, 4 operation metrics,
9 runtime stages, 16 lineage edges, 16 reconciliation items, and a sanitized
12-row review queue. The bounded commands are:

```powershell
glio-noncode audit-cell-state-frontier-data --output cell-state-data.json
glio-noncode evaluate-cell-state-frontier-fixture --output cell-state-evaluation.json
glio-noncode replay-cell-state-frontier --output cell-state-replay.json
glio-noncode cell-state-frontier-quality-gate --output cell-state-quality.json
glio-noncode evaluate-cell-state-frontier-scenarios --output cell-state-scenarios.json
glio-noncode cell-state-frontier-schema --output cell-state-schema.json
glio-noncode run-cell-state-frontier-pipeline --run-id cell-state-ci --output cell-state-pipeline.json
glio-noncode build-cell-state-frontier-release --run-id cell-state-ci --output cell-state-release.json
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

### Domain 09 C01-C04 topology context evidence gate

The Domain 09 C01-C04 tranche binds contact import, matrix QC, boundary
ensembles, and insulation deltas to a closed public aggregate fixture. It has
one positive path and three controls per operation, sixteen records total, four
public source receipts, and one exact GRCh38 glioma adult stem-like core
context. Payloads contain no subject-level identifiers.

- C01 `contact_import` parses Hi-C and Micro-C-shaped long-form rows, converts
  coordinates through the existing parser, retrieves exact assay/context pairs,
  and preserves supported, partial, ambiguous, and foreign-context states.
- C02 `matrix_qc` reports duplicate canonical pairs, zero signals, signal
  ranges, mean/max normalization, empty input, and foreign-context exclusion.
- C03 `boundary_ensemble` clusters caller and assay observations within a
  declared tolerance and retains single-assay, multi-assay, competing-cluster,
  malformed, and foreign-context evidence.
- C04 `insulation_delta` retains alternate-minus-reference direction,
  relative-delta missingness, replicate count, zero-baseline behavior, invalid
  scores, and foreign-context controls.

The release layer adds typed contracts, schema checks, source closure, fixture
evaluation, replay receipts, metrics, policy decisions, reconciliation,
quality gates, boundary checks, integrity invariants, depth audits, candidate
and delta audits, validation matrices, scenarios, accessibility, review
queues, views, reports, runbook steps, bundles, artifact inventories, and a
twelve-stage runtime. The provenance graph explicitly closes source receipts
to record envelopes and result addresses, including one-to-many source reuse.
Every result remains descriptive topology evidence; the
package makes no causal, clinical, enhancer, or target-gene conclusion.

The stored receipt surfaces are deliberately separable: parser issues remain
on the adapter result, QC fields remain beside normalized values, boundary
clusters retain observation IDs and assay IDs, and insulation measurements
retain raw hashes and replicate counts. A downstream review can therefore
inspect the exact evidence boundary without reconstructing source rows from a
single summary score.

The negative controls are also operation-specific. Contact ambiguity comes
from multiple exact-context matches; matrix partialness comes from duplicate
or zero-signal rows; boundary ambiguity comes from equally supported distant
clusters; and insulation abstention comes from a missing baseline score. A
foreign-context control is retained for each surface so transport is never
silently assumed. The resulting review queue has twelve non-supported rows,
while the accepted release still carries all sixteen result addresses.

The runtime ordering is fixed: data and contracts are checked before source
closure; evaluation feeds schema, metrics, lineage, provenance, policy, and
reconciliation; quality precedes boundary, integrity, depth, validation,
accessibility, review, and release; and the final inventory records every
bundle member and result address. This ordering makes a failed control visible
at the stage where it first becomes relevant and keeps later artifacts from
appearing to validate a missing input.

The command facade exposes the same bounded outputs used by the pipeline:
fixture JSON, data audit, evaluation, replay, quality, contracts, adapters,
schema, sources, export, review, and the full runtime. Each command is
deterministic for the checked-in aggregate fixture, writes no private rows,
and preserves enough receipt information for a reviewer to compare runs.

The complete command surface is:

```powershell
glio-noncode topology-context-frontier-fixture --output topology-fixture.json
glio-noncode topology-context-frontier-data --output topology-data.json
glio-noncode topology-context-frontier-evaluate --output topology-evaluation.json
glio-noncode topology-context-frontier-replay --output topology-replay.json
glio-noncode topology-context-frontier-quality --output topology-quality.json
glio-noncode topology-context-frontier-contracts --output topology-contracts.json
glio-noncode topology-context-frontier-adapters --output topology-adapters.json
glio-noncode topology-context-frontier-schema --output topology-schema.json
glio-noncode topology-context-frontier-sources --output topology-sources.json
glio-noncode topology-context-frontier-export --output topology-export.json
glio-noncode topology-context-frontier-review --output topology-review.json
glio-noncode run-topology-context-frontier-pipeline --output topology-pipeline.json
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

### Domain 09 C05-C08 topology beta release slice

The C05-C08 slice closes the four beta operations as one deterministic public
aggregate package. Every operation has one positive record and three controls,
four source receipts, context-gated replay, state and issue reconciliation,
content addresses, review rows, release artifacts, and a twelve-stage pipeline.

- Loop and stripe fixtures preserve two-anchor coordinates, feature kind,
  signal, resolution, replicate IDs, caller metadata, source versions, and
  row-level parser issues. Missing metadata is partial; divergent signals are
  ambiguous; foreign context is out of domain.
- Promoter-capture fixtures preserve promoter identity, target-element identity,
  bait IDs, coordinates, signal, resolution, replicate IDs, and source receipts.
- Enhancer-promoter scoring retains all exact-context observations, median
  signal, spread, bounded normalization, source versions, and explicit absent
  or foreign-context states.
- Activity-by-contact retains contact and activity components separately,
  model/version receipts, missingness, component disagreement, and the bounded
  descriptive product. It is not a probability or causal conclusion.

The aggregate package can be replayed and inspected with:

```powershell
glio-noncode topology-beta-frontier-fixture --output topology-beta-fixture.json
glio-noncode topology-beta-frontier-evaluate --output topology-beta-evaluation.json
glio-noncode topology-beta-frontier-review --output topology-beta-review.json
glio-noncode topology-beta-frontier-pipeline --output topology-beta-pipeline.json
```

The closed fixture contains 16 records, 4 source receipts, 4 positive paths,
12 control paths, 12 accepted pipeline stages, 20 release artifacts, and a
replay receipt whose expected and observed evaluation addresses match.

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

### Domain 09 C09-C12 topology alpha evidence gate

The C09-C12 alpha package turns the four structural primitives into a closed,
fixture-backed public aggregate release surface. Each operation has one
positive record and three controls. Controls retain partial fields, mixed motif
orientations, channel disagreement, invalid molecular vocabulary, missing edge
edits, and foreign context instead of collapsing them into support.

- The boundary motif adapter preserves left/right orientation labels, median
  score, observation identity, source version, and mixed-orientation review.
- The CTCF/cohesin adapter retains independent channel deltas and combined
  descriptive labels while keeping absent channels visible.
- The IDH/insulator adapter compares mutant and wildtype state rows while
  retaining methylation as a separate measurement channel.
- The SV adapter simulates declared contact-edge loss, gain, preservation, and
  rewiring with affected nodes and explicit edge receipts.

The deeper assurance layer includes operation conformance, source receipt
checks, evidence cells, claim boundaries, typed failure definitions, query and
inspection views, deterministic regression checks, ordered stage ledgers,
governance decisions, package manifests, release notes, bounded runtime limits,
and sanitized exports. The extended assurance report adds a locked data
dictionary, state-transition rules, operation scorecards, independent lineage
and checksum audits, positive/control comparisons, deterministic partitions,
typed next actions, append-only stage audit logging, resource ceilings, a
release gate, canonical serialization, a validation report, and an operator
handbook. The pipeline contains 16 records, 4 source receipts, 12 review items,
20 artifacts, and 12 passing stages.

Run the complete alpha surface locally:

```powershell
glio-noncode topology-alpha-frontier-fixture --output topology-alpha-fixture.json
glio-noncode topology-alpha-frontier-evaluate --output topology-alpha-evaluation.json
glio-noncode topology-alpha-frontier-contracts --output topology-alpha-contracts.json
glio-noncode topology-alpha-frontier-schema --output topology-alpha-schema.json
glio-noncode topology-alpha-frontier-metrics --output topology-alpha-metrics.json
glio-noncode topology-alpha-frontier-review --output topology-alpha-review.json
glio-noncode topology-alpha-frontier-release --output topology-alpha-release.json
glio-noncode topology-alpha-frontier-summary --output topology-alpha-summary.json
```

The package is descriptive public aggregate infrastructure. Orientation,
channel deltas, IDH comparisons, and contact-edge simulations do not establish
mechanism, probability, patient-level findings, or treatment effect.

The alpha verification matrix is intentionally explicit:

| Surface | C09 | C10 | C11 | C12 |
| --- | --- | --- | --- | --- |
| Primitive adapter | motif orientation | CTCF/cohesin delta | IDH/insulator state | SV edge simulation |
| Positive path | convergent pair | dual-channel disruption | mutant/wildtype pair | deletion/gain/rewire |
| Partial control | one-sided motif | missing cohesin | mutant-only or invalid row | missing or unresolved edits |
| Ambiguity control | mixed orientations | opposing channels | retained state uncertainty | explicit review state |
| Context control | foreign context | foreign context | foreign context | foreign context |
| Receipt fields | observation IDs | variant IDs | region IDs | SV IDs and edges |
| Primary review | orientation proof | channel agreement | vocabulary and methylation | edge closure |
| Release limit | score threshold | delta threshold | dysfunction threshold | bounded edit set |

The shared execution contract is the same for every column: load only the
closed public aggregate fixture, resolve the operation-specific adapter, retain
the primitive state and issue codes, attach source and result addresses, compare
the result to expected controls, and route every non-supported path to review.
The source registry verifies four aggregate receipts. The evidence matrix maps
all 16 records to source, result, issue, and review fields. The claim boundary
records one permitted descriptive statement and one blocked over-interpretation
for every row. The failure catalog gives each observed issue a category,
severity, remediation, and release effect.

The operational layers then make the result repeatable: the query plan layer
reproduces control and positive slices, the projection layer emits public-safe
fields, the partition layer makes operation/role/state coverage inspectable,
and the comparison layer pairs each positive path with its three controls. The
state-transition audit confirms that all outputs use the seven-value topology
state vocabulary. The scorecard aggregates per-operation support, review,
address, and evidence closure. The lineage and checksum audits independently
recheck source-to-record-to-result relations. Resource ceilings cap records,
sources, review items, artifacts, and stages.

The release gate is blocking for execution, replay, scope, manifest, and
artifact failures. Review queue and trace checks remain visible as advisory
records. A canonical serializer gives equivalent dictionaries the same output
bytes, while the validation report renders fixture, replay, quality, review,
release, and observability sections. The operator handbook describes load,
replay, inspect, release, and remote-check procedures with evidence to retain.

No row is promoted by a missing field, unresolved context, opposing channel,
or unknown edge. Those cases stay addressable and reviewable.

The package therefore supports both a compact summary command and a deep
inspection path. Reviewers can start with the summary address, select an
operation or control class, inspect its source and result receipts, compare it
with the positive path, and retain the corresponding release-gate decision.
This preserves a short handoff without removing the detailed evidence needed
to reproduce the decision.

The recorded limits also make future growth deliberate: expanding the fixture
requires a contract update, a new control balance, refreshed evidence counts,
new address checks, and a corresponding workflow assertion.

That contract keeps the alpha plane auditable as additional public aggregate
sources and operation variants are introduced.

Every expansion remains
versioned,
bounded,
addressed,
tested,
reviewable,
and release-gated.

### Domain 09 C13-C16 topology frontier evidence gate

The Domain 09 C13-C16 tranche composes four public aggregate topology inference
boundaries over one exact GRCh38 glioma context. It keeps source receipts, signed
state changes, edge uncertainty, path closure, assay receipts, review states,
lineage, and release addresses visible without turning topology observations into
causal, clinical, or treatment claims.

- C13 `ecdna_regulatory_contact` applies the existing ecDNA contact model with
  source-count and contact-strength controls.
- C14 `compartment_switch` preserves signed A/B transitions, stable controls,
  exact-context gating, and malformed paired-score controls.
- C15 `topology_uncertainty_transport` transports declared signal across edges,
  retains accumulated uncertainty, and exposes disconnected-path controls.
- C16 `three_d_evidence_publication` binds path IDs, assay IDs, exact context,
  source receipts, and a content-addressed publication bundle.

The fixture contains 4 positive records, 12 controls, 5 public source receipts,
120 evaluation checks, 20 schema checks, 12 quality checks, 4 operation metrics,
9 runtime stages, 16 lineage edges, 16 reconciliation items, and a sanitized
12-row review queue. The bounded commands are:

```powershell
glio-noncode audit-topology-frontier-data --output topology-data.json
glio-noncode evaluate-topology-frontier-fixture --output topology-evaluation.json
glio-noncode replay-topology-frontier --output topology-replay.json
glio-noncode topology-frontier-quality-gate --output topology-quality.json
glio-noncode evaluate-topology-frontier-scenarios --output topology-scenarios.json
glio-noncode topology-frontier-schema --output topology-schema.json
glio-noncode run-topology-frontier-pipeline --run-id topology-ci --output topology-pipeline.json
glio-noncode build-topology-frontier-release --run-id topology-ci --output topology-release.json
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

### Domain 10 C01-C04 link-graph foundation depth

The C01-C04 foundation tranche closes the first four candidate-link
operations over a fresh public aggregate fixture. It contains 16 records,
four records per operation, four positive records, twelve controls, and five
versioned source receipts. Every row is replayed through the existing typed
primitives and retains expected state, issue codes, measurements, evidence
IDs, context, and content addresses.

- C01 `coordinate_overlap` covers supported overlap, multiple-overlap
  ambiguity, no-overlap absence, and context mismatch.
- C02 `nearest_gene` covers supported proximity, distance ties, bounded-window
  abstention, and context mismatch.
- C03 `ccre_assignment` covers supported assignment, multiple cCRE ambiguity,
  absent cCRE, and context mismatch.
- C04 `enhancer_gene_consensus` covers multi-method support, single-method
  partial state, contradictory evidence, and context mismatch.

The assurance surface adds operation contracts, receipt ledgers, normalized
records, stable field projections, benchmark cases, comparison cells,
regression sentinels, conformance rules, named invariants, resource budgets,
decision traces, provenance matrices, risk controls, quality dashboards, and
release readiness. The ordered workflow has six passing stages and remains a
public aggregate research boundary.

```powershell
glio-noncode link-graph-foundation-frontier-fixture --output link-foundation-fixture.json
glio-noncode link-graph-foundation-frontier-evaluate --output link-foundation-evaluation.json
glio-noncode link-graph-foundation-frontier-contracts --output link-foundation-contracts.json
glio-noncode link-graph-foundation-frontier-schema --output link-foundation-schema.json
glio-noncode link-graph-foundation-frontier-metrics --output link-foundation-metrics.json
glio-noncode link-graph-foundation-frontier-review --output link-foundation-review.json
glio-noncode link-graph-foundation-frontier-release --output link-foundation-release.json
glio-noncode link-graph-foundation-frontier-summary
```

### Domain 10 C05-C08 link-graph beta depth

The C05-C08 beta tranche extends the link graph over a fresh public aggregate
fixture with four independently replayable operations: activity-by-contact,
coaccessibility, molecular QTL, and allele-specific link evidence. The fixture
contains 16 records, one positive and three controls per operation, four source
receipts, a declared GRCh38 glioma stem-like context, and four foreign-context
controls. No row is patient-level and no result is a causal, clinical, or
preferred-target conclusion.

- C05 `activity_by_contact` preserves activity, contact, replicate, support,
  source, and exact-context measurements while retaining single-method and
  replicate controls.
- C06 `coaccessibility` preserves path identity and alternative-gene evidence
  while retaining missing-evidence, alternative-gene, and context-mismatch
  controls.
- C07 `molecular_qtl` preserves effect and q-value measurements with a bounded
  support transform and explicit weak-q-value and missing-evidence controls.
- C08 `allele_specific` preserves gain/loss direction and retains direction
  conflicts as contradictory evidence rather than collapsing them.

The beta depth plane is organized as a 12-stage executable pipeline: data
audit, contracts, sources, typed evaluation, schema, metrics, lineage, quality,
validation, review, release, and artifacts. Independent modules provide
adapters, source checks, normalization, projections, comparisons, budgets,
receipts, policy, decision traces, controls, failures, invariants, scenario
catalogs, validation orchestration, audit history, traceability, report
rendering, and bounded runtime output. The complete fixture replays with 16 of
16 state matches and 16 of 16 issue matches before release readiness is
calculated. A 96-cell operational matrix cross-checks six dimensions for every
record and keeps the context, state, issue, receipt, and measurement boundaries
queryable as one deterministic export.

```powershell
glio-noncode link-graph-beta-frontier-fixture --output link-beta-fixture.json
glio-noncode link-graph-beta-frontier-evaluate --output link-beta-evaluation.json
glio-noncode link-graph-beta-frontier-contracts --output link-beta-contracts.json
glio-noncode link-graph-beta-frontier-schema --output link-beta-schema.json
glio-noncode link-graph-beta-frontier-metrics --output link-beta-metrics.json
glio-noncode link-graph-beta-frontier-review --output link-beta-review.json
glio-noncode link-graph-beta-frontier-release --output link-beta-release.json
glio-noncode link-graph-beta-frontier-summary
```

### Domain 10 C09-C12 link-graph alpha depth

The C09-C12 alpha tranche binds the four existing link primitives to one
closed, public aggregate fixture. It contains 16 records: one positive and
three controls for each operation, plus five versioned source receipts. Every
record replays through the typed adapter registry and receives a content
address, state, issue codes, measurements, and evidence IDs.

- C09 `crispr_perturbation` retains perturbation direction, weak support,
  opposing-direction contradiction, and context mismatch.
- C10 `contact_3d` retains normalized contact, assay kind, resolution, weak
  contact, alternative genes, and context mismatch.
- C11 `promoter_tethering` retains distance and component accounting while
  exposing missing-component abstention, tied candidates, and foreign context.
- C12 `multi_gene_graph` retains edge paths, alternatives, node degree,
  connected components, single-evidence partial state, and contradiction.

The supporting assurance plane includes contracts, source registry, schema,
metrics, lineage, provenance, policy, reconciliation, quality gates, depth
audits, candidate accounting, deltas, validation and scenario matrices,
accessibility, integrity, review queue, release bundle, artifacts,
observability, replay, control catalog, failure catalog, scorecard, and
operator runbook. The pipeline has 12 passing stages and does not select a
preferred gene or convert a candidate edge into a mechanism claim.

```powershell
glio-noncode link-graph-alpha-frontier-fixture --output link-alpha-fixture.json
glio-noncode link-graph-alpha-frontier-evaluate --output link-alpha-evaluation.json
glio-noncode link-graph-alpha-frontier-metrics --output link-alpha-metrics.json
glio-noncode link-graph-alpha-frontier-review --output link-alpha-review.json
glio-noncode link-graph-alpha-frontier-release --output link-alpha-release.json
glio-noncode link-graph-alpha-frontier-summary
```

### Domain 10 C13-C16 link frontier evidence gate

The Domain 10 C13-C16 tranche hardens the link-evidence plane over one exact
GRCh38 glioma context. It keeps correlated support, target alternatives,
calibration error, abstention, source receipts, lineage, replay, and release
limitations visible. Candidate links remain descriptive research evidence and
are not causal, clinical, pathogenicity, or actionability conclusions.

- C13 `link_dependence_correction` groups correlated paths and downweights
  duplicate support while retaining raw support, group size, and zero-support
  controls.
- C14 `target_gene_ranking` ranks declared component scores deterministically,
  retaining alternative genes and review state for zero-support candidates.
- C15 `link_calibration_abstention` applies explicit uncertainty and calibration
  thresholds and exposes high-error and empty-input controls.
- C16 `link_evidence_publication` binds link IDs, source IDs, exact context,
  content addresses, sanitized exports, and a release manifest.

The fixture contains 4 positive records, 12 controls, 5 public source receipts,
120 evaluation checks, 20 schema checks, 12 quality checks, 51 operation-depth
checks, 4 operation metrics, 9 runtime stages, content-addressed lineage,
reconciliation items, and a review queue. The bounded commands are:

```powershell
glio-noncode audit-link-frontier-data --output link-data.json
glio-noncode evaluate-link-frontier-fixture --output link-evaluation.json
glio-noncode replay-link-frontier --output link-replay.json
glio-noncode link-frontier-quality-gate --output link-quality.json
glio-noncode link-frontier-depth-audit --output link-depth.json
glio-noncode evaluate-link-frontier-scenarios --output link-scenarios.json
glio-noncode link-frontier-schema --output link-schema.json
glio-noncode run-link-frontier-pipeline --run-id link-ci --output link-pipeline.json
glio-noncode build-link-frontier-release --run-id link-ci --output link-release.json
```

The detailed gate, schema, and operator references are maintained in
`docs/LINK_FRONTIER_EVIDENCE_GATE.md`, `docs/LINK_FRONTIER_SCHEMA.md`, and
`docs/LINK_FRONTIER_OPERATIONS.md`.

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

### Domain 11 C01-C04 foundation build

The four foundation capabilities are exercised as a closed public-aggregate
replay plane. `TypedHypothesisObjectBuilder`, `FactorGraphConstructor`,
`ContextConditionedPriorModel`, and `MeasurementLikelihoodModel` are bound to
four operation adapters and a 16-row fixture. Each operation has one supported
positive and three controls: missing evidence, contradiction or incomplete
lineage, and foreign-context or out-of-support input. Five HTTPS public source
receipts are carried through every record.

The implementation is organized into the following modules:

- public-data and adapters preserve source IDs, exact context, typed payloads,
  expected states, issue floors, and content addresses;
- contracts and schema close the required input/output fields for all four
  capability IDs;
- evaluation, metrics, replay, lineage, provenance, integrity, and validation
  matrices make state and issue behavior reproducible and inspectable;
- policy, reconciliation, review, operational, quality-gate, depth, claim
  boundary, and assurance surfaces keep controls visible and prevent foreign or
  contradictory rows from crossing the release boundary;
- runtime, bundle, release, artifact, observability, view, JSON, CSV, and
  Markdown surfaces provide a 19-stage release rehearsal with 16 artifacts.

The pinned commands are:

```powershell
glio-noncode causal-foundation-frontier-data-audit --output foundation-data.json
glio-noncode causal-foundation-frontier-evaluate --output foundation-evaluation.json
glio-noncode causal-foundation-frontier-policy --output foundation-policy.json
glio-noncode causal-foundation-frontier-review --output foundation-review.json
glio-noncode causal-foundation-frontier-quality-gate --output foundation-quality.json
glio-noncode causal-foundation-frontier-runtime --output foundation-runtime.json
glio-noncode causal-foundation-frontier-release --output foundation-release.json
glio-noncode causal-foundation-frontier-integrity --output foundation-integrity.json
glio-noncode export-causal-foundation-frontier-review-csv --output foundation-review.csv
```

The release state is ready only when the fixture audit, exact replay, contract
coverage, schema, metrics, graph receipts, reconciliation, review coverage,
depth audit, quality gate, artifact inventory, and claim boundary agree. Four
positive rows are retained for aggregate research review; ten control rows are
blocked or abstained. The outputs remain bounded proxies and are not calibrated
clinical probabilities, individual causal findings, diagnostic determinations,
prognoses, treatment selections, or patient-care instructions.

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

The C05-C08 public aggregate frontier now provides the deeper release plane for
these four primitives. It is pinned to a 16-row, 5-source fixture with one
positive and three controls per operation: independent-source minimums,
directional or negative-control conflict, replicate ambiguity, missing alternate
alleles, and foreign-context quarantine. Every row has a stable receipt, typed
payload, expected state floor, issue-code floor, adapter result, lineage edge,
provenance node, policy disposition, operational action, and review status.

The release rehearsal runs 27 ordered stages and produces 16 content-addressed
artifacts. The additional planes include schema and contract reports, exact
metrics, integrity checks, scenario and validation matrices, deterministic
replay, operational cells, explicit allowed and excluded uses, CSV/Markdown/JSON
exports, and a compact assurance statement. Four supported positive rows are
retained for bounded aggregate method review; incomplete rows remain in review,
while contradictory, ambiguous, and foreign-context controls cannot be promoted.

The C05-C08 command surface is:

```powershell
glio-noncode causal-beta-frontier-data-audit --output beta-data.json
glio-noncode causal-beta-frontier-evaluate --output beta-evaluation.json
glio-noncode causal-beta-frontier-quality-gate --output beta-quality.json
glio-noncode causal-beta-frontier-runtime --output beta-runtime.json
glio-noncode causal-beta-frontier-release --output beta-release.json
glio-noncode causal-beta-frontier-integrity --output beta-integrity.json
glio-noncode causal-beta-frontier-operational --output beta-operational.json
glio-noncode causal-beta-frontier-boundary --output beta-boundary.json
glio-noncode export-causal-beta-frontier-review-csv --output beta-review.csv
glio-noncode export-causal-beta-frontier-review-markdown --output beta-review.md
glio-noncode export-causal-beta-frontier-json --output beta-exports.json
```

The C05-C08 surface remains limited to public aggregate method validation,
reproducibility testing, research triage, and evidence review. It excludes
patient-level inference, diagnosis, treatment selection, individual risk
scoring, and clinical decision support.

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

### Domain 11 C09-C12 frontier depth build

The C09-C12 tranche closes the four external-alpha controls as one
content-addressed release surface. A fresh public aggregate fixture is pinned
to version `2026.08.d11-c09-c12.v1` with five HTTPS source receipts, sixteen
rows, four positive paths, twelve controls, four foreign-context controls, and
the boundary `public_aggregate_non_patient`. The fixture covers source
omission sensitivity, addressed/missing/unresolved confounders, dependent and
contradictory paths, measured-negative evidence, positive/negative conflict,
and exact-context quarantine.

Each row is replayed through the real alpha primitive, then normalized into a
typed result with expected state, observed state, issue codes, output envelope,
and content address. The release runtime has 31 ordered stages:

1. public data audit;
2. adapter registry;
3. fixture replay;
4. capability contracts;
5. schema closure;
6. operation metrics;
7. source-to-result lineage;
8. provenance graph;
9. address and graph integrity;
10. implementation-depth audit;
11. bounded policy;
12. row decisions;
13. expected/observed reconciliation;
14. review queue;
15. control-coverage inventory;
16. per-row decision traces;
17. faceted projections;
18. cross-plane diagnostics;
19. scenario matrix;
20. validation matrix;
21. quality gate;
22. release bundle;
23. release manifest;
24. artifact inventory;
25. deterministic replay;
26. operational action matrix;
27. allowed/excluded claim boundary;
28. stable review view;
29. canonical exports;
30. assurance statement;
31. executable runbook.

The C09-C12 command surface is:

```powershell
glio-noncode causal-alpha-frontier-data-audit --output alpha-data.json
glio-noncode causal-alpha-frontier-contracts --output alpha-contracts.json
glio-noncode causal-alpha-frontier-schema --output alpha-schema.json
glio-noncode causal-alpha-frontier-evaluate --output alpha-evaluation.json
glio-noncode causal-alpha-frontier-replay --output alpha-replay.json
glio-noncode causal-alpha-frontier-metrics --output alpha-metrics.json
glio-noncode causal-alpha-frontier-lineage --output alpha-lineage.json
glio-noncode causal-alpha-frontier-provenance --output alpha-provenance.json
glio-noncode causal-alpha-frontier-policy --output alpha-policy.json
glio-noncode causal-alpha-frontier-review --output alpha-review.json
glio-noncode causal-alpha-frontier-quality-gate --output alpha-quality.json
glio-noncode causal-alpha-frontier-runtime --output alpha-runtime.json
glio-noncode causal-alpha-frontier-release --output alpha-release.json
glio-noncode causal-alpha-frontier-artifacts --output alpha-artifacts.json
glio-noncode causal-alpha-frontier-depth-audit --output alpha-depth.json
glio-noncode causal-alpha-frontier-integrity --output alpha-integrity.json
glio-noncode causal-alpha-frontier-scenarios --output alpha-scenarios.json
glio-noncode causal-alpha-frontier-validation-matrix --output alpha-validation.json
glio-noncode causal-alpha-frontier-operational --output alpha-operational.json
glio-noncode causal-alpha-frontier-boundary --output alpha-boundary.json
glio-noncode causal-alpha-frontier-assurance --output alpha-assurance.json
glio-noncode causal-alpha-frontier-runbook --output alpha-runbook.json
glio-noncode export-causal-alpha-frontier-review-csv --output alpha-review.csv
glio-noncode export-causal-alpha-frontier-review-markdown --output alpha-review.md
glio-noncode export-causal-alpha-frontier-json --output alpha-exports.json
```

The operational matrix allows three exact-context descriptive rows, routes
nine partial/contradictory/measured-negative rows to review, and quarantines
four foreign-context rows. The release manifest and assurance layer exclude
causal identification, clinical diagnosis, treatment recommendation,
prognosis, and patient care. Negative evidence remains assay-bound, declared
dependence grouping remains a bounded proxy, and checklist completion does not
prove the absence of unmeasured confounding.

## Domain 11 causal frontier evidence

Domain 11 now verifies the four causal-evidence capabilities with a bounded,
public aggregate fixture. The fixture contains one positive and three control
records for each operation, five public source receipts, an exact context key,
and a declared non-patient boundary. The fixture is intentionally small enough
to replay in continuous integration while preserving the fields needed for a
reviewer to follow every transformation.

The verified operation surfaces are:

- `PosteriorDecompositionEngine` retains prior, likelihood, measurement,
  dependence penalty, raw posterior, normalized posterior, state, and top
  hypothesis identity. Zero mass is a review state and empty or out-of-bound
  components are invalid controls.
- `RegulatoryDriverHypothesisPosterior` retains driver identity, evidence IDs,
  support, prior, posterior, rank, and minimum-support review. Low support is
  not silently promoted into a supported driver.
- `SelectivePredictionAndAbstention` retains score, uncertainty, the
  uncertainty-aware threshold, abstention, and issue codes. Weak score and
  high uncertainty are separate observable controls.
- `CausalDossierPublisher` binds hypothesis IDs to evidence addresses and
  emits a content-addressed research manifest. It does not upgrade a manifest
  into a causal, diagnostic, prognostic, or treatment conclusion.

The surrounding evidence boundary adds contracts, schema fields, fixture
receipts, deterministic replay, a 33-scenario threshold matrix, source and
transform lineage, operation metrics, policy decisions, reconciliation,
observability events, JSON/CSV exports, a 12-check quality gate, a 10-stage
runtime, a release manifest, and an 18-check depth audit. Controls are run in
the same path as positive records. A release can therefore show that invalid,
empty, weak, uncertain, and mismatched inputs remain visible.

The public sources are used only as aggregate context and receipts:

| Source receipt | Use in this boundary |
| --- | --- |
| ENCODE | functional genomics source context |
| 4D Nucleome | topology and dependence context |
| NCBI GEO | public molecular observation context |
| PubMed | publication and evidence-address context |
| NIH Common Fund | research-use and provenance context |

The D11 command surface is deliberately split into audit, replay, evaluation,
and export steps so a reviewer can stop after any receipt:

```powershell
glio-noncode causal-frontier-data-audit --output causal-data-audit.json
glio-noncode causal-frontier-contracts --output causal-contracts.json
glio-noncode causal-frontier-schema --output causal-schema.json
glio-noncode causal-frontier-evaluate --output causal-evaluation.json
glio-noncode causal-frontier-replay --output causal-replay.json
glio-noncode causal-frontier-metrics --output causal-metrics.json
glio-noncode causal-frontier-lineage --output causal-lineage.json
glio-noncode causal-frontier-policy --output causal-policy.json
glio-noncode causal-frontier-quality-gate --output causal-quality.json
glio-noncode causal-frontier-runtime --output causal-runtime.json
glio-noncode causal-frontier-release --output causal-release.json
glio-noncode causal-frontier-depth-audit --output causal-depth.json
```

The D11 boundary supports aggregate evidence review, method development,
reproducibility testing, and research triage. It excludes patient care,
diagnostic determination, treatment selection, pathogenicity declaration, and
actionability. Thresholds, source IDs, context, issue codes, abstentions, and
release decisions remain part of the exported record.

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

The aggregate cohort benchmark plane adds a deterministic evaluation boundary
for declared source and target records. `cohort-benchmark` partitions rows by
group, source, context, stable hash, or collection time; audits duplicate IDs,
lineage reuse, optional source/context overlap, and temporal order; and then
evaluates only the selected held-out split for calibration and selective risk.
It reports Brier score, log loss, expected/maximum calibration error,
calibration slope/intercept, coverage-risk curves, abstention rate, and area
under the risk-coverage curve. A separate transport plane compares declared
domains for feature overlap, positive-rate shift, score shift, and Brier shift.
Every plane is addressed and states `accepted`, `review`, `blocked`, or
`abstained`; leakage errors block the suite and insufficient labels/scores
abstain. The implementation is descriptive and does not claim external
validation, clinical performance, or transportability.

```powershell
glio-noncode cohort-benchmark cohort-records.json --split-strategy temporal --source-domain source --target-domain target --output cohort-benchmark.json
glio-noncode cohort-benchmark-schema --output cohort-benchmark-schema.json
glio-noncode cohort-benchmark-capabilities --output cohort-benchmark-capabilities.json
```

See [docs/COHORT_BENCHMARKS.md](COHORT_BENCHMARKS.md) for the complete row,
configuration, CLI, API, reproducibility, and public-boundary contract.

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

The Domain 12 C01-C04 foundation frontier now verifies the four cohort
selection and control primitives over a separate public aggregate fixture:

- `CohortQueryBuilder` preserves exact context, variant kind, origin,
  chromosome, sample, callable criteria, and every exclusion reason;
- `LocalBackgroundMutationModel` reports callable bases, observed variants,
  descriptive rate, target-space expectation, uncertainty, and the explicit
  zero-observation limitation;
- `SequenceContextControlMatcher` selects bounded Hamming-distance controls;
- `ChromatinContextControlMatcher` selects controls by normalized RMS feature
  distance with complete-vector and feature-range requirements.

The fixture contains 16 pseudonymous aggregate records: one positive and three
controls for each operation. It cites five public aggregate sources and covers
supported, partial, absent, abstained, and foreign-context paths. The 39-stage
runtime joins strict adapters, contracts, schema, evaluation, metrics,
lineage, provenance, policy, reconciliation, review, quality, replay, bundle,
release, artifacts, diagnostics, scenarios, validation, operational matrix,
claim boundary, assurance, runbook, and query surfaces. No patient-level rows
are imported or published.

```powershell
glio-noncode cohort-foundation-frontier-data-audit --output cohort-foundation-data.json
glio-noncode cohort-foundation-frontier-contracts --output cohort-foundation-contracts.json
glio-noncode cohort-foundation-frontier-schema --output cohort-foundation-schema.json
glio-noncode cohort-foundation-frontier-evaluate --output cohort-foundation-evaluation.json
glio-noncode cohort-foundation-frontier-runtime --output cohort-foundation-runtime.json
glio-noncode cohort-foundation-frontier-release --output cohort-foundation-release.json
glio-noncode cohort-foundation-frontier-depth-audit --output cohort-foundation-depth.json
glio-noncode cohort-foundation-frontier-assurance --output cohort-foundation-assurance.json
glio-noncode cohort-foundation-frontier-sources --output cohort-foundation-sources.json
glio-noncode cohort-foundation-frontier-integrity --output cohort-foundation-integrity.json
glio-noncode cohort-foundation-frontier-control-coverage --output cohort-foundation-controls.json
glio-noncode cohort-foundation-frontier-traces --output cohort-foundation-traces.json
glio-noncode cohort-foundation-frontier-invariants --output cohort-foundation-invariants.json
glio-noncode cohort-foundation-frontier-thresholds --output cohort-foundation-thresholds.json
glio-noncode cohort-foundation-frontier-observability --output cohort-foundation-observability.json
glio-noncode cohort-foundation-frontier-accessibility --output cohort-foundation-accessibility.json
glio-noncode cohort-foundation-frontier-performance --output cohort-foundation-performance.json
glio-noncode cohort-foundation-frontier-schema-migrations --output cohort-foundation-migrations.json
glio-noncode cohort-foundation-frontier-failure-injections --output cohort-foundation-failures.json
glio-noncode cohort-foundation-frontier-recovery --output cohort-foundation-recovery.json
glio-noncode cohort-foundation-frontier-package --output cohort-foundation-package.json
glio-noncode cohort-foundation-frontier-claim-evidence --output cohort-foundation-claim-evidence.json
glio-noncode cohort-foundation-frontier-audit-log --output cohort-foundation-audit-log.json
glio-noncode cohort-foundation-frontier-review-sla --output cohort-foundation-review-sla.json
glio-noncode cohort-foundation-frontier-data-dictionary --output cohort-foundation-data-dictionary.json
glio-noncode cohort-foundation-frontier-compatibility --output cohort-foundation-compatibility.json
glio-noncode cohort-foundation-frontier-change-control --output cohort-foundation-change-control.json
glio-noncode cohort-foundation-frontier-retention --output cohort-foundation-retention.json
glio-noncode cohort-foundation-frontier-reproducibility --output cohort-foundation-reproducibility.json
glio-noncode cohort-foundation-frontier-dataset-manifest --output cohort-foundation-dataset.json
glio-noncode cohort-foundation-frontier-transcript --output cohort-foundation-transcript.txt
glio-noncode cohort-foundation-frontier-summary --output cohort-foundation-summary.json
glio-noncode export-cohort-foundation-frontier-review-csv --output cohort-foundation-review.csv
glio-noncode export-cohort-foundation-frontier-review-markdown --output cohort-foundation-review.md
```

The foundation frontier remains descriptive research infrastructure. It does
not produce a significance test, causal null proof, clinical risk estimate,
diagnosis, prognosis, treatment recommendation, or transportability claim.

The query boundary is:

```powershell
glio-noncode cohort-query cohort.json --output cohort-selection.json
```

The Domain 12 convergence frontier now closes the four C13-C16 operations with
a deterministic public aggregate fixture. The fixture contains 16 records: one
positive record and three controls for subgroup fairness, transportability,
federated summaries, and cohort discovery. Five public source receipts identify
the evidence boundary without importing patient-level rows. Positive records
exercise the supported or published paths; controls deliberately exercise a
parity gap, feature gap, distribution shift, privacy-floor violation, empty
input, context mismatch, and invalid payload controls.

Every record receives an execution receipt and seven record-level checks, while
eight global checks validate fixture shape, operation coverage, issue vocabulary,
and deterministic addresses. The resulting 120-check evaluation is joined to
36 lineage edges, 11 metrics, 12 blocking quality checks, a 10-stage runtime
rehearsal, and a four-check release manifest. Controls stay in the review view;
they are never converted into an absent-effect conclusion.

The four operation boundaries are:

- subgroup fairness retains each group denominator, positive count, rate, gap,
  and review group;
- transportability retains source and target feature sets, overlap, shift, and
  feature-specific review IDs;
- federated summaries retain site counts, means, spread, and privacy-floor
  review without merging raw site rows;
- cohort discovery publishes only an aggregate feature and analysis manifest
  with exact context and content addresses.

Additional depth surfaces make the boundary inspectable under change. The
scenario matrix has 33 rows, threshold probing covers 972 probes, the artifact
inventory has seven nodes, the invariant runner has ten checks, and
observability emits 26 structured events. Public aggregate exports include
canonical JSON, indented JSON, release manifests, and a review CSV with all 16
records.

The Domain 12 frontier commands are:

```powershell
glio-noncode cohort-frontier-data-audit --output cohort-data-audit.json
glio-noncode cohort-frontier-contracts --output cohort-contracts.json
glio-noncode cohort-frontier-schema --output cohort-schema.json
glio-noncode cohort-frontier-evaluate --output cohort-evaluation.json
glio-noncode cohort-frontier-replay --output cohort-replay.json
glio-noncode cohort-frontier-metrics --output cohort-metrics.json
glio-noncode cohort-frontier-lineage --output cohort-lineage.json
glio-noncode cohort-frontier-policy --output cohort-policy.json
glio-noncode cohort-frontier-quality-gate --output cohort-quality.json
glio-noncode cohort-frontier-runtime --output cohort-runtime.json
glio-noncode cohort-frontier-bundle --output cohort-bundle.json
glio-noncode cohort-frontier-release --output cohort-release.json
glio-noncode export-cohort-frontier-review-csv --output cohort-review.csv
glio-noncode cohort-frontier-depth-audit --output cohort-depth.json
```

This frontier is research infrastructure for aggregate cohort review, method
development, reproducibility testing, and triage. It excludes patient care,
diagnosis, prognosis, treatment selection, individual risk, and clinical cohort
claims. A published discovery result is a content-addressed manifest, not a
validated cohort conclusion.

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

The C01-C04 validation-planning frontier adds a public aggregate release
boundary for four core planning capabilities. It contains 16 records, with one
positive and three controls for each of evidence-gap analysis, assay eligibility,
MPRA planning, and STARR-seq planning. Five public source receipts identify the
planning evidence boundary; no patient-level rows or restricted samples are
included.

The positive C01 record retains missing measurement and high uncertainty as
ranked gaps. The C02 positive route retains matching model, insert bounds,
controls, readouts, alternatives, and sensitivity. The C03 and C04 positive
packages retain paired reference and alternate constructs. Controls cover context
mismatch, missing typed inputs, model mismatch, missing controls and readouts,
empty inventory, insert bounds, construct budget, and empty target lists.

The frontier has 120 evaluation checks, 36 lineage edges, 13 metrics, 12
quality checks, 10 runtime stages, 31 scenario rows, 972 threshold probes, 26
observability events, seven artifact nodes, and 20 depth checks. A ready plan is
a research review artifact. It is not assay success, efficacy, safety, causal
validation, or a clinical decision.

The validation-planning frontier commands are:

```powershell
glio-noncode validation-frontier-data-audit --output validation-data.json
glio-noncode validation-frontier-contracts --output validation-contracts.json
glio-noncode validation-frontier-schema --output validation-schema.json
glio-noncode validation-frontier-evaluate --output validation-evaluation.json
glio-noncode validation-frontier-replay --output validation-replay.json
glio-noncode validation-frontier-metrics --output validation-metrics.json
glio-noncode validation-frontier-lineage --output validation-lineage.json
glio-noncode validation-frontier-policy --output validation-policy.json
glio-noncode validation-frontier-quality-gate --output validation-quality.json
glio-noncode validation-frontier-runtime --output validation-runtime.json
glio-noncode validation-frontier-observability --output validation-observability.json
glio-noncode validation-frontier-artifacts --output validation-artifacts.json
glio-noncode validation-frontier-bundle --output validation-bundle.json
glio-noncode validation-frontier-release --output validation-release.json
glio-noncode export-validation-frontier-review-csv --output validation-review.csv
glio-noncode validation-frontier-review-queue --output validation-queue.json
glio-noncode validation-frontier-depth-audit --output validation-depth.json
```

These surfaces preserve blockers, abstentions, controls, limitations, source
receipts, allowed uses, and excluded uses. They do not replace assay design
review, synthesis review, institutional approval, or experimental validation.

### Domain 13 C05-C12 validation-beta frontier

The C05-C12 validation-beta tranche now promotes the perturbation and research
planning primitives into a closed public aggregate evidence plane. It uses one
positive row and three controls for each of eight operation families, for 32
records over seven public source receipts. The exact context is
`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment`; foreign territory and
post-treatment rows are retained as out-of-domain controls.

The eight operation families are:

- CRISPRi and CRISPRa guide design, with independent mode receipts and explicit
  candidate-budget, context, and no-target boundaries;
- base-editing design, retaining single-base chemistry and unsupported-edit
  blockers;
- prime-editing design, retaining PBS, RTT, edit-length, and flank controls;
- allele-specific reporter planning, preserving paired reference/alternate
  constructs and construct budgets;
- model-system eligibility, with exact context, cell-state, model, and evidence
  floors;
- guide/oligo adaptation, retaining valid sequences and quarantining malformed
  rows with source hashes;
- deterministic controls and biological/technical replicate randomization; and
- transparent power/replication estimation with effect, variance, shortfall,
  context, and normal-approximation assumptions visible.

The frontier is backed by typed contracts and schemas, public source closure,
content-addressed records, 32-row fixture evaluation, 32-row reconciliation,
source-to-result lineage, state-aware publish/review/quarantine policy, a
24-item review queue, deterministic replay, 12 quality checks, 20 depth checks,
25 runtime stages, 40 threshold probes, a 32-cell six-plane validation matrix,
an eight-operation reproducible handoff, release and bundle manifests,
CSV/Markdown/JSON views, and negative-boundary probes. Positive rows are
publishable only as bounded research
planning receipts. The surface does not claim guide efficacy, off-target safety,
assay success, causal effect, clinical utility, institutional approval, or
automatic execution.

The C05-C12 command surface is:

```powershell
glio-noncode validation-beta-frontier-fixture --output validation-beta-fixture.json
glio-noncode validation-beta-frontier-data --output validation-beta-data.json
glio-noncode validation-beta-frontier-contracts --output validation-beta-contracts.json
glio-noncode validation-beta-frontier-schema --output validation-beta-schema.json
glio-noncode validation-beta-frontier-evaluate --output validation-beta-evaluation.json
glio-noncode validation-beta-frontier-quality --output validation-beta-quality.json
glio-noncode validation-beta-frontier-replay --output validation-beta-replay.json
glio-noncode validation-beta-frontier-thresholds --output validation-beta-thresholds.json
glio-noncode validation-beta-frontier-validation-matrix --output validation-beta-matrix.json
glio-noncode validation-beta-frontier-handoff --output validation-beta-handoff.json
glio-noncode validation-beta-frontier-report --format markdown --output validation-beta-review.md
glio-noncode run-validation-beta-frontier-pipeline --output validation-beta-runtime.json
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

The C01-C04 evidence-lifecycle frontier adds a public aggregate verification
boundary for versioned graph construction, citation resolution, claim-edge
validation, and contradiction/disagreement tracking. It contains 16 records,
with one positive and three controls for each operation. Five HTTPS source
receipts identify the aggregate boundary; no patient-level rows are included.

The C01 citation path retains one valid row and one quarantined row. Controls
cover malformed JSON, duplicate citation IDs, and an empty table. The C02 graph
path retains a superseded claim in history while exposing the active claim.
Controls cover missing lineage, graph-context mismatch, and duplicate claim IDs.
The C03 edge path verifies supported, missing-source, context-mismatch, and
absent-edge states. The C04 disagreement path retains positive and negative
values separately while controls cover clear, incomplete, and out-of-domain
states.

The frontier has 120 evaluation checks, 36 lineage edges, 13 metrics, 12
quality checks, 10 runtime stages, 31 scenario rows, 972 threshold probes, 26
observability events, seven artifact nodes, 20 depth checks, and a 16-row
review queue with four ready rows and twelve held controls. A ready lifecycle
record is a research review artifact; it is not experimental success or a
clinical conclusion.

The evidence-lifecycle frontier commands are:

```powershell
glio-noncode evidence-lifecycle-data-audit --output lifecycle-data.json
glio-noncode evidence-lifecycle-contracts --output lifecycle-contracts.json
glio-noncode evidence-lifecycle-schema --output lifecycle-schema.json
glio-noncode evidence-lifecycle-evaluate --output lifecycle-evaluation.json
glio-noncode evidence-lifecycle-replay --output lifecycle-replay.json
glio-noncode evidence-lifecycle-metrics --output lifecycle-metrics.json
glio-noncode evidence-lifecycle-lineage --output lifecycle-lineage.json
glio-noncode evidence-lifecycle-policy --output lifecycle-policy.json
glio-noncode evidence-lifecycle-quality-gate --output lifecycle-quality.json
glio-noncode evidence-lifecycle-runtime --output lifecycle-runtime.json
glio-noncode evidence-lifecycle-observability --output lifecycle-observability.json
glio-noncode evidence-lifecycle-artifacts --output lifecycle-artifacts.json
glio-noncode evidence-lifecycle-bundle --output lifecycle-bundle.json
glio-noncode evidence-lifecycle-release --output lifecycle-release.json
glio-noncode evidence-lifecycle-review-queue --output lifecycle-queue.json
glio-noncode export-evidence-lifecycle-review-csv --output lifecycle-review.csv
glio-noncode evidence-lifecycle-depth-audit --output lifecycle-depth.json
```

### D14 evidence lifecycle portable offline handoff

The D14 evidence lifecycle runtime now has a closed offline handoff with 21
exact-byte artifacts. The handoff includes fixture and source receipts,
operation contracts, schema, evaluation, metrics, policy, lineage,
reconciliation, quality, release, replay, review, queue, scenario, inventory,
observability, CSV, and normalized runtime projections. It conserves 16
records, 120 evaluation checks, 26 events, five HTTPS receipts, four operation
families, and the public aggregate boundary.

```powershell
glio-noncode evidence-lifecycle-offline-bundle --destination lifecycle-bundle --output lifecycle-bundle.json
glio-noncode evidence-lifecycle-offline-bundle-verify lifecycle-bundle --output lifecycle-bundle-verification.json
glio-noncode evidence-lifecycle-offline-bundle-query lifecycle-bundle --resource records --operation graph_construction
glio-noncode evidence-lifecycle-offline-bundle-schema --output lifecycle-bundle-schema.json
glio-noncode evidence-lifecycle-offline-bundle-validate lifecycle-bundle/bundle.json --output lifecycle-bundle-validation.json
glio-noncode evidence-lifecycle-offline-bundle-audit lifecycle-bundle --output lifecycle-bundle-audit.json
glio-noncode evidence-lifecycle-offline-bundle-observability lifecycle-bundle --output lifecycle-bundle-observability.json
glio-noncode evidence-lifecycle-offline-bundle-runtime --output lifecycle-bundle-runtime.json
glio-noncode evidence-lifecycle-offline-bundle-indexes lifecycle-bundle --output lifecycle-bundle-indexes.json
glio-noncode evidence-lifecycle-offline-bundle-boundary lifecycle-bundle --output lifecycle-bundle-boundary.json
glio-noncode evidence-lifecycle-offline-bundle-reconciliation lifecycle-bundle --output lifecycle-bundle-reconciliation.json
glio-noncode evidence-lifecycle-offline-bundle-summary lifecycle-bundle --format markdown --output lifecycle-bundle-summary.md
```

The manifest and every artifact are independently inspectable after checkout.
Verification rejects altered bytes, unsafe paths, missing artifacts, address
drift, non-canonical JSON, private subject keys, forbidden attribution keys,
and denominator drift. The bundle is research-operational evidence only; it
does not make a clinical, diagnostic, prognostic, treatment, or individual
risk determination.

### D14 closure projections and release packet

The D14 closure layer independently closes the portable handoff across ten
address-only indexes, 34 reconciliation checks, operation/state/queue summary
counters, eight certification domains with 48 evidence-linked checks, 62
timestamp-free closure events, 18 metrics, a connected 356-node graph, ten
negative controls, and a twelve-stage runtime. The closure boundary retains
the public aggregate scope and excludes direct identity, attribution, model,
and language fields from public projection rows.

```powershell
glio-noncode evidence-lifecycle-offline-bundle-closure-query lifecycle-bundle --resource records --operation graph_construction
glio-noncode evidence-lifecycle-offline-bundle-closure-boundary lifecycle-bundle --output closure-boundary.json
glio-noncode evidence-lifecycle-offline-bundle-closure-indexes lifecycle-bundle --output closure-indexes.json
glio-noncode evidence-lifecycle-offline-bundle-closure-reconciliation lifecycle-bundle --output closure-reconciliation.json
glio-noncode evidence-lifecycle-offline-bundle-closure-summary lifecycle-bundle --format markdown --output closure-summary.md
glio-noncode evidence-lifecycle-offline-bundle-closure-certification lifecycle-bundle --output closure-certification.json
glio-noncode evidence-lifecycle-offline-bundle-closure-observability lifecycle-bundle --output closure-observability.json
glio-noncode evidence-lifecycle-offline-bundle-closure-graph lifecycle-bundle --output closure-graph.json
glio-noncode evidence-lifecycle-offline-bundle-closure-failures lifecycle-bundle --output closure-failures.json
glio-noncode evidence-lifecycle-offline-bundle-closure-runtime --output closure-runtime.json
glio-noncode evidence-lifecycle-offline-bundle-closure-export --destination closure-export --output closure-export.json
glio-noncode evidence-lifecycle-offline-bundle-closure-export-verify closure-export --output closure-export-verification.json
```

Closure exports are canonical UTF-8 exact-byte files. Verification reports
missing, changed, and unexpected paths. Read-only HTTP projections are
available at `/v1/evidence-lifecycle/bundle/closure-*`; export writing is an
explicit CLI filesystem operation. See
[`EVIDENCE_LIFECYCLE_CLOSURE_OPERATIONS.md`](EVIDENCE_LIFECYCLE_CLOSURE_OPERATIONS.md)
for the contracts and runtime handoff.

These lifecycle surfaces preserve source versions, row hashes, raw records,
supersession, missing citations, context mismatch, disagreement state,
abstention, review policy, release boundaries, and replay addresses. They do
not replace source reconciliation, adjudication, experimental validation,
institutional review, or clinical governance.

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

### Domain 14 C05-C12 lifecycle beta frontier

The C05-C12 tranche adds a separate public aggregate package for the eight
scientific-beta and external-alpha review surfaces. It contains 32 records:
one positive and three controls for each operation, nine HTTPS source receipts,
and the exact context GRCh38|glioma|adult|stem_like|core|untreated.

The operation surfaces are:

- C05 evidence-tier adjudication, retaining directional conflict and
  unclassified-tier partialness;
- C06 provenance lineage, retaining parent and supersession edges;
- C07 uncertainty ledger, retaining dimension-labeled drivers without
  presenting a calibrated probability;
- C08 reviewer routing, retaining role, priority, contradiction, and context
  blockers;
- C09 blinded adjudication, retaining masked receipts, missing decisions, and
  split verdicts;
- C10 comment/change log, retaining append-only comments and before/after
  changes;
- C11 research-only release decisions, retaining gates, roles, rejection, and
  review-required states;
- C12 evidence deltas, retaining added, changed, and context-shifted records.

The accepted runtime has 25 ordered stages, 166 evaluation checks, 40
threshold probes, a 32-cell validation matrix across six evidence planes,
32 scenario cells, deterministic replay, a 73-edge source/execution lineage
graph, an eight-check quality gate, review queue and SLA projections, a
research-only release bundle, and a depth audit. The runtime is accepted only
when the positive rows reconcile, controls remain visible, all content
addresses close, and policy boundaries remain explicit.

The beta-frontier commands are:

~~~powershell
glio-noncode lifecycle-beta-frontier-data-audit --output lifecycle-beta-data.json
glio-noncode lifecycle-beta-frontier-evaluate --output lifecycle-beta-evaluation.json
glio-noncode lifecycle-beta-frontier-pipeline --output lifecycle-beta-runtime.json
glio-noncode lifecycle-beta-frontier-thresholds --output lifecycle-beta-thresholds.json
glio-noncode lifecycle-beta-frontier-validation-matrix --output lifecycle-beta-matrix.json
glio-noncode lifecycle-beta-frontier-handoff --output lifecycle-beta-handoff.json
~~~

These commands are aggregate research infrastructure. They do not produce
patient-level inference, diagnosis, treatment selection, causal authorization,
or automatic dossier publication.

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

The replay-gated review workspace is the provenance-first companion to that
navigation model. It renders typed hypothesis edges, payload-free evidence
claims, explicit alternatives, source-centric provenance, explainable human
review queue items, and per-dimension deltas between two verified runs. Support,
uncertainty, context fit, evidence score/confidence, categorical state changes,
and presence changes remain separate dimensions; there is no aggregate review
score. Current and baseline runs must both pass replay verification, and raw
evidence payloads plus producer metadata are withheld from the public view.

```powershell
glio-noncode review-workspace RUN_ID --data-root .glio --output review-workspace.json
glio-noncode review-workspace RUN_ID --baseline-run-id BASELINE_RUN_ID --data-root .glio --output review-deltas.json
glio-noncode review-workspace-schema --output review-workspace-schema.json
glio-noncode review-workspace-capabilities --output review-workspace-capabilities.json
glio-noncode review-workspace-export RUN_ID --data-root .glio --format markdown --output review-workspace.md
glio-noncode review-workspace-release RUN_ID --data-root .glio --output review-release
glio-noncode review-workspace-release-verify review-release --output verification.json
glio-noncode review-workspace-index RUN_ID --data-root .glio --output review-index.json
glio-noncode review-workspace-query RUN_ID --collection evidence --state contradictory --data-root .glio --output review-query.json
glio-noncode review-workspace-release-query review-release --collection evidence --output release-query.json
glio-noncode review-workspace-plan RUN_ID --data-root .glio --output review-plan.json
glio-noncode review-workspace-plan-query RUN_ID --lane provenance --data-root .glio --output plan-query.json
glio-noncode review-workspace-release-plan review-release --output release-plan.json
glio-noncode review-workspace-plan-execution RUN_ID --data-root .glio --output execution.json
glio-noncode review-workspace-plan-execution-query RUN_ID --view events --kind start --data-root .glio --output execution-events.json
glio-noncode review-workspace-plan-execution-query RUN_ID --view operations --data-root .glio --output execution-operations.json
glio-noncode review-workspace-plan-execution-query RUN_ID --view operations --attention-kind blocked --limit 25 --data-root .glio --output blocked-operations.json
glio-noncode review-workspace-plan-execution-query RUN_ID --view transitions --kind complete --disposition requires_checks --data-root .glio --output execution-transitions.json
glio-noncode review-workspace-plan-execution-simulate RUN_ID --data-root .glio --proposals proposals.json --include-report --output execution-simulation.json
glio-noncode review-workspace-plan-execution-batch RUN_ID --data-root .glio --proposals proposals.json --include-simulation --output execution-batch.json
glio-noncode review-workspace-plan-execution-audit RUN_ID --data-root .glio --include-report --output execution-audit.json
glio-noncode review-workspace-plan-event RUN_ID --action-id ACTION_ID --kind start --event-id EVENT_ID --occurred-at 2026-09-01T12:00:00Z --data-root .glio --output execution.json
glio-noncode review-workspace-plan-execution-release RUN_ID --data-root .glio --output execution-release
glio-noncode review-workspace-plan-execution-release-verify execution-release --output execution-release-verification.json
glio-noncode review-workspace-plan-execution-release-query execution-release --status open --output execution-release-query.json
glio-noncode review-workspace-plan-execution-release-query execution-release --view events --kind start --output execution-release-events.json
glio-noncode review-workspace-plan-execution-release-query execution-release --view operations --output execution-release-operations.json
glio-noncode review-workspace-plan-execution-release-query execution-release --view transitions --executable true --output execution-release-transitions.json
glio-noncode review-workspace-plan-execution-release-diff execution-release-a execution-release-b --output execution-release-diff.json
glio-noncode review-workspace-plan-execution-metrics-diff-schema --output execution-metrics-diff-schema.json
glio-noncode review-workspace-plan-execution-operations-schema --output execution-operations-schema.json
glio-noncode review-workspace-plan-execution-operations-capabilities --output execution-operations-capabilities.json
glio-noncode review-workspace-plan-execution-operations-diff-schema --output execution-operations-diff-schema.json
glio-noncode review-workspace-plan-execution-transitions-schema --output execution-transitions-schema.json
glio-noncode review-workspace-plan-execution-transitions-capabilities --output execution-transitions-capabilities.json
glio-noncode review-workspace-plan-execution-transitions-diff-schema --output execution-transitions-diff-schema.json
glio-noncode review-workspace-plan-execution-transitions-diff-capabilities --output execution-transitions-diff-capabilities.json
glio-noncode review-workspace-plan-execution-simulation-schema --output execution-simulation-schema.json
glio-noncode review-workspace-plan-execution-simulation-capabilities --output execution-simulation-capabilities.json
glio-noncode review-workspace-plan-execution-batch-schema --output execution-batch-schema.json
glio-noncode review-workspace-plan-execution-batch-capabilities --output execution-batch-capabilities.json
glio-noncode review-workspace-plan-execution-audit-schema --output execution-audit-schema.json
glio-noncode review-workspace-plan-execution-audit-capabilities --output execution-audit-capabilities.json
glio-noncode review-workspace-release-diff release-a release-b --output release-diff.json
```

See [the review workspace contract](REVIEW_WORKSPACE.md).

The review-workspace triage-plan layer expands the explainable queue into
ordered descriptive work. It emits intake, context, provenance, alternative,
and disposition-preparation actions, keeps cross-queue evidence dependencies
explicit, and verifies queue closure, dependency closure, topological order,
lane closure, bounds, and the public boundary. Plan queries return complete
facets over bounded action pages, and plan exports are deterministic JSON,
Markdown, and CSV. The plan remains an operational checklist: it never stores
a reviewer decision, raw evidence payload, private identifier, or attribution
field. Live and verified offline release inputs use the same synthesis logic.

The execution layer makes the triage plan operational without mutating a
dossier. Its hash-chained append-only ledger accepts explicit start, complete,
block, skip, and reopen transitions; completion requires completed plan
dependencies and every declared public check identifier. Replay exposes
readiness, dependency waits, next actions, blocked actions, event history,
exact-byte manifest checks, and deterministic action/event/check exports. The
HTTP execution surface is read-only; CLI event appends are the only write path.

The execution simulator provides a second read-only control point before an
append. It replays up to 500 proposed transitions in sequence, automatically
links predecessors, evaluates state, dependency, required-check, reason, and
timestamp gates, and returns a projected execution, metrics, operations, and
transition frontier without writing the ledger. The first invalid proposal
stops the sequence and the remaining proposals are explicitly marked
`not_evaluated`; JSON, Markdown, and CSV exports plus CLI and HTTP surfaces are
available for the ephemeral result.

The batch execution surface turns an accepted simulation into an explicit
append. It captures a content-addressed base, supports event-count and
predecessor guards for optimistic concurrency, validates the full sequence
before writing, and refreshes the ledger manifest once. Simulation rejection,
stale-base conflict, duplicate event ID, and successful commit are all returned
as structured receipts. The CLI is the explicit filesystem write path and the
HTTP batch endpoint is the corresponding authenticated write surface.

The execution-release layer packages the replay report, event stream, metrics,
attention operations, transition preflight, and deterministic JSON/Markdown/CSV
projections into twenty exact-byte
artifacts, including the source plan, dependency graph, required-check
declarations, plan-level exports, action timing, lane throughput, dependency
wait, check-coverage, and critical-path metrics. Its independent verifier
checks safe paths, manifest addresses, nested plan/report/action/check
addresses, event-stream replay, metrics reconciliation, required artifact
closure, transition-frontier reconciliation, and the public boundary before
offline loading. Verified releases support bounded action, metrics, operations,
and transition-frontier views plus deterministic
event/action/check and source-plan diffs without a live run store. Release
diffs also carry deterministic operations deltas for queue movement, attention
class changes, and recommendation changes. The transition diff additionally
tracks appendable-option movement, precondition changes, per-action
recommendations, and right-minus-left frontier counts. CI runs this
execution/release surface explicitly, including operations, operations-diff,
transition-frontier, and transition-diff schema and capability commands, on
every push and pull request.

The C01–C04 workspace frontier adds a public aggregate verification package for
these four surfaces. The fixture contains 16 records across five HTTPS source
receipts: one positive and three controls per operation. Evaluation executes
the existing case, cohort, variant, and track primitives and records 120
checks. Controls cover context mismatch, malformed case input, duplicate
variant identity, callability exclusion, absent variants, malformed interval
rows, and empty track input.

The frontier package extends the read models with a 14-check quality gate, 21
depth checks, 36 lineage edges, 13 metrics, eight ordered runtime stages, 24
observability events, 972 bounded threshold probes, seven release artifacts,
33 scenarios, deterministic replay, adapter receipts, a release manifest, and
a 16-row review queue. Three supported positive rows are ready for research
navigation; 13 partial, absent, abstained, invalid, or out-of-domain rows stay
held for review. Accessibility labels, keyboard order, focus boundary, and
reading order remain in the public payload.

The verification commands are:

```powershell
glio-noncode workspace-frontier-evaluate --output workspace-frontier-evaluation.json
glio-noncode workspace-frontier-quality-gate --output workspace-frontier-quality.json
glio-noncode workspace-frontier-runtime --output workspace-frontier-runtime.json
glio-noncode workspace-frontier-review-queue --output workspace-frontier-queue.json
glio-noncode export-workspace-frontier-review-csv --output workspace-frontier-review.csv
```

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

The C05-C08 beta frontier package now verifies these projections through a
fresh public aggregate fixture. It contains 16 rows across five HTTPS receipts:
four positive paths and twelve controls. The evaluator records 103 checks and
keeps foreign context, invalid focus, missing mediator kinds, contradiction,
foreign posterior components, unreconciled residuals, missing support, empty
tables, and pagination behavior as explicit states.

The beta release package adds four operation contracts, four schemas, 32
scenario cases, 42 threshold probes, a 21-check depth audit, 20 invariants,
36 lineage edges, 13 descriptive metrics, deterministic replay, eight runtime
stages, structured observability, seven release artifacts, a quality gate,
review queue, release manifest, and stable CSV export. Three positive surfaces
are ready under research policy; partial, absent, abstained, contradictory,
invalid, and out-of-domain surfaces remain visible for review.

The beta verification commands are:

```powershell
glio-noncode beta-frontier-evaluate --output beta-frontier-evaluation.json
glio-noncode beta-frontier-quality-gate --output beta-frontier-quality.json
glio-noncode beta-frontier-runtime --output beta-frontier-runtime.json
glio-noncode beta-frontier-review-queue --output beta-frontier-queue.json
glio-noncode export-beta-frontier-review-csv --output beta-frontier-review.csv
```

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

The C09-C12 collaboration frontier now promotes these four bounded surfaces
from partial to verified through a separate public aggregate package. The
fixture contains 16 records across five HTTPS receipts: four positive paths and
twelve controls. The evaluator emits 48 row checks, three for every record,
and retains foreign context, malformed cards, unknown dependencies, invalid
launch runtime, unbounded resources, invalid snapshot signatures, expired
snapshots, foreign snapshots, inactive members, and unknown members.

The package is implemented module-by-module with contracts, field schema,
operation adapters, projection assertions, metrics, lineage, reconciliation,
policy, quality gate, deterministic replay, runtime rehearsal, structured
observability, accessibility, aggregate boundary checks, invariants, scenario
matrix, threshold probes, validation matrix, runbook, sanitized review view,
prioritized review queue, release manifest, address-only bundle, artifact
inventory, canonical JSON, and CSV exports. The end-to-end pipeline exercises
all of these surfaces and returns 16 named evidence addresses.

The C09-C12 verification commands are:

```powershell
glio-noncode gamma-frontier-data-audit --output gamma-data.json
glio-noncode gamma-frontier-contracts --output gamma-contracts.json
glio-noncode gamma-frontier-schema --output gamma-schema.json
glio-noncode gamma-frontier-evaluate --output gamma-evaluation.json
glio-noncode gamma-frontier-replay --output gamma-replay.json
glio-noncode gamma-frontier-metrics --output gamma-metrics.json
glio-noncode gamma-frontier-lineage --output gamma-lineage.json
glio-noncode gamma-frontier-policy --output gamma-policy.json
glio-noncode gamma-frontier-quality-gate --output gamma-quality.json
glio-noncode gamma-frontier-runtime --output gamma-runtime.json
glio-noncode gamma-frontier-observability --output gamma-observability.json
glio-noncode gamma-frontier-artifacts --output gamma-artifacts.json
glio-noncode gamma-frontier-bundle --output gamma-bundle.json
glio-noncode gamma-frontier-release --output gamma-release.json
glio-noncode gamma-frontier-review-queue --output gamma-queue.json
glio-noncode gamma-frontier-accessibility --output gamma-accessibility.json
glio-noncode gamma-frontier-compliance --output gamma-boundary.json
glio-noncode gamma-frontier-invariants --output gamma-invariants.json
glio-noncode gamma-frontier-adapters --output gamma-adapters.json
glio-noncode gamma-frontier-scenarios --output gamma-scenarios.json
glio-noncode gamma-frontier-thresholds --output gamma-thresholds.json
glio-noncode gamma-frontier-validation --output gamma-validation.json
glio-noncode gamma-frontier-runbook --output gamma-runbook.json
glio-noncode gamma-frontier-pipeline --output gamma-pipeline.json
glio-noncode export-gamma-frontier-review-csv --output gamma-review.csv
```

The package is research-use infrastructure. Board state is not experiment
execution or approval; launch plans do not execute code; HMAC integrity is not
identity or scientific validation; access policy does not replace institutional
controls. Secrets remain outside compact exports.

### Module-fabric offline bundle boundary

The repository-wide module-fabric runtime now has a materialized offline
handoff in addition to its in-memory release manifest. `module-fabric-bundle`
executes the 16-domain, 256-capability integration runtime and writes a closed
21-artifact public directory containing fixture, evaluation, metrics, depth,
lineage, replay, quality, release, runtime, compliance, catalog, schema,
dictionary, source, summary, trace, review, check, and Markdown projections.

The root manifest records exact UTF-8 byte counts, line counts, artifact
addresses, check addresses, runtime identity, and the bundle address. The
independent verifier reopens the directory without the producing runtime and
rejects malformed JSON, non-UTF-8 bytes, unsafe paths, symlinks, duplicate or
unexpected files, missing artifacts, address drift, schema mismatch, and
direct-identifier or attribution/language metadata. Blocked bundles retain
their diagnostics for review instead of being silently discarded.

```powershell
glio-noncode module-fabric-bundle --destination module-fabric-bundle
glio-noncode module-fabric-bundle-verify module-fabric-bundle
glio-noncode module-fabric-bundle-query module-fabric-bundle --resource records --domain-id D01
glio-noncode module-fabric-bundle-diff module-fabric-bundle-a module-fabric-bundle-b
glio-noncode module-fabric-bundle-observability module-fabric-bundle --format metrics-csv
glio-noncode module-fabric-bundle-schema
glio-noncode module-fabric-bundle-runtime
glio-noncode module-fabric-bundle-audit module-fabric-bundle
```

The bundle is a public aggregate module-integration receipt. Its independent
audit reconciles the 32 fixture records, 394 evaluation checks, 24 runtime
stages, 478 lineage nodes, 521 lineage edges, 20 quality checks, 12 compliance
checks, 16 schema domains, five HTTPS source receipts, and all CSV/Markdown
projections. The filesystem verifier runs this semantic audit after exact-byte
verification. It does not publish subject-level records, infer biological
truth, or convert reference resolution into a clinical or deployment decision.

### Repository public-surface audit

`public-surface-audit` is the repository-wide boundary check for the projections
that can be consumed by local service clients or offline handoff tooling. It
audits 110 named surfaces: service status, capabilities, program, operational,
D01-D16 program-release, and service-release projections, both service
closures, the service schema and snapshot, and the capability-certification,
module-fabric, validation-design, evidence-lifecycle, workbench-release, and
durable service-release handoff projections. Each surface
receives a deterministic content address and violation-path list.

The D15 workbench-release closure extends that boundary with 56 artifact
checks, 44 denominator reconciliations, ten indexes, 60 certification checks,
184 observability events, a 404-node connected graph, twelve negative controls,
and a fourteen-stage replayable runtime. Its exact-byte export, bounded query,
schema audit, and release summaries remain aggregate-only and preserve the
same public-key policy.

Runtime values are rejected when they contain attribution, language, or direct
private-key fields. Input schema declarations may retain subject/sample field
names because they describe accepted request shape; they are not data values.
The audit is exposed by both `GET /v1/public-surface/audit` and:

```powershell
glio-noncode public-surface-audit --output public-surface-audit.json
```

The command exits non-zero when the closed 110-surface inventory or any
projection boundary check fails, making it suitable for release automation.

### Cross-run portfolio release boundary

The persisted-run plane now has a repository-wide handoff contract in addition
to its single-dossier, batch, and workspace releases. `portfolio-release`
selects a bounded set of replay-verified runs and namespaces each member's
dossier release, workspace release, run record, event evidence, and member
status under a stable relative path. A member that is valid but awaiting human
review remains in the package as `blocked` with its failed check identifiers;
the package is accepted only when every selected member is independently ready.

The package emits a public portfolio projection, member JSON, CSV summary,
Markdown report, release checks, and exact-byte artifact manifests. Its
filesystem verifier checks UTF-8 decoding, byte and line counts, content
addresses, safe relative paths, duplicate identities, unexpected files,
member-to-artifact closure, manifest address reconstruction, and the direct
identifier/attribution/language boundary. JSON artifacts are projected before
publication, so agent, model, author, programming-language, and direct subject
fields do not enter the handoff. Query and diff commands operate on a verified
directory without reopening the source store, while the staged runtime records
selection, assembly, artifact closure, boundary verification, and final
address stages for reproducible operations.

```powershell
glio-noncode portfolio-release --data-root .glio --release-ready-only --as-of 2026-09-01T12:00:00Z --destination portfolio-release
glio-noncode portfolio-release-verify portfolio-release --output portfolio-release-verification.json
glio-noncode portfolio-release-query portfolio-release --state ready --output portfolio-ready.json
glio-noncode portfolio-release-lineage portfolio-release --output portfolio-lineage.json
glio-noncode portfolio-release-observability portfolio-release --format metrics-csv --output portfolio-metrics.csv
glio-noncode portfolio-release-schema --output portfolio-schema.json
glio-noncode portfolio-release-diff portfolio-release-a portfolio-release-b --output portfolio-diff.json
glio-noncode portfolio-release-runtime --data-root .glio --release-ready-only --output portfolio-runtime.json
```

### Architecture program offline handoff boundary

The sixteen-domain architecture program now has a producer-independent public
transport boundary. Its 18 exact-byte artifacts retain the eleven existing
runtime/release projections and add operational, domain-operation, stage,
quality, release-check, specification, and capability projections. The handoff
closes 172 program checks, 18 quality checks, 12 source stages, seven
certification domains, and 36 certification checks. Artifact hashes cover the
bytes written, and the root address covers the complete manifest inventory and
checks.

The offline boundary rejects direct identifiers, attribution and model keys,
unsafe paths, missing or extra files, byte drift, denominator drift, malformed
JSON, and non-deterministic replay. Address-only indexes support artifact,
path, domain, check, stage, and state lookups; bounded queries support JSON or
CSV output. Seven certification domains independently cover manifest,
inventory, runtime, release, reconciliation, query, and public-boundary
closure.

```powershell
glio-noncode architecture-program-offline-bundle --destination architecture-program-bundle
glio-noncode architecture-program-offline-verify architecture-program-bundle
glio-noncode architecture-program-offline-query architecture-program-bundle --resource domains --domain-id D08
glio-noncode architecture-program-offline-indexes architecture-program-bundle
glio-noncode architecture-program-offline-reconciliation architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-summary architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-certification architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-runtime --output architecture-program-offline-runtime.json
glio-noncode architecture-program-offline-observability architecture-program-bundle --format metrics-csv
```

The HTTP equivalents are `/v1/architecture/offline/bundle`, `/query`,
`/schema`, `/audit`, `/boundary`, `/indexes`, `/reconciliation`, `/summary`,
`/runtime`, and `/certification`. The service reuses one immutable bundle for
related requests with the same identifiers. `/observability` adds a
timestamp-free stage event stream and twelve aggregate metrics.

## Repository module inventory and depth control plane

The repository now exposes an AST-only module inventory for the complete local
package. It discovers modules without importing or executing them, counts
physical/nonblank/comment lines, extracts class and function declarations,
resolves local import edges, retains unresolved edges and syntax issues, and
closes deterministic family, role, state, package, symbol, and dependency-target
indexes. The inventory has no absolute machine paths and no source payload copy.

The dependency graph reports incoming/outgoing degree, roots, leaves, strongly
connected cycle components, and unresolved-edge counts. The depth plane gives
each module an explainable score over parse state, test references, public
surface, dependency resolution, and implementation scale, then aggregates those
rows into an overall percentage. The percentage is an implementation-maturity
signal only and is not a scientific or clinical claim.

The review queue turns parse failures, unresolved imports, missing test
references, large or isolated modules, low public surface, high fan-out, and
cycles into explicit next actions. Timestamp-free events and metrics provide
reproducible operational views. The fixed ten-artifact packet includes JSON,
CSV, audit, runtime, and capability artifacts; its verifier checks exact bytes,
safe paths, unexpected files, addresses, and the public boundary before load.

```powershell
glio-noncode module-inventory --format summary --output module-summary.json
glio-noncode module-inventory-depth --format markdown --output module-depth.md
glio-noncode module-inventory-review --format markdown --output module-review.md
glio-noncode module-inventory-packet --destination module-inventory-packet
glio-noncode module-inventory-packet-verify module-inventory-packet
```

The service equivalents are under `/v1/module-inventory`, including bounded
queries, graph and depth views, observability, and packet verification. See
[the module inventory contract](MODULE_INVENTORY.md).

## Module change impact and release gate

The module inventory now has a baseline-to-candidate change-control plane. It
compares immutable module rows, symbol shape, line and test-reference deltas,
and local import edges. A reverse graph over both snapshots propagates impact
from direct changes to direct dependents and transitive dependents. Each row
retains source IDs, shortest paths, reasons, severity, and a bounded risk value.

The verification layer converts the closure into ordered review, public-surface,
removed-module, unresolved-edge, and dependent-replay tasks. The policy layer
applies explicit thresholds for critical and high impact, removals, unresolved
direct edges, clean inputs, test-reference changes, and minimum task coverage.
The independent audit checks address references, row ordering, path termination,
counter conservation, task closure, gate references, and the public boundary.

The runtime has seven stages—input, diff, impact, verification, policy, replay,
and public—and observability emits timestamp-free events and metrics. The
ten-artifact packet includes both inventories, the diff, impact report,
verification plan, gate, audit, runtime, observability, and bounded Markdown
summary. Its verifier rejects unsafe paths, symlinks, extra or missing files,
byte drift, address drift, and forbidden public keys before offline query or
replay is allowed.

```text
glio-noncode module-impact --left-source-root baseline --right-source-root candidate
glio-noncode module-impact-verification --format csv
glio-noncode module-impact-packet --left-source-root baseline --right-source-root candidate --destination impact-packet
glio-noncode module-impact-packet-query impact-packet --resource impacts --severity high
glio-noncode module-impact-packet-replay impact-packet
```

The service equivalents are under `/v1/module-impact`, including bounded
queries, policy, verification, runtime, observability, packet verification,
packet diff, and packet replay. See [the module impact contract](MODULE_IMPACT.md).

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

The public mission-plan projection is intentionally separate from the typed
internal planner. It preserves the decision state, workflow DAG, dependency
order, resource envelope, review flags, aggregate selection counts, registry
address, and content address while omitting internal routing identifiers and
raw request metadata. The receipt is hydrated with address verification and
can be exported as canonical JSON, Markdown, or step-level CSV. The public
contract and capability declarations are available as both CLI and HTTP
surfaces:

```powershell
glio-noncode mission-plan mission.json --format json --output mission-plan.json
glio-noncode mission-plan mission.json --format markdown --output mission-plan.md
glio-noncode mission-plan mission.json --format steps-csv --output mission-plan-steps.csv
glio-noncode mission-plan-schema --output mission-plan-schema.json
glio-noncode mission-plan-capabilities --output mission-plan-capabilities.json
```

The corresponding API routes are `POST /v1/mission/plan`,
`GET /v1/mission/plan/schema`, and `GET /v1/mission/plan/capabilities`.
Malformed workflows, duplicate identifiers, cycles, restricted metadata, and
tampered content addresses fail closed. This is a read-only research planning
surface; it does not execute handlers or authorize clinical decisions.

The public plan release plane turns a validated receipt into a portable,
producer-independent handoff. It writes five exact-byte artifacts plus a
content-addressed manifest, checks public-boundary safety, workflow order,
step counts, resource totals, and receipt addressing, then independently
verifies the directory before offline hydration. Verified releases support
bounded filters by step kind, dependency, optionality, and determinism;
addressed plan-to-plan diffs with structural and resource deltas; a
timestamp-free six-stage runtime rehearsal; and configurable policy gates for
workflow, resource, artifact, boundary, and warning acceptance. The release,
query, diff, runtime, and policy schema/capability projections are included
in the repository's 99-surface audit. Catalog gates add explicit policy
thresholds, required coverage, aggregate resource limits, failure-visible
checks, and strict public-boundary validation. The gate runtime records a
timestamp-free six-stage rehearsal; the packet materializes eight exact-byte
JSON artifacts with manifest and offline verification; and the bounded gate
query filters checks by identity, category, acceptance, or text.
Gate diffs classify added, removed, changed, and unchanged checks between
two addressed decisions; gate observability conserves aggregate gate and
runtime counters as timestamp-free metrics.

```powershell
glio-noncode mission-plan-release mission.json --destination mission-release --output mission-release.json
glio-noncode mission-plan-release-verify mission-release --output mission-release-verification.json
glio-noncode mission-plan-release-query mission-release --kind review --format markdown --output mission-review.md
glio-noncode mission-plan-release-diff left-plan.json right-plan.json --format csv --output mission-diff.csv
glio-noncode mission-plan-release-runtime mission.json --destination mission-release-runtime --output mission-runtime.json
glio-noncode mission-plan-release-policy mission-release --policy release-policy.json --format markdown --output mission-policy.md
glio-noncode mission-plan-release-catalog mission-release left-release --destination release-catalog --output release-catalog.json
glio-noncode mission-plan-release-catalog-query release-catalog --workflow-kind review --format csv --output review-releases.csv
glio-noncode mission-plan-release-catalog-diff old-catalog new-catalog --format markdown --output catalog-diff.md
glio-noncode mission-plan-release-catalog-audit release-catalog --output catalog-audit.json
glio-noncode mission-plan-release-catalog-report release-catalog --format markdown --output catalog-report.md
glio-noncode mission-plan-release-catalog-gate release-catalog --format markdown --output catalog-gate.md
glio-noncode mission-plan-release-catalog-gate-runtime release-catalog --output catalog-gate-runtime.json
glio-noncode mission-plan-release-catalog-gate-packet release-catalog --destination catalog-gate-packet --output catalog-gate-packet.json
glio-noncode mission-plan-release-catalog-gate-packet-verify catalog-gate-packet --output catalog-gate-packet-verification.json
glio-noncode mission-plan-release-catalog-gate-query catalog-gate-packet --category acceptance --output gate-acceptance.json
glio-noncode mission-plan-release-catalog-gate-diff old-gate.json new-gate.json --format markdown --output gate-diff.md
glio-noncode mission-plan-release-catalog-gate-observability catalog-gate.json --runtime catalog-gate-runtime.json --output gate-metrics.json
glio-noncode mission-plan-conformance mission-plan.json --output conformance.json
glio-noncode mission-plan-replay mission-plan.json --format markdown --output replay.md
glio-noncode mission-plan-release-schema --output mission-plan-release-schema.json
glio-noncode mission-plan-release-query-schema --output mission-plan-release-query-schema.json
glio-noncode mission-plan-release-diff-schema --output mission-plan-release-diff-schema.json
glio-noncode mission-plan-release-runtime-schema --output mission-plan-release-runtime-schema.json
glio-noncode mission-plan-release-policy-schema --output mission-plan-release-policy-schema.json
glio-noncode mission-plan-release-catalog-schema --output mission-plan-release-catalog-schema.json
glio-noncode mission-plan-release-catalog-query-schema --output mission-plan-release-catalog-query-schema.json
glio-noncode mission-plan-conformance-schema --output mission-plan-conformance-schema.json
glio-noncode mission-plan-replay-schema --output mission-plan-replay-schema.json
```

The release catalog inventories multiple verified public handoffs with stable
release and plan addresses, collision checks, exact-byte materialization,
offline hydration, and bounded filters. Public conformance independently
reconciles receipt addresses, workflow order, aggregate resources, and
boundary fields. Public replay records the same checks as a timestamp-free
six-stage ledger and never executes a workflow handler. Catalog reports add
conserved aggregate totals plus state, decision, and workflow distributions;
shares use integer basis points so the output is stable across runtimes.

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

## Module certification and contract coverage

Wave 10 adds a per-module certification matrix layered on the static module
inventory. It records eight checks for every source row: parse state, symbol
surface, dependency closure, test evidence, documentation evidence, package
export evidence, public-boundary safety, and implementation scale. The matrix
is content addressed and preserves all failed checks as actionable gaps.

The new surfaces are:

- `module_certification`: deterministic evidence extraction, row scoring, gap
  construction, and matrix verification;
- `module_certification_policy`: explicit aggregate thresholds and independent
  policy checks;
- `module_certification_tasks`: one stable remediation task per failed check;
- `module_certification_review`: module-grouped severity routing for open gaps;
- `module_certification_diff`: baseline-to-candidate score, gap, symbol, line,
  and check-state changes;
- `module_certification_schema`: field registry and conservation validation;
- `module_certification_runtime`: seven timestamp-free stages from inventory to
  public boundary;
- `module_certification_observability`: bounded events and aggregate metrics;
- `module_certification_packet`: ten exact-byte offline artifacts plus manifest;
- `module_certification_packet_query`: verified offline query, diff, and replay.

The checks are static and source-execution-free. Test and Markdown files are
read once per file and tokenized; package exposure is collected from the
initializer AST. Internal modules may receive `not_applicable` coverage checks,
while public modules need explicit test, documentation, and export evidence.
This makes the aggregate percentage explainable without treating a scalar as a
scientific result.

```powershell
glio-noncode module-certification --format summary
glio-noncode module-certification --format markdown --output certification.md
glio-noncode module-certification-tasks --format csv --output certification-tasks.csv
glio-noncode module-certification-audit --output certification-audit.json
glio-noncode module-certification-runtime --output certification-runtime.json
glio-noncode module-certification-observability --format metrics-csv --output certification-metrics.csv
glio-noncode module-certification-packet --destination certification-packet
glio-noncode module-certification-packet-verify certification-packet
glio-noncode module-certification-packet-query certification-packet --resource gaps --limit 50
```

The HTTP boundary is `/v1/module-certification`, with bounded query routes for
modules, checks, gaps, and tasks plus policy, runtime, observability, audit,
packet verification, packet query, packet diff, and packet replay. Continuous
integration materializes the schemas and capabilities and runs the focused
31-test certification contract suite.

## Certification evidence lineage and quality

The certification control plane also exposes an evidence graph and a
quality/readiness report. Lineage records connect module IDs to source rows,
test references, Markdown references, package-export AST observations, and
dependency targets. Each record keeps a relative path, digest, line count,
relation, and content address; unresolved dependencies remain visible. The
quality report aggregates check-kind conservation and family conservation,
identifies blocker modules and top gap IDs, measures non-source evidence
coverage, and classifies readiness as `ready`, `warning`, or `blocked`.

```powershell
glio-noncode module-certification-lineage --resource modules --limit 50
glio-noncode module-certification-lineage --resource edges --resolved
glio-noncode module-certification-quality --resource checks --limit 50
glio-noncode module-certification-quality --resource families --format markdown
```

The corresponding API routes are `/v1/module-certification/lineage` and
`/v1/module-certification/quality`, with query, schema, and capabilities
variants. These projections are aggregate-only, deterministic, bounded, and
source-execution-free.

Quality policy evaluation provides strict or customized threshold gates over
evidence coverage, check pass rates, family scores, blocker counts, all-module
certification, and readiness. Every policy and decision is immutable and
content addressed; the API and CLI expose bounded decision queries and CSV
output.

Policy comparison views make threshold changes auditable: they retain both
policy addresses, changed field names, changed check IDs, failed-count deltas,
and acceptance transitions. This keeps a relaxed local review visibly
different from a strict release decision while preserving deterministic
replay.
The comparison output is a public aggregate and contains no source payload.
It is suitable for pull-request review, offline archival, and CI annotations.
An unchanged policy produces an empty changed-field tuple.
An unchanged gate produces an empty changed-decision tuple.
Changed threshold values are kept beside their content addresses.
Changed pass states are keyed by stable check IDs.

## Module implementation workbench

The module workbench is the detailed module-by-module implementation surface.
It joins the static inventory, certification matrix, evidence lineage, and
quality report into per-module assessments with seven explainable dimensions,
resolved graph fan-in/fan-out, evidence-kind counts, depth bands, delivery
risk, family rollups, and a stable task queue. The queue covers parsing,
dependency closure, tests, documentation, public contract, decomposition,
integration review, and certification closure.

```powershell
glio-noncode module-workbench --format summary
glio-noncode module-workbench --resource tasks --format csv --output module-tasks.csv
glio-noncode module-workbench --resource modules --depth-band blocked
glio-noncode module-workbench-policy --format markdown --output module-policy.md
glio-noncode module-workbench-audit --format csv --output module-audit.csv
```

The policy layer supports score, deep-module percentage, blocked-module,
high-risk, family-score, dimension-registry, test-reference, and evidence
thresholds. The independent audit recomputes nested addresses, public-key
safety, depth and risk conservation, family conservation, module ordering, and
task coverage. The snapshot diff classifies added, changed, removed, and
unchanged modules and reports signed score and task deltas. All projections
are deterministic, bounded, timestamp-free, and source-execution-free. See
[the module workbench contract](MODULE_WORKBENCH.md).

Release reconciliation adds a cross-artifact gate over the matrix, lineage,
and quality addresses. It exposes independent conservation checks, blocker
reconciliation, public-key review, readiness policy, bounded check queries,
and a release-eligibility result. The lineage audit separately recomputes
graph targets, support references, counters, relative paths, and limits.

```powershell
glio-noncode module-certification-lineage-audit --plane graph
glio-noncode module-certification-release --format markdown
```

## Module workbench execution depth

The module workbench execution layer is the operational continuation of the
module-by-module depth surface. It converts a bounded task portfolio into an
addressed execution ledger with deterministic prerequisites, evidence
requirements, immutable transition events, state-count conservation, and
reviewable blockers. `start`, `complete`, `block`, `unblock`, `skip`, `reopen`,
and `supersede` commands are validated against the task lifecycle; `complete`
requires the declared evidence receipt count.

Five public aggregate planes are exposed:

| Plane | Function |
| --- | --- |
| Execution | Build, query, export, and evolve task state |
| Audit | Reconstruct events and check addresses, prerequisites, evidence, counts, and boundaries |
| Policy | Apply completion, evidence, exception, event-budget, and audit thresholds |
| Runtime | Compose portfolio, plan, replay, policy, audit, and handoff stages |
| Diff | Compare task identity, state, completion, evidence, and event deltas |

The surfaces remain local-first, timestamp-free, path-free, and identity-free.
They retain aggregate receipts and review explanations but do not assert that a
completed implementation task is a scientific, diagnostic, treatment, or
clinical conclusion. See [the execution contract](MODULE_WORKBENCH_EXECUTION.md).

The execution review projection groups task state back into module-level rows.
It routes blocked modules to attention, active modules to evidence follow-up,
ready modules to the next-task queue, waiting modules to prerequisite review,
and completed modules to verification or complete state. Each row conserves
task counts, carries bounded blocker explanations and next-task IDs, and reports
completion and evidence coverage. It is exposed through the
`module_workbench_execution_review_*` functions and the
`/v1/module-workbench/execution/review` API family.

### Portable archive transport, reconciliation, and indexing

The execution packet has a deterministic binary transport boundary in addition
to its exact-byte directory form. Archive construction uses fixed ZIP metadata,
stores the manifest before thirteen packet artifacts, and preserves packet
addresses and exact member bytes. Verification covers ZIP structure, safe
relative paths, canonical manifest bytes, exact member content, hydrated packet
state, public-boundary keys, and atomic storage policy. Loading and unpacking
are fail-closed and never silently replace an existing destination.

The transfer surface chunks archive bytes into addressed ranges, verifies each
payload independently, and supports idempotent partial-to-completed resumption.
Reassembly checks ordinals, offsets, archive ownership, byte conservation, and
the final archive address. The nine-stage archive runtime composes build,
write, verify, load, chunk, resume, assemble, unpack, and query with stable
stage addresses.

Archive reconciliation compares two verified containers member by member. It
reports added, removed, modified, and unchanged paths, archive/payload/entry
byte deltas, exact-byte identity, packet compatibility, and format
compatibility. The archive index catalogs multiple verified archives without
retaining their binary payloads or source paths; it conserves records and byte
totals, groups packet addresses, detects duplicate archive addresses, and
supports unambiguous address resolution.

```powershell
glio-noncode module-workbench-execution-packet-archive-schema
glio-noncode module-workbench-execution-packet-archive-transfer-schema
glio-noncode module-workbench-execution-packet-archive-runtime-schema
glio-noncode module-workbench-execution-packet-archive-diff-schema
glio-noncode module-workbench-execution-packet-archive-index-schema
glio-noncode module-workbench-execution-packet-archive packet --destination packet.zip
glio-noncode module-workbench-execution-packet-archive-verify packet.zip
glio-noncode module-workbench-execution-packet-archive-diff left.zip right.zip --format markdown
glio-noncode module-workbench-execution-packet-archive-index left.zip right.zip --resource duplicates
```

The matching HTTP family is read-only and builds the current public aggregate
in memory. Archive diff routes compare deterministic current projections with
query-selectable left and right archive IDs; direct multi-archive catalogs and
filesystem comparison remain explicit local operations. Every schema and
capability projection declares deterministic, offline, bounded, path-free,
timestamp-free, and identity-free behavior.

### Durable archive object stores and checkpoints

Archive stores persist many verified packet archives as one deterministic
content-addressed catalog. They keep canonical manifest metadata separate from
exact ZIP objects, deduplicate identical bytes, record registration operations
in a hash-linked journal, enforce optimistic expected-head appends, and write
through an atomic directory replacement. Load and verify are fail-closed;
verification covers manifest, object bytes, addresses, journal continuity,
public keys, count conservation, and storage policy. Replay rehydrates every
object and proves its packet and archive addresses. Queries and diffs expose
bounded summary, entry, operation, head, and byte-total views without raw
payloads or paths.

Checkpoints capture a complete addressed store boundary without binary data.
Comparisons prove exact matches and append-only extensions, or classify journal
forks, missing addresses, foreign store IDs, and other blocked states. Added
and missing operation/entry resources are queryable and exportable.

```powershell
glio-noncode module-workbench-execution-packet-archive-store left.zip right.zip --destination archive-store
glio-noncode module-workbench-execution-packet-archive-store-verify archive-store
glio-noncode module-workbench-execution-packet-archive-store-query archive-store --resource operations
glio-noncode module-workbench-execution-packet-archive-store-runtime left.zip right.zip
glio-noncode module-workbench-execution-packet-archive-store-checkpoint archive-store --output checkpoint.json
glio-noncode module-workbench-execution-packet-archive-store-checkpoint-compare archive-store checkpoint.json
glio-noncode module-workbench-execution-packet-archive-store-checkpoint-schema
glio-noncode module-workbench-execution-packet-archive-store-checkpoint-capabilities
```

The HTTP family is read-only and builds the current public aggregate in
memory. Store checkpoint comparisons are also read-only projections; local
directory persistence and exported checkpoint files remain explicit CLI or
Python operations.

Archive-store recovery diagnostics inspect a possibly blocked directory
without hydrating or changing it. Findings cover directory safety, manifest
readability and canonical bytes, entry shape, safe object tokens, regular-file
and symlink policy, exact object-byte addresses, missing or extra objects,
object-set conservation, and the identity-free public boundary. The report is
addressed and conserves passed/blocked finding counts, so it is still useful
when normal fail-closed loading cannot proceed.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-recovery archive-store --format markdown
glio-noncode module-workbench-execution-packet-archive-store-recovery-query archive-store --plane objects
glio-noncode module-workbench-execution-packet-archive-store-recovery-schema
glio-noncode module-workbench-execution-packet-archive-store-recovery-capabilities
```

### Archive-store replication and promotion

The replication boundary turns two verified persisted stores into a
deterministic, reviewable transfer plan. It proves that both stores represent
the same logical store, that target journal and entry sequences are exact
prefixes of the source, and that every object and journal operation is either
reused, copied, or explicitly marked as a conflict. Object counts, operation
counts, required bytes, and the transfer ratio are conserved in the addressed
plan. Divergence, identity mismatch, verification failure, and stale expected
heads fail closed.

Apply is an explicit filesystem operation separate from the plan. It rebuilds
the plan, re-verifies both inputs, checks the expected target head, atomically
writes the source boundary, reloads the destination, and returns a receipt
containing only store addresses, counts, and outcomes. A promotion decision
holds an accepted extension until the receipt proves the target address equals
the source address. Exact matches are safe noops. Query and runtime outputs
are bounded, deterministic, path-free, timestamp-free, and identity-free.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication source-store target-store --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-query source-store target-store --resource entries --action copy
glio-noncode module-workbench-execution-packet-archive-store-replication-runtime source-store target-store --apply --destination promoted-store
glio-noncode module-workbench-execution-packet-archive-store-replication-schema
glio-noncode module-workbench-execution-packet-archive-store-replication-runtime-capabilities
```

The public plan has summary, entries, operations, and checks resources.
Runtime stages cover planning, source verification, target verification,
reconciliation, optional apply, promotion evaluation, and lifecycle closure.
Every nested row and final receipt has a deterministic content address, so a
downloaded packet store can be reviewed offline and compared across runs.

### Portable replication packet

The replication packet materializes a fixed, path-free review bundle from a
verified plan. Its canonical manifest records plan, promotion, optional
receipt/runtime references, artifact byte counts, per-file content addresses,
and packet checks. The default packet includes plan JSON, CSV, and Markdown,
a bounded summary query, and promotion JSON. Runtime artifacts can be added
when a runtime receipt is available. The writer uses an atomic directory
replacement; the loader rejects non-canonical manifests, missing or extra
artifacts, symlinks, byte-address mismatches, and forbidden identity fields.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication-packet source-store target-store --destination replication-packet --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-query source-store target-store --resource artifacts --role plan
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-replay replication-packet
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-schema
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-query-capabilities
```

Packet manifests and query responses are content-addressed and deterministic
for identical verified inputs. API routes mirror the CLI beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet`,
including build, bounded query, replay, schema, and capabilities routes.

### Replication packet diffs and release assurance

Two persisted replication packets can be loaded and verified before any
comparison is emitted. The diff classifies every fixed-vocabulary artifact as
`added`, `removed`, `unchanged`, or `changed`, retains left/right byte counts
and addresses, and separately checks packet format, references, artifact
conservation, release eligibility, and the identity-free boundary. Matching
packets are accepted noops; append-only extensions can be promotable; changed
or divergent content is accepted for inspection but held from promotion.

The release projection turns those checks into an explicit `promotable`,
`hold`, or `blocked` decision. The ordered runtime records packet loading,
left/right verification, comparison, release evaluation, and closure with
addressed stages. Independent assurance adds severity-bearing findings:
integrity, candidate acceptance, boundary state, required removals, content
changes, release decision, public boundary, and optional runtime closure.
Warnings create a review hold; blockers fail closed. All projections are
bounded, deterministic, timestamp-free, path-free, and identity-free.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff left-packet right-packet --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-query left-packet right-packet --resource artifacts --action changed
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release left-packet right-packet --format summary
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-runtime left-packet right-packet --format summary
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-assurance left-packet right-packet --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-query left-packet right-packet --resource findings --severity blocker
```

The HTTP family mirrors these operations under
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff`.
Operational requests provide `left_directory` and `right_directory`; schema
and capability routes do not read the filesystem. Query responses carry an
independent content address, so a review consumer can verify pagination and
filters without trusting transport metadata.

### Multi-packet diff matrices

Release windows can compare several persisted packet pairs in one bounded,
path-free matrix. Each pair is independently loaded, verified, diffed, and
assigned a release decision. The matrix conserves item count, accepted and
release-ready counts, every diff state, every release state, and the aggregate
score. A single divergent pair can therefore hold the window without hiding
which pair caused the hold. Matrix rows retain only pair identifiers,
addresses, states, release outcomes, scores, and bounded detail; filesystem
paths, timestamps, private fields, and attribution metadata are excluded.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-batch `
  --pair "baseline=left-packet=left-packet" `
  --pair "candidate=left-packet=right-packet" --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query `
  --pair "baseline=left-packet=left-packet" --release-state hold --limit 20
```

The matrix API uses repeatable `pair` query values beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/batch`.
Schema and capability projections are filesystem-independent, while matrix
build and query requests verify each supplied pair before emitting output.

### Policy-governed release-window handoffs

A release window applies an explicit policy to a verified matrix instead of
relying on the matrix score alone. Policies bound minimum pair count, minimum
release-ready score, held and blocked pair counts, changed artifacts, required
removals, and whether all pairs must be accepted or release-ready. Eleven
ordered checks retain observed values, expected thresholds, severity, detail,
and remediation. Policy failures produce `promotable`, `hold`, or `blocked`
states; a warning can require review, while a blocker fails closed.

The release-window runtime records seven addressed stages: load, verify the
matrix, resolve policy, evaluate, audit, release, and complete. A blocking
policy result marks audit blocked and skips release/closure stages. Independent
assurance rechecks linkage, conservation, decision semantics, score bounds,
held-pair review, optional runtime closure, window admissibility, and the
identity-free public boundary. JSON, CSV, Markdown, bounded query, schema, and
capabilities outputs remain path-free, timestamp-free, and identity-free.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window `
  --pair "baseline=left-packet=left-packet" `
  --pair "candidate=left-packet=right-packet" `
  --minimum-score 1.0 --maximum-hold-count 0 --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime `
  --pair "baseline=left-packet=left-packet" --format summary
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance-query `
  --pair "candidate=left-packet=right-packet" --resource findings --severity blocker --passed
```

The HTTP family is available beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window`.
Operational routes accept repeatable `pair=PAIR_ID=LEFT=RIGHT` values and
bounded policy query parameters; schema and capability routes do not inspect
the filesystem.

### Release-window policy sensitivity

The sensitivity plane compares explicit release-window policies on one
verified packet matrix. Each scenario records its policy address, window
address, state, readiness, acceptance, score, and check counts. The aggregate
conserves scenario state totals and can expose a deterministic
best-promotable reference, but it remains analysis-only and cannot grant a
release or mutate packet storage.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity `
  --pair "matched=left-packet=left-packet" `
  --scenario "strict=1.0=0" `
  --scenario "review=0.0=1" `
  --allow-held --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-query `
  --pair "matched=left-packet=left-packet" `
  --scenario "strict=1.0=0" --resource scenarios --state promotable
```

Sensitivity JSON, CSV, Markdown, bounded scenario queries, schemas, and
capabilities are exposed beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/sensitivity`.
The CLI and HTTP API use repeatable `scenario` values in the form
`SCENARIO_ID=MINIMUM_SCORE=MAXIMUM_HOLD_COUNT`; all shared limits remain
explicit and outputs are deterministic, path-free, timestamp-free, and
identity-free.

### Durable release-window review stores

The durable review-store plane turns one verified decision ledger into an
exact three-artifact handoff: `review-store.json`, `review-ledger.json`, and
`review-operations.json`. The writer uses a temporary sibling directory and
an atomic replacement; the loader rejects missing, extra, symlinked,
non-regular, non-canonical, byte-mismatched, or content-address-mismatched
artifacts. A genesis operation records the ledger address, append operations
retain the predecessor address, and callers can require an expected head
before appending a new review decision.

The store can be queried by summary, operations, checks, or hydrated ledger
entries. Runtime emits eight addressed stages for load, store verification,
ledger verification, operation verification, replay, head resolution,
readiness evaluation, and completion. Independent assurance recomputes the
store/link/head/chain/replay/public-boundary findings and separates warnings
from blockers. Store diffs classify exact, append-only, and divergent
revisions. JSON, CSV, Markdown, CLI, HTTP, schema, capability, and Actions
surfaces are available; public projections exclude paths, timestamps,
attribution, private fields, and identity metadata.

### Durable review-store catalogs and federation

The catalog layer indexes multiple independently persisted review stores into a
single deterministic, content-addressed collection. Each catalog records
ordered store entries, a genesis operation, append-only registration
operations, and explicit format, entry, operation, storage, and public-boundary
checks. Catalog writes are an exact three-artifact transport with canonical
JSON, regular-file enforcement, byte counts, atomic replacement, and
optimistic expected-catalog-address guards. Loading a catalog is path-free in
the public model and rehydrates only the declared store artifacts.

Catalog queries are bounded and address their receipts. Summary, entries,
operations, and checks can be filtered by store state, acceptance, readiness,
evidence window, text, offset, and limit. The catalog runtime has eight
content-addressed stages: load, catalog verification, entry verification,
operation verification, window reconciliation, release-set resolution,
readiness evaluation, and completion. A structurally valid held catalog is
accepted but not release-ready; blocked or divergent collections fail closed.

Federation applies an explicit collection policy over selected stores. It
checks catalog acceptance, minimum member and ready thresholds, selected-window
coherence, ledger uniqueness, blocked-member exclusion, known-store selection,
and the public boundary. It distinguishes ready, held, mixed, blocked, and
empty collections, preserving the difference between a valid held collection
and a structurally invalid one. Catalog diffs classify exact, append-only, and
divergent revisions with one bounded action per store.

The full plane is available through deterministic JSON, CSV, Markdown, CLI,
HTTP, schema, capability, and GitHub Actions surfaces. No path, timestamp,
reviewer, operator, agent, model, language, patient, or other identity-bearing
field crosses the public boundary. Regression tests cover ordering,
rehydration, tampering, missing and extra artifacts, append guards, readiness
holds, blocked members, mixed windows, unknown selections, query receipts,
diff states, and downloaded review-store data.

### Independent catalog assurance and release gate

Catalog verification is complemented by a separate assurance computation that
rechecks aggregate addresses, version and boundary, entry count and ordinals,
member and entry addresses, genesis and registration conservation, journal
predecessor links, evidence-window references, optional hydrated-store
addresses, catalog verification, acceptance conservation, readiness, and the
public boundary. Findings are individually addressed and classified as pass,
warning, or blocker. A valid held catalog is accepted with a readiness warning;
rejected members, broken links, or malformed evidence create blockers.

The release gate combines four independently addressed projections: the
catalog, its eight-stage runtime, the selected federation, and catalog
assurance. It checks cross-projection catalog linkage, runtime reconciliation,
federation acceptance, assurance acceptance, member conservation, and public
boundary safety. Release readiness requires every check to pass, while a
structurally valid held collection remains accepted and is reported as held.
Unknown selections, rejected catalogs, structural runtime failures, and
assurance blockers fail closed.

Both planes expose bounded finding/check queries with receipt addresses and
deterministic JSON, CSV, and Markdown projections. CLI and HTTP routes are
available beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/assurance`
and `/gate`, with schema and capability routes for each base and query
surface. Public projections carry no paths, timestamps, attribution,
reviewer/operator data, agent or model fields, language metadata, or identity
fields.

### Portable catalog release packet

The catalog release packet is the durable handoff above the five independently
addressed projections: catalog, runtime, federation, assurance, and release
gate. It writes an exact six-file directory containing one canonical manifest
and `catalog.json`, `runtime.json`, `federation.json`, `assurance.json`, and
`gate.json`. Every component has a byte count, byte address, and component
address in the manifest. Writes are staged in a sibling temporary directory
and published atomically; existing destinations require an explicit overwrite
flag.

Loading is fail-closed. The loader rejects symlinks, directories, missing or
extra files, non-canonical JSON, manifest mutations, wrong kind-to-file
bindings, byte mismatches, and component addresses that do not match the
packet summary. It then rehydrates the typed component objects and reruns each
component verifier before returning the packet. A blocked release remains a
valid, transportable blocked packet, while a held packet remains accepted but
not release-ready.

The packet exposes deterministic JSON, CSV, and Markdown projections plus a
bounded artifact query with an addressed query receipt. CLI commands are
available under
`module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet`
and `-query`; HTTP routes are available under
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet`.
Both base and query schema/capability projections are part of the public
surface and GitHub Actions checks. The packet boundary contains no paths,
timestamps, attribution, agent/model/language metadata, or identity-bearing
fields.

### Catalog packet transitions and review decisions

The packet transition layer compares two verified six-file catalog packets by
the fixed catalog, runtime, federation, assurance, and gate artifact kinds. It
records unchanged, changed, added, and removed actions with both content and
byte addresses, conserves action counts, classifies exact versus changed
packets, and maps release state transitions such as promotion, hold, block,
recovery, and regression. Every diff has independent addressed checks and
bounded summary/action/check queries.

The review layer turns one verified packet diff into an append-only decision
record. Promote is accepted only for an accepted, release-ready transition;
hold preserves accepted evidence that is not ready; block preserves failure
evidence; and supersede records an explicit replacement decision. Follow-up
decisions must continue from the current head packet and can use an expected
head address for optimistic concurrency. Review persistence is an exact,
atomic two-file `manifest.json` plus `review.json` transport with canonical
bytes, fail-closed rehydration, bounded queries, JSON/CSV/Markdown exports,
and tamper detection. Public outputs contain no paths, timestamps,
attribution, agent/model/language metadata, or identity-bearing fields.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff `
  --left-packet-directory .\out\packet-a `
  --right-packet-directory .\out\packet-b --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review `
  --left-packet-directory .\out\packet-a `
  --right-packet-directory .\out\packet-b --format summary
```

### Release-window decision ledger

The decision ledger turns verified release-window evidence into an explicit,
append-only review history. It supports promote, hold, block, and supersede
decisions; preserves the window and assurance addresses; requires actions for
non-promote outcomes; and rejects promotion unless the underlying window and
packet assurance are already release-ready. Empty or tampered ledgers fail
closed. No reviewer, operator, or agent identity is part of the public model.

```powershell
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review `
  --pair "matched=left-packet=left-packet" `
  --decision "promote=promote=verified evidence is ready" --format summary
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-query `
  --pair "matched=left-packet=left-packet" `
  --decision "promote=promote=verified evidence is ready" --resource entries --limit 20
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime `
  --pair "matched=left-packet=left-packet" `
  --decision "promote=promote=verified evidence is ready" --format markdown
glio-noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-query `
  --pair "matched=left-packet=left-packet" --resource findings --severity blocker
```

The HTTP review family is available beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review`.
It includes bounded ledger, runtime, assurance, and revision-diff routes,
query routes, JSON/CSV/Markdown exports, schemas, and capability projections.
Revision diffs classify exact, append-only, and divergent histories while
retaining the evidence scope. Every projection is deterministic, bounded,
path-free, timestamp-free, and identity-free.

### Portable module execution handoff

The module workbench execution packet packages the report, bounded portfolio,
initial and current ledgers, review projection, independent audit, policy gate,
runtime, schema, and capabilities into thirteen exact-byte artifacts. It
supports atomic local writes, safe-path and canonical-JSON verification,
address-chain checks, offline queries, replay receipts, packet diffs, explicit
release gates, a seven-stage runtime, and normalized inspection findings across
verification and release planes. The default public projection is timestamp-
free, path-free, and identity-free. See
[docs/MODULE_WORKBENCH_EXECUTION_PACKET.md](MODULE_WORKBENCH_EXECUTION_PACKET.md).

### Independent packet-review assurance and release gates

Packet review decisions are now followed by an independent assurance pass. The
assurance builder recomputes the review chain, decision policy, head
conservation, readiness classification, public projection, and—when supplied—
the packet-diff structure and linkage. Its findings retain expected and
observed values, a warning or blocker severity, an explicit pass state, and a
content address. The assurance result separates structural acceptance from
release readiness: a held or superseded review can be accepted evidence while
remaining non-ready, whereas failed findings are not accepted.

The release gate then combines the typed diff, review, and assurance. It
requires all component links and acceptance checks, closes the decision table,
classifies ready versus held versus blocked state, and only returns
`release_ready=true` for an accepted promote decision over ready evidence. A
blocked result remains persistable as an auditable rejection; persistence
verifies the record itself rather than silently discarding failed release
evidence.

Both boundaries use canonical, path-free, timestamp-free JSON. Each durable
record is an exact two-file directory: `manifest.json` plus `assurance.json`
or `gate.json`. The loader rejects noncanonical bytes, manifest divergence,
unknown files, symlinks, byte-address mismatches, and invalid nested addresses.
Queries are bounded and addressed, with summary, findings/checks, severity,
pass-state, kind, text, offset, and limit controls. JSON, CSV, and Markdown
projections are deterministic.

The CLI exposes the full packet-review assurance and gate families:

```text
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance --left-packet-directory LEFT --right-packet-directory RIGHT --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-query --left-packet-directory LEFT --right-packet-directory RIGHT --kind diff-linkage
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate --left-packet-directory LEFT --right-packet-directory RIGHT --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-query --left-packet-directory LEFT --right-packet-directory RIGHT --kind diff-link
```

The loopback API mirrors those commands under `/packet/review/assurance` and
`/packet/review/gate`, including `/query`, `/schema`, `/capabilities`, and
query schema/capability resources. Directory arguments are caller inputs only;
they are never echoed in public responses. The public-surface audit counts the
four assurance and four gate schema/capability projections and rejects
attribution, agent, model, language, user, path, and timestamp fields.

### Longitudinal packet-review gate history

The gate-history boundary turns one packet-review gate into a durable
append-only decision history. The first event records the current gate head;
later events append a new verified gate projection, point to the exact prior
head address, receive the next contiguous ordinal, and update conserved
promote, hold, block, and supersede counters. An optional expected-head value
provides an optimistic concurrency guard: a caller with a stale head cannot
silently fork the published history. A gate address may occur only once.

Each decision is closed into a public state projection:

| Decision | State | Accepted | Release ready |
|---|---|---:|---:|
| `promote` | `ready` | true | true |
| `hold` | `held` | true | false |
| `supersede` | `held` | true | false |
| `block` | `blocked` | false | false |

The history verifier independently recomputes aggregate and entry addresses,
entry conservation, ordinal and previous-head continuity, decision closure,
decision counters, head projection, gate uniqueness, and the public boundary.
Accepted blocked histories remain useful rejection evidence; history transport
validity is separate from whether the current head is release-ready.

History persistence is an atomic exact two-file directory containing
`manifest.json` and `history.json`. The manifest embeds the public history,
the canonical document byte count, a document byte address, and its own
content address. Load rejects extra or missing files, symlinks, noncanonical
JSON, manifest divergence, byte mismatches, malformed entries, and failed
verification. There are no paths, timestamps, personal identities, or runtime
metadata in the published projection.

The history query plane supports `summary`, `entries`, and `checks` resources.
Entries can be filtered by decision, state, acceptance, release readiness, or
case-insensitive text and paged with bounded offset/limit controls. Every query
is content-addressed and can be rendered as deterministic JSON, CSV, or
Markdown.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history `
  --left-packet-directory LEFT --right-packet-directory RIGHT --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query `
  --left-packet-directory LEFT --right-packet-directory RIGHT --resource entries --decision-filter promote
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-schema
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-capabilities
```

The loopback API mirrors the history family beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history`.
It exposes the history, query, schema, capability, query-schema, and
query-capability resources. A valid blocked history returns a successful
transport response with `state=blocked`; callers inspect the public readiness
fields for release policy.

### Deterministic gate-history replay

The replay boundary reconstructs the complete state timeline from a verified
gate history. It begins at `start`, retains each gate and entry head address,
checks the before/after state chain, preserves the decision and readiness
flags, and projects the terminal state independently. This gives a release
consumer a compact explanation of how a current head was reached without
re-reading all packet directories.

Replay produces eight ordered checks: source-history verification,
event-conservation, event-address verification, transition-chain continuity,
history-head linkage, decision/state closure, terminal projection, and the
public boundary. A replay report is accepted only when every check passes.
Tampered histories produce an inspectable rejected report but cannot be
exported as an accepted replay receipt.

The replay query plane provides `summary`, `events`, and `checks` resources,
with decision, before-state, after-state, acceptance, readiness, text, and
bounded paging filters. Replay events and query receipts are independently
content-addressed and available as JSON, CSV, and Markdown.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay `
  --left-packet-directory LEFT --right-packet-directory RIGHT --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query `
  --left-packet-directory LEFT --right-packet-directory RIGHT --resource events --after-state ready
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-schema
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-capabilities
```

The replay API is available below the history route at `/replay`, including
the same six read-only resources and format negotiation. Both history planes
are covered by focused regression tests, public-surface checks, continuous
integration commands, and the persisted downloaded-packet fixture.

### Portable observatory closure packets

The observatory closure packet is a single path-free handoff for the verified
longitudinal observatory, its independently recomputed packet verification,
the explicit release policy, and the policy runtime. It preserves ready,
held, and blocked outcomes as distinct public states. The packet address is
acyclic because the verification link is checked by the independent receipt
instead of being used to address that receipt; the runtime is replayed during
verification to prove deterministic policy closure.

The exact packet directory contains only `manifest.json`, `observatory.json`,
`verification.json`, `policy.json`, and `runtime.json`. Every component has a
canonical UTF-8 byte receipt, content address, and fixed file name. Writers
are atomic. Loads reject symlinks, extra or missing files, noncanonical JSON,
manifest drift, byte tampering, nested address mismatch, stale verification,
and nondeterministic runtime replay. Directory paths are input-only and never
appear in public output.

The packet query plane provides bounded `summary`, `artifacts`,
`verification`, `observations`, `transitions`, `stages`, and `policy-checks`
resources with kind/state/pass/text filters and addressed JSON, CSV, and
Markdown exports. The CLI family is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-query
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-verify
```

The loopback API adds `/observatory/packet`, `/observatory/packet/query`,
`/observatory/packet/verify`, and packet schema/capability resources below
the observatory route. These surfaces remain deterministic, bounded,
timestamp-free, identity-free, and free of agent, model, language, and other
attribution fields.

### Multi-packet observatory registry

The packet registry indexes multiple portable observatory closure packets in a
canonical order. Each entry retains the packet ID, packet and verification
addresses, state, acceptance, readiness, artifact count, and its own entry
address. Registry state is derived from conserved ready/held/blocked counts:
an all-ready collection is `ready`, a non-ready accepted collection is
`held`, a collection containing blocked or rejected evidence is `blocked`,
and an empty index is `empty`. Duplicate packet IDs and duplicate packet
addresses are rejected.

Registry transport uses exactly `manifest.json`, `registry.json`,
`packets.json`, and `verification.json`. The packet metadata document is
retained separately from the entry index so a registry can be rehydrated and
checked without source directories. The independent receipt recomputes the
registry address, entry order and addresses, packet linkage, state and
readiness conservation, and the public boundary. Writers are atomic and
loaders reject symlinks, unknown files, noncanonical JSON, byte tampering,
manifest drift, and stale verification.

The registry query plane supports `summary`, `entries`, `packets`,
`verification`, and `checks` with bounded state, acceptance, readiness, text,
offset, and limit filters. JSON, CSV, and Markdown results are addressed and
deterministic. The CLI family is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-query
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-verify
```

The API mirrors the registry at `/observatory/packet/registry` with build,
query, verify, schema, capabilities, query-schema, query-capabilities,
verification-schema, and verification-capabilities resources. Source paths
are input-only and never appear in registry projections.

### Observatory packet registry federation

Federation composes independently verified packet registries into one
addressed collection without merging or reinterpreting their scientific
claims. Registries are sorted by registry ID and address; registry and packet
counts are conserved; duplicate registry IDs or addresses are rejected; and
policy bounds make minimum/maximum registry count, packet count, blocked and
held budgets, acceptance, release readiness, and empty collections explicit.
Federation state is `ready`, `held`, `blocked`, or `empty` and remains
separate from the underlying registry evidence.

The portable federation directory contains exactly:

```text
manifest.json
federation.json
registries.json
policy.json
verification.json
runtime.json
```

Each document is canonical JSON with byte receipts. Loaders reject unknown or
missing files, symlinks, noncanonical bytes, manifest drift, stale addresses,
and stale verification/runtime receipts. The federation query plane exposes
`summary`, `registries`, `packet-rollup`, `verification`, `policy-checks`, and
`stages`, all with bounded state, acceptance, readiness, text, offset, and
limit filters. JSON, CSV, and Markdown exports are deterministic and
path-free.

The CLI family adds federation build, query, verify, and runtime replay
commands below the existing observatory packet registry command. The API
nests the same resources below `/observatory/packet/registry/federation`.
Federation accepts repeatable `registry_directory` inputs or reloads an
existing `input` directory. The runtime replays load, verify, policy, project,
and complete stages, preserving accepted-but-held and blocked outcomes for
review. Source paths remain input-only and never enter public projections.

### Observatory packet registry federation assurance and release gate

The federation assurance layer independently replays federation verification
and runtime closure, then records 21 addressed findings across federation,
registry, packet, verification, runtime, policy, public, and persistence
planes. Findings distinguish passing evidence, readiness warnings, and
release blockers. The release gate turns those findings and component states
into an explicit `promote`, `hold`, or `block` decision without merging any
member evidence.

The portable gate package contains exactly:

```text
manifest.json
assurance.json
gate.json
```

The manifest binds canonical bytes, byte hashes, file addresses, federation
linkage, and the gate address. Loads reject extra or missing files, symlinks,
noncanonical JSON, stale manifest addresses, byte tampering, stale findings,
and broken assurance/gate linkage. The query plane exposes `summary`,
`findings`, `blockers`, `warnings`, `checks`, and `failed` resources with
bounded severity, pass, required, plane, text, and paging filters. JSON, CSV,
and Markdown exports are deterministic and path-free.

The CLI family adds `...-federation-assurance-gate`, its query and verify
commands, and component schema/capability commands. The API mirrors these
resources below `/observatory/packet/registry/federation/assurance-gate`.
Required failures block, optional readiness failures hold, and only a fully
verified, warning-free federation can be promoted.

### Operational federation review routing and snapshot diffs

The review projection routes all 21 assurance findings and 15 release-gate
checks into one addressed operational queue. Passing records are `clear`;
optional failures become `review` with high priority; required failures become
`blocked` with critical priority. Queue counts conserve every source record,
and the queue remains accepted only when no blocker is present.

Review queues persist as exactly two canonical files:

```text
manifest.json
review.json
```

The manifest binds the queue address, canonical bytes, file address, and exact
file set. Loaders reject missing or extra files, symlinks, noncanonical JSON,
tampered bytes, stale manifest addresses, and stale item or queue addresses.
Snapshot diffs compare stable `(record_type, plane, kind)` keys and classify
`added`, `removed`, `unchanged`, or `changed` records, with explicit
`resolved_count` and `unchanged`/`improved`/`regressed`/`changed` snapshot
states. Queue and diff queries support bounded state, priority, action, pass,
record-type, plane, text, and paging filters with deterministic JSON, CSV, and
Markdown exports. The CLI and API expose build, verify, query, diff, schema,
and capability surfaces below the federation assurance-gate review boundary.
## Federation review decision ledger

The federation review decision ledger is the write-side operational layer for
the review queue. It preserves the immutable queue-item snapshot and records
bounded append-only adjudication entries. Each entry is addressed, chained to
the preceding head, and limited to one of five explicit actions:
`acknowledge`, `remediate`, `waive`, `escalate`, or `reopen`.

`remediate` requires an evidence address, `waive` is limited to non-critical
warning items, and `reopen` requires a prior closed decision. An optimistic
`--expected-head-address` guard prevents stale writers from forking the chain.
Decision replay exposes covered, open, closed, unreviewed, escalated, and
blocked counts. Closing operational items never promotes the source queue: the
original assurance gate remains authoritative and a non-ready source remains
non-ready until a new verified queue is supplied.

The portable package contains exactly `manifest.json`, `ledger.json`, and
`entries.json`, with canonical bytes, per-file receipts, entry-chain checks,
symlink rejection, and deterministic content addresses. Decision snapshots can
be compared as added, removed, unchanged, or changed rows, including explicit
open-to-closed resolutions.

Example commands:

```text
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions --input review-queue --destination decision-ledger --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-append --input decision-ledger --item-address ITEM_ADDRESS --action remediate --rationale "condition remediated" --evidence-address EVIDENCE_ADDRESS --destination decision-ledger-next
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-query --input decision-ledger --resource open --limit 50
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-diff --baseline decision-ledger --candidate decision-ledger-next --format markdown
```

The HTTP surface is nested under `/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decisions`, with read-only build, append projection, query, verify, diff, schema, and capabilities routes.

## Independent decision assurance and release gating

The decision-ledger assurance layer independently recomputes ledger linkage,
queue-item addresses, entry ancestry, evidence requirements, waiver policy,
count conservation, source readiness, and the public boundary. It emits 12
addressed findings and an 8-check release gate. Required failures block;
optional closure/readiness failures hold; only a warning-free, fully closed
ledger whose source queue was release-ready can promote.

Its exact handoff contains only:

```text
manifest.json
assurance.json
gate.json
```

The loader verifies canonical JSON, exact file membership, byte hashes, file
addresses, nested assurance/gate addresses, and manifest linkage. Queries can
select summary, findings, blockers, warnings, checks, or failed records with
bounded severity, pass, required, plane, text, and paging filters. The CLI
family is rooted at `...-review-decisions-assurance`; the HTTP surface reuses
the review decision prefix and adds assurance component schema and capability
routes. The layer is an independent release control and cannot promote a
non-ready source queue merely because its operational decisions are closed.

### Assurance snapshot diffs

Independent decision assurance gates can be compared without reusing either
snapshot's mutable state. The diff joins 12 assurance findings and 8 release
checks by stable plane/kind keys, then reports `added`, `removed`, `unchanged`,
and `changed` records together with `improved`, `regressed`, or mixed
`changed` outcome state. It compares semantic pass, severity, and requirement
fields while retaining both addressed snapshots for audit linkage.

Diffs are bounded and path-free, support action/plane/text filters with
deterministic paging, and export as JSON, CSV, or Markdown. Their portable
handoff is exactly `manifest.json` and `diff.json`; canonical bytes, byte
receipts, file membership, manifest linkage, and nested record addresses are
verified on reload. The CLI family is rooted at
`...-review-decisions-assurance-diff`, and the HTTP family is rooted at
`.../review/decisions/assurance-diff`.

## Longitudinal decision-assurance history

The assurance-history layer records repeated verified decision-assurance gates
as an append-only public projection. Each observation retains assurance, gate,
ledger, and source-queue addresses; conserved quality counts; an optimistic
previous-head link; and a transition classification of `initial`, `stable`,
`improved`, `regressed`, or `changed`. Gate state is projected as `ready`,
`held`, or `blocked`, preserving the difference between structural acceptance
and release readiness.

The history package contains exactly `manifest.json`, `history.json`, and
`entries.json`. Canonical bytes, file receipts, entry ancestry, unique
snapshot IDs, terminal state, counters, and public-boundary constraints are
verified on reload. An independent seven-check replay receipt validates the
chain without trusting stored aggregate fields. Bounded transition/state/text
queries and JSON/CSV/Markdown exports are exposed through
`...-review-decisions-assurance-history` and the HTTP
`.../review/decisions/assurance-history` route family. Multiple observations
can be built from persisted assurance gates, including real downloaded-data
rebuilds, without copying source paths into public output.

## Multi-history decision-assurance series

The assurance-history-series layer aggregates independently verified histories
into a deterministic, sorted public projection. It reports ready, held,
blocked, empty, and mixed history membership; conserves observation,
transition, acceptance, and release-readiness totals; and retains each
history's address and terminal projection. A series diff classifies history
membership as added, removed, unchanged, or changed and assigns improved or
regressed direction when the terminal gate state moves.

Series packages contain exactly `manifest.json`, `series.json`, and
`entries.json`. Independent eight-check replay, canonical-byte receipts,
manifest linkage, bounded history/state/text queries, and JSON/CSV/Markdown
exports are available through
`...-review-decisions-assurance-history-series` and its HTTP
`.../review/decisions/assurance-history-series` route family. The projection
is read-only over persisted histories and never exposes source paths or
private runtime metadata.

## History-series policy evaluation

The series policy layer converts a history-series projection into a bounded
operating decision. Policies can set minimum history and observation coverage,
maximum held and blocked populations, current acceptance and release-readiness
requirements, and whether mixed terminal states are allowed. Nine addressed
checks classify failures as required blockers or optional warnings, producing
passed, hold, or blocked outcomes with separate acceptance and release-ready
flags.

Policy evaluations contain exactly `manifest.json`, `policy.json`, and
`evaluation.json`. Canonical bytes, per-file receipts, nested policy/check
addresses, exact file membership, and manifest linkage are verified on reload.
The policy CLI and HTTP routes expose JSON/CSV/Markdown projections and
schemas/capabilities without exposing source paths or private runtime fields.

## Portable decision-assurance series release handoff

The release layer closes the series-to-policy-to-evaluation chain with eight
independently addressed stages: series replay, policy verification, evaluation
verification, component linkage, acceptance, release readiness, public-boundary
review, and transport-contract validation. Required failures block acceptance;
an optional readiness failure holds the handoff. The resulting state is ready,
hold, or blocked, with separate accepted and release-ready projections.

The portable package contains exactly `manifest.json`, `series.json`,
`policy.json`, `evaluation.json`, and `release.json`. Atomic writes, canonical
bytes, exact file membership, nested addresses, and manifest linkage are
verified on reload. A release diff compares the top-level receipt and every
closure stage, retaining baseline/candidate values and classifying added,
removed, unchanged, and changed records with improved or regressed direction.
Bounded release and diff queries plus JSON/CSV/Markdown, CLI, HTTP, schema,
capability, and public-surface audit projections are available without
exposing local paths or private runtime metadata.

## Release-package admission registry

The registry layer admits only independently verified series-release packages.
It sorts entries by stable package and release identifiers, rejects duplicate
package/release identities, retains package and release content addresses, and
conserves ready, hold, blocked, accepted, and release-ready populations. The
registry is a publication index, not a data merge, so nested series, policy,
and evaluation documents remain independently addressed.

The exact registry handoff is `manifest.json`, `entries.json`, and
`registry.json`; the exact registry diff handoff is `manifest.json` plus
`diff.json`. Both are atomic, canonical-byte, exact-file, path-free transports
with reload verification. Registry queries cover summary, membership, state,
acceptance, and readiness; registry diffs preserve stable package keys and
added/removed/unchanged/changed plus improved/regressed direction. CLI, HTTP,
schema, capability, and public-surface audit projections are included.

## Release-registry federation

The federation layer aggregates independently verified release registries as
addressed members. It preserves each registry's stable identity, package and
release receipts, terminal state, acceptance, and release-readiness values;
the underlying series, policy, evaluation, and release documents are never
merged into one scientific payload. Package keys are scoped by source registry
so identical package identifiers from different registries remain distinct,
while duplicate registry identities and duplicate source-scoped package
identities fail closed.

Federation admission recomputes member and package counts, ready/held/blocked
state totals, accepted totals, and release-ready totals. Seven independent
structural checks cover bounded membership, unique identities, package and
state conservation, readiness conservation, and public projection closure.
Seven policy checks cover minimum coverage, blocked and held budgets, blocked
state prevention, empty-federation policy, and release-readiness requirements.
Required policy failures block the federation; optional readiness failures
hold it. An empty federation is explicit and is accepted only when policy
allows it.

The runtime is a five-stage fail-closed closure: member admission, structural
verification, policy evaluation, readiness aggregation, and completion. Each
stage retains input/output addresses and a bounded state. The bundle cross-links
the federation, policy, verification, policy evaluation, and runtime receipts,
then exposes one accepted and one release-ready projection. A held federation
is accepted for review but is not release-ready; blocked input registries
remain blocked regardless of a permissive blocked-member budget.

The exact federation transport contains eight canonical UTF-8 documents:
`manifest.json`, `federation.json`, `members.json`, `packages.json`,
`policy.json`, `verification.json`, `policy-evaluation.json`, and
`runtime.json`. Writes are atomic and reject existing destinations unless
overwrite is explicit. Reload verification rejects missing or extra files,
directories and symlinks in the artifact set, non-canonical JSON, changed
bytes, invalid content addresses, mismatched split projections, nested
receipt drift, and public-boundary violations. The independent diff transport
contains exactly `manifest.json` and `diff.json` and classifies member/package
records as added, removed, unchanged, or changed with improved, regressed, or
changed readiness direction.

Bounded federation queries expose summary, members, packages, ready, held,
blocked, accepted, release-ready, verification checks, policy checks, and
runtime stages. Diff queries expose summary, actions, directions, and text
matches. Every query has an addressed request/result receipt, deterministic
ordering, offset/limit bounds, and JSON/CSV/Markdown renderings. The CLI
command family is the long-form
`module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry-federation`;
the matching HTTP family is the existing release-registry path with a
`/federation` suffix. Schema and capability commands describe the closed
public contracts and fixed file set without exposing local paths, users,
agents, models, languages, or nested private metadata.

## Independent federation assurance gate

The release-registry federation gate is a second, independent review boundary
over a persisted federation. It recomputes source federation integrity,
verification, policy, runtime, count conservation, state coherence, and the
path-free public boundary instead of trusting the source aggregate decision.
Ten addressed findings classify failures as blockers or warnings. A blocker
produces `block`; a warning produces `hold`; a clean assurance produces
`promote`. The release gate then applies eight independent checks, preserving
required-versus-optional failures and making acceptance and release readiness
explicit.

The portable gate package contains exactly three canonical UTF-8 documents:
`manifest.json`, `assurance.json`, and `gate.json`. Atomic writes reject
non-empty destinations unless overwrite is explicit. Reload checks exact file
membership, canonical bytes, stable content addresses, source linkage, and a
byte receipt for every data document. The public projection excludes local
paths, users, agents, models, languages, and private metadata.

Gate queries are bounded and deterministic. They expose summary, findings,
blockers, warnings, failed findings, checks, failed checks, required failures,
and optional failures, with plane, severity, passed, text, offset, and limit
filters. JSON, CSV, and Markdown outputs are available through the long-form
CLI command family and the `/release-registry/federation/gate` HTTP routes.
The gate command consumes an already persisted federation and can persist a
portable gate package for CI review or downstream release decisions.

## Operational federation gate review

The review layer turns a persisted release-registry federation gate into an
operator-facing queue without replacing the source gate. Every assurance
finding and every release-gate check becomes one stable, source-addressed
review item. Passing records are clear; failed optional records are high
priority review items; failed required records are critical blockers. The
queue retains record type, source identifier, plane, severity, requiredness,
evidence address, and the recomputed item address so a reviewer can explain
exactly which source assertion caused the route.

Review verification is independent of queue construction. It recomputes item
counts, finding/check coverage, source linkage, item addresses, initial
state/priority rules, public-boundary closure, source-gate authority, and
queue-address integrity. Verification readiness describes whether the review
projection is internally healthy; it does not promote a source gate that is
held or blocked. A held source therefore remains held while its review
package can still be structurally verified and routed.

The exact portable queue package is `manifest.json`, `queue.json`,
`items.json`, and `verification.json`. The manifest records exact canonical
UTF-8 byte receipts and the queue, gate, assurance, federation, and runtime
addresses. Atomic writes reject non-empty destinations without explicit
overwrite. Reload verification rejects missing or extra files, directories,
symlinks, non-canonical JSON, changed bytes, split-document drift, invalid
addresses, and public-boundary violations.

The append-only decision ledger freezes the queue item identities and records
acknowledge, remediate, waive, escalate, and reopen actions. Each entry has a
stable decision ID, item address, evidence address, rationale, predecessor
head, and content address. Remediation and waiver require a non-empty
evidence address. Required blockers cannot be waived. Every append supplies
the expected current head, so concurrent reviewers cannot silently fork a
decision chain. Replay derives item states from the queue and entries and
keeps source acceptance and source release readiness authoritative.

The exact ledger package is `manifest.json`, `ledger.json`, `entries.json`,
and `replay.json`. The decision diff is an analysis-only two-file package,
`manifest.json` plus `diff.json`, and classifies every stable item as added,
removed, unchanged, or changed with improved, regressed, or no direction.
Queue, decision, replay, and diff queries are bounded, deterministic, and
available as JSON, CSV, or Markdown. The long-form CLI and HTTP routes expose
build, verify, query, schema, capability, append, and diff operations. The
HTTP append route is POST-only and accepts a persisted ledger directory plus
an expected head; it optionally writes a new exact package to a destination.

## Review-state interpretation

| Source condition | Queue state | Review action | Ledger release-ready |
| --- | --- | --- | --- |
| all source findings and checks pass | `clear` | no action required | `true` |
| optional source failures exist | `review` | acknowledge, remediate, escalate, or evidence-backed waiver | remains source-controlled |
| required source failures exist | `blocked` | acknowledge, remediate, or escalate; waiver is rejected | `false` |

Ledger actions are operational records, not scientific edits. A remediation
entry can mark a review item resolved in the replay while the source gate
continues to report its original release decision. This preserves the audit
distinction between “an operator recorded handling” and “the source evidence
changed.” A new source gate and a new queue snapshot are required to change
the authoritative release result.

## Independent assurance of the review decision ledger

The release-registry federation review decision ledger now has an independent
assurance boundary. The boundary treats the persisted ledger as an untrusted
snapshot and recomputes its operational invariants. It is intentionally
separate from the source federation gate and from the ledger's own constructor
validation.

The assurance boundary consumes the current four-file ledger package and emits
an addressed assurance report plus an independent release gate. It does not
silently convert older observatory or federation artifacts. A downloaded
artifact is usable only when its exact version, boundary, files, canonical
bytes, and fields match the current review-ledger contract.

The independent report contains fourteen findings:

| # | Finding | Plane | Required | Purpose |
| ---: | --- | --- | :---: | --- |
| 0 | `ledger-address` | ledger | yes | recompute the ledger content address |
| 1 | `ledger-contract` | ledger | yes | enforce current version, boundary, and entry count |
| 2 | `queue-linkage` | queue | yes | retain queue, gate, assurance, and replay links |
| 3 | `item-addresses` | queue | yes | recompute unique frozen item addresses |
| 4 | `entry-chain` | entries | yes | verify ordinals, predecessor heads, and terminal head |
| 5 | `entry-item-linkage` | entries | yes | match every decision to exactly one frozen item |
| 6 | `action-counters` | ledger | yes | conserve counts across all five action types |
| 7 | `evidence-policy` | policy | yes | enforce evidence only for remediation and waiver |
| 8 | `transition-policy` | policy | yes | replay the action state machine independently |
| 9 | `replay-projection` | replay | yes | reproduce item states, counts, and readiness |
| 10 | `source-authority` | source | yes | prevent local handling from overriding source readiness |
| 11 | `closure-readiness` | policy | no | explain a valid but not-yet-promotable ledger |
| 12 | `public-boundary` | public | yes | reject forbidden nested keys and private metadata |
| 13 | `replay-addresses` | replay | yes | recompute replay-item and replay-snapshot addresses |

The assurance report distinguishes a blocker from a warning. Required failures
produce `blocked` and `accepted=false`. Optional failures produce `warning`
and `accepted=true`, but `release_ready=false`. No warning-free assertion is
made when an optional closure condition is false.

The independent release gate contains ten checks:

| # | Check | Required | Failed result |
| ---: | --- | :---: | --- |
| 0 | `assurance-accepted` | yes | block |
| 1 | `assurance-release-ready` | yes | block |
| 2 | `source-accepted` | yes | block |
| 3 | `source-release-ready` | no | hold |
| 4 | `ledger-clear` | no | hold |
| 5 | `no-open-items` | no | hold |
| 6 | `no-blocked-items` | yes | block |
| 7 | `no-escalated-items` | no | hold |
| 8 | `head-continuity` | yes | block |
| 9 | `public-boundary` | yes | block |

The gate states are deterministic:

| Required failures | Optional failures | Gate state | Release-ready |
| ---: | ---: | --- | :---: |
| 0 | 0 | `promote` | yes |
| 0 | 1 or more | `hold` | no |
| 1 or more | any | `block` | no |

This creates an important distinction between an accepted review record and a
promotable source decision. For example, a held source with a structurally
perfect ledger produces fourteen passing assurance findings, but the source
readiness gate check fails as an optional check and the independent gate stays
on hold. Recording remediation does not rewrite the source gate.

### Public data shape

The assurance projection contains only:

1. bounded identifiers;
2. fixed-vocabulary state, severity, plane, and action values;
3. content addresses;
4. bounded explanatory text;
5. counters and boolean outcomes; and
6. deterministic nested reports.

The public projection excludes local paths, user names, contact data, agent,
assistant, author, model, and language attributes, private metadata, secrets,
tokens, and runtime credentials. The public-surface audit closes ten new
schema/capability records and raises the expected closed inventory from 513 to
523.

### Durable package shape

The assurance package is exactly:

```text
manifest.json
assurance.json
gate.json
```

The manifest contains version, boundary, ledger linkage, assurance linkage,
gate linkage, the exact file list, byte counts, byte addresses, file addresses,
and a manifest address. Loaders reject missing files, extra files, symlinks,
non-canonical JSON, changed bytes, and split-document linkage.

The assurance diff package is exactly:

```text
manifest.json
diff.json
```

Diff records join findings and checks by their plane and kind. They retain
both snapshot addresses and classify records as added, removed, unchanged, or
changed. Outcome direction is independently reported as improved or regressed
when the pass/severity score changes.

## Longitudinal release-registry decision-assurance history

The release-registry federation gate review decision-ledger assurance history
module records a sequence of independently verified assurance gates as an
append-only, content-addressed timeline. Each entry retains the public source
gate, assurance, ledger, and snapshot addresses, the terminal state, the
release decision, and a transition classification relative to the prior entry.
The transition vocabulary is fixed: `initial`, `stable`, `improved`,
`regressed`, and `changed`.

The history builder accepts already persisted current-format assurance gates or
the upstream current-format decision ledgers after independent assurance is
recomputed. It rejects legacy directory shapes, duplicate snapshots, invalid
expected heads, unknown mapping keys, non-public fields, and non-conserved
counts. The history verifier replays the entry chain, recomputes the quality
comparison, checks the terminal projection, and verifies every content address.

History persistence is exactly `manifest.json`, `history.json`, and
`entries.json`. Diff persistence is exactly `manifest.json` and `diff.json`.
Writers use canonical UTF-8 JSON, atomic replacement, explicit overwrite
authorization, and path-free public projections. Loaders reject extra files,
symlinks, non-canonical bytes, manifest receipt drift, and legacy artifacts.

History queries expose bounded `summary`, `entries`, `initial`, `stable`,
`improved`, `regressed`, and `changed` resources with state, transition,
acceptance, readiness, and text filters. Diff queries expose bounded summary,
item, action, direction, gate-state, and text resources. All query results are
addressed and available through JSON, fixed-column CSV, and Markdown renderers.

The public API and CLI expose builders, verifiers, serializers, schemas, and
capabilities. The focused suite covers deterministic reruns, chain ancestry,
optimistic concurrency, every transition class, all diff actions and
directions, pagination, typed-boundary rejection, exact package files,
canonical-byte tampering, manifest tampering, extra-file rejection, legacy
download rejection, and current-format downloaded-data execution.

See [docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY.md](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY.md)
for the complete operator contract.

### Query and export behavior

Assurance queries expose `summary`, `findings`, `blockers`, `warnings`,
`checks`, and `failed`. Filters cover severity, pass state, requiredness,
plane, text, offset, and limit. Diff queries expose `summary`, `actions`,
`added`, `removed`, `changed`, `unchanged`, `improved`, and `regressed`, with
action, plane, and text filters.

The same projections are available as canonical JSON, fixed-column CSV, and
deterministic Markdown. Query windows are bounded to prevent accidental
unbounded export from a malformed or adversarial package.

### CLI and HTTP behavior

The long-form CLI command family supports assurance build, verify, query,
schemas, capabilities, diff, diff verify, and diff query operations. Build and
verify return zero only for a promoted gate. A held or blocked gate returns
status 2 while still emitting the structured result, allowing CI to preserve a
review artifact without treating a hold as an input parse failure.

The HTTP family mirrors those operations under the current review decision
ledger route. Build and verify return 200 for promotion and 422 for a held or
blocked gate. Structural errors remain client errors and never become a
promotable empty report.

### Verification behavior

The focused tests cover ready, held, and blocked source ledgers; deterministic
addresses; custom IDs; mapping round trips; every finding and check address;
tampered ledger, item, entry, counter, evidence, replay, source, and public
projections; independent transition replay; every query resource and filter;
exact three-file assurance persistence; exact two-file diff persistence;
canonical-byte and manifest tamper rejection; symlink and extra-file
rejection; CLI operations; HTTP operations; public-surface audit; and Actions
registration.

The existing preserved downloaded artifact from the prior observatory boundary
continues to demonstrate strict incompatibility. The current loader rejects it
as the wrong package shape rather than silently converting old fields. That
behavior is part of the public compatibility contract.

## Cross-run assurance-history observatory

The release-registry federation gate review decision-ledger assurance-history
observatory aggregates several current-format assurance histories while
retaining every history as a source-scoped member. It computes conserved entry,
transition, gate, finding, and check totals, folds member terminal posture into
an explicit `empty`, `ready`, `held`, `blocked`, or `mixed` state, and requires
conjunctive acceptance and readiness before promotion.

The package contains exactly `manifest.json`, `observatory.json`,
`members.json`, `verification.json`, and `metrics.json`. The loader verifies
canonical bytes, artifact receipts, exact file names, regular-file boundaries,
manifest linkage, independently recomputed eight-check verification, and
derived metrics. Diffs contain exactly `manifest.json` and `diff.json` and
compare stable member IDs with added, removed, unchanged, changed, improved,
regressed, and mixed classifications.

Bounded JSON, CSV, and Markdown projections are available through the Python
module, the long-form CLI, and the HTTP route appended to
`.../decision-ledger/assurance-history/observatory`. The downloaded-data demo
loads current persisted history packages, reloads its own output, and emits
path-free reports. The focused suite covers empty, ready, held, blocked, mixed,
deterministic, tamper, legacy-shape, exact-file, CLI, HTTP, and real downloaded
history behavior. Verification-query resources expose addressed summary,
checks, failed, required, and optional windows with severity, pass-state, text,
offset, and limit filters. See
[the observatory contract](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY.md)
for the operator contract and
[the test catalog](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_TEST_CATALOG.md)
for the full coverage map.
