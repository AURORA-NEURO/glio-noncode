# Editing-design frontier failure modes

| Condition | Result | Disposition |
| --- | --- | --- |
| foreign context | blocked | quarantine context |
| unsupported CRISPR mode | review | choose a declared mode |
| empty target inventory | review | add a target or retain hold |
| short guide sequence | review | provide a sufficient sequence window |
| multi-base base-edit substitution | review | route to a compatible design |
| reference mismatch | review | repair the sequence receipt |
| edit outside editing window | review | revise window or design |
| prime edit too long | review | review edit family |
| prime flank shortage | review | obtain a sufficient public sequence window |
| missing reporter pair | review | supply reference and alternate constructs |
| duplicate construct | review | repair construct identities |
| budget overflow | review | reduce or re-budget constructs |
| incomplete top-level payload | rejected | repair schema before execution |

The failure-injection plane executes an empty mapping through all four adapters and confirms schema rejection with visible issue codes.
