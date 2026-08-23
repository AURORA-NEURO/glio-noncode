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
