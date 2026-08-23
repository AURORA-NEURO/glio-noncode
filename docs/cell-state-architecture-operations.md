# D08 Operation Register

The operation register is ordered and dependency-aware. Each row joins a capability, family, plane, source receipts, input contract, output contract, and control policy.

| ID | Operation | Family | Plane | Positive output |
| --- | --- | --- | --- | --- |
| D08-C01 | disease ontology context | cell context frontier | taxonomy | supported |
| D08-C02 | adult-pediatric route | cell context frontier | taxonomy | supported |
| D08-C03 | molecular class state | cell context frontier | taxonomy | supported |
| D08-C04 | territory context assembly | cell context frontier | taxonomy | supported |
| D08-C05 | developmental lineage prior | cell context beta frontier | prior | supported |
| D08-C06 | glioblastoma malignant state prior | cell context beta frontier | prior | supported |
| D08-C07 | IDH-mutant lineage state prior | cell context beta frontier | prior | supported |
| D08-C08 | H3K27-altered developmental state prior | cell context beta frontier | prior | supported |
| D08-C09 | spatial niche prior | cell context alpha frontier | territory | supported |
| D08-C10 | core-margin territory prior | cell context alpha frontier | territory | supported |
| D08-C11 | recurrence state prior | cell context alpha frontier | territory | supported |
| D08-C12 | treatment-induced state prior | cell context alpha frontier | territory | supported |
| D08-C13 | cell-state abundance interval | cell state frontier | cell_state | accepted |
| D08-C14 | single-cell reference mapping | cell state frontier | cell_state | accepted |
| D08-C15 | cell-state OOD detection | cell state frontier | cell_state | accepted |
| D08-C16 | cell-state context publication | cell state frontier | cell_state | published |

## Delegation contract

For C01-C12, the aggregate stores a family record identifier, family context, family record projection, family receipt summary, and the operation payload. The evaluator uses the record identifier to locate the positive family receipt and copies its observed state and issue codes into a D08 execution receipt.

For C13-C16, the payload is typed at the D08 boundary and sent to the corresponding primitive. The evaluator records the primitive report in a sanitized summary, keeps stable identifiers and review identifiers, and addresses the resulting output.

## Control contract

Controls are evaluated before family delegation. A foreign context returns `out_of_domain`; malformed input returns `invalid`; identity conflict returns `contradictory`. Each held result carries one stable issue code and zero primary/secondary counts. This makes a false positive impossible to hide behind a family evaluator.

## Evidence joins

Operations reference all source receipts for their family. Cases reference the source subset carried by their positive family record. The source registry prefixes family identifiers so collisions between public tranches cannot silently merge. The lineage view exposes family-to-source, source-to-operation, and operation-to-case relationships.
