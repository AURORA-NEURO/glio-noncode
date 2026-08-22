# Domain 11 traceability map

## Traceability objective

Traceability connects a declared public source to a fixture record, an operation
execution, a check, a metric, a policy decision, a quality gate, a bundle, and a
release manifest. The map lets a reviewer move from a summary back to the
smallest available receipt.

## Primary chain

```text
source receipt
  -> fixture record
    -> normalized input
      -> operation output
        -> evaluation checks
          -> metrics and policy
            -> lineage and reconciliation
              -> quality gate
                -> release bundle
                  -> release manifest
```

Every arrow is represented by an address or an explicit edge. A summary without
a parent address is incomplete for this boundary.

## Source to record

The record stores `source_ids`. The fixture source map resolves those IDs to
source receipts. The audit checks that every ID resolves and that the source URI
uses HTTPS.

| Record family | Source context |
| --- | --- |
| C13 | ENCODE and NCBI GEO |
| C14 | ENCODE and 4D Nucleome |
| C15 | NCBI GEO and 4D Nucleome |
| C16 | PubMed and NIH Common Fund |

Source references are not treated as independent replications by default. The
lineage graph shows reuse of a source receipt explicitly.

## Record to execution

The evaluator retains one execution per record. The execution stores operation,
role, context, state, issues, output, and error. The execution address is based
on these fields and does not include timing.

The evaluator also creates seven checks per record. These checks compare:

- expected state;
- expected issue tuple;
- operation identity;
- context;
- source references;
- address presence;
- role and acceptance.

## Execution to checks

Check IDs use the record ID and check kind:

```text
C13-POS-001:state
C13-POS-001:issues
C13-POS-001:operation
```

Global checks use the `global:` prefix. This naming scheme allows a reviewer to
find a failure without reading every output field.

## Checks to metrics

Metrics derive from execution and check values. Each metric keeps numerator and
denominator. Operation acceptance is one accepted execution out of four for
each operation in the current fixture. Control rejection is twelve out of
twelve.

Metrics are not independent evidence. They summarize repository behavior and
fixture coverage.

## Policy trace

Policy decisions point to operation and issue code sets. The current policy
allows supported aggregate paths into review and allows a valid dossier
manifest into publication. Controls remain in evaluation even when positive
paths are releasable.

The policy decision address can be inspected beside the release bundle address.

## Reconciliation trace

Reconciliation joins a fixture record to its execution by record ID. It compares
expected and observed state and exact issue tuple. The resulting item stores the
policy decision for that operation.

The reconciliation address is included in the bundle so a release cannot hide a
changed control expectation.

## Lineage trace

The lineage graph has two edge kinds:

| Edge kind | Parent | Child |
| --- | --- | --- |
| source-to-execution | source receipt | execution receipt |
| fixture-to-execution | fixture receipt | execution receipt |

There are 20 source edges and 16 fixture edges in the current fixture. The graph
has 16 terminal execution addresses and is acyclic.

## Quality trace

The quality gate stores check IDs, observed values, required values, rationale,
and severity. It binds data audit, evaluation, contracts, schema, lineage,
reconciliation, content addresses, boundary, control counts, and vocabulary.

The gate has 12 checks. Its content address is included in the release
manifest. A changed check result changes the gate address.

## Runtime trace

The runtime adds ten ordered stage receipts. Stage outputs are linked by the
returned objects, while each stage stores its output address. Runtime timing is
diagnostic and does not change deterministic operation receipts.

| Stage | Output |
| --- | --- |
| data-audit | data audit |
| contracts | contract registry |
| schema | schema manifest |
| fixture-replay | evaluation |
| metrics | metrics report |
| policy | policy |
| lineage | lineage graph |
| reconciliation | reconciliation |
| quality-gate | quality gate |
| release-bundle | bundle |

## Bundle trace

The release bundle binds fixture, evaluation, metrics, lineage, reconciliation,
policy, and release notes. The bundle notes retain the public boundary and
excluded uses in plain text.

## Release trace

The release manifest binds bundle, quality gate, and replay. Its four checks
answer:

1. is the bundle addressable?
2. is the quality gate accepted?
3. is replay accepted?
4. are positive operation decisions releasable?

The release state is ready only when all four checks pass.

## Artifact inventory

The artifact inventory provides a seven-node packaging view:

1. fixture;
2. evaluation;
3. metrics;
4. lineage;
5. quality;
6. bundle;
7. release.

Each artifact stores parent addresses, byte estimate, summary, content, and an
inventory address. The release artifact is the inventory root.

## Threshold trace

The threshold report keeps four profiles and 324 probes. A probe stores score,
uncertainty, support, evidence count, pass flags, review expectation, and
address. The report is useful when a threshold changes because it reveals which
boundary combinations move from accepted to review.

## Invariant trace

Ten reusable invariants cover context, addresses, role separation, posterior
bounds, support visibility, abstention, dossier addressing, source receipts,
issue vocabulary, and replay stability. The invariant runner returns named
failed IDs, so extension modules can share the same review vocabulary.

## Reviewer navigation

Use this order when a release check fails:

1. read the failed check ID;
2. locate the related execution or global check;
3. follow record ID to fixture;
4. resolve source IDs;
5. inspect expected and observed values;
6. follow execution address into lineage;
7. inspect policy decision;
8. inspect bundle and release check.

Do not begin with a free-form conclusion. Begin with the receipt chain.

## Traceability invariants

The following should remain true:

- every record has an execution;
- every execution has an address;
- every record source ID resolves;
- every execution has a fixture edge;
- every positive operation has one positive record;
- every operation has three controls;
- every issue code is declared;
- every release check has evidence address;
- every release has allowed and excluded uses;
- every deterministic replay has stable content addresses.

## Change review

When an address changes, compare the object body first. When a count changes,
compare the fixture and registry. When an issue code changes, compare the
contract and control records. When a source changes, compare URI, release, and
scope.

Traceability is complete when a reviewer can explain every release field using
one of the source, fixture, execution, check, policy, lineage, or quality
receipts without adding an unsupported claim.
