# D10 Operation Catalog

| ID | Family | Operation | Evidence retained |
| --- | --- | --- | --- |
| D10-C01 | foundation | coordinate overlap | variant and regulatory-element interval relationship |
| D10-C02 | foundation | nearest gene | distance, ties, and bounded-window abstention |
| D10-C03 | foundation | cCRE assignment | cCRE multiplicity and no-assignment controls |
| D10-C04 | foundation | enhancer-gene consensus | method-specific support and contradiction |
| D10-C05 | beta | activity by contact | activity, contact, replicate, and partial support |
| D10-C06 | beta | coaccessibility | score, alternative genes, and missing evidence |
| D10-C07 | beta | molecular QTL | effect, q-value, bounded support, and weak evidence |
| D10-C08 | beta | allele-specific | gain/loss direction, conflict, and missing evidence |
| D10-C09 | alpha | CRISPR perturbation | perturbation mode, direction, effect, and disagreement |
| D10-C10 | alpha | 3D contact | assay, resolution, signal, and alternative genes |
| D10-C11 | alpha | promoter tethering | distance prior, components, ties, and abstention |
| D10-C12 | alpha | multi-gene graph | edge paths, single evidence, and contradiction |
| D10-C13 | frontier | dependence correction | correlated support groups and corrected link support |
| D10-C14 | frontier | target-gene ranking | component scores, ranks, alternatives, and support |
| D10-C15 | frontier | calibration and abstention | uncertainty, calibration error, and decision state |
| D10-C16 | frontier | evidence publication | bundle identity, context, receipts, and publication state |

## Control order

The first row for every operation is the family positive. The next three rows are retained as `control_a`, `control_b`, and `control_c`. Their family-specific issue vocabulary remains intact. This prevents the aggregate from erasing meaningful distinctions such as `distance_tie`, `missing_evidence`, `direction_disagreement`, `contradictory_evidence`, `publication_context_mismatch`, or `invalid_publication_input`.

## Shared receipt checks

Every case receives checks for aggregate state, family result state, issue vocabulary, count summary, source receipt presence, and output address. Eight global checks then verify source, operation, case, positive, control, receipt, pass-rate, and family coverage. The resulting total is 64 times six plus eight: 392 checks.
