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
glio-noncode evaluate-batch examples/case-small.json --output batch-result.json
glio-noncode schema
glio-noncode sources
glio-noncode registry
glio-noncode bindings
glio-noncode references
glio-noncode capabilities
```

To inspect a downloaded ZIP as bounded data, with explicit member selection,
lineage, replay, audits, queries, and snapshot diffs, run
`python examples/downloaded_data_ingestion_demo.py` against the downloaded
archive. The complete workflow and HTTP surface are documented in
[docs/DOWNLOADED_DATA_INGESTION.md](docs/DOWNLOADED_DATA_INGESTION.md).
For the value-free schema-contract demo, run
`python examples/downloaded_data_contract_demo.py` against the same archive.
For a real value-free schema-evolution comparison over two member selections,
run `python examples/downloaded_data_contract_diff_demo.py` against the same
archive; it reports structural additions, removals, changes, queries, and
audited exact-file runtime output.
For policy-governed compatibility decisions over that diff, run
`python examples/downloaded_data_contract_compatibility_demo.py` against the
same archive; it reports safe/review/breaking counts, independent audits, and
an exact seven-file value-free runtime handoff.
For deterministic remediation actions over those compatibility findings, run
`python examples/downloaded_data_contract_remediation_demo.py` against the
same archive; it reports required none/review/repair/migrate/restore/investigate
actions, bounded queries, independent audits, and the exact seven-file plan
runtime.
For value-free resolution and closure tracking after review, run
`python examples/downloaded_data_contract_resolution_demo.py` against the
same archive; it reports pending/resolved/waived/rejected dispositions,
required open actions, release state, independent audits, and the exact
seven-file resolution runtime.
For longitudinal value-free resolution history over real downloaded data, run
`python examples/downloaded_data_contract_resolution_history_demo.py` against
the same archive; it records addressed initial/improved/regressed/unchanged
snapshots and emits an exact six-file history runtime.
To compare two history handoffs deeply, run
`python examples/downloaded_data_contract_resolution_history_diff_demo.py`;
it reports added/removed/changed/unchanged entries, transition deltas,
independent audits, bounded queries, and an exact six-file diff runtime.
For a policy-governed release decision over that diff, run
`python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`;
it reports explicit promote/hold/block rules, independent policy and runtime
audits, bounded rule queries, an exact eight-file review runtime, and a
portable five-file policy-review package with independent package audits. Two
or more package handoffs can then be admitted to a four-file registry for
readiness and decision queries.
For a transportable handoff of the cross-history observatory, run
`python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
against the same archive; it emits a deterministic six-member ZIP archive,
strict archive verification, a 17-check archive audit, bounded archive queries,
and a 12-check query audit. See
[docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE.md](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE.md).

The same runtime can be served locally:

```powershell
glio-noncode serve --host 127.0.0.1 --port 8765
```

Loopback is the safe default. For an institutional or private-network bind,
generate an explicit authenticated deployment profile and keep credentials in
a separate file:

```powershell
glio-noncode deployment-profile --profile-id glio-institutional --host 10.0.0.12 --exposure private_network --authentication api_key --principal-id institutional-operator --output deployment-profile.json
glio-noncode serve --host 10.0.0.12 --deployment-profile deployment-profile.json --api-key-file deployment-credentials.json --audit-root deployment-audit
```

Non-loopback profiles require API-key authentication, TLS intent, auditing, and
declared principals. The API exposes a redacted hash-chained audit ledger at
`GET /v1/deployment/audit`, durable store status at
`GET /v1/deployment/audit/status`, and requires an explicit `--audit-root` so
restart/replay verification and retention enforcement remain available. Both
the profile and profile schema are included in the repository-wide
public-surface audit. See [deployment profiles](docs/DEPLOYMENT_PROFILES.md).

Then send the JSON manifest to `POST http://127.0.0.1:8765/v1/evaluate` or a manifest list to `POST http://127.0.0.1:8765/v1/evaluate-batch`. `GET /healthz` reports service health and `GET /v1/schema` returns the contract summary. The certified capability and architecture surfaces are available from `GET /v1/status`, `GET /v1/capabilities`, `GET /v1/architecture/program`, `GET /v1/architecture/operational`, and `GET /v1/architecture/diff`. Persisted case runs can be listed, reopened, verified, queried, searched across runs, assigned, and reviewed through the `/v1/runs/{run_id}` projections, `GET /v1/search`, `GET /v1/search/closure`, `GET /v1/batches`, `GET /v1/batches/{batch_id}`, `GET /v1/review-queue`, `GET /v1/review-queue/closure`, `GET /v1/review-operations`, `GET /v1/review-operations/closure`, `POST /v1/runs/{run_id}/assignment`, and `POST /v1/runs/{run_id}/review`; see [docs/SERVICE_SURFACE.md](docs/SERVICE_SURFACE.md) for query parameters and offline closures.

To enrich a manifest from bounded live public references, use:

```powershell
glio-noncode fetch-public examples/case-small.json --window-bp 2000 --output public-reference.json
glio-noncode evaluate examples/case-small.json --live-reference --window-bp 2000 --output live-dossier.json
glio-noncode evaluate-batch examples/case-small.json --data-root .glio --output batch-result.json
glio-noncode batch-catalog --data-root .glio --output batch-catalog.json
glio-noncode batch-release batch-<content-digest> --data-root .glio --output batch-release
glio-noncode batch-release-verify batch-release --output batch-release-verification.json
```

Batch evaluation isolates each manifest. Successful items retain their normal
persisted run and dossier addresses; failed items retain their position, input
address, and explicit error category. The batch remains rejected when any item
fails, and identical canonical input reopens the existing content-addressed
batch result.

Batch handoffs can be copied offline. They include a private-key-filtered input
projection and result object, summary and gate evidence, item/failure/run CSVs,
and Markdown, with byte-level artifact verification and a blocked state for
partial batches.

To inspect locally persisted runs and their replay evidence:

```powershell
glio-noncode run-catalog --data-root .glio
glio-noncode run-inspect run-<run-id> --data-root .glio --output run-inspection.json
glio-noncode run-portfolio --data-root .glio --as-of 2026-09-01T12:00:00Z --output run-portfolio.json
glio-noncode run-portfolio --data-root .glio --closure --as-of 2026-09-01T12:00:00Z --output run-portfolio-closure.json
glio-noncode portfolio-release --data-root .glio --release-ready-only --as-of 2026-09-01T12:00:00Z --destination portfolio-release
glio-noncode portfolio-release-verify portfolio-release --output portfolio-release-verification.json
glio-noncode portfolio-release-query portfolio-release --artifact-kind workspace --output workspace-artifacts.json
glio-noncode portfolio-release-lineage portfolio-release --output portfolio-lineage.json
glio-noncode portfolio-release-observability portfolio-release --format metrics-csv --output portfolio-metrics.csv
glio-noncode portfolio-release-schema --output portfolio-release-schema.json
glio-noncode portfolio-release-runtime --data-root .glio --release-ready-only --output portfolio-runtime.json
glio-noncode storage-audit --data-root .glio --output storage-audit.json
glio-noncode storage-maintenance --data-root .glio --format markdown --output storage-maintenance.md
glio-noncode storage-catalog --data-root .glio --format markdown --output storage-catalog.md
glio-noncode storage-catalog-observability --data-root .glio --format metrics-csv --output storage-catalog-metrics.csv
glio-noncode storage-catalog-packet --data-root .glio --destination storage-catalog-packet
glio-noncode storage-catalog-packet-verify storage-catalog-packet --output storage-catalog-verification.json
glio-noncode run-search --data-root .glio --query enhancer --resource hypotheses --output search.json
glio-noncode run-search --data-root .glio --resource evidence --state supported --closure --output evidence-search-closure.json
glio-noncode run-review run-<run-id> review.json --data-root .glio --output reviewed-dossier.json
glio-noncode run-query run-<run-id> evidence --state supported --data-root .glio --output supported-evidence.json
glio-noncode run-query run-<run-id> lineage --data-root .glio --output run-lineage.json
glio-noncode run-query run-<run-id> closure --data-root .glio --output dossier-query-closure.json
glio-noncode run-history run-<run-id> --data-root .glio --output run-history.json
glio-noncode run-compare run-<run-id> run-<run-id> --source-snapshot 0 --target-snapshot 1 --data-root .glio --output review-transition.json
glio-noncode run-compare-release run-<run-id> run-<run-id> --source-snapshot 0 --target-snapshot 1 --data-root .glio --output comparison-release
glio-noncode review-queue --data-root .glio --scope open --output review-queue.json
glio-noncode review-queue --data-root .glio --closure --output review-queue-closure.json
glio-noncode review-operations --data-root .glio --as-of 2026-09-01T12:00:00Z --output review-operations.json
glio-noncode review-operations --data-root .glio --closure --as-of 2026-09-01T12:00:00Z --output review-operations-closure.json
glio-noncode review-assign run-<run-id> assignment.json --data-root .glio --output assignment-result.json
```

The review queue is a deterministic operational projection over persisted runs.
It prioritizes integrity blocks, pending or returned reviews, missing reviews,
warnings, uncertainty, abstained evidence, and unassigned work while retaining
explicit filters and content addresses. Assignments are append-only events, so
reviewer, queue, due-time, and note metadata remain replayable rather than
replacing the run history.

The review-operations projection adds reproducible SLA state to that queue:
overdue, due-soon, scheduled, undated, and invalid due dates are separated;
case age and remaining time are explicit; and reviewer/queue workload rows show
open, blocked, critical, overdue, and completed counts. Pass `--as-of` when
producing a handoff so the same persisted inputs produce the same operational
report.

Cross-run search replays persisted runs before exposing their public dossier
projections. It can find hypotheses, evidence claims, validation routes,
reviews, and run summaries with deterministic ranking and filters. Corrupt runs
remain visible as blocked operational evidence without leaking their scientific
records; a complete search closure is suitable for offline handoff.

The run portfolio joins replay integrity, review/SLA state, workspace history,
and portable release readiness for every persisted run. It is useful for
operator triage and offline handoff planning: a pending-review run remains
inspectable, while its release is explicitly held until the human-review gate
passes. The fixed `--as-of` timestamp makes due-state and portfolio addresses
reproducible.

`storage-audit` checks the complete local object store and run/batch indexes for
canonical bytes, content-address drift, missing references, orphan objects,
unexpected files, and replay failures. It is read-only and emits operational
metadata rather than stored case payloads.

`storage-maintenance` turns that audit into a bounded, deterministic,
review-only action ledger. It can query actions by kind, severity, text, or
reversibility and export JSON, CSV, or Markdown. It never deletes, quarantines,
rewrites, restores, or replays anything; an external approval and execution
boundary remains required. Use `storage-maintenance-verify` for strict plan
validation, `storage-maintenance-diff` to compare two saved plans, and
`storage-maintenance-packet` to create an independently verifiable offline
handoff.

For deeper operations, `storage-maintenance-observability` emits timestamp-free
events and aggregate metrics, while `storage-maintenance-review` emits a
priority-ordered queue with explicit recovery, repair, replay, reopen, and
quarantine routes. These are read-only projections and are included in the
exact-byte maintenance packet.

`storage-lineage` projects the store audit into a deterministic, address-only
graph of run/batch roots, object references, missing addresses, and orphan
objects. It supports bounded node/edge queries, structural diffs, CSV and
Markdown exports, and strict graph verification. The companion
`storage-lineage-observability` and `storage-lineage-review` commands expose
timestamp-free events, graph health metrics, and prioritized non-mutating review
recommendations. `storage-lineage-packet` creates a fixed ten-artifact,
exact-byte offline handoff; its verifier rejects path, byte, identity, and
public-boundary drift before hydration.

