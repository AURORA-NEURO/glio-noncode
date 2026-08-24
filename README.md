# GLIO-NONCODE

GLIO-NONCODE is a local-first research workbench for turning glioma non-coding variants and bounded structural events into inspectable regulatory hypotheses.

The first release slice is deliberately narrow and reproducible. It accepts a case manifest, canonical variant identities, context-qualified candidate regulatory elements, and typed numeric evidence inputs. It produces a dossier containing:

- decomposed variant → regulatory element → gene → cell-state paths;
- separate evidence claims for sequence, chromatin, topology, linking, state, cohort, and functional channels;
- explicit missing, negative, contradictory, out-of-domain, and abstained states;
- context transport and uncertainty for every claim;
- content-addressed inputs and outputs plus a hash-chained run event log;
- validation routes ranked by expected information gain and feasibility; and
- a research-use-only policy boundary with a human review gate.

This repository does not diagnose, classify clinical significance, recommend treatment, decide trial eligibility, or declare an individual variant actionable. A high-support hypothesis is a research object that requires expert review and independent validation.

## Quick start

```powershell
python -m pip install -e .
glio-noncode evaluate examples/case-small.json --output dossier.json
glio-noncode schema
glio-noncode sources
glio-noncode registry
glio-noncode bindings
glio-noncode references
glio-noncode capabilities
```

The same runtime can be served locally:

```powershell
glio-noncode serve --host 127.0.0.1 --port 8765
```

Then send the JSON manifest to `POST http://127.0.0.1:8765/v1/evaluate`. `GET /healthz` reports service health and `GET /v1/schema` returns the contract summary.

To enrich a manifest from bounded live public references, use:

```powershell
glio-noncode fetch-public examples/case-small.json --window-bp 2000 --output public-reference.json
glio-noncode evaluate examples/case-small.json --live-reference --window-bp 2000 --output live-dossier.json
```

Live retrieval is optional. Each request is rate-limited, retried only with unchanged semantics, cached locally, and recorded with source/version/URL/response hashes. A source failure remains a warning or abstention; it is never converted to a negative measurement.

To canonicalize an external variant file before constructing a case manifest:

```powershell
glio-noncode intake variants.vcf --source-id cohort-vcf --genome-build GRCh38 --output intake.json
```

The intake boundary accepts VCF, gVCF, TSV, JSON, and binary BCF, expands multiallelic records,
preserves source hashes and sample/INFO fields, skips no-call and reference-only
genotypes by default, and defers symbolic or breakend alleles to structural
reconstruction. The bounded role/tool registry is available with `registry`.

The product denominator and evidence-backed implementation ledger are documented
in [docs/CAPABILITIES.md](docs/CAPABILITIES.md). Regulatory tracks can be
parsed with `parse-track`, and supported small variants can be normalized with
`normalize`; both commands preserve explicit limitations and abstentions.

The full capability ledger can also be certified against the live checkout. The
certification resolves all implementation and test references, closes the 256-
row/16-domain denominator, and emits addressed JSON, CSV, Markdown, replay, and
negative-control projections:

```powershell
glio-noncode capability-certification
glio-noncode capability-certification-runtime --output capability-runtime.json
glio-noncode capability-certification-report --format markdown --output capability-report.md
glio-noncode capability-certification-query --domain-id D05
glio-noncode capability-certification-replay
glio-noncode capability-certification-failures
```

See [docs/CAPABILITY_CERTIFICATION.md](docs/CAPABILITY_CERTIFICATION.md) for
the row checks, global denominators, runtime stages, projection contract, and
extension rules.

The sixteen architecture domains can now be executed through one normalized
program runtime. It resolves and runs D01–D16, reconciles 172 domain/global
checks, preserves each domain's stage/evaluation/artifact denominators, scans
all public projections for private keys, and emits deterministic replay and
missing-reference controls:

