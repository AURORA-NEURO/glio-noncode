# Structural architecture evidence gate

The evidence gate separates adapter execution from publication. Every case
has an expected architecture state, expected result state, expected counts,
expected issue codes, and a content address. The evaluator compares those
declarations with the sanitized adapter receipt.

## State policy

`accepted` means that a positive case produced an addressed result without an
adapter issue, or that a declared control was held with its declared boundary
reason. `review` means the case is intentionally not publishable. The runtime
can publish a fixture only when all case assertions pass and the release gate
is satisfied.

The three architecture control classes are deliberately independent of the
four scientific families:

| Control | Required issue | Result state | Action |
| --- | --- | --- | --- |
| foreign context | `context_mismatch` | `out_of_domain` | verify assembly and context before replay |
| malformed input | `malformed_input` | `invalid` | repair input shape and replay |
| duplicate identity | `duplicate_identity` | `contradictory` | adjudicate identity without collapse |

The policy runs before a control can enter the adapter path. This preserves a
clear distinction between a domain detector finding an issue inside a valid
record and the architecture rejecting a record envelope at the boundary.

## Seven validation planes

Each operation receives a cell for every plane:

1. ingestion — case identity, public identifier, and payload shape;
2. reconstruction — operation and input/output contracts;
3. haplotype — operation, source joins, and context retention;
4. context — exact six-field context and source joins;
5. provenance — sources and content addresses;
6. review — expected state and issue declaration;
7. release — address and public identifier required for export.

The resulting matrix has 112 cells. A missing field is represented as an
explicit review state rather than being silently inferred.

## Source and privacy boundary

Source receipts require HTTPS, public aggregate scope, a version, a license,
and an address. The fixture audit rejects common subject-level identifiers,
including patient, individual, medical-record, specimen, and sample-name
fields. No export function includes the original operation payload in a
receipt view.

## Quality checks

The quality gate checks the source audit, 20-stage runtime, 64 case receipts,
16 positive cases, 48 held controls, dependency plan, review queue, 64-event
ledger, six artifacts, and published release state. Any failed check leaves
the release in `review`.