`storage-catalog` is the normalized indexed read model over that audit. It
unifies object, missing-reference, run, batch, and unexpected filesystem rows,
then closes address, path, kind, and state indexes for bounded deterministic
queries. Its observability plane emits timestamp-free events and aggregate
metrics for row quality and index coverage. `storage-catalog-packet` creates a
fixed ten-artifact offline handoff whose verifier checks exact bytes, identities,
safe paths, unexpected files, and the public metadata boundary before loading.
See [docs/STORAGE_CATALOG.md](docs/STORAGE_CATALOG.md) for the complete
contract and route matrix.

`portfolio-release` is the repository-wide handoff boundary. It selects a
bounded set of persisted runs, retains a namespaced dossier and workspace
release closure for every member, emits run summaries/events, CSV and Markdown
reports, and keeps blocked members visible with their failed gate identifiers.
The package is accepted only when every selected member passes replay, human
review, dossier, workspace, artifact, and public-boundary checks. Its verifier
rejects tampering, unsafe or unexpected paths, address drift, missing member
artifacts, invalid manifest counts, and prohibited private, attribution, or
language metadata. `portfolio-release-query` and `portfolio-release-diff`
operate on verified directories without reopening the source store.

The history-diff recovery plan also has a verifiable [execution receipt](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_HISTORY_DIFF_ARCHIVE_TRANSFER_RECOVERY_EXECUTION.md). It records applied, pending, and rejected chunk outcomes; derives planned, in-progress, complete, or blocked state; preserves byte/index conservation; supports assembler-backed progress; and exposes independent 18-check execution and 12-check query audits through CLI, local HTTP, schema, capability, and public inventory surfaces. The downloaded-ZIP demo persists canonical receipt, negative-control, audit, query, and query-audit artifacts without source paths, payload bytes, agent metadata, or language metadata.

Live retrieval is optional. Each request is rate-limited, retried only with unchanged semantics, cached locally, and recorded with source/version/URL/response hashes. A source failure remains a warning or abstention; it is never converted to a negative measurement.

To canonicalize an external variant file before constructing a case manifest:

```powershell
glio-noncode intake variants.vcf --source-id cohort-vcf --genome-build GRCh38 --output intake.json
```

The intake boundary accepts VCF, gVCF, TSV, JSON, and binary BCF, expands multiallelic records,
preserves source hashes and sample/INFO fields, skips no-call and reference-only
genotypes by default, and defers symbolic or breakend alleles to structural
reconstruction. The bounded role/tool registry is available with `registry`.

For larger variant sources, the streaming boundary reads VCF one line at a time
and raw or BGZF BCF one byte block at a time while retaining a bounded result
set and a complete input address:

```powershell
glio-noncode stream-variants variants.vcf --source-id cohort-vcf --output streaming.json
glio-noncode stream-variants variants.bcf --input-format bcf --output streaming-bcf.json
glio-noncode normalize-breakend 7 100 'G]17:198982]' --output breakend.json
glio-noncode streaming-intake-schema
```

