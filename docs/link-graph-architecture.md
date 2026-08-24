# D10 Regulatory Link Graph and Target Association

D10 is the public aggregate for regulatory-element, variant, and gene association evidence in adult glioma. It joins four public family tranches into one deterministic release surface:

| Family | Operations | Scope |
| --- | ---: | --- |
| `link_graph_foundation_frontier` | C01-C04 | coordinate overlap, nearest-gene baseline, cCRE assignment, enhancer-gene consensus |
| `link_graph_beta_frontier` | C05-C08 | activity-by-contact, coaccessibility, molecular-QTL, allele-specific evidence |
| `link_graph_alpha_frontier` | C09-C12 | perturbation, 3D contact, promoter tethering, multi-gene graph |
| `link_frontier` | C13-C16 | dependence correction, target-gene ranking, calibration/abstention, evidence publication |

The aggregate boundary is `public_aggregate_non_patient` with exact context `GRCh38|glioma|adult|stem_like|core|unknown`. It has 19 source receipts, 16 ordered operations, and 64 cases. Every operation contains one positive family record and three preserved family controls, yielding 16 positive and 48 control cases.

## What is retained

D10 does not replace the family evaluators. It imports their public fixtures, evaluates each family record through its existing adapter path, and places the result into a shared receipt shape. The delegate fixture ID, delegate record ID, delegate context, result state, issue codes, output address, source receipts, and sanitized payload summary remain visible.

The family result state is not collapsed into a binary answer. Examples include `supported`, `partial`, `ambiguous`, `absent`, `abstained`, `contradictory`, `out_of_domain`, `invalid`, and `published`. The aggregate state is separate: positive cases are `accepted`, while all controls are `review`.

## Runtime and release

The runtime has 22 stages covering fixture construction, source auditing, schema validation, dependency planning, four family readiness gates, case execution, review, lineage, ledger, metrics, replay, artifacts, release, quality, depth, control closure, and observability. It publishes only after 392 checks pass and six sanitized artifacts are materialized.

Link association is descriptive and non-causal. The release does not select a clinical target, infer treatment response, or turn proximity, contact, perturbation, or regulatory activity into a diagnostic conclusion.

The checked-in public fixture is [data/link-graph-architecture-public-aggregate.json](../data/link-graph-architecture-public-aggregate.json).
