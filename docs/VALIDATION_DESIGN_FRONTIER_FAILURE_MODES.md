# Validation-design frontier failure modes

| Failure | State | Required action |
| --- | --- | --- |
| wrong context | blocked | quarantine the context and review the source join |
| missing evidence dimension | review | add a public evidence receipt or retain the gap |
| unsupported assay | review | route to a supported capability or review |
| unchanged MPRA alleles | review | repair the allele pair |
| construct budget overflow | review | reduce or explicitly re-budget constructs |
| invalid STARR-seq strand | review | use `+` or `-` |
| empty construct list | review | add constructs or keep package open |
| missing top-level fields | rejected | repair the payload shape |
| private marker | prohibited | remove the input before processing |

The failure-injection stage executes empty mappings through all four operation entry points. No failure case is silently promoted to a success state. The evaluator preserves issue codes even when the role is a control row.