Breakend mate coordinates, bracket orientation, deferred structural status,
source row hashes, duplicate accounting, and resource ceilings are visible in
the streaming receipt. The matching raw-body API is `POST /v1/intake/stream`;
see [docs/STREAMING_VARIANT_IMPORT.md](docs/STREAMING_VARIANT_IMPORT.md) for
the full CLI, API, and limitation contract.

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
glio-noncode capability-certification-bundle --destination capability-certification-bundle --output capability-certification-bundle.json
glio-noncode capability-certification-bundle-verify capability-certification-bundle --output capability-certification-bundle-verification.json
glio-noncode capability-certification-bundle-query capability-certification-bundle --resource certificates --domain-id D05
glio-noncode capability-certification-bundle-observability capability-certification-bundle --format metrics-csv --output capability-certification-metrics.csv
glio-noncode capability-certification-bundle-schema --output capability-certification-bundle-schema.json
glio-noncode capability-certification-bundle-runtime --output capability-certification-bundle-runtime.json
glio-noncode capability-certification-bundle-audit capability-certification-bundle --output capability-certification-bundle-audit.json
glio-noncode public-surface-audit --output public-surface-audit.json
```

The service-release registry is the top-level aggregate handoff for the public
service. It composes the accepted capability, architecture, operational, and
D01-D16 program-release surfaces into six registry rows, 13 exact-byte
artifacts, 15 dependencies, 24 gates, 78 observability events, 24 metrics,
five reviewer views, eight negative controls, and a fourteen-stage replayable
runtime:

```text
glio-noncode service-release --plane snapshot --output service-release.json
glio-noncode service-release --plane query --resource gates --accepted --output service-release-gates.json
glio-noncode service-release --plane runtime --output service-release-runtime.json
glio-noncode service-release --plane export --destination service-release-export --output service-release-export.json
glio-noncode service-release-export-verify service-release-export --output service-release-verification.json
```

The durable service-release handoff adds a versioned, independently verified
filesystem boundary over the same 13 aggregate artifacts:

```text
glio-noncode service-release-handoff --plane build --destination service-release-handoff --output service-release-handoff.json
glio-noncode service-release-handoff --plane verify --directory service-release-handoff --output service-release-handoff-verification.json
glio-noncode service-release-handoff --plane query --directory service-release-handoff --surface-id program-release
glio-noncode service-release-handoff --plane replay --directory service-release-handoff
glio-noncode service-release-handoff-verify service-release-handoff
```

See [docs/SERVICE_RELEASE_REGISTRY.md](docs/SERVICE_RELEASE_REGISTRY.md) for
atomic writes, manifest inspection, bounded queries, address-only diffs,
replay receipts, symlink controls, and public-boundary verification.

See [docs/SERVICE_RELEASE_REGISTRY.md](docs/SERVICE_RELEASE_REGISTRY.md) for
the full API, schema, query, export, reconciliation, negative-control, and
replay contracts.

The whole-product release-assurance gate joins the capability catalog,
sixteen-domain architecture program, public service-release registry, and
repository public-surface audit into one addressed readiness decision. It
closes four domains, 20 evidence links, 28 checks, 48 observability events, 16
metrics, 53 graph nodes, 20 plan steps, four reviewer views, eight negative
controls, 12 replay stages, and 10 exact-byte export artifacts. It also offers
independent reconciliation, address-only diffing, a ten-resource catalog,
boundary compliance, structural budgets, an operator queue, and a reviewer
report, portable checkpoint, and reviewer queue:

```text
glio-noncode release-assurance --plane snapshot --output release-assurance.json
glio-noncode release-assurance --plane status --output release-status.json
glio-noncode release-assurance --plane query --resource checks --passed-only
glio-noncode release-assurance --plane runtime --output release-runtime.json
glio-noncode release-assurance --plane export --destination release-assurance-export
glio-noncode release-assurance-export-verify release-assurance-export
```

Append-only release history is available with
`glio-noncode release-assurance --plane history --format markdown` and
`GET /v1/release-assurance/history`.
Explicit readiness thresholds are available with
`glio-noncode release-assurance --plane thresholds` and
`GET /v1/release-assurance/thresholds`.

The durable handoff packages 19 aggregate artifacts for offline transfer and
verification:

```text
glio-noncode release-assurance-handoff --plane build --destination release-assurance-handoff
glio-noncode release-assurance-handoff --plane verify --directory release-assurance-handoff
glio-noncode release-assurance-handoff --plane query --directory release-assurance-handoff --role runtime
glio-noncode release-assurance-handoff --plane replay --directory release-assurance-handoff
glio-noncode release-assurance-handoff-verify release-assurance-handoff
```

See [docs/RELEASE_ASSURANCE.md](docs/RELEASE_ASSURANCE.md) for the manifest,
atomic write, query, diff, replay, and tamper-verification contract.

The final cross-plane release attestation binds the accepted whole-product
release-assurance runtime, the D01-D16 program-release closure, and the
mission-plan release catalog gate by immutable addresses. It retains three
component rows and 26 acceptance checks, runs an eight-stage deterministic
replay, exports a seven-payload plus manifest packet, and supports bounded
queries, address-only diffs, aggregate observability, strict hydration, and
fail-closed exact-byte verification. A longitudinal registry now chains
accepted attestation summaries into a bounded, address-only history with
initial, advance, repeat, and blocked transition states. The registry can be
replayed, queried, compared, exported, and verified offline:

```text
glio-noncode release-assurance-attestation --plane attestation --format markdown --output attestation.md
glio-noncode release-assurance-attestation --plane runtime --output attestation-runtime.json
glio-noncode release-assurance-attestation --plane query --resource checks --passed-only
glio-noncode release-assurance-attestation --plane packet --destination release-assurance-attestation-packet
glio-noncode release-assurance-attestation-packet-verify release-assurance-attestation-packet
glio-noncode release-assurance-attestation --plane capabilities
glio-noncode release-assurance-attestation --plane registry --registry-id release-history
glio-noncode release-assurance-attestation --plane registry-query --registry-resource transitions --transition-state advance
glio-noncode release-assurance-attestation --plane registry-diff --format markdown
glio-noncode release-assurance-attestation --plane registry-packet --registry-id release-history --destination release-history-packet
glio-noncode release-assurance-attestation-registry-packet-verify release-history-packet
glio-noncode release-assurance-attestation --plane registry-store --store-id release-history-store
glio-noncode release-assurance-attestation --plane registry-store-append --store-id release-history-store
glio-noncode release-assurance-attestation --plane registry-store-audit --store-id release-history-store
glio-noncode release-assurance-attestation --plane registry-store-packet --store-id release-history-store --destination release-history-store-packet
glio-noncode release-assurance-attestation-registry-store-packet-verify release-history-store-packet
glio-noncode release-assurance-attestation --plane registry-store-gate --store-id release-history-store --gate-no-packet
glio-noncode release-assurance-attestation --plane registry-store-gate-query --store-id release-history-store --gate-no-packet --failed-only
glio-noncode release-assurance-attestation --plane registry-store-gate-plan --store-id release-history-store --gate-no-packet
glio-noncode release-assurance-attestation --plane registry-store-gate-packet --store-id release-history-store --gate-no-packet --destination release-history-store-gate-packet
glio-noncode release-assurance-attestation-registry-store-gate-packet-verify release-history-store-gate-packet
```

The read-only API is rooted at `/v1/release-assurance/attestation` and adds
runtime, packet metadata, schema, capabilities, query, diff, observability,
and packet-verification routes, including the longitudinal registry under
`/registry`. POST verification, query, diff, replay, and registry routes
rehydrate only public aggregate projections and never execute handlers.

The operational registry store adds policy-checked append, optimistic head
checks, duplicate rejection, idempotent retry handling, bounded batch append,
operation history, audit, replay, and store diffs. Its public JSON, CSV, and
Markdown projections contain only decisions and addresses.
Store packets make the same state portable through eight exact UTF-8 payloads
plus a manifest, atomic writes, exact-byte verification, and offline hydration
after acceptance.

The store promotion gate evaluates a fixed 20-check denominator across identity,
acceptance, capacity, audit integrity, operation history, packet verification,
baseline continuity, and public-boundary safety. It emits `ready/promote`,
`hold/retain`, or `blocked/block-release`, supports bounded failed-check queries,
and provides an append preflight plan and state diff. Release policy requires an
accepted exact-byte packet by default; `--gate-no-packet` is intended only for
local structural checks.
The gate packet serializes the accepted or held decision into six exact UTF-8
payloads plus its manifest for offline review and archiving.

The matching read-only API starts at `GET /v1/release-assurance` and includes
status, bounded queries, schema, indexes, summaries, observability, graph,
negative controls, plan, views, runtime, and export routes. See
[docs/RELEASE_ASSURANCE.md](docs/RELEASE_ASSURANCE.md) for denominators,
replay semantics, the public boundary, and extension rules.

See [docs/CAPABILITY_CERTIFICATION.md](docs/CAPABILITY_CERTIFICATION.md) for
the row checks, global denominators, runtime stages, offline bundle contract,
projection contract, and extension rules.

The sixteen architecture domains can now be executed through one normalized
program runtime. It resolves and runs D01–D16, reconciles 172 domain/global
checks, preserves each domain's stage/evaluation/artifact denominators, scans
all public projections for private keys, and emits deterministic replay and
missing-reference controls:

```text
glio-noncode architecture-program-report --format markdown --output architecture-program-report.md
glio-noncode architecture-program-runtime --output architecture-program-runtime.json
glio-noncode architecture-program-operational --output architecture-program-operational.json
glio-noncode architecture-program-operational --closure --output architecture-program-operational-closure.json
glio-noncode architecture-program-diff --control missing-fixture --output architecture-program-diff.json
glio-noncode architecture-program-diff --control missing-runtime --closure --output architecture-program-diff-closure.json
glio-noncode architecture-program-summary
glio-noncode architecture-program-receipts-csv --output architecture-program-receipts.csv
glio-noncode architecture-program-checks-csv --output architecture-program-checks.csv
glio-noncode architecture-program-query --domain-id D08
glio-noncode architecture-program-replay
glio-noncode architecture-program-failures
```

See [docs/PROGRAM_RUNTIME.md](docs/PROGRAM_RUNTIME.md) for the stage contract,
public-boundary controls, denominators, closure artifact, and extension rules.

An accepted program run can also be packaged and reopened as a portable offline
release bundle:

```text
glio-noncode architecture-program-bundle --output .glio/architecture-program-release
glio-noncode architecture-program-verify-bundle .glio/architecture-program-release
```

The bundle contains the complete runtime/report, compact and tabular exports,
replay and failure controls, specifications, a content-addressed manifest, and
filesystem verification receipts.

The operational trace closes the handoff between the twelve-stage program
runtime and its eleven-artifact release. It records deterministic workload
budgets, artifact byte budgets, 26 integrity and boundary checks, utilization
counters, and a tamper-evident public projection in
`data/architecture-program-operational-closure.json`.

The program diff surface compares baseline and candidate domain receipts,
checks, stages, and issue-code transitions. It retains accepted-to-review
regressions and recovery controls as addressed public evidence instead of
silently flattening them into a single status.

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

The D15 workbench release also has a portable offline handoff. It materializes
56 exact-byte artifacts: the public fixture, evaluation, all release assurance
planes, 49 normalized runtime stages, four address-only indexes, a review CSV,
and a data dictionary. The root manifest carries 26 closure checks and retains
the D15 denominators of five HTTPS sources, 16 records, four positive paths,
12 controls, four operation families, 80 evaluation checks, and 49 stages:

```powershell
glio-noncode workbench-release-offline-bundle --destination workbench-release-bundle --output workbench-release-bundle.json
glio-noncode workbench-release-offline-bundle-verify workbench-release-bundle --output workbench-release-verification.json
glio-noncode workbench-release-offline-bundle-query workbench-release-bundle --resource records --operation review_form
glio-noncode workbench-release-offline-bundle-audit workbench-release-bundle --output workbench-release-audit.json
glio-noncode workbench-release-offline-bundle-runtime --output workbench-release-runtime.json
glio-noncode workbench-release-offline-bundle-indexes workbench-release-bundle --output workbench-release-indexes.json
glio-noncode workbench-release-offline-bundle-boundary workbench-release-bundle --output workbench-release-boundary.json
glio-noncode workbench-release-offline-bundle-reconciliation workbench-release-bundle --format markdown --output workbench-release-reconciliation.md
glio-noncode workbench-release-offline-bundle-summary workbench-release-bundle --format markdown --output workbench-release-summary.md
glio-noncode workbench-release-offline-bundle-certification workbench-release-bundle --format markdown --output workbench-release-certification.md
```

The D15 closure handoff adds an independent release layer over those source
artifacts. It reconciles 56 artifacts, 16 records, 80 evaluation checks, 80
validation cells, 16 evidence cells, 52 lineage edges, 12 review rows, 16
diagnostics, and 49 runtime stages. It also emits a ten-domain certification
with 60 checks, 184 sequenced events, 24 metrics, a 404-node connected graph,
twelve negative controls, a fourteen-stage deterministic runtime, and a
fourteen-file exact-byte export packet:

```powershell
glio-noncode workbench-release-offline-bundle-closure-runtime --output workbench-release-closure-runtime.json
glio-noncode workbench-release-offline-bundle-closure-query workbench-release-bundle --resource validation --limit 100
glio-noncode workbench-release-offline-bundle-closure-summary workbench-release-bundle --format markdown --output workbench-release-closure-summary.md
glio-noncode workbench-release-offline-bundle-closure-certification workbench-release-bundle --output workbench-release-closure-certification.json
glio-noncode workbench-release-offline-bundle-closure-export --destination workbench-release-closure-export --output workbench-release-closure-export.json
glio-noncode workbench-release-offline-bundle-closure-export-verify workbench-release-closure-export --output workbench-release-closure-verification.json
```

The architecture program now has a portable public handoff for its complete
sixteen-domain runtime. It closes 18 exact-byte artifacts, 172 program checks,
18 quality checks, 12 source runtime stages, 11 source release projections,
seven certification domains, and 36 certification checks. See
[architecture program offline operations](docs/ARCHITECTURE_PROGRAM_OFFLINE_OPERATIONS.md)
for the complete transport, query, verification, and replay workflow.

```text
glio-noncode architecture-program-offline-bundle --destination architecture-program-bundle
glio-noncode architecture-program-offline-bundle-verify architecture-program-bundle
glio-noncode architecture-program-offline-query architecture-program-bundle --resource domains --domain-id D08
glio-noncode architecture-program-offline-audit architecture-program-bundle
glio-noncode architecture-program-offline-runtime --output architecture-program-runtime.json
glio-noncode architecture-program-offline-certification architecture-program-bundle --format markdown
glio-noncode architecture-program-offline-observability architecture-program-bundle --format metrics-csv
```

The top-level D01-D16 program release closure composes that accepted offline
handoff into a deterministic public release layer. It retains 16 domains, 18
portable artifacts, 120 ordered dependencies, 96 release gates, 19 source and
aggregate reconciliation checks, 96 certification checks, 266 observability
events, 96 metrics, a 251-node connected graph, 12 negative controls, a
23-step plan, a 14-stage runtime, and a 15-artifact exact-byte export. The
runtime reuses one source bundle for projection, reconciliation, and replay.
See [program release closure operations](docs/PROGRAM_RELEASE_CLOSURE_OPERATIONS.md)
for the complete contract and review checklist.

```text
glio-noncode program-release-closure --output program-release-closure-runtime.json
glio-noncode program-release-closure-query --resource gates --domain-id D01
glio-noncode program-release-closure-schema
glio-noncode program-release-closure-boundary
glio-noncode program-release-closure-indexes
glio-noncode program-release-closure-reconciliation
glio-noncode program-release-closure-summary
glio-noncode program-release-closure-certification
glio-noncode program-release-closure-observability
glio-noncode program-release-closure-operations
glio-noncode program-release-closure-graph
glio-noncode program-release-closure-failures
glio-noncode program-release-closure-plan
glio-noncode program-release-closure-export --destination program-release-export
glio-noncode program-release-closure-export-verify program-release-export
```

The D16 deployment-governance frontier now has the same portable review
surface. It covers C13 privacy/security policy, C14 local offline bundles,
C15 federated execution, and C16 release/rollback gates. The source handoff
closes 51 exact-byte artifacts, 5 sources, 16 records, 4 positives, 12
controls, 80 evaluation checks, and 38 runtime stages. Its independent D16
closure adds 19 bounded resources, 10 indexes, 47 reconciliation checks, 22
summary checks, 60 certification checks across 10 domains, 151 observability
events, 24 metrics, a 599-node/866-edge connected graph, 12 negative
controls, and a 14-stage deterministic runtime. See [deployment frontier
offline operations](docs/DEPLOYMENT_FRONTIER_OFFLINE_OPERATIONS.md) and
[deployment frontier closure operations](docs/DEPLOYMENT_FRONTIER_CLOSURE_OPERATIONS.md)
for the full CLI, HTTP, query, verification, and replay workflow.

```text
glio-noncode deployment-frontier-offline-bundle --destination deployment-frontier-bundle --output deployment-frontier-bundle.json
glio-noncode deployment-frontier-offline-bundle-verify deployment-frontier-bundle --output deployment-frontier-verification.json
glio-noncode deployment-frontier-offline-bundle-query deployment-frontier-bundle --resource records --role control --format csv
glio-noncode deployment-frontier-offline-bundle-audit deployment-frontier-bundle --output deployment-frontier-audit.json
glio-noncode deployment-frontier-offline-bundle-runtime --output deployment-frontier-runtime.json
glio-noncode deployment-frontier-offline-bundle-certification deployment-frontier-bundle --format markdown --output deployment-frontier-certification.md
glio-noncode deployment-frontier-offline-bundle-closure-query deployment-frontier-bundle --resource records --operation privacy_security_policy --format markdown
glio-noncode deployment-frontier-offline-bundle-closure-certification deployment-frontier-bundle --output deployment-frontier-closure-certification.json
glio-noncode deployment-frontier-offline-bundle-closure-export --destination deployment-frontier-closure-export --output deployment-frontier-closure-export.json
glio-noncode deployment-frontier-offline-bundle-closure-export-verify deployment-frontier-closure-export --output deployment-frontier-closure-verification.json
```

The cross-domain frontier-release closure composes the independent D13, D14,
D15, and D16 handoffs into one public aggregate release package. It conserves
four domain receipts, 155 source artifacts, six forward dependencies, and 24
release gates. The aggregate counters retain 20 source receipts, 64 source
records, 360 evaluation checks, 52 closure stages, 216 certification checks,
and 158 reconciliation checks. The package adds bounded resource queries,
seven address-only indexes, a 13-step dependency-ordered release plan, eight
certification planes with 48 checks, 193 observability events, 24 metrics, a
connected 189-node/191-edge release graph, 12 structural negative controls, a
12-stage deterministic runtime, and a 13-artifact exact-byte export packet.

```text
glio-noncode frontier-release-closure --output frontier-release-snapshot.json
glio-noncode frontier-release-closure-query --resource artifacts --domain-id D15 --limit 100
glio-noncode frontier-release-closure-summary --format markdown --output frontier-release-summary.md
glio-noncode frontier-release-closure-certification --output frontier-release-certification.json
glio-noncode frontier-release-closure-plan --output frontier-release-plan.json
glio-noncode frontier-release-closure-runtime --output frontier-release-runtime.json
glio-noncode frontier-release-closure-export --destination frontier-release-export --output frontier-release-export.json
glio-noncode frontier-release-closure-export-verify frontier-release-export --output frontier-release-verification.json
```

The corresponding HTTP surface is rooted at `/v1/frontier-release/closure`.
It exposes snapshot, query, schema, boundary, indexes, reconciliation,
summary, certification, observability, graph, failure, plan, runtime, and
export projections. Every cross-domain path is aggregate-only and rejects
unsafe paths, duplicate identities, failed gates, incomplete denominators,
nondeterministic replay, and forbidden attribution keys before acceptance. See
[frontier release closure operations](docs/FRONTIER_RELEASE_CLOSURE_OPERATIONS.md)
for the complete contract, resource catalog, release sequence, and verification
matrix.

The offline boundary verifies canonical UTF-8 bytes, safe relative paths,
exact artifact addresses, public keys, independent joins, deterministic replay,
bounded resource queries, and no agent, model, or programming-language
attribution fields.

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
glio-noncode validation-design-frontier-bundle --destination validation-design-bundle --output validation-design-bundle.json
glio-noncode validation-design-frontier-bundle-verify validation-design-bundle --output validation-design-bundle-verification.json
glio-noncode validation-design-frontier-bundle-query validation-design-bundle --resource records --operation gap_analysis
glio-noncode validation-design-frontier-bundle-schema --output validation-design-bundle-schema.json
glio-noncode validation-design-frontier-bundle-audit validation-design-bundle --output validation-design-bundle-audit.json
glio-noncode validation-design-frontier-bundle-observability validation-design-bundle --output validation-design-bundle-observability.json
glio-noncode validation-design-frontier-bundle-runtime --output validation-design-bundle-runtime.json
glio-noncode validation-design-frontier-bundle-closure-boundary validation-design-bundle --output validation-design-closure-boundary.json
glio-noncode validation-design-frontier-bundle-closure-indexes validation-design-bundle --output validation-design-closure-indexes.json
glio-noncode validation-design-frontier-bundle-closure-reconciliation validation-design-bundle --output validation-design-closure-reconciliation.json
glio-noncode validation-design-frontier-bundle-closure-summary validation-design-bundle --format markdown --output validation-design-closure-summary.md
glio-noncode validation-design-frontier-bundle-closure-certification validation-design-bundle --output validation-design-closure-certification.json
glio-noncode validation-design-frontier-bundle-closure-observability validation-design-bundle --output validation-design-closure-observability.json
glio-noncode validation-design-frontier-bundle-closure-runtime --output validation-design-closure-runtime.json
glio-noncode validation-design-frontier-bundle-closure-failure-injection validation-design-bundle --output validation-design-closure-failures.json
glio-noncode validation-design-frontier-bundle-closure-export validation-design-closure-export --output validation-design-closure-export.json
glio-noncode validation-design-frontier-bundle-closure-export-verify validation-design-closure-export --output validation-design-closure-export-verification.json
```

