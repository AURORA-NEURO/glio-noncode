# D03 specimen architecture

The specimen architecture module is the composition boundary for Domain 03.
It connects the existing typed specimen planes into one public aggregate
execution path while preserving each plane's scientific logic and fixture
contract.

## Boundary

The checked-in fixture is `examples/specimen-architecture-public-aggregate.json`.
It is pinned to the context:

`GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment`

Every source receipt is HTTPS, public aggregate scoped, and content addressed.
The fixture contains 15 source receipts, 16 operation specifications, 16
positive payloads, and 48 control cases. Positive payloads are drawn from the
existing public aggregate fixture planes. Control payloads are intentionally
small boundary probes and contain no subject-level identity.

The release boundary retains source receipts, operation declarations,
expected states, result states, bounded counts, issue codes, and content
addresses. It does not publish raw subject-level observations.

## Composition model

The module has seven architectural planes:

| Plane | Responsibility | Operations |
| --- | --- | --- |
| ingestion | source and fixture intake | all operations |
| ontology | structured specimen vocabulary mapping | ontology_mapping |
| purity_integrity | matched normal, purity, ploidy, and integrity receipts | matched_normal, purity_ploidy, sample_integrity |
| origin_clonality | origin, mosaicism, cancer cell fraction, and subclone receipts | origin, mosaicism, cancer_cell_fraction, subclone |
| lineage | region, longitudinal, phase, and treatment context receipts | region_lineage, longitudinal_linking, phase_mapping, treatment_context |
| preanalytic | quality, assay, identity, and context envelope receipts | preanalytic_quality, assay_lineage, identity_adjudication, context_envelope |
| release | review, lineage, replay, artifacts, and publication gate | all operations |

Each operation has one positive case and three conservative controls:

1. positive: exact context and a typed adapter dispatch;
2. foreign_context: held with `context_mismatch` and `out_of_domain`;
3. malformed_input: held with `malformed_input` and `invalid`;
4. identity_conflict: held with `identity_conflict` and `contradictory`.

The policy layer makes this distinction before adapter execution. This keeps a
control from being mistaken for a scientific negative result.

## Contracts

`specimen_architecture_contracts.py` defines the common vocabulary:

- `SpecimenArchitectureSource` for source receipts;
- `SpecimenArchitectureOperationSpec` for operation identity and dependencies;
- `SpecimenArchitectureCase` for expected state, result, issue, and count;
- `SpecimenArchitectureExecution` for sanitized adapter output;
- `SpecimenArchitectureCaseReceipt` for expected-versus-observed closure;
- `SpecimenArchitecturePlan` for ordered operation dependencies;
- `SpecimenArchitectureReviewQueue` for held controls;
- `SpecimenArchitectureLedger` for hash-linked case lineage;
- `SpecimenArchitectureArtifact` and `SpecimenArchitectureRelease` for publication;
- `SpecimenArchitectureRuntime` for the 20-stage end-to-end run.

All meaningful objects are content addressed. Addresses are used for replay,
artifact joins, and release rollback keys; they are not identifiers for
individual people.

## Adapter dispatch

The operations module keeps the dispatch map explicit:

| Family | Adapter boundary | Positive operation count |
| --- | --- | ---: |
| core specimen context | `specimen_frontier_fixture_eval` | 4 |
| beta specimen frontier | `specimen_beta_frontier_fixture_eval` | 4 |
| lineage specimen frontier | `specimen_lineage_fixture_eval` | 4 |
| preanalytic frontier | `specimen_preanalytic_fixture_eval` | 4 |

The architecture layer normalizes the four receipt shapes into one execution
shape. It does not reimplement ontology mapping, matched-normal resolution,
variant-origin classification, lineage resolution, or preanalytic assessment.

## Validation depth

The validation matrix is seven planes by 16 operations, or 112 cells. Every
cell requires four declared cases and four passing receipts. The global
evaluation additionally requires 16 accepted positive receipts and 48 review
receipts. The release gate requires:

- accepted data audit;
- accepted operation evaluation;
- executable 16-node plan;
- accepted 48-item review queue;
- accepted 64-event ledger;
- 112 passing validation cells;
- closed schema, access, runbook, and replay checks;
- six addressed release artifacts.

## Running the module

The direct Python surface is:

```python
from glio_noncode.specimen_architecture_runtime import run_specimen_architecture

runtime = run_specimen_architecture(run_id="local-replay")
assert runtime.accepted
```

The focused tests are:

```text
python -m unittest tests.test_specimen_architecture tests.test_specimen_architecture_exports
```

The module is designed for offline replay. A caller may pass another fixture
path to the public data loader, provided the same closed contract and scope
rules are satisfied.