```text
glio-noncode architecture-program-report --format markdown --output architecture-program-report.md
glio-noncode architecture-program-runtime --output architecture-program-runtime.json
glio-noncode architecture-program-summary
glio-noncode architecture-program-receipts-csv --output architecture-program-receipts.csv
glio-noncode architecture-program-checks-csv --output architecture-program-checks.csv
glio-noncode architecture-program-query --domain-id D08
glio-noncode architecture-program-replay
glio-noncode architecture-program-failures
```

See [docs/PROGRAM_RUNTIME.md](docs/PROGRAM_RUNTIME.md) for the stage contract,
public-boundary controls, denominators, closure artifact, and extension rules.

The D16 C13–C16 deployment-governance depth surface can be rehearsed locally
from its public aggregate fixture:

```powershell
glio-noncode deployment-frontier-data-audit --output deployment-data.json
glio-noncode deployment-frontier-evaluate --output deployment-evaluation.json
glio-noncode deployment-frontier-pipeline --output deployment-runtime.json
glio-noncode deployment-frontier-report --output deployment-report.md
```

The four operation boundaries, data dictionary, failure modes, and release
controls are documented in [docs/DEPLOYMENT_FRONTIER_OPERATIONS.md](docs/DEPLOYMENT_FRONTIER_OPERATIONS.md),
[docs/DEPLOYMENT_FRONTIER_DATA_DICTIONARY.md](docs/DEPLOYMENT_FRONTIER_DATA_DICTIONARY.md),
[docs/DEPLOYMENT_FRONTIER_FAILURE_MODES.md](docs/DEPLOYMENT_FRONTIER_FAILURE_MODES.md),
and [docs/DEPLOYMENT_FRONTIER_RELEASE.md](docs/DEPLOYMENT_FRONTIER_RELEASE.md).

The D13 C13–C16 validation-release frontier provides independent depth for
off-target risk, validation value-of-information planning, experiment package
manifests, and result-to-claim updates. It uses 16 aggregate planning rows,
80 row checks, 50 ordered runtime stages, and a checked-in public fixture:

```powershell
glio-noncode validation-release-frontier-data-audit --output validation-release-data.json
glio-noncode validation-release-frontier-evaluate --output validation-release-evaluation.json
glio-noncode validation-release-frontier-pipeline --output validation-release-runtime.json
glio-noncode validation-release-frontier-review-csv --output validation-release-review.csv
```

See [docs/VALIDATION_RELEASE_FRONTIER_OPERATIONS.md](docs/VALIDATION_RELEASE_FRONTIER_OPERATIONS.md),
[docs/VALIDATION_RELEASE_FRONTIER_DATA_DICTIONARY.md](docs/VALIDATION_RELEASE_FRONTIER_DATA_DICTIONARY.md),
[docs/VALIDATION_RELEASE_FRONTIER_FAILURE_MODES.md](docs/VALIDATION_RELEASE_FRONTIER_FAILURE_MODES.md),
and [docs/VALIDATION_RELEASE_FRONTIER_RELEASE.md](docs/VALIDATION_RELEASE_FRONTIER_RELEASE.md).
The callable surface is listed in [docs/VALIDATION_RELEASE_FRONTIER_API.md](docs/VALIDATION_RELEASE_FRONTIER_API.md),
with the release audit in [docs/VALIDATION_RELEASE_FRONTIER_CHECKLIST.md](docs/VALIDATION_RELEASE_FRONTIER_CHECKLIST.md).

The D14 C13–C16 evidence-release frontier now provides a dedicated lifecycle
boundary for evidence-tier reclassification, deprecation and supersession,
reproducibility bundles, and signed dossier verification. It uses 16 aggregate
rows, 81 deterministic checks, 53 ordered runtime stages, and five public HTTPS
source receipts:

```powershell
glio-noncode evidence-release-frontier-data-audit --output evidence-release-data.json
glio-noncode evidence-release-frontier-evaluate --output evidence-release-evaluation.json
glio-noncode evidence-release-frontier-pipeline --output evidence-release-runtime.json
glio-noncode evidence-release-frontier-review-csv --output evidence-release-review.csv
```