The planning boundary is public aggregate research use. Its offline bundle
materializes 27 exact-byte artifacts, including fixture, evaluation, runtime,
quality, lineage, replay, release, review, source, schema, report, and
observability projections. The verifier checks safe paths, exact bytes,
content addresses, public-boundary keys, and an independent cross-artifact
audit. It does not diagnose, claim assay efficacy, infer individual outcomes,
or establish causal certainty.

The closure handoff adds an independent 33-check reconciliation, nine
address-only indexes, eight certification domains with 48 evidence-linked
checks, 158 timestamp-free events, 18 aggregate metrics, 11 bounded query
resources, and a 12-stage runtime replay. Its public boundary excludes agent,
model, language, and direct identity attribution fields. See
[D13 closure operations](docs/VALIDATION_DESIGN_CLOSURE_OPERATIONS.md).

The D14 evidence lifecycle surface also has a portable offline handoff with 21
exact-byte artifacts, 16 aggregate records, 120 evaluation checks, 26
observability events, five HTTPS receipts, and a normalized ten-stage runtime:

```powershell
glio-noncode evidence-lifecycle-offline-bundle --destination lifecycle-bundle --output lifecycle-bundle.json
glio-noncode evidence-lifecycle-offline-bundle-verify lifecycle-bundle --output lifecycle-bundle-verification.json
glio-noncode evidence-lifecycle-offline-bundle-query lifecycle-bundle --resource records --operation graph_construction
glio-noncode evidence-lifecycle-offline-bundle-audit lifecycle-bundle --output lifecycle-bundle-audit.json
glio-noncode evidence-lifecycle-offline-bundle-runtime --output lifecycle-bundle-runtime.json
glio-noncode evidence-lifecycle-offline-bundle-indexes lifecycle-bundle --output lifecycle-bundle-indexes.json
glio-noncode evidence-lifecycle-offline-bundle-boundary lifecycle-bundle --output lifecycle-bundle-boundary.json
glio-noncode evidence-lifecycle-offline-bundle-reconciliation lifecycle-bundle --output lifecycle-bundle-reconciliation.json
glio-noncode evidence-lifecycle-offline-bundle-summary lifecycle-bundle --format markdown --output lifecycle-bundle-summary.md
```

The verifier reconstructs the manifest address, checks canonical UTF-8 bytes,
safe paths, exact artifact hashes, public-boundary keys, and release state. An
independent audit reconciles fixture, evaluation, runtime, replay, release,
review, queue, and observability artifacts without a service or database.

The D14 closure layer adds 10 address-only indexes, 34 independent
reconciliation checks, a 16-counter reviewer summary, 8 certification domains
with 48 checks, 62 closure events, 18 metrics, a 356-node connected graph, ten
negative controls, and a 12-artifact exact-byte export packet. All projections
retain the public aggregate boundary and exclude direct identity, attribution,
model, and language fields:

```powershell
glio-noncode evidence-lifecycle-offline-bundle-closure-query lifecycle-bundle --resource queue --disposition hold_for_repair
glio-noncode evidence-lifecycle-offline-bundle-closure-reconciliation lifecycle-bundle --output lifecycle-closure-reconciliation.json
glio-noncode evidence-lifecycle-offline-bundle-closure-certification lifecycle-bundle --output lifecycle-closure-certification.json
glio-noncode evidence-lifecycle-offline-bundle-closure-runtime --output lifecycle-closure-runtime.json
glio-noncode evidence-lifecycle-offline-bundle-closure-export --destination lifecycle-closure-export --output lifecycle-closure-export.json
glio-noncode evidence-lifecycle-offline-bundle-closure-export-verify lifecycle-closure-export --output lifecycle-closure-export-verification.json
```

See [D14 closure operations](docs/EVIDENCE_LIFECYCLE_CLOSURE_OPERATIONS.md)
for the projection contracts, runtime stages, and review handoff.

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
rehearses a 24-stage runtime with source closure, lineage, replay, quality,
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
glio-noncode module-fabric-bundle --destination module-fabric-bundle --output module-fabric-bundle.json
glio-noncode module-fabric-bundle-verify module-fabric-bundle --output module-fabric-bundle-verification.json
glio-noncode module-fabric-bundle-query module-fabric-bundle --resource records --domain-id D01 --output module-fabric-records.json
glio-noncode module-fabric-bundle-observability module-fabric-bundle --format metrics-csv --output module-fabric-bundle-metrics.csv
glio-noncode module-fabric-bundle-schema --output module-fabric-bundle-schema.json
glio-noncode module-fabric-bundle-runtime --output module-fabric-bundle-runtime.json
glio-noncode module-fabric-bundle-audit module-fabric-bundle --output module-fabric-bundle-audit.json
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

Materialized module-fabric bundles are durable offline handoffs: writes are
atomic, non-empty destinations require explicit overwrite intent, symlinked
paths are refused, and filesystem-backed loads or queries verify exact bytes
and closed-tree integrity before exposing data. Release-blocked bundles remain
inspectable when their filesystem integrity is intact; tampered trees fail
closed.
`module-fabric-bundle` materializes the full public runtime into a portable
21-artifact directory. `module-fabric-bundle-verify` reopens it without the
producer, checks canonical UTF-8 bytes, content addresses, safe paths,
artifact closure, and public-boundary keys, while the query, diff,
observability, schema, and staged-runtime commands support offline consumers.
The [operations](docs/MODULE_FABRIC_OPERATIONS.md),
[schema](docs/MODULE_FABRIC_SCHEMA.md), and
[release](docs/MODULE_FABRIC_RELEASE.md) documents define its bounded use.

`public-surface-audit` checks the repository's complete published projection
inventory: service status and closures, both offline bundle manifests and
schemas, the D01-D16 program-release snapshot, the service-release registry,
and the service snapshot projections. It rejects attribution,
language, and direct-private-key paths in runtime projections while allowing
subject/sample field names only where they are explicitly declared as input
schema fields. The result is a deterministic 110-surface audit, including the
durable service-release handoff, authenticated deployment profile/schema,
versioned reference manifest/schema, and portable execution-release contracts,
suitable for local release checks and CI.

The public mission-plan contract is a separate lossy projection over the
typed planner. `mission-plan` emits a deterministic receipt with workflow
steps, dependencies, resource totals, review state, aggregate selection
counts, registry address, and a content address; internal routing identifiers
and raw request metadata are rejected at the boundary. Consumers can retrieve
the contract and capability declarations with `mission-plan-schema` and
`mission-plan-capabilities`, or use `POST /v1/mission/plan` and the matching
schema/capabilities endpoints. JSON, Markdown, and step-level CSV exports are
available for offline review.

Public plans can also be materialized as portable release handoffs. The
release contains five exact-byte artifacts, a content-addressed manifest,
five reconciliation checks, independent verification, stable step queries,
plan-to-plan structural diffs, and a timestamp-free staged runtime. These
operations work without reopening the planner after a release is verified:

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
glio-noncode mission-plan-release-catalog-gate-query catalog-gate-packet --accepted --format csv --output accepted-gate-checks.csv
glio-noncode mission-plan-release-catalog-gate-diff old-gate.json new-gate.json --format markdown --output gate-diff.md
glio-noncode mission-plan-release-catalog-gate-observability catalog-gate.json --runtime catalog-gate-runtime.json --output gate-metrics.json
glio-noncode mission-plan-conformance mission-plan.json --output conformance.json
glio-noncode mission-plan-replay mission-plan.json --format markdown --output replay.md
```

Release verifiers reject missing or unexpected files, unsafe paths, symlinks,
byte drift, address drift, malformed checks, and restricted metadata. Release
query, diff, and runtime projections remain read-only and research-use only.
The policy evaluator adds explicit workflow-kind, determinism, resource,
artifact, warning, and public-boundary gates without authorizing execution.
Catalogs inventory multiple releases with exact-byte verification and bounded
queries, semantic audits, and aggregate reports; conformance and replay
independently reconcile public receipts without executing handlers. Reports
conserve release counts and expose state, decision, and workflow distributions
with integer basis-point shares. The catalog gate composes those reports with
explicit thresholds, required state/decision/workflow coverage, a public-key
boundary check, and failure-visible addressed checks. Its runtime rehearses
the gate without handlers; its packet closes the catalog, gate, report, audit,
runtime, policy, summary, and manifest into exact UTF-8 bytes for offline
verification and bounded queries.

The reference boundary is also available directly:

```powershell
glio-noncode reference-manifest --format summary --output reference-summary.json
glio-noncode reference-manifest --format markdown --output reference-manifest.md
glio-noncode reference-manifest-schema --output reference-manifest-schema.json
glio-noncode adapter-conformance adapter-input.json --output adapter-conformance.json
```

The cohort benchmark suite evaluates aggregate records across deterministic
splits, leakage controls, held-out calibration, selective-risk coverage, and
declared source-to-target transport shifts. It is descriptive research
infrastructure and abstains when evidence is insufficient:

```powershell
glio-noncode cohort-benchmark cohort-records.json --split-strategy temporal --source-domain source --target-domain target --output cohort-benchmark.json
glio-noncode cohort-benchmark-schema --output cohort-benchmark-schema.json
glio-noncode cohort-benchmark-capabilities --output cohort-benchmark-capabilities.json
```

See [cohort benchmark operations](docs/COHORT_BENCHMARKS.md).

The provenance-first review workspace keeps hypotheses, evidence edges,
alternatives, source lineage, review work items, and per-dimension deltas
separate from any aggregate score:

```powershell
glio-noncode review-workspace RUN_ID --data-root .glio --output review-workspace.json
glio-noncode review-workspace RUN_ID --baseline-run-id BASELINE_RUN_ID --data-root .glio --output review-deltas.json
glio-noncode review-workspace-schema --output review-workspace-schema.json
glio-noncode review-workspace-export RUN_ID --data-root .glio --format markdown --output review-workspace.md
glio-noncode review-workspace-export RUN_ID --data-root .glio --format csv --collection evidence --output evidence.csv
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
glio-noncode review-workspace-plan-execution-query RUN_ID --view metrics --data-root .glio --output execution-metrics.json
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
glio-noncode review-workspace-plan-execution-release-query execution-release --view metrics --output execution-release-metrics.json
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

