# Workspace frontier operations

## Operating model

The workspace frontier is a deterministic read-model pipeline. It starts with
public aggregate source receipts, constructs typed records, runs four surface
operations, measures the outputs, reconciles expected states, and assembles a
release manifest. Every stage has a stable content address.

The pipeline is intentionally usable from a CLI, a test process, a future API,
or a notebook. The same fixture and the same context key should produce the
same record order, facet counts, state values, and release addresses.

## Runtime stages

| Sequence | Stage | Input | Output |
| ---: | --- | --- | --- |
| 1 | fixture-load | none | fixture address |
| 2 | contract-load | none | contract address |
| 3 | surface-execution | fixture and contracts | evaluation address |
| 4 | metric-measurement | evaluation | metrics address |
| 5 | lineage-build | fixture and evaluation | lineage address |
| 6 | policy-review | evaluation and policy | decision address |
| 7 | reconciliation | evaluation and policy | reconciliation address |
| 8 | bundle-assembly | fixture, evaluation, metrics, reconciliation | bundle address |

The runtime report retains the full evaluation, metrics, reconciliation, and
bundle objects. The stage list is not a substitute for those objects; it is an
ordered receipt that explains how they were composed.

## Daily verification

The shortest useful check is:

```powershell
python -m pytest -q tests/test_workspace_frontier_evidence.py tests/test_workspace_frontier_depth.py
```

The CLI-only check is:

```powershell
glio-noncode workspace-frontier-evaluate
glio-noncode workspace-frontier-quality-gate
glio-noncode workspace-frontier-release
```

The complete focused check is:

```powershell
python -m pytest -q tests/test_workspace_frontier_evidence.py tests/test_workspace_frontier_depth.py tests/test_workspace_frontier_evidence_cli.py
```

## Input adapter operations

The adapter registry contains one adapter per surface.

### Case manifest adapter

Required fields are `case_id`, `subject_id`, `context_key`, and `variants`.
The adapter retains input versions and normalizes variant identity through the
typed model. Missing variants are an input error, not an absent search result.

### Cohort record adapter

Required fields are `evidence_id`, `query_id`, `context_key`, and `records`.
The adapter retains the callable flag, source IDs, sample labels, and
selection criteria. A non-callable record is excluded with an explicit reason.

### Variant identity adapter

Required fields are a case snapshot and `variant_id`. The adapter resolves an
exact identity and groups only declared relationships. A missing ID is an
abstention. A context mismatch is withheld before detail is returned.

### Interval track adapter

Required fields are `source_id`, `genome_build`, `text`, and `context_key`.
Accepted formats include BED, narrowPeak, GFF3, and JSON. Coordinates and row
hashes remain attached to each rendered record. Parser issues are visible in
the workspace warning set.

## Query behavior

Workspace search supports text, exact context, record type, state, chromosome,
interval overlap, source intersection, tag conjunction, offset, and limit.
Results are sorted by record type, label, and record ID. This ordering makes
pagination stable even when the input fixture is provided in a different
order.

The bounded query limits are:

| Parameter | Lower bound | Upper bound |
| --- | ---: | ---: |
| offset | 0 | no fixed upper bound |
| limit | 1 | 500 |
| command-palette limit | 1 | 100 |
| overlap limit | 1 | 100 |

An interval matches when the record and request are on the same normalized
chromosome and their closed intervals overlap. A text match searches the
record ID, label, tags, searchable text, and serialized field values.

## Facet behavior

The browser returns deterministic counts for:

- record type;
- state;
- source ID.

Facet counts are computed over the complete ordered match set, not only the
current page. A client can therefore render a page while showing filters for
the full selection.

## Context behavior

Every workspace has one context key. Search with no context filter uses the
workspace context. Search with an equal context returns normal records.
Search with a different context returns an empty page, `out_of_domain`, and a
warning. Variant detail follows the same rule. Track and cohort builders carry
their context key into every record.