The operation, schema, failure, release, and data-boundary contracts are documented
in [docs/EVIDENCE_RELEASE_FRONTIER_OPERATIONS.md](docs/EVIDENCE_RELEASE_FRONTIER_OPERATIONS.md),
[docs/EVIDENCE_RELEASE_FRONTIER_API.md](docs/EVIDENCE_RELEASE_FRONTIER_API.md),
[docs/EVIDENCE_RELEASE_FRONTIER_SCHEMA.md](docs/EVIDENCE_RELEASE_FRONTIER_SCHEMA.md),
[docs/EVIDENCE_RELEASE_FRONTIER_FAILURE_MODES.md](docs/EVIDENCE_RELEASE_FRONTIER_FAILURE_MODES.md),
and [docs/EVIDENCE_RELEASE_FRONTIER_RELEASE.md](docs/EVIDENCE_RELEASE_FRONTIER_RELEASE.md).

The D15 C13–C16 workbench-release frontier provides an independent boundary for
structured review forms, report export, global search, and accessibility and
human-factors evaluation. It uses 16 public aggregate rows, 80 deterministic checks,
49 ordered runtime stages, and five HTTPS source receipts:

```powershell
glio-noncode workbench-release-frontier-data-audit --output workbench-release-data.json
glio-noncode workbench-release-frontier-evaluate --output workbench-release-evaluation.json
glio-noncode workbench-release-frontier-pipeline --output workbench-release-runtime.json
glio-noncode workbench-release-frontier-review-csv --output workbench-release-review.csv
```

The D13 C01–C04 validation-design frontier provides an independent planning
surface for evidence gaps, assay eligibility, MPRA packaging, and STARR-seq
packaging. It uses five public source receipts, sixteen balanced aggregate
scenarios, eighty row checks, and a seventy-nine-stage runtime with replay,
reconciliation, review routing, failure rehearsal, and release assurance.

```text
glio-noncode validation-design-frontier-data-audit --output validation-design-data.json
glio-noncode validation-design-frontier-evaluate --output validation-design-evaluation.json
glio-noncode validation-design-frontier-pipeline --output validation-design-runtime.json
glio-noncode validation-design-frontier-review-csv --output validation-design-review.csv
```

The planning boundary is public aggregate research use. It does not diagnose,
claim assay efficacy, infer individual outcomes, or establish causal certainty.

The D13 C05–C08 editing-design frontier independently covers CRISPRi/CRISPRa,
base-editing, prime-editing, and allele-specific reporter design. It executes
16 aggregate scenarios, 80 checks, 70 assurance planes, and a 79-stage runtime.

```text
glio-noncode editing-design-frontier-data-audit --output editing-design-data.json
glio-noncode editing-design-frontier-evaluate --output editing-design-evaluation.json
glio-noncode editing-design-frontier-pipeline --output editing-design-runtime.json
glio-noncode editing-design-frontier-review-csv --output editing-design-review.csv
```

The D13 C09–C12 planning frontier is an independent surface for model-system
eligibility, guide/oligo adaptation, deterministic controls and randomization,
and transparent power/replication estimates. It executes 16 public aggregate
scenarios, 80 row checks, 69 assurance planes, and a 28-stage runtime. It keeps
foreign context, malformed rows, missing target identity, empty evidence, and
replicate shortfalls visible as review boundaries.

```text
glio-noncode planning-frontier-data-audit --output planning-data.json
glio-noncode planning-frontier-evaluate --output planning-evaluation.json
glio-noncode planning-frontier-pipeline --output planning-runtime.json
glio-noncode planning-frontier-review-csv --output planning-review.csv
```