See [review workspace operations](docs/REVIEW_WORKSPACE.md).

See [reference manifest operations](docs/REFERENCE_MANIFEST.md). Reference
manifests carry source receipts, declared access and license terms,
coordinate system, supported contexts, channels, checksums when available,
and explicit availability states. They contain metadata only; adapter
conformance repeats bounded element and claim probes and records deterministic,
context, output, and public-boundary checks without embedding reference data.

The reference track boundary adds a deterministic columnar interval index with
block-pruned overlap queries and exact or assembly-safe context-lattice matching:

    glio-noncode build-reference-index tracks.json --index-id glioma-track --assembly GRCh38 --output reference-index.json
    glio-noncode query-reference-index reference-index.json --chromosome 7 --start 5500000 --end 5600000 --context-key GRCh38|glioma|adult|tumor|brain|baseline --mode lattice --output reference-query.json

See [reference interval index operations](docs/REFERENCE_INTERVAL_INDEX.md).

Declared reference-track adapters bind each indexed reading to a source
license, access mode, coordinate system, supported context, limitations, and
deterministic conformance receipt. See [reference track adapter operations](docs/REFERENCE_TRACK_ADAPTERS.md).

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

## Module inventory

The repository includes a static module control plane for inspecting the full
package without importing or executing discovered source files. It reports
module, symbol, local-import, index, graph, test-reference, observability, and
review rows, plus a module-by-module depth percentage that is explicitly a
repository maturity signal rather than a scientific claim:

```powershell
glio-noncode module-inventory --format summary --output module-summary.json
glio-noncode module-inventory-depth --format markdown --output module-depth.md
glio-noncode module-inventory-review --format markdown --output module-review.md
glio-noncode module-inventory-graph --format json --output module-graph.json
glio-noncode module-inventory-packet --destination module-inventory-packet
glio-noncode module-inventory-packet-verify module-inventory-packet
```

The fixed packet contains ten exact-byte artifacts for offline inspection.
Queries are bounded and deterministic; unresolved imports, parse failures,
cycles, large modules, isolated modules, and test-reference gaps remain
visible as review work. See [docs/MODULE_INVENTORY.md](docs/MODULE_INVENTORY.md)
for the contract, route matrix, depth dimensions, and verification rules.

## Module change impact and release gate

The module inventory now feeds a second control plane for comparing an immutable
baseline against a candidate snapshot. `module-impact` classifies added,
removed, changed, and unchanged modules; compares symbol and import shape;
propagates direct, dependent, and transitive impact through reverse edges; and
turns the result into explicit verification tasks and policy checks:

```powershell
glio-noncode module-impact --left-source-root baseline --right-source-root candidate
glio-noncode module-impact-verification --format csv --output impact-tasks.csv
glio-noncode module-impact-audit --left-source-root baseline --right-source-root candidate
glio-noncode module-impact-packet --left-source-root baseline --right-source-root candidate --destination module-impact-packet
glio-noncode module-impact-packet-verify module-impact-packet
glio-noncode module-impact-packet-replay module-impact-packet
```

The packet contains ten exact-byte artifacts for offline diff, impact, gate,
audit, runtime, and observability review. See
[docs/MODULE_IMPACT.md](docs/MODULE_IMPACT.md) for thresholds, API routes,
limitations, and the verification model.

## Module certification and contract coverage

The certification control plane evaluates every discovered source module against
the same explicit contract matrix. Each row records parse integrity, symbol
surface, local dependency closure, test evidence, documentation evidence,
package export evidence, public-boundary safety, and implementation scale. The
result is a scoreable review surface: failed checks become stable gaps, gaps
become ordered remediation tasks, and module gaps are grouped into a severity
routed review queue.

```powershell
glio-noncode module-certification --format summary --output certification-summary.json
glio-noncode module-certification --format markdown --output certification.md
glio-noncode module-certification-tasks --format csv --output certification-tasks.csv
glio-noncode module-certification-audit --output certification-audit.json
glio-noncode module-certification-runtime --output certification-runtime.json
glio-noncode module-certification-observability --format metrics-csv --output certification-metrics.csv
glio-noncode module-certification-packet --destination module-certification-packet
glio-noncode module-certification-packet-verify module-certification-packet
glio-noncode module-certification-packet-query module-certification-packet --resource gaps --limit 50
```

The matrix is static and source-execution-free. It reads each evidence file
once, uses content addresses rather than machine paths, keeps internal modules
eligible for `not_applicable` checks, and leaves every failed check visible in
the gap and task projections. The default policy is intentionally conservative;
it can be replaced with an explicit threshold policy for staged development.
The HTTP equivalents are under `/v1/module-certification` and include bounded
module/check/gap/task queries, policy, runtime, observability, audit, packet,
packet verification, packet query, packet diff, and packet replay.

See [docs/MODULE_CERTIFICATION.md](docs/MODULE_CERTIFICATION.md) for the field
contract, scoring rules, route matrix, artifact layout, and failure behavior.

## Design boundaries

The system treats a scalar score as a view, not as the ontology. Evidence is append-only, source dependence is grouped before aggregation, context transport is visible, and missing evidence is never silently converted to a negative result. Structural variation is represented as a first-class input kind even though the initial fixture focuses on a point variant.

Scientific quantities in this slice are deterministic transformations of supplied observations. The runtime does not invent measurements, claim that a generic annotation proves a glioma mechanism, or hide unsupported inputs behind a narrative.

The release-assurance attestation provides the final public cross-plane gate
over the accepted runtime, D01-D16 program-release closure, and mission-plan
release catalog gate. It closes three component rows and 26 checks, runs eight
replay stages, and exposes exact-byte packet, bounded query, structural diff,
aggregate metrics, and a 26-row reviewer disposition plane:

```text
python -m glio_noncode release-assurance-attestation --plane attestation
python -m glio_noncode release-assurance-attestation --plane packet --destination release-packet
python -m glio_noncode release-assurance-attestation --plane review --format markdown
python -m glio_noncode release-assurance-attestation --plane review-query --failed-only
```

The review output is timestamp-free and address-only. Accepted checks are
closed with a `retain` disposition; failed checks remain open with a
`block-release` disposition. Source payloads, private identifiers, and runtime
attribution are excluded from the public projection.

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

## Certification evidence depth

Per-module certification is backed by two additional static projections. The
lineage graph ties source modules to test, documentation, export, and
dependency evidence with relative paths, digests, line counts, and resolved
edges. The quality report conserves check-kind and family states, surfaces
blockers and top gaps, measures non-source evidence coverage, and classifies
release readiness. Both projections support bounded queries, CSV/Markdown
exports, schemas, capabilities, and independent content-address verification.
An independent lineage audit and release reconciliation report additionally
check graph targets, conservation, public keys, and whether the quality state
is eligible for release.

Quality policy evaluation adds configurable evidence, pass-rate, family-score,
blocker, all-certified, and ready-state thresholds for CI release decisions.

```powershell
python -m glio_noncode module-certification-lineage --resource modules --limit 50
python -m glio_noncode module-certification-quality --resource checks --limit 50
```

## Module implementation workbench

The module workbench turns the inventory, certification matrix, evidence
lineage, and quality report into a detailed implementation view for every
module. It measures seven explainable depth dimensions, resolved fan-in and
fan-out, evidence kinds, depth bands, delivery risk, family rollups, and a
stable task queue covering parse repair, dependency closure, tests,
documentation, public contracts, decomposition, integration review, and
certification closure.

```powershell
python -m glio_noncode module-workbench --format summary
python -m glio_noncode module-workbench --resource tasks --format csv --output module-tasks.csv
python -m glio_noncode module-workbench --resource modules --risk high --limit 50
python -m glio_noncode module-workbench-policy --format summary
python -m glio_noncode module-workbench-audit --format csv --output module-audit.csv
```

The workbench also provides immutable policy gates, independent conservation
audits, and baseline-to-candidate snapshot diffs. Its public API is under
`/v1/module-workbench` with bounded query, schema, capabilities, policy, and
audit routes, plus a complete seven-stage runtime handoff. See
[docs/MODULE_WORKBENCH.md](docs/MODULE_WORKBENCH.md) for the scoring model,
task contract, verification rules, and full route matrix.

## Module workbench execution

The execution layer turns a selected workbench portfolio into a deterministic,
evidence-gated task ledger. It derives prerequisites, supports immutable
`planned`, `ready`, `in_progress`, `blocked`, `completed`, `skipped`, and
`superseded` states, appends addressed transition events, and refuses
completion without the declared evidence receipts. Independent audits
reconstruct the event graph, check prerequisites and public keys, and conserve
state and event counts. Progress policies, runtime handoff, and task-level
snapshot diffs keep implementation progress reviewable without claiming that
selection or completion proves scientific validity.

```powershell
python -m glio_noncode module-workbench-execution --format summary
python -m glio_noncode module-workbench-execution --resource items --format csv --output execution-items.csv
python -m glio_noncode module-workbench-execution-audit --format csv --output execution-audit.csv
python -m glio_noncode module-workbench-execution-policy --format summary
python -m glio_noncode module-workbench-execution-runtime --format json
```

See [docs/MODULE_WORKBENCH_EXECUTION.md](docs/MODULE_WORKBENCH_EXECUTION.md)
for transition rules, evidence requirements, query resources, and API routes.

The execution review view groups that ledger back by module and routes blocked,
evidence-pending, ready, waiting, verification, complete, and superseded work
with conserved progress/evidence rollups and bounded next-task queues:

```powershell
python -m glio_noncode module-workbench-execution-review --format summary
python -m glio_noncode module-workbench-execution-review --review-state attention --format markdown
```

The execution system also has a portable exact-byte handoff packet. It
packages the bounded portfolio, initial and current ledgers, review projection,
independent audit, policy gate, runtime, schema, and capabilities into a
thirteen-artifact directory that can be verified and queried offline:

