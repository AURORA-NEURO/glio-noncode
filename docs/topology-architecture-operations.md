# D09 Operation Catalog

Each D09 operation is a separately addressable contract. The family evaluator supplies the positive observation; the aggregate retains the public source receipts and applies the shared context, identity, input, and release controls. A receipt also retains the aggregate context and the delegated family context so context transport can be inspected rather than inferred.

| ID | Family | Plane | Operation | Public evidence focus |
| --- | --- | --- | --- | --- |
| D09-C01 | context | context_qc | contact import | paired contact observations with source identifiers |
| D09-C02 | context | context_qc | contact matrix QC | matrix dimensions, sparsity, and quality thresholds |
| D09-C03 | context | context_qc | boundary ensemble | boundary calls across declared observations |
| D09-C04 | context | context_qc | insulation delta | local insulation comparison with direction retained |
| D09-C05 | beta | contact_inference | loop or stripe evidence | loop and stripe record support |
| D09-C06 | beta | contact_inference | promoter capture | promoter-centered contact evidence |
| D09-C07 | beta | contact_inference | enhancer-promoter contact | enhancer and promoter pairing with context |
| D09-C08 | beta | contact_inference | activity by contact | contact-weighted regulatory support |
| D09-C09 | alpha | topology_alpha | boundary motif | declared motif and spacing evidence |
| D09-C10 | alpha | topology_alpha | CTCF/cohesin support | factor support at topology boundaries |
| D09-C11 | alpha | topology_alpha | IDH insulator state | IDH-conditioned insulation observation |
| D09-C12 | alpha | topology_alpha | structural-variant rewiring | declared rearrangement and contact change |
| D09-C13 | frontier | frontier_release | ecDNA contact | extrachromosomal contact path with bounded claim |
| D09-C14 | frontier | frontier_release | compartment switch | signed compartment transition and delta |
| D09-C15 | frontier | frontier_release | topology uncertainty transport | uncertainty carried across context joins |
| D09-C16 | frontier | frontier_release | topology evidence publication | publication receipt and release state |

## Delegation boundary

Positive cases use the family-specific public evaluators already present in the repository. The aggregate does not fabricate measurements. It converts each family result into a common receipt shape, preserves family summary fields, and binds the result to the aggregate operation and source registry.

Control cases are intentionally uniform so every operation is tested against the same release boundary:

- `foreign_context`: adult scope is replaced by pediatric scope and must yield `context_mismatch` with review state.
- `malformed_input`: the required payload shape is invalid and must yield `malformed_input` with an invalid result state.
- `identity_conflict`: the declared record identity disagrees with the observed identity and must yield `identity_conflict` with a contradictory result state.

## Coverage invariants

The contract matrix requires four families, four planes, 16 operations, and four cases per operation. Control coverage requires 16 observations for each held scenario. The evaluation requires 64 passing receipts and 458 passing checks: seven checks for each case and ten global checks for source, operation, case, state, family, balance, and context closure. Any deviation blocks the release.