The planning surface is public aggregate research planning only. It does not
prove model fidelity, guide activity, assay validity, statistical certainty,
safety, clinical utility, or institutional approval. See the dedicated
[planning operations](docs/PLANNING_FRONTIER_OPERATIONS.md),
[schema](docs/PLANNING_FRONTIER_SCHEMA.md),
[failure modes](docs/PLANNING_FRONTIER_FAILURE_MODES.md),
[release](docs/PLANNING_FRONTIER_RELEASE.md), and
[runbook](docs/PLANNING_FRONTIER_RUNBOOK.md) notes.

The repository-wide module fabric closes the integration boundary across all
256 catalog capabilities and 16 domains. It resolves every declared
implementation and test reference, evaluates 32 public aggregate rows (one
positive and one held control per domain), emits 256 named record checks, and
rehearses a 20-stage runtime with source closure, lineage, replay, quality,
and release receipts:

```text
glio-noncode module-fabric-data-audit --output module-fabric-data.json
glio-noncode module-fabric-evaluate --output module-fabric-evaluation.json
glio-noncode module-fabric-depth --output module-fabric-depth.json
glio-noncode module-fabric-quality --output module-fabric-quality.json
glio-noncode module-fabric-runtime --output module-fabric-runtime.json
glio-noncode module-fabric-report --format markdown --output module-fabric-report.md
glio-noncode module-fabric-review-csv --output module-fabric-review.csv
glio-noncode module-fabric-ledger --output module-fabric-ledger.json
glio-noncode module-fabric-ledger-audit --output module-fabric-ledger-audit.json
glio-noncode module-fabric-recovery --output module-fabric-recovery.json
```

The operational ledger retains 20 ordered stage receipts, conserved 32-row
denominators, and explicit 16-positive / 16-review counts without copying raw
fixture payloads. Its recovery output routes held controls to manual review and
cannot promote them automatically. See the [module-fabric operations notes](docs/MODULE_FABRIC_OPERATIONS.md),
[ledger notes](docs/MODULE_FABRIC_OPERATIONS_LEDGER.md),
[schema](docs/MODULE_FABRIC_SCHEMA.md), and
[release gates](docs/MODULE_FABRIC_RELEASE.md).

The module fabric audits repository wiring only. It does not infer biological
truth, validate clinical utility, authorize deployment, or copy private
subject data. Its checked-in public aggregate fixture is
[examples/module-fabric-public-aggregate.json](examples/module-fabric-public-aggregate.json).
The [operations](docs/MODULE_FABRIC_OPERATIONS.md),
[schema](docs/MODULE_FABRIC_SCHEMA.md), and
[release](docs/MODULE_FABRIC_RELEASE.md) documents define its bounded use.

The D16 coordination architecture now composes all 16 platform-control
capabilities into one functional public-aggregate runtime. It contains 16
dependency-ordered operations, 64 positive/control cases, 20 runtime stages,
112 seven-plane validation cells, a 64-event hash chain, offline deployment
artifacts, federated assignment receipts, and release/rollback gates:

```text
glio-noncode coordination-fixture --output coordination.json
glio-noncode coordination-data-audit --input coordination.json
glio-noncode coordination-runtime --output coordination-runtime.json
glio-noncode coordination-quality --output coordination-quality.json
glio-noncode coordination-depth --output coordination-depth.json
glio-noncode coordination-validation --output coordination-validation.json
glio-noncode coordination-runbook --output coordination-runbook.json
glio-noncode coordination-review-csv --output coordination-review.csv
glio-noncode coordination-query --state review --output coordination-review.json
glio-noncode coordination-failures --output coordination-failures.json
```

The [coordination operations](docs/COORDINATION_ARCHITECTURE_OPERATIONS.md),
[schema](docs/COORDINATION_ARCHITECTURE_SCHEMA.md),
[runbook](docs/COORDINATION_ARCHITECTURE_RUNBOOK.md), and
[release gate](docs/COORDINATION_ARCHITECTURE_RELEASE.md) documents define the
runtime boundary. The checked-in fixture is
[examples/coordination-architecture-public-aggregate.json](examples/coordination-architecture-public-aggregate.json).