```powershell
python -m glio_noncode module-workbench-execution-packet --destination .\out\execution-packet
python -m glio_noncode module-workbench-execution-packet-verify .\out\execution-packet
python -m glio_noncode module-workbench-execution-packet-query .\out\execution-packet --resource links
python -m glio_noncode module-workbench-execution-packet-replay .\out\execution-packet
python -m glio_noncode module-workbench-execution-packet-release .\out\execution-packet --format summary
python -m glio_noncode module-workbench-execution-packet-runtime --destination .\out\packet-runtime
python -m glio_noncode module-workbench-execution-packet-inspection .\out\execution-packet --format markdown
python -m glio_noncode module-workbench-execution-packet-inspection-query .\out\execution-packet --plane bytes --passed
python -m glio_noncode module-workbench-execution-packet-archive .\out\execution-packet --destination .\out\execution-packet.zip
python -m glio_noncode module-workbench-execution-packet-archive-verify .\out\execution-packet.zip
python -m glio_noncode module-workbench-execution-packet-archive-query .\out\execution-packet.zip --resource entries --kind artifact
python -m glio_noncode module-workbench-execution-packet-archive-chunk .\out\execution-packet.zip --chunk-size 65536
python -m glio_noncode module-workbench-execution-packet-archive-runtime .\out\execution-packet --destination .\out\execution-packet.zip --unpack-destination .\out\unpacked-packet
python -m glio_noncode module-workbench-execution-packet-archive-diff .\out\left.zip .\out\right.zip --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-index .\out\left.zip .\out\right.zip --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store .\out\left.zip .\out\right.zip --destination .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-verify .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-query .\out\archive-store --resource operations
python -m glio_noncode module-workbench-execution-packet-archive-store-runtime .\out\left.zip .\out\right.zip --format csv
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint .\out\archive-store --output .\out\archive-checkpoint.json
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint-compare .\out\archive-store .\out\archive-checkpoint.json
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery .\out\archive-store --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery-query .\out\archive-store --plane objects
```

The packet writer addresses exact UTF-8 bytes and rejects unsafe paths, missing
or unlisted files, non-canonical JSON, and broken address links. The release
gate remains separate from the packet and returns inspectable failed checks.
See [docs/MODULE_WORKBENCH_EXECUTION_PACKET.md](docs/MODULE_WORKBENCH_EXECUTION_PACKET.md)
for the artifact contract, offline query resources, replay and diff behavior,
inspection findings, API routes, and failure matrix.

For the current downloaded-data assurance-history observatory, the repository
also supports deterministic ZIP archiving and content-addressed chunk
transport. Build, verify, inspect, and query the handoff with the generated
long-form commands below:

```powershell
python -m glio_noncode <observatory-command>-archive --input review-output/observatory --destination review-output/observatory.zip --format summary
python -m glio_noncode <observatory-command>-archive-verify --input review-output/observatory.zip
python -m glio_noncode <observatory-command>-archive-transfer --input review-output/observatory.zip --destination review-output/transfer --chunk-size 65536 --format summary
python -m glio_noncode <observatory-command>-archive-transfer-verify --input review-output/transfer
python -m glio_noncode <observatory-command>-archive-transfer-query --input review-output/transfer --resource chunks --limit 50
```

The policy package registry observatory now adds a persisted inspection
runtime over its archive, archive audit, bounded query, and query audit. It
emits six ordered stage receipts, a path-free acceptance state, and an exact
seven-file reloadable directory with canonical byte receipts. The supplied
downloaded-data demo exercises this runtime on the generated observatory ZIP;
reload rejects missing, extra, non-canonical, tampered, or cross-linked files.

The runtime can then be inspected directly with a bounded query over its
persisted receipts. Query resources cover the six stages, four component links,
component counters, and seven materialized runtime documents. Exact filters,
deterministic pagination, row addresses, and an independent 15-check query
audit make the handoff reviewable without reopening the downloaded source.

Filtered runtime queries can also be sealed into exact five-file snapshots.
Snapshots retain the filtered query, independent query audit, summary, manifest,
and per-file byte receipts, with strict reload-time tamper and cross-link
rejection plus a separate 15-check snapshot audit. The downloaded-data demo
builds and verifies this snapshot against the generated observatory ZIP.

Persisted runtime-query snapshots can also be compared as value-free revisions.
The deterministic diff preserves stable row identities, classifies added,
removed, changed, and unchanged rows, emits changed-field evidence and receipt
address deltas, and is sealed as an exact four-file handoff with an independent
15-check audit. The downloaded-data demo builds this diff from full and filtered
snapshots of the generated observatory ZIP.

Snapshot diffs have a bounded inspection query as well. It exposes summary,
item, change-class, and changed-field resources with exact identity, component,
field, direction, state-transition, address, and text filters, deterministic
pagination, addressed rows, and an independent 12-check query audit. The
downloaded-data demo emits the query and audit projections from its real ZIP
comparison.

Filtered diff-query pages can also be sealed into exact five-file snapshots.
These handoffs retain the source diff address, query and audit receipts, source
snapshot identities, deterministic counts, and per-file byte receipts without
copying source values or paths. Reloading is canonical and fail-closed, and a
separate 15-check audit recomputes the linkage, state, summary, manifest, byte
receipts, and public boundary. See
[docs/DOWNLOADED_DATA_DIFF_QUERY_SNAPSHOTS.md](docs/DOWNLOADED_DATA_DIFF_QUERY_SNAPSHOTS.md).

Two persisted diff-query snapshots can then be compared longitudinally. The
comparison requires the same query shape, pairs public rows by
`(resource, identity, field)`, classifies added/removed/changed/unchanged rows,
retains both endpoint receipts, and emits an exact four-file handoff with a
separate 15-check audit. See
[docs/DOWNLOADED_DATA_QUERY_SNAPSHOT_COMPARISONS.md](docs/DOWNLOADED_DATA_QUERY_SNAPSHOT_COMPARISONS.md).
Those persisted comparisons can then be inspected without reopening the source
snapshots: query summary, action classes, changed fields, source resources,
stable keys, identities, directions, transitions, addresses, or bounded text,
with an independent twelve-check query audit. The same result is available as
JSON, CSV, Markdown, a CLI command, and a loopback HTTP route.

Filtered comparison-query pages can also be sealed into exact five-file,
value-free handoffs. They retain the comparison identity, complete query shape,
query rows, independent query audit, summary, canonical manifest, and per-file
byte receipts. Reloading is atomic and fail-closed, with an independent
15-check snapshot audit. See
[docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOTS.md](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOTS.md).

Multiple persisted comparison-query snapshot handoffs can then be admitted into
an exact four-file registry. The registry rejects duplicate snapshot identities,
folds state and acceptance conservatively, preserves complete query shape and
public addresses, and provides independent 16-check registry and 12-check query
audits with bounded projections. See
[docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY.md](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY.md).

The archive and transfer boundaries preserve public content addresses, reject
path and attribution metadata, and re-verify nested bytes before reassembly.
See [the archive-transfer contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER.md)
and [the runnable transfer demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_demo.py).

The certificate-observatory handoff has a focused ZIP boundary as well. The
exact eight-member archive, sixteen-check archive audit, bounded archive query,
fourteen-check resumable transfer, and archive runtime are available with
explicit commands such as:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive --input C:\data\certificate-observatory-package --destination C:\data\certificate-observatory.zip --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-audit --input C:\data\certificate-observatory.zip --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-transfer --input C:\data\certificate-observatory.zip --destination C:\data\certificate-observatory-transfer --chunk-size 4096 --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-runtime --input C:\data\certificate-observatory-package --destination C:\data\certificate-observatory-runtime.zip --transfer-destination C:\data\certificate-observatory-runtime-transfer --format summary
```

The implementation is covered by the downloaded-data observatory example and
the archive boundary contract tests, including exact ZIP replay, tamper
rejection, pagination, partial receiving, CLI, HTTP, and closed-schema checks.
See [the registry federation contract](docs/registry-federation.md#certificate-observatory-zip-archive-and-resumable-transfer).

The multi-snapshot certificate-observatory archive registry is now available as
the next operational layer. It ingests one or more verified observatory package
directories, ZIPs, or public JSON documents; derives content-addressed entries,
package groups, conserved counters, and a deterministic index; and can persist
an exact five-file registry. It also supplies sixteen registry-audit checks,
bounded summary/entry/accepted/held/package queries, fourteen query-audit
checks, added/removed/changed/unchanged diffs with changed-field disclosure,
diff-query auditing, a package-loading runtime, and a four-file append-only
registry history with predecessor links. Build and inspect real downloaded
handoffs with:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry `
  --input C:\data\primary-observatory-package `
  --input C:\data\replica-observatory-package `
  --entry-id primary-entry --entry-id replica-entry `
  --archive-id primary-archive --archive-id replica-archive `
  --destination C:\data\observatory-archive-registry --format summary
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-query `
  --input C:\data\observatory-archive-registry --resource entries --resource packages --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-audit `
  --input C:\data\observatory-archive-registry --format summary
```

The standalone [archive-registry demo](examples/registry_federation_certificate_observatory_archive_registry_demo.py)
accepts downloaded package directories, archive ZIPs, or public JSON inputs
and prints the complete path-free registry/report/diff/history result. The
[archive-registry contract](docs/CERTIFICATE_OBSERVATORY_ARCHIVE_REGISTRY.md)
documents the object graph, persistence and replay rules, API namespace,
limits, failure model, and verification matrix. The real downloaded-data demo
now runs two archive snapshots through the registry, diff, history, and runtime
planes, derives a deterministic health report with held/failed/source-alert
signals, and reports every independent audit and disk replay result without
publishing local paths or attribution metadata.

The health report can also be built and audited directly:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-report `
  --input C:\data\observatory-archive-registry --format markdown
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-report-audit `
  --input C:\data\archive-registry-report.json --format summary
```

It exposes explicit `ready`, `review`, and `blocked` states with
content-addressed alerts and a twenty-check independent report audit. The
report preserves a blocked decision when source evidence fails while proving
that the public health projection itself is internally coherent.

Interrupted chunk receivers can resume from the addressed ZIP with the
recovery boundary. It reports missing ranges first, verifies the source archive
and transfer manifest match, fills only validated chunks, and emits a twelve-
check path-free recovery audit. The downloaded-data example exercises this
repair path as well as the complete transfer path. For a package directory,
the standalone [recovery demo](examples/registry_federation_certificate_observatory_archive_recovery_demo.py)
can simulate an interrupted receiver and produce the same public receipts.

