# D07 data contract

## Fixture envelope

```text
fixture_id
version
boundary
context_key
sources[19]
operations[16]
cases[64]
content_address
```

The fixture version is
`2026.08.d07-chromatin-architecture.v1`. The boundary is
`public_aggregate_chromatin_accessibility_methylation`.

## Source receipt

Every source has a prefixed ID, family, title, URI, version, public aggregate
scope, license label, explicit `public_aggregate` marker, and SHA-256 address.
The 19 source receipts come from the
four checked-in public tranches. The aggregate source registry requires every
source to join at least one operation and at least one case.

## Operation contract

Every operation declares:

- a D07 operation ID and blueprint capability ID;
- an ordinal and family;
- an evidence plane;
- an input and output contract name;
- predecessor dependencies;
- source joins;
- the control policy;
- a content address.

The dependency graph is a total order from D07-C01 through D07-C16. The
family boundaries remain explicit in the graph and in every receipt.

## Case contract

The aggregate case carries a scenario, exact context, delegated context, source joins, a typed
expected state, expected result state, issue-code floor, bounded counts, and a
description. Positive cases are accepted candidates. Controls are review-only.

Raw family records are retained in the fixture so that the evaluator can prove
which public input produced a receipt. The evaluator strips raw input fields
from execution summaries and all reporting projections.

## Compliance rules

The compliance surface checks:

1. the public aggregate boundary;
2. exact context preservation;
3. HTTPS source locators;
4. aggregate source scope;
5. absence of subject-level keys;
6. source and case addresses;
7. explicit positive/control policy.

The extended compliance surface also verifies operation addresses, delegated
contexts, and explicit mismatch issues on foreign controls. Restricted metadata
keys are detected recursively in object and array payloads.

The schema declares 33 receipt and release fields. The data dictionary gives
30 public fields with type, domain, requiredness, visibility, description, and
its own address. The distinction is intentional: the schema includes an
internal release-only field while the public dictionary lists the exported
fields.

## Release artifacts

The six artifacts are:

| Artifact | Visibility | Contents |
| --- | --- | --- |
| d07-fixture | public | fixture envelope and source joins |
| d07-evaluation | public | sanitized 64-case receipts |
| d07-policy | review | acceptance and review decisions |
| d07-review | review | 48 held controls |
| d07-lineage | public | source-to-case-to-receipt links |
| d07-metrics | public | operation, family, scenario, and issue counts |

The release adds explicit limitations stating that measurements remain
descriptive and that control paths are not publishable evidence.