The D01 variant identity and intake architecture now provides a complete
public-aggregate intake boundary over the first sixteen capabilities. It has
six HTTPS source receipts, sixteen dependency-ordered operations, sixty-four
balanced cases, seven validation planes, twenty runtime stages, a sixty-four
event hash-linked receipt ledger, five offline bundle artifacts, deterministic
replay, and explicit release rollback metadata:

```text
glio-noncode intake-architecture-fixture --output intake-architecture.json
glio-noncode intake-architecture-data-audit --input intake-architecture.json
glio-noncode intake-architecture-plan --input intake-architecture.json
glio-noncode intake-architecture-evaluate --input intake-architecture.json
glio-noncode intake-architecture-runtime --input intake-architecture.json --output intake-runtime.json
glio-noncode intake-architecture-quality --input intake-architecture.json
glio-noncode intake-architecture-depth --input intake-architecture.json
glio-noncode intake-architecture-validation --input intake-architecture.json
glio-noncode intake-architecture-replay --input intake-architecture.json
glio-noncode intake-architecture-review-csv --input intake-architecture.json
glio-noncode intake-architecture-report --input intake-architecture.json --format markdown
```

The implementation composes the canonical VCF/BCF/gVCF intake parser,
regulatory-track parser, VRS-shaped normalizer, categorical normalizer,
multi-allelic decomposer, repeat-aware normalizer, and source-qualified
identity resolver. Malformed, foreign-context, and duplicate-identity rows are
held for review with their original content addresses. The boundary contains
public identifiers and aggregate receipts only; it does not establish specimen
custody, biological authentication, clinical interpretation, or individual
outcomes. See the [D01 operations](docs/INTAKE_ARCHITECTURE_OPERATIONS.md),
[schema](docs/INTAKE_ARCHITECTURE_SCHEMA.md),
[runbook](docs/INTAKE_ARCHITECTURE_RUNBOOK.md), and
[release gate](docs/INTAKE_ARCHITECTURE_RELEASE.md) documents. The checked-in
fixture manifest is
[examples/intake-architecture-public-aggregate.json](examples/intake-architecture-public-aggregate.json).

See [docs/WORKBENCH_RELEASE_FRONTIER_OPERATIONS.md](docs/WORKBENCH_RELEASE_FRONTIER_OPERATIONS.md),
[docs/WORKBENCH_RELEASE_FRONTIER_API.md](docs/WORKBENCH_RELEASE_FRONTIER_API.md),
[docs/WORKBENCH_RELEASE_FRONTIER_SCHEMA.md](docs/WORKBENCH_RELEASE_FRONTIER_SCHEMA.md),
[docs/WORKBENCH_RELEASE_FRONTIER_FAILURE_MODES.md](docs/WORKBENCH_RELEASE_FRONTIER_FAILURE_MODES.md),
and [docs/WORKBENCH_RELEASE_FRONTIER_RUNBOOK.md](docs/WORKBENCH_RELEASE_FRONTIER_RUNBOOK.md).

## Design boundaries

The system treats a scalar score as a view, not as the ontology. Evidence is append-only, source dependence is grouped before aggregation, context transport is visible, and missing evidence is never silently converted to a negative result. Structural variation is represented as a first-class input kind even though the initial fixture focuses on a point variant.

Scientific quantities in this slice are deterministic transformations of supplied observations. The runtime does not invent measurements, claim that a generic annotation proves a glioma mechanism, or hide unsupported inputs behind a narrative.

## Repository layout

```text
src/glio_noncode/       typed domain, runtime, API, storage, and reports
schemas/                machine-readable public contract
examples/               small reproducible case manifest
tests/                  unit and integration coverage
docs/                   architecture, contribution, and release-boundary notes
.github/workflows/      automated quality checks
```

## Development

```powershell
python -m unittest discover -s tests -t . -v
python -m compileall -q src tests
```

The project uses only the Python standard library at runtime. Optional development tools may be added later behind explicit lockfiles and reproducibility checks.