The next coordination layer is the [observatory archive registry contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY.md),
which registers multiple independently verified downloaded observatory
archives without merging their source histories. It provides conserved
metrics, eight-check verification, exact five-file persistence, bounded state
queries, CLI/HTTP routes, and a [runnable registry demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_demo.py).
The independent [registry-audit contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_AUDIT.md)
adds twelve raw-package checks and structured incomplete reports for damaged
or tampered registry directories.
The [registry-diff contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_DIFF.md)
compares two verified registry snapshots with deterministic added, removed,
changed, unchanged, state-transition, readiness-transition, and aggregate
registry-change records. It includes bounded queries, CLI/HTTP routes, schemas,
capabilities, and a [runnable diff demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_demo.py).
The independent [registry-diff-audit contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_DIFF_AUDIT.md)
adds fixed structural, linkage, conservation, and content-address replay checks;
the diff audit preserves an addressable incomplete report for malformed public
mappings. See the [runnable diff-audit demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_demo.py).
The [diff-audit query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_DIFF_AUDIT_QUERY.md)
adds bounded summary, check, pass/fail, and evidence inspection with stable
pagination, filtering, and query-address replay. See the [runnable query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_query_demo.py).
The [ordered registry history contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY.md)
turns repeated verified registry downloads into a deterministic timeline of
snapshots and adjacent transitions. It preserves endpoint linkage, ordinal
ordering, state-count conservation, canonical artifact receipts, exact
four-file persistence, and JSON/CSV/Markdown exports. See the [runnable history
demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_demo.py).
The independent [registry-history-audit contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_AUDIT.md)
adds fixed sequence, adjacency, endpoint, conservation, nested-address, and
content-address checks while preserving an incomplete diagnostic report for
malformed public mappings. See the [runnable history-audit demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_demo.py).
The [registry-history query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_QUERY.md)
adds bounded snapshot, transition, state-change, acceptance, release-readiness,
ordinal, text, and pagination inspection with deterministic query addresses.
See the [runnable history-query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_query_demo.py).
The [registry-history-audit query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_AUDIT_QUERY.md)
adds bounded audit summary, check, pass/fail, evidence, filtering, pagination,
and query-address replay over the thirteen history checks. See the [runnable
audit-query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_query_demo.py).
The [registry-history release gate contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE.md)
adds an explicit public policy boundary with deterministic `ready`, `held`, and
`blocked` decisions, independent audit dependency, transition budgets, check
addresses, CLI/HTTP routes, schemas, and a [runnable release-gate demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_demo.py).
The [registry-history release-gate query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE_QUERY.md)
adds bounded summary, check, pass/fail, hold, and blocking inspection with
stable filters, pagination, query-address replay, exports, and a [runnable
query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_query_demo.py).
The [registry-history release-gate package contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE_PACKAGE.md)
adds exact three-file persistence, canonical artifact receipts, atomic writes,
safe reload, manifest inspection, CLI/HTTP verification, and a [runnable
package demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_demo.py).
The independent [release-gate package audit contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE_PACKAGE_AUDIT.md)
checks raw package membership, canonical bytes, manifest receipts, gate and
policy linkage, nested check identities, decision projection, and content
addresses while preserving a public diagnostic for damaged handoffs. See the
[runnable package-audit demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_demo.py).
The [release-gate package-audit query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE_PACKAGE_AUDIT_QUERY.md)
adds bounded summary, check, pass/fail, evidence, filtering, pagination, and
content-addressed inspection over package audit reports, including damaged
package diagnostics. See the [runnable query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_query_demo.py).
The [package-audit release certificate contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE_PACKAGE_AUDIT_RELEASE_CERTIFICATE.md)
adds an explicit policy-governed `ready`, `held`, or `blocked` decision over
independent package audits, with addressed checks, namespace validation, and
content-address replay. See the [runnable certificate demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_demo.py).
The [package-audit release certificate query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_GATE_PACKAGE_AUDIT_RELEASE_CERTIFICATE_QUERY.md)
adds bounded certificate summary, check, pass/fail, hold, blocking, evidence,
severity, pagination, and raw-package-to-certificate inspection. See the
[runnable certificate-query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_query_demo.py).
The [downloaded-history release evidence pipeline contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md)
composes history loading, release-gate evaluation, package materialization, independent package audit, and release certification into one path-free receipt. See the
[runnable end-to-end pipeline demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_demo.py).
The companion [release evidence pipeline query contract](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md)
provides bounded stage, decision, and evidence resources over the consolidated receipt, with a
[runnable query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_demo.py).
The same chain can be exported as a verified five-file [release evidence handoff bundle](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md), preserving the pipeline receipt and all query views with canonical bytes and manifest receipts.
The bundle now has an independent [audit and revision-diff surface](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md): operators can inspect failed checks and compare baseline/candidate bundles by semantic transitions and per-file byte hashes. See the [bundle diff demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_demo.py).
The diff is also queryable by semantic field, changed/unchanged artifact, file name, action, changed field, and bounded text search through the [bundle diff query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_demo.py).
The revision itself now has a twelve-check [bundle diff audit](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md) for namespace safety, semantic/count conservation, nested addresses, and mapping replay.
Its addressed checks are queryable by pass/fail status, check identity, text, and bounded pagination through the same audit boundary.
The pipeline also exposes timestamp-free [observability events and denominator metrics](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md), suitable for operational inspection without changing release semantics.
The thirteen audit checks are also filterable through the [observability audit query](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md), including failed-check and evidence-address views with deterministic pagination. See the [observability audit query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query_demo.py).
Those events and metrics are also available through bounded [observability queries](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md), including accepted/rejected views, stage/event/metric filters, pagination, replay addresses, and JSON/CSV/Markdown exports. See the [observability query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_query_demo.py).
The same projection has a thirteen-check [independent observability audit](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md) for event ordering, transition linkage, metric conservation, decision conservation, namespace safety, and content-address replay. See the [observability audit demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_demo.py).
The operational projection can also be materialized as an exact nine-file [observability handoff bundle](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md) containing the events, metrics, accepted/rejected views, independent audit, audit-check query, and byte-receipted manifest. See the [observability bundle demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_demo.py).
The persisted handoff is then queryable without rebuilding history through ten verified resources—summary, projection, event/metric and decision views, audit checks, and evidence—with bounded filters, pagination, replay addresses, and JSON/CSV/Markdown exports. See the [observability bundle query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query_demo.py).
Two persisted observability handoffs can also be compared across all nine files, semantic receipt fields, byte hashes, and nested query addresses, then independently audited through twelve conservation and replay checks with bounded audit queries. See the [observability bundle diff demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_demo.py) and [diff audit-query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_audit_query_demo.py).
The verified comparison can now be evaluated by a policy-driven [promotion gate](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md) that emits ready, held, or blocked decisions, separates integrity blockers from policy holds, enforces change budgets, and exposes bounded check queries. See the [promotion-gate demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_demo.py) and [promotion-gate query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_query_demo.py).

Federated archive registries now have an evidence-preserving resolution and
reconciliation layer. The resolution module applies an explicit quorum to each
entry and retains `resolved`, `review`, or `blocked` outcomes with candidate,
supporting, missing, dissenting, and rationale evidence. The reconciliation
plan expands that result into a deterministic peer-by-entry matrix of no-op,
missing-request, consensus-replacement, or manual-review operations. It is
analysis-only: it never mutates a source registry. The exact nine-file runtime
persists the federation, consensus, resolution, plan, four independent audit
projections, and manifest for byte-level replay. Use downloaded registry
directories or public registry JSON with:

```powershell
python -m glio_noncode.cli registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-reconciliation-runtime `
  --input C:\data\primary-registry --input C:\data\replica-registry `
  --peer-id primary --peer-id replica --quorum 2 `
  --destination C:\data\reconciliation-runtime --format summary
