# Domain 12 C05-C08 depth contract

This release tranche turns four cohort primitives into a reviewable aggregate
evidence plane. The operation layer remains deliberately descriptive:

| ID | Question | Primary denominator | Positive output |
| --- | --- | --- | --- |
| C05 | Do variants recur across distinct samples or cluster locally? | Callable recurrence observations | Recurrent variant and hotspot receipt |
| C06 | Does a region exceed a callable-space comparator? | Callable bases | Burden, expected count, and excess receipt |
| C07 | Do observed variants converge on a functional feature? | Feature support rows | Feature ranking and observed/control contrast |
| C08 | Do genes converge on a pathway or regulon? | Versioned set membership rows | Set ranking and direction-conflict receipt |

Each operation has four paths: one supported path, one absence or
contradiction path, one partial path, and one foreign-context path. The fixture
is public-aggregate only and uses pseudonymous row keys. It is not a clinical
cohort and it is not a calibrated statistical null.

The release contract is layered. Boundary modules declare public source
receipts and exact context. Adapter and schema modules reject malformed
shapes. Execution modules invoke the existing typed testers. Measurement
modules retain denominators and control counts. Trace modules connect source,
input, result, policy, and release addresses. Projection modules separate
public summaries from review and operations views. Control modules enforce
state ceilings, claim ceilings, change control, mutation probes, and review
protocols.

The four supported rows are the only rows eligible for the public summary.
Absent, partial, foreign-context, and contradictory rows remain in the review
or quarantine surfaces. A comparator is never inferred when it is missing.
Opposing directions are never averaged away. A missing calibration requirement
is recorded as a future evidence need rather than represented as a
significance result.

Useful entry points:

```powershell
python -m glio_noncode cohort-beta-frontier-fixture --output fixture.json
python -m glio_noncode cohort-beta-frontier-evaluate --output evaluation.json
python -m glio_noncode cohort-beta-frontier-quality --output quality.json
python -m glio_noncode cohort-beta-frontier-report --format markdown --output report.md
```

The module catalog, release checks, mutation cases, evidence matrix, sampling
notes, comparator receipts, calibration requirements, access model, safety
report, publication plan, and review protocol are independently addressable
so downstream review can inspect one plane without losing the full runtime
receipt.
