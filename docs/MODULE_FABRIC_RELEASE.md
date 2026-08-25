# Module fabric release boundary

The module fabric release is a research-workflow integration receipt. It is
publishable only when all release gates pass.

## Release gates

| Gate | Requirement |
| --- | --- |
| public data | fixture version, boundary, HTTPS sources, counts, and addresses pass |
| evaluation | all 32 records pass all 256 checks |
| depth | 256 catalog rows, 16 domains, implementation/test coverage, and reference closure pass |
| lineage | every fixture, source, record, execution, and reference node has valid endpoints |
| replay | the same fixture yields the same evaluation and receipt addresses |
| quality | all combined assurance checks pass |

The release carries at least these content-addressed artifacts:

- fixture;
- data audit;
- fixture evaluation;
- metrics;
- depth audit;
- lineage graph;
- replay report; and
- quality gate.

An unresolved implementation or test declaration creates a reference failure,
which makes the positive row review and blocks the release. A held control is
not a failure of the source data; it is evidence that the boundary test is
working.

## Runtime

The full runtime publishes 24 ordered stages:

1. fixture load;
2. public boundary audit;
3. catalog snapshot;
4. domain denominator closure;
5. capability denominator closure;
6. positive/control indexing;
7. reference resolution;
8. fixture evaluation;
9. metrics conservation;
10. depth audit;
11. lineage closure;
12. replay verification;
13. combined quality gate;
14. release materialization;
15. manifest serialization;
16. source-join retention;
17. control-boundary retention;
18. public projection sanitization;
19. stage receipt addressing;
20. release decision;
21. evaluation checks closure;
22. compliance closure;
23. observability closure; and
24. runtime finalization.

The separate operational ledger intentionally retains the stable first 20
stages so downstream reconciliation consumers keep a fixed denominator. The
bundle boundary includes the complete 24-stage runtime report.

Each stage has an input address and output address. This makes a stage-level
drift visible without copying domain payloads into the runtime report.

## Allowed and excluded uses

Allowed uses are repository reference auditing, aggregate integration replay,
release-readiness review, and routing unresolved declarations for repair.

Excluded uses are biological inference, clinical utility validation, treatment
recommendation, individual classification, or deployment authorization. The
module fabric can prove that a declaration resolves; it cannot prove that the
resolved implementation is scientifically correct.

## Recovery

When a release is held:

1. inspect the failed check or reference receipt;
2. repair the catalog declaration or implementation surface;
3. rerun `module-fabric-evaluate`;
4. rerun `module-fabric-depth` and `module-fabric-replay`;
5. rerun `module-fabric-quality`; and
6. create a new release address.

Existing receipts remain immutable. A repair is a new snapshot, not an edit of
the previous release.
