# D07 operations and control policy

## Operation catalog

| ID | Operation | Family | Positive result |
| --- | --- | --- | --- |
| D07-C01 | chromatin track retrieval | chromatin context | supported |
| D07-C02 | accessibility delta | chromatin context | supported |
| D07-C03 | histone context | chromatin context | supported |
| D07-C04 | H3K27ac activity | chromatin context | supported |
| D07-C05 | methylation context retrieval | methylation | supported |
| D07-C06 | CpG creation/loss | methylation | supported |
| D07-C07 | methylation-sensitive motif | methylation | supported |
| D07-C08 | IDH hypermethylation context | methylation | supported |
| D07-C09 | chromatin-state segmentation | chromatin state | supported |
| D07-C10 | allele-specific chromatin | chromatin state | supported |
| D07-C11 | epigenomic purity | chromatin state | supported |
| D07-C12 | batch/composition correction | chromatin state | supported |
| D07-C13 | context imputation with confidence | cross-assay | accepted |
| D07-C14 | assay support and coverage | cross-assay | accepted |
| D07-C15 | cross-assay concordance | cross-assay | accepted |
| D07-C16 | chromatin evidence publish | cross-assay | published |

The operation IDs are distinct even where two family adapters expose the same
low-level operation name. That distinction prevents a C09 segmentation receipt
from being confused with the C13 cross-assay context tranche.

## Case policy

Each operation receives four cases:

| Scenario | Aggregate state | Result state | Counts |
| --- | --- | --- | --- |
| positive | accepted | family or release result | primary 1, secondary 1 |
| foreign_context | review | out_of_domain | primary 0, secondary 0 |
| malformed_input | review | invalid | primary 0, secondary 0 |
| identity_conflict | review | contradictory | primary 0, secondary 0 |

Controls are evaluated before family delegation. A foreign context therefore
cannot become a positive result merely because a family adapter recognizes the
record shape. A malformed record cannot reach a scientific adapter. An identity
conflict cannot be silently replaced by the most recent row.

## Receipt requirements

Every receipt preserves:

- case and operation identity;
- family and evidence plane;
- expected and observed aggregate states;
- expected and observed family result states;
- issue-code floors and observed issue codes;
- bounded primary and secondary counts;
- a sanitized summary;
- an output address and receipt address.

Raw family payloads remain on the fixture side of the boundary. They are not
copied into review summaries, CSV receipts, metrics, or release artifacts.

## Cross-assay primitives

C13 uses a two-feature public aggregate example. One value is observed and one
is filled from a declared prior with confidence 0.91. The output reports both
origins and does not turn the prior into a measurement.

C14 requires ATAC, DNase, and H3K27ac support for one feature. C15 receives
three concordant directions and records the direction mode and concordance.
C16 publishes two exact-context features only after the assay set is declared.

These outputs are descriptive evidence receipts. They are not calibrated
probabilities and do not establish biological causation.
