# Module fabric operations

The module fabric is a repository integration surface. It audits whether the
capability ledger's declared implementation and test references resolve, and
whether those references remain closed across the full 16-domain product
denominator.

It is intentionally separate from domain science. A resolved reference proves
that a module or test surface can be imported. It does not prove that the
underlying method is scientifically sufficient, calibrated, causal, clinical,
or suitable for deployment.

## Operations

| Operation | Input | Output | Positive condition | Held-control condition |
| --- | --- | --- | --- | --- |
| `resolve_capability_references` | one public aggregate capability row | implementation and test receipts | all ledger references resolve | foreign context or ownership drift is review |
| `module_fabric_audit` | complete public aggregate fixture | evaluation, depth, lineage, and release receipts | every declared reference closes | unresolved reference blocks release |

## Domain denominator

The catalog contains 256 capabilities: 16 capabilities in each of D01 through
D16. The fixture intentionally samples the first capability in each domain,
with one positive row and one control row per domain. This gives an exact,
balanced 32-row integration sample while the reference resolver audits the
full catalog rather than only the sampled rows.

The positive row expects:

- the declared capability to exist;
- the capability prefix and domain to match;
- the declared capability order to match the catalog;
- all implementation references to resolve;
- all test-module references to resolve; and
- the exact public aggregate context to be retained.

The control row deliberately declares a foreign domain and a foreign context.
It must remain `review` and must retain both `foreign_domain` and
`context_mismatch`. A control cannot be promoted merely because its imports
are valid.

## Source boundary

The checked-in fixture uses five HTTPS receipts. The receipts are public
aggregate portals or repository-level references; they are not individual
records. Source IDs are joined explicitly from each row to the source
registry. Missing or foreign source IDs fail the data boundary before release.

## CLI

```powershell
python -m glio_noncode module-fabric-fixture --output examples/module-fabric-public-aggregate.json
python -m glio_noncode module-fabric-data-audit
python -m glio_noncode module-fabric-evaluate
python -m glio_noncode module-fabric-depth
python -m glio_noncode module-fabric-replay
python -m glio_noncode module-fabric-quality
python -m glio_noncode module-fabric-runtime
python -m glio_noncode module-fabric-report --format markdown
python -m glio_noncode module-fabric-review-csv
python -m glio_noncode module-fabric-failures
```

The commands return success only when their own acceptance state is true.
`module-fabric-review-csv` is a projection command and returns success after
serializing the bounded rows; it does not turn review rows into accepted rows.

## Reference resolution

A dotted declaration is first attempted as a complete importable module. If
that fails, the resolver searches the final dotted segment as an attribute of
the longest importable module prefix. This distinction matters for test
modules such as `tests.test_module_fabric` and callable declarations such as
`glio_noncode.module_fabric_operations.evaluate_module_fabric_record`.

Every receipt retains:

- the original declaration;
- implementation or test kind;
- resolved module name;
- optional symbol name;
- resolved or failed state;
- bounded error detail; and
- a content address.

The public projection retains counts and declaration strings but does not
copy module objects, raw fixture payloads, or private subject fields.

## Failure behavior

The operation keeps failures explicit:

- unknown capability: `unknown_capability` and `review`;
- prefix or domain drift: `domain_mismatch` or `foreign_domain`;
- order drift: `capability_order_mismatch`;
- missing declaration sets: `missing_implementation_references` or
  `missing_test_references`;
- import or attribute failures: a namespaced reference failure code; and
- foreign context: `context_mismatch`.

Positive rows with any issue are held for review. Controls with no boundary
issue receive `control_boundary_missing` and remain held. This prevents a
control from becoming an accepted result by accident.
