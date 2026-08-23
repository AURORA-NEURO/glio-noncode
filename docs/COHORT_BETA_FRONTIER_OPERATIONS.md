# C05-C08 operations and review protocol

The public aggregate evidence plane has three dispositions:

| Disposition | Meaning | Default action |
| --- | --- | --- |
| `publish` | A supported exact-context row passed fixture reconciliation and the claim ceiling. | Include the bounded summary and immutable receipt. |
| `review` | A row is incomplete or ambiguous but may be resolved with additional evidence. | Collect comparator, definition, or transport evidence. |
| `quarantine` | A row is foreign-context, contradictory, absent, or contract-invalid. | Exclude it from the target aggregate and retain its reason. |

The operation owners inspect different evidence:

1. C05 recurrence review checks distinct sample identity, callable flags,
   recurrence thresholds, local hotspot window, and source version.
2. C06 burden review checks the region key, exact context, callable bases,
   overlap rules, background comparator, and denominator provenance.
3. C07 functional review checks feature namespace, support bounds, observed
   versus control labels, leading ties, and feature-definition provenance.
4. C08 set review checks pathway or regulon namespace, versioned membership,
   gene deduplication, direction counts, and contradictory leading sets.

Every review starts with the same questions: does the row match the exact
context, are public source receipts present, is the declared comparator
available, and does the proposed wording stay below the claim ceiling? A
reviewer cannot promote a row merely because the result is numerically large.
The relevant denominator and source receipt must be present.

The release owner may publish only the four supported fixture rows. Twelve
other rows remain represented in the review and quarantine surfaces. This is
intentional: the release is designed to preserve uncertainty and boundary
failures for later work.

The calibration layer records four future requirements: a recurrence null, a
callable regional null, matched feature controls, and pathway or regulon set
transport. These requirements do not alter the descriptive runtime state and
are not converted into p-values or significance flags.

Mutation probes cover missing context, foreign context, unknown source,
non-callable recurrence, missing burden comparator, missing functional
controls, direction flips, duplicate row keys, missing callable bases, and
invalid recurrence thresholds. Each probe is expected to block or isolate
the changed input.

The operational matrix, error taxonomy, claim dictionary, fixture manifest,
module catalog, release checks, safety report, and review protocol can be
inspected independently. Their content addresses are carried into the main
runtime report when a release rehearsal is executed.