## Case operation runbook

1. Load or construct a `CaseManifest`.
2. Check that variant IDs are unique.
3. Build the immutable case workspace.
4. Inspect five section IDs.
5. Run a bounded search to obtain record counts and facets.
6. Inspect warnings for missing dossier or validation sections.
7. Inspect accessibility metadata from the frontier fixture.
8. Retain the workspace content address.

The case surface may be `partial` while remaining useful for navigation. That
state is expected when optional dossier or validation material is absent.

## Cohort operation runbook

1. Load records with source IDs and exact context keys.
2. Build a `CohortQuery` with explicit callability behavior.
3. Run the query builder and retain excluded counts and reasons.
4. Assemble the discovery evidence envelope.
5. Build the cohort workspace.
6. Inspect separate cohort, background, and control sections.
7. Search with a bounded record-type query.
8. Retain state, facets, and content address.

An empty selection is `absent`; it is not a supported empty table. A selection
available only in another context is `out_of_domain`.

## Variant operation runbook

1. Build the containing case workspace.
2. Request one exact variant ID.
3. Pass an optional context key only when the caller has one.
4. Inspect the variant record and typed relationship groups.
5. Treat an absent ID as `abstained`.
6. Never infer a relationship from distance, name similarity, or shared source.

The variant output is intentionally compact. It points back to the containing
workspace address so a client can retrieve the broader record set when needed.

## Track operation runbook

1. Parse the supplied track using the declared or detected format.
2. Retain the input hash, header hash, source ID, and parse issues.
3. Build a context-qualified track workspace.
4. Search by record type or interval overlap.
5. Inspect coordinate labels and source facets.
6. Preserve warning text when any parse issue exists.

Track rows are annotations. Interval overlap is not activity, binding,
regulation, mechanism, or causality.

## Review queue procedure

The review queue is built after policy decisions and release assembly. For each
execution it records:

- row identity;
- operation;
- priority;
- disposition;
- issue codes;
- source IDs;
- rationale;
- content address.

Supported positive rows with no issues are ready. Partial, absent, abstained,
invalid, and out-of-domain rows stay held or withheld. The queue does not
rewrite the original execution state.

## Artifact procedure

The artifact inventory contains seven public artifacts:

1. fixture;
2. evaluation;
3. metrics;
4. quality gate;
5. runtime;
6. release bundle;
7. release manifest.

Each artifact lists dependencies. The root is
`workspace-artifact-release`. A missing dependency, duplicate artifact ID, or
empty address should fail a future inventory extension.

## Troubleshooting

### Evaluation is not accepted

Print the failed check IDs. Compare the first failing record with its fixture
expectation. The most common causes are changed parser normalization, changed
context handling, changed issue wording, or an altered public fixture payload.

### Quality gate is not accepted

Inspect the quality check IDs. If evaluation passes but the quality gate fails,
the issue is usually in lineage, reconciliation, schema fields, accessibility
metadata, or boundary strings.

### Replay drifts

Compare evaluation and execution addresses. A fixture timestamp, unordered
mapping, parser output order, or runtime-only identifier may have entered the
addressed payload. Runtime IDs should remain outside deterministic evaluation
addresses.

### CLI output is empty

Use `python -m glio_noncode <command>` or the installed `glio-noncode` entry
point. Commands write JSON to standard output unless `--output` is supplied.

### CSV has the wrong row count

The header plus 16 review rows should produce 17 lines. Confirm the input
fixture is the default public aggregate and that no row is dropped while
building the review view.

## Operational handoff

Before a release commit, record:

- focused test result;
- full test result;
- targeted lint result;
- CLI compile result;
- staged restricted-metadata scan result;
- added-line count;
- commit ID;
- both remote Actions run IDs.

Do not describe a frontier as complete when only the implementation module
exists. The evidence gate, test modules, CLI, docs, registry, and CI command
matrix are part of the surface.