```

The [resolution and reconciliation contract](docs/ARCHIVE_REGISTRY_FEDERATION_RESOLUTION.md)
documents the state machine, exact persistence, query filters, audit checks,
CLI/HTTP routes, failure semantics, and verification matrix. The standalone
[reconciliation demo](examples/registry_federation_certificate_observatory_archive_registry_federation_reconciliation_demo.py)
prints path-free resolution items and per-peer operations from the supplied
downloads, so missing and divergent replicas remain visible instead of being
silently flattened.
The companion [reconciliation operator runbook](docs/ARCHIVE_REGISTRY_FEDERATION_RECONCILIATION_RUNBOOK.md)
walks through source validation, ready/review/blocked interpretation, exact
nine-file replay, query handoffs, retry handling, and the downstream executor
boundary.
Multiple verified handoffs can now be indexed under deterministic path-free labels in a bounded [observability bundle catalog](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md), with accepted/ready/rejected denominators, evidence-address queries, pagination, replay addresses, and JSON/CSV/Markdown exports. See the [catalog demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_demo.py) and [catalog query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_demo.py).
Catalog revisions can now be compared by label with added/removed/changed/unchanged classifications, accepted/ready/artifact deltas, a twelve-check independent audit, and bounded audit queries. See the [catalog diff demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_demo.py) and [catalog diff audit-query demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_audit_query_demo.py).
Catalog report and promotion controls now add deterministic acceptance/readiness ratios, label partitions, policy budgets, ready/held/blocked decisions, a second independent gate audit, a composed promote/hold/block release packet with action evidence, and bounded report/gate/packet queries. The [catalog report and promotion demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_promotion_demo.py) runs that full flow on ordinary downloaded handoffs; see the [release-evidence pipeline reference](docs/RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE.md) for CLI and HTTP contracts.

The durable [catalog promotion package runtime and registry demo](examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_runtime_registry_demo.py) runs that flow on real downloaded handoff directories, persists an exact five-file package, reloads and verifies it, audits twelve package invariants, queries its evidence, and optionally indexes the package in a two-file registry. Registry revisions can be compared by package identity and independently audited across eleven conservation checks. Public results contain labels, decisions, counts, and content addresses only; local input paths and private attribution metadata are excluded.

The new [package-registry federation boundary](docs/registry-federation.md) reconciles multiple verified registries with quorum-aware missing and divergent package detection, addressed actions, fourteen-check independent audits, transition diffs, release-gate policy evaluation, append-only history, a cross-history observatory, a sixteen-check pairwise agreement matrix for multi-peer topology analysis, quorum-safe consensus receipts that retain dissent while emitting explicit remediation actions, and typed non-mutating remediation plans with independent audits, bounded queries, exact four-file handoff packages, and independent query-result audits. The consensus release-control plane adds explicit policy, twenty gate checks, independent gate/package/diff/history/observatory audits, bounded projections, exact six-file handoff packages, transition review, and cross-history acceptance monitoring. The certificate plane adds 19 issuance checks, issued/withheld promote/hold decisions, an independent 20-check certificate audit, filterable evidence queries, an independent 11-check query-result audit, an exact nine-file handoff package, an 18-check package audit, and acceptance-aware certificate transition diffs with a 14-check audit. Its history stream adds append-only issued/withheld decision retention, independent 14-check history auditing, exact three-file persistence, and reloaded-address verification. The certificate-history observatory now adds seven resource views, bounded history/certificate/disposition filters, independent 16-check aggregate and 13-check query audits, deterministic acceptance/trend reports with alerts, an independent 15-check report audit, and an exact eight-file snapshot package with an independent 15-check package audit. Observatory transitions can be compared by logical history-entry key with added/removed/changed/unchanged classifications, acceptance and failure deltas, independent 16-check diff and 13-check diff-query audits, and a composed runtime that loads histories, runs every audit, reports health, and optionally persists the snapshot package. Exact package replay now compares all eight canonical members byte-for-byte and emits a separately auditable 13-check replay receipt. The CLI and local HTTP API expose build, query, audit, diff, gate, certificate, history, observatory, matrix, consensus, consensus-runtime, consensus-diff, consensus-history, consensus-observatory, consensus-remediation, consensus-remediation-package, remediation-query-audit, and consensus-gate lifecycle operations. The [real-data federation demo](examples/registry_federation_real_downloaded_data_demo.py) exercises clean replica acceptance and divergent downloaded-registry rejection with strict-quorum transition accounting, canonical persistence, independent audits, remediation steps, release-gate package replay, certificate issuance and withholding, certificate query-view auditing, certificate package replay, certificate history append/reload auditing, certificate-history observatory queries and health reporting, exact observatory-package replay, transition diff auditing, persisted runtime replay, and byte-level snapshot replay auditing. The [policy package registry history/diff demo](examples/downloaded_data_contract_resolution_history_diff_policy_demo.py) now appends real downloaded registry snapshots, reports improved/unchanged transitions, compares baseline and candidate histories, exposes addressed audit/query evidence, folds both persisted registry histories into an exact five-file observatory with independently auditable member and transition queries, exports that observatory as a deterministic ZIP with byte-level replay and an independent archive audit, and supports manifest-only archive queries with independent query-result audits.
See the [release-control operations guide](docs/CONSENSUS_RELEASE_CONTROL_OPERATIONS.md) for repeatable clean/divergent workflows, HTTP examples, failure triage, transport verification, and CI expectations.

The archive-registry federation boundary now compares independently downloaded
registry snapshots while preserving each peer's identity and entry evidence.
It classifies entries as consistent, missing, or divergent, evaluates strict
quorum, emits a readiness report, supports bounded federation and diff queries,
and persists an exact six-file runtime with byte-level replay receipts. The
CLI and local HTTP API expose every typed operation, independent audit, schema,
and capability contract. See the [archive-registry federation guide](docs/ARCHIVE_REGISTRY_FEDERATION.md)
and the [downloaded-data federation demo](examples/registry_federation_certificate_observatory_archive_registry_federation_demo.py).

Persisted comparison-query snapshot registries now have a longitudinal [history
surface](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY.md)
with deterministic initial/improved/regressed/unchanged/changed transitions,
exact four-file handoffs, independent history and query audits, bounded
transition filters, and a real downloaded-ZIP demonstration in
`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`.
Those histories can also be combined in a deterministic [cross-history
observatory](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY.md)
with exact five-file handoffs, folded member and transition summaries,
independent aggregate and query audits, and bounded state/trend inspection.
That observatory can now be handed off over a resumable [archive transfer
boundary](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER.md):
the deterministic ZIP is split into addressed byte ranges, persisted as a
canonical manifest plus chunks, resumed out of order, inspected through
manifest-only progress/query views, independently audited, and reassembled
through the nested archive verifier. The real downloaded-ZIP demo writes both
the complete transfer and a two-chunk partial receiver state.
It also emits a path-free [recovery plan](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY.md)
for that partial state: every missing chunk becomes an addressed action,
resume-versus-assemble is explicit, checkpoint safety and the next chunk are
recorded, and independent recovery/query audits can be run without exposing
source paths, records, or payload bytes.
The recovery plan can now be materialized as a verifiable [execution receipt](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION.md):
planned, in-progress, complete, and blocked states are derived from conserved
chunk indices and byte ranges; assembler-backed receipts prove which actions
are present; rejected actions fail closed; and independent execution and
execution-query audits cover the persisted JSON/CSV/Markdown surfaces. The
downloaded-ZIP demo writes all four progression states and their audit/query
artifacts without source paths or payload bytes.

Those execution receipts now have a durable [runtime handoff](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME.md):
an atomic exact seven-file package with a canonical manifest, per-file byte
receipts, strict reload verification, five-stage readiness replay, independent
runtime and query audits, and bounded summary/stage/artifact/component/outcome
inspection. The downloaded-ZIP demo persists and reloads the handoff so it can
be transferred, reviewed, or queried offline without source paths, payload
bytes, agent metadata, or language metadata.

The runtime registry can now be federated across independently persisted registry boundaries. The [runtime-registry federation](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION.md) preserves source-scoped registry and runtime identities, folds ready/empty/blocked members into ready/mixed/blocked outcomes, and emits an exact five-file package with independent assurance and ten bounded query resources. The downloaded-ZIP demo builds and reloads a two-member federation without source paths, payload bytes, agent metadata, or language metadata.

That federation now has a portable [six-member deterministic ZIP archive](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE.md). It preserves the exact five-file federation inside a canonical outer manifest, records byte receipts and archive size, rejects unsafe or non-canonical ZIPs, and exposes independent 18-check archive audits plus ten bounded archive resources with a 12-check query audit. The downloaded-ZIP demo builds, reloads, audits, queries, and persists the archive through the CLI and local HTTP API without publishing source paths, payload bytes, agent metadata, or language metadata.

That archive now has a [resumable transfer boundary](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER.md). The verified ZIP is split into addressed byte ranges, persisted as a canonical manifest plus complete or partial chunks, resumed out of order, queried through seven manifest-only resources, independently audited, and reassembled through the nested archive verifier. The downloaded-ZIP demo writes the complete six-chunk transfer, a two-chunk partial receiver, progress, audit, query, and query-audit artifacts.

That federation archive transfer now has a path-free [recovery plan](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY.md). It derives four addressed missing-chunk actions from the real two-chunk checkpoint, conserves received and remaining bytes, chooses `resume` for partial state or `assemble` for a complete transfer, and exposes independent recovery/query audits through CLI and local HTTP API surfaces without source paths, payload bytes, agent metadata, or language metadata.
That recovery plan now has a path-free [execution receipt](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION.md). It records applied, pending, and rejected missing-chunk outcomes; derives planned, in-progress, complete, or blocked state; conserves indexes and bytes; exposes independent 18-check execution and 12-check query audits; and runs through CLI, local HTTP, schema, capability, and public inventory surfaces without source paths, payload bytes, agent metadata, or language metadata.

That federation-specific execution receipt now has a durable [runtime handoff](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME.md). It composes the execution, 18-check audit, seven-resource query, and 12-check query audit into a five-stage ready/blocked state; persists an exact seven-file canonical package with manifest byte receipts; rejects non-canonical or tampered reloads; and exposes CLI, local HTTP, schema, capability, and public inventory surfaces. The downloaded-ZIP demo writes the runtime directory and reports its state, stage, audit, query, and content-address evidence without source paths, payload bytes, agent metadata, or language metadata.
That history-diff execution receipt now has its own exact [runtime handoff](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_HISTORY_DIFF_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME.md). It binds the receipt, independent audit, bounded query, and query audit into five ordered stages; persists an exact seven-file package atomically; verifies manifest byte receipts and canonical replay; exposes sixteen runtime checks plus twelve query-assurance checks; and is available through CLI, local HTTP, schemas, capabilities, public inventory, and the real downloaded-ZIP demo without source paths, payload bytes, agent metadata, or language metadata.
That exact history-diff runtime handoff now has a deterministic [runtime admission registry](docs/HISTORY_DIFF_RUNTIME_REGISTRY.md). It admits one or more runtime receipts, sorts and deduplicates identities, folds empty/ready/blocked state, persists an exact four-file package, and exposes sixteen registry checks plus seven bounded resources and twelve query-assurance checks through CLI, local HTTP, schemas, capabilities, public inventory, and the downloaded-ZIP demo without source paths, payload bytes, agent metadata, or language metadata.
The registry now also has an addressed [longitudinal history](docs/HISTORY_DIFF_RUNTIME_REGISTRY_HISTORY.md). It records same-identity snapshots with ancestry-linked addresses and deterministic initial/improved/regressed/unchanged/changed transitions, persists an exact four-file history package, and exposes sixteen history checks plus seven bounded history resources and twelve query-assurance checks through CLI, local HTTP, schemas, capabilities, public inventory, and the downloaded-ZIP demo.
That longitudinal history now has an exact [history diff](docs/HISTORY_DIFF_RUNTIME_REGISTRY_HISTORY_DIFF.md). It compares same-identity baseline and candidate snapshots by stable ordinal, preserves field-level changes with two-sided addresses, classifies added/removed/changed/unchanged items, derives directional readiness, persists an exact four-file diff package, and exposes sixteen diff checks plus eight bounded diff resources and thirteen query-assurance checks through CLI, local HTTP, schemas, capabilities, public inventory, Actions, and the downloaded-ZIP demo.

Those runtime handoffs can now be admitted into a deterministic [recovery execution runtime registry](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY.md): duplicate identities are rejected, ready/blocked state and acceptance counters are conserved, and the exact four-file registry package reloads fail closed after tampering. Independent registry and registry-query audits expose bounded summary, entry, runtime, state, readiness, address, and bounds projections. The downloaded-ZIP demo builds two runtime entries, persists the registry, and emits JSON/CSV/Markdown review artifacts without source paths, payload bytes, agent metadata, or language metadata.

The federation-specific runtime handoff now has its own [runtime registry boundary](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY.md): one or more federation runtime receipts are sorted, admitted, folded into empty/ready/blocked state, and persisted as an exact four-file package with strict manifest, canonical-byte, address, and tamper replay. Sixteen registry checks, seven bounded query resources, and twelve query-assurance checks are available through the CLI, local HTTP API, schemas, capabilities, and public inventory. The downloaded-ZIP demo builds and reloads this boundary without source paths, source records, payload bytes, or private metadata.
The federation runtime registry also has an append-only longitudinal history boundary. It tracks addressed snapshots, stable ancestry, ready/empty/blocked state, acceptance and readiness counts, deterministic initial/improved/regressed/unchanged/changed transitions, exact four-file persistence, independent history and query audits, bounded resource queries, and the full CLI/API/schema/capability surface. The downloaded-ZIP demo builds an empty baseline plus a ready candidate, persists and reloads the history, and exposes the complete review surface without source paths or payload bytes.

That federation runtime-registry history can now be compared directly through a deterministic [history diff](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_HISTORY_DIFF.md). It classifies stable ordinal snapshots as added, removed, changed, or unchanged; preserves both history addresses and field-level evidence; persists an exact four-file package; exposes independent 16-check diff and 13-check query audits; and supports bounded summary, item, change, address, and bound queries through CLI, HTTP, schemas, capabilities, and public inventory. The downloaded-ZIP demo now produces this comparison package without source paths, payload bytes, agent metadata, or language metadata.

That history diff now has a portable [deterministic archive](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_HISTORY_DIFF_ARCHIVE.md): one canonical outer manifest plus the exact four history-diff projections, fixed ZIP metadata, per-member receipts, strict reload, nested replay, and atomic persistence. Independent 18-check archive and 13-check query audits, eight bounded archive resources, CLI/API/schema/capability surfaces, and Actions coverage are included. The downloaded-ZIP demo writes and reloads the archive while keeping source paths, payload bytes, agent metadata, and language metadata out of public outputs.

The archive now has a resumable [addressed transfer boundary](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_HISTORY_DIFF_ARCHIVE_TRANSFER.md): deterministic fixed-size chunk receipts, public manifests, complete and partial atomic receiver directories, out-of-order idempotent assembly, strict nested-archive verification, independent 18-check transfer audits, and bounded receiver-aware queries with independent 12-check query audits. The downloaded-ZIP demo exercises the complete and partial states and reassembles the exact archive without exposing chunk bytes, source paths, agent metadata, or language metadata in public projections.

That transfer now has a path-free [recovery plan](docs/DOWNLOADED_DATA_COMPARISON_QUERY_SNAPSHOT_REGISTRY_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_FEDERATION_ARCHIVE_TRANSFER_RECOVERY_EXECUTION_RUNTIME_REGISTRY_HISTORY_DIFF_ARCHIVE_TRANSFER_RECOVERY.md): every missing chunk becomes an addressed action, received and remaining indexes and bytes are conserved, and the plan chooses `resume` or `assemble` with explicit checkpoint and next-index state. Independent 17-check recovery and 12-check query audits, bounded seven-resource recovery queries, CLI/API/schema/capability surfaces, and real downloaded-ZIP artifacts are included.
