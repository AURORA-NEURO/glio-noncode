# Workspace frontier review playbook

## Review objective

Reviewers should determine whether the four Domain 15 workspace surfaces
preserve exact context, explicit state, source receipts, bounded queries,
accessibility metadata, and release evidence. The review is about contract
integrity, not visual polish or scientific interpretation.

## First pass

Read these files in order:

1. `docs/WORKSPACE_FRONTIER_EVIDENCE_GATE.md`;
2. `docs/WORKSPACE_FRONTIER_SCHEMA.md`;
3. `src/glio_noncode/workspace_frontier_public_data.py`;
4. `src/glio_noncode/workspace_frontier_fixture_eval.py`;
5. `src/glio_noncode/workspace_frontier_quality_gate.py`;
6. `tests/test_workspace_frontier_evidence.py`;
7. `.github/workflows/ci.yml`.

Confirm that the code, tests, docs, and CI use the same fixture version and
operation names.

## Required checks

### Source boundary

- all source URIs use HTTPS;
- source IDs are unique;
- every record has a source ID;
- the boundary is `public_aggregate_non_patient`;
- no individual-level row was introduced;
- content addresses are present.

### Role separation

- there are four positive rows;
- there are twelve controls;
- controls cannot become accepted executions;
- positive and control issue sets are distinct where expected;
- review queue dispositions match policy.

### Context protection

- the exact fixture context appears in every record;
- mismatch controls return no applicable rows;
- variant mismatch is withheld before detail is returned;
- track and cohort mismatch remain explicit.

### Query protection

- pagination limits remain bounded;
- facets cover full match sets;
- intervals use normalized chromosomes;
- overlap is inclusive at the closed interval boundary;
- source and state filters do not mutate underlying records.

### Accessibility retention

- case keyboard order is present;
- case labels are present;
- focus boundary is present;
- case reading order is present;
- cohort row and section labels are present;
- track interval, coordinate, and issue labels are present.

## Deep review by surface

### Case workspace

Check that duplicate variant IDs fail before workspace construction. Check that
missing dossier material produces a partial state and a warning rather than
invented evidence. Check that the five section IDs are ordered and stable.

### Cohort workspace

Check that non-callable rows remain excluded when required. Check that selected
rows, background summary, and controls have different record types. Check that
the exclusion reason map survives into the execution output.

### Variant explorer

Check that one exact ID is resolved. Check that an absent ID produces
abstention. Check that the relationship list is empty when no link is declared.
Check that nearby coordinates are not used as a fallback.

### Regulatory track browser

Check that valid features keep normalized coordinates and source attributes.
Check that malformed rows leave a partial batch with an issue. Check that an
empty input is invalid. Check that the warning explains annotation-only use.

## Evidence arithmetic review

Verify the following counts directly from the output objects:

| Object | Expected |
| --- | ---: |
| fixture sources | 5 |
| fixture records | 16 |
| positive rows | 4 |
| controls | 12 |
| evaluation checks | 120 |
| quality checks | 14 |
| depth checks | 21 |
| lineage edges | 36 |
| metrics | 13 |
| runtime stages | 8 |
| observability events | 24 |
| threshold probes | 972 |
| artifacts | 7 |
| review rows | 16 |
| ready rows | 3 |
| held rows | 13 |
| CSV lines | 17 |

If a count changes, determine whether the contract changed or a row was
silently dropped. Count changes should not be accepted because they “look
cleaner.”

## Replay review

Run two replay commands and compare:

- fixture ID;
- evaluation address;
- execution address tuple;
- drift field list;
- stable flag.

The replay ID may differ. The addressed evaluation and execution rows must not.
If they differ, inspect timestamps, mapping order, enum reconstruction, and
parser normalization.

## Release review

The release manifest is ready only when bundle, quality, replay, runtime,
boundary, and address checks pass. Inspect the root artifact and dependency
addresses. Verify that a ready release still includes held review rows.

## CLI review

Run the commands below and inspect both exit code and JSON shape:

```powershell
glio-noncode workspace-frontier-data-audit
glio-noncode workspace-frontier-evaluate
glio-noncode workspace-frontier-quality-gate
glio-noncode workspace-frontier-runtime
glio-noncode workspace-frontier-review-queue
glio-noncode workspace-frontier-thresholds
glio-noncode export-workspace-frontier-review-csv
```

The CLI should use the default fixture when no input path is supplied. A
malformed input path should return a nonzero exit code and a useful error.

## Test review

Focused tests should cover both direct module calls and subprocess CLI calls.
The direct tests check typed values and addresses. The CLI tests check parser
registration, serialization, output paths, and malformed input behavior.

The full suite is required because the registry coverage counts and package
exports are shared surfaces.

## Metadata review

New repository lines must not add authorship fields, runtime attribution
fields, co-signature trailers, or implementation-language metadata. Keep
commit messages descriptive of the build boundary. Keep the staged addition
scan clean before commit.

## Scope review

This frontier does not add browser rendering, multi-user collaboration,
clinical interpretation, causal inference, treatment recommendations, or
individual-level data. Those are separate capability surfaces. Scope should
remain narrow enough that the evidence gate can be replayed in every CI lane.

## Approval checklist

- [ ] public aggregate boundary is explicit;
- [ ] five source receipts are HTTPS and addressed;
- [ ] four positive rows and twelve controls are present;
- [ ] 120 evaluation checks pass;
- [ ] 14 quality checks pass;
- [ ] 21 depth checks pass;
- [ ] replay has no drift;
- [ ] context controls withhold rows;
- [ ] source and issue accounting survives export;
- [ ] accessibility metadata survives output;
- [ ] review queue retains held rows;
- [ ] CLI commands run without a fixture path;
- [ ] focused suite passes;
- [ ] full suite passes;
- [ ] targeted lint passes;
- [ ] staged metadata scan is clean;
- [ ] both Actions lanes pass.
