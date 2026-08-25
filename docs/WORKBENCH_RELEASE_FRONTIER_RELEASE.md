# Workbench release frontier release note

This build adds a dedicated D15 C13-C16 release boundary for structured review,
report export, global search, and accessibility and human-factors checks. It
contains four independent operation adapters, sixteen public aggregate rows, five
HTTPS source receipts, eighty deterministic checks, a forty-nine-stage runtime,
review routing, artifact accounting, failure injection, and safe export projections.

The controls deliberately preserve incomplete forms, duplicate reports, no-match
searches, malformed search identities, failed criteria, and foreign contexts. The
positive paths are not sufficient by themselves; the release also requires the
negative boundaries to replay as declared.

This is a research workbench surface. It is not a clinical interface certification,
individual diagnosis, causal claim, or treatment authorization.

The build is intentionally offline-replayable. Public URLs identify source portals
and scopes; the fixture does not require network retrieval to evaluate. All controls
remain visible in the fixture, evaluation, queue, and package. The next build can
extend the workbench without changing this contract unless its version, fixture
address, and tests are updated together.

The module boundaries are explicit: contracts own states and records, support owns
safe parsing, operations own behavior, public data owns the aggregate fixture,
adapters own dispatch, evaluation owns checks, and runtime owns ordered composition.
The assurance planes preserve the same separation for metrics, lineage, policy,
replay, review, integrity, evidence, access, artifacts, and release.

## Portable offline handoff

The `workbench_release_frontier_offline_*` modules make the complete D15
runtime consumable without the producer process. A default handoff contains 56
exact-byte UTF-8 artifacts:

- `fixture.json`, `data-audit.json`, adapters, schema, evaluation, metrics,
  policy, lineage, reconciliation, quality, replay, view, queue, handoff,
  integrity, depth, controls, validation, evidence, access, failure injection,
  diagnostics, artifacts, release, and summary planes;
- provenance, source registry, freshness, compatibility, release checks,
  execution plan, run manifest, audit log, transcript, report, review SLA,
  review protocol, claim boundary, recovery, performance, operational,
  compliance, query, partitions, scenario, resources, bundle, and
  observability planes;
- the normalized `runtime.json` trace, fixture/stage/operation/denominator
  indexes, a public-key index, `review.csv`, and a data dictionary.

The root manifest carries 26 checks and reconstructs its own address. The
filesystem verifier recomputes every artifact byte address and rejects path
traversal, missing files, symlinks, hidden files, private keys, and attribution
fields. Query projections are bounded and support records, executions, checks,
sources, stages, operation partitions, denominator counts, public keys, and
artifact metadata. Independent audit, reconciliation, summary, and six-stage
offline replay receipts are available through both CLI and local HTTP routes.

The independent certification plane groups 41 source checks into manifest,
fixture, evaluation, runtime, index, security, and release domains. Every check
retains evidence artifact IDs and a content address; certification can be
queried by domain or failure state and exported as JSON, CSV, or Markdown.

The handoff remains public aggregate research infrastructure: it is not a
clinical interface certification, diagnosis, causal conclusion, or treatment
authorization.
