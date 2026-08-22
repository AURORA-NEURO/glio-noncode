# Workspace frontier release notes

## Release identity

The Domain 15 C01–C04 release surface is identified by:

```text
workspace-frontier-public-aggregate
2026.08.d15-c01-c04.v1
2026.08.d15.v1
```

The first value is the fixture ID. The second is the fixture revision. The
third is the contract and schema revision.

## Included surfaces

- case workspace with five section IDs;
- cohort workspace with separate selected, background, and control sections;
- variant explorer with exact identity and declared relationships;
- regulatory track browser with source-accounted interval records.

## Evidence included

The release contains:

- five public HTTPS source receipts;
- 16 fixture records;
- four positive paths;
- twelve controls;
- 120 evaluation checks;
- 14 quality checks;
- 21 depth checks;
- 36 lineage edges;
- 13 descriptive metrics;
- eight ordered runtime stages;
- 24 observability events;
- 972 bounded threshold probes;
- seven public artifacts;
- 33 scenarios;
- 16 review rows;
- three ready research-navigation rows;
- thirteen held or withheld rows.

## Registry result

After this build the repository ledger reports:

| Measure | Value |
| --- | ---: |
| total capabilities | 256 |
| verified | 132 |
| partial | 124 |
| planned | 0 |
| total implementation coverage | 51.56% |
| MVP capabilities | 64 |
| MVP implementation coverage | 50.0% |

The four newly verified rows are Domain 15 C01 through C04.

## Release gate

The release state is `ready` when all of the following pass:

1. bundle accepted;
2. quality gate accepted;
3. replay stable;
4. runtime accepted;
5. public boundary exact;
6. artifact addresses present.

The ready state does not mean every row is supported. Review rows remain in the
release object and preserve their own states and issue codes.

## Review outcomes

The default positive outcomes are:

| Surface | State | Disposition |
| --- | --- | --- |
| case workspace | partial | hold |
| cohort workspace | supported | ready |
| variant explorer | supported | ready |
| regulatory track browser | supported | ready |

The partial case result is intentional because no optional dossier snapshot is
provided. The three controls on each surface remain held or withheld according
to their state and issue codes.

## Boundary statement

This release is a deterministic research navigation package backed by public
aggregate data. It does not establish clinical validity, diagnosis, prognosis,
treatment response, causality, activity, binding, or individual-level risk.
Interval overlap remains an annotation filter. Cohort counts remain descriptive
fixture accounting. A missing variant remains abstained.

## Compatibility

Consumers may rely on:

- stable operation enum values;
- stable state enum values;
- exact context key transport;
- declared issue code strings;
- deterministic fixture ordering;
- content-addressed source and execution receipts;
- JSON trailing newline;
- review CSV header and row shape.

Consumers should not rely on:

- browser rendering;
- screen-reader behavior;
- large-track throughput;
- multi-user persistence;
- identity or access governance;
- external source availability;
- clinical meaning of any state.

## Upgrade procedure

For a compatible documentation-only or CLI help update:

1. run focused tests;
2. run full tests;
3. run targeted lint;
4. run CLI compile;
5. run staged metadata scan;
6. push the commit;
7. wait for both Actions lanes.

For a fixture or schema change:

1. create a new fixture version;
2. update source and record receipts;
3. update controls and expected issue sets;
4. update evaluation arithmetic;
5. update replay expectations;
6. update metrics and depth counts;
7. update docs, registry, and CI;
8. run the full release procedure.

## Handoff commands

```powershell
glio-noncode workspace-frontier-data-audit
glio-noncode workspace-frontier-evaluate
glio-noncode workspace-frontier-quality-gate
glio-noncode workspace-frontier-runtime
glio-noncode workspace-frontier-release
glio-noncode workspace-frontier-review-queue
```

For a CSV handoff:

```powershell
glio-noncode export-workspace-frontier-review-csv --output workspace-frontier-review.csv
```

## Verification record

The commit record should include the exact commit ID, test totals, warning
status, focused lint result, compile result, staged line count, restricted
metadata scan result, and both Actions URLs. This keeps the handoff tied to a
specific repository state.

## Follow-on work

The next Domain 15 partial rows include topology viewing, causal-chain
exploration, posterior decomposition, evidence tables, validation experiment
boards, notebook launch plans, shareable snapshots, and collaboration access.
Those surfaces remain separate capability packages and should not be inferred
from the C01–C04 read-model gate.
