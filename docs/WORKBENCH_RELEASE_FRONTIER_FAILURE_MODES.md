# Workbench release frontier failure modes

| Failure | State | Action |
| --- | --- | --- |
| required form field missing | review | complete the field and rerun |
| form value outside choices | review | use declared vocabulary or update schema |
| foreign review context | blocked | quarantine the row |
| report section list empty | review | provide an ordered section |
| duplicate section identity | review | issue unique section IDs |
| unsupported report format | review | select JSON, Markdown, or CSV |
| search no matches | review | retain no-match evidence and inspect scope |
| search record identity missing | rejected | repair record identity |
| search foreign context | blocked | prevent transport across context |
| accessibility criterion failed | review | remediate the surface |
| partial accessibility criteria | review | declare and evaluate all required criteria |
| private marker in output | rejected by safety gate | remove the private field |
| invalid schema shape | rejected | repair input structure |

The runtime never converts an empty result into a negative scientific finding. It
never converts a failed interface criterion into a user-level judgment. It never
silently drops a foreign-context row. A repair must be replayed against the same
record and then against the complete fixture before release.
