# Deployment frontier operations

This document defines the D16 C13–C16 deployment-governance depth surface. It
is a local-first research infrastructure boundary for four operations:
privacy/security policy, local deployment bundles, federated execution, and
release/rollback decisions.

The implementation keeps public portal receipts separate from operational
measurements. The receipts point to the NCI Genomic Data Commons, ENCODE, 4D
Nucleome, DepMap, and GA4GH public portals. The fixture measurements are
deterministic operational values and do not represent donor rows, site-local
raw data, or scientific effect sizes.

The canonical checked-in fixture is
`examples/deployment-frontier-public-aggregate.json`; its content address is
validated before it is accepted for replay.

## Operation contract

| Capability | Positive boundary | Control boundaries | Output state |
| --- | --- | --- | --- |
| C13 privacy/security policy | declared aggregate read with an allowed role | role mismatch, context mismatch, sensitive access | `ready` or `denied` |
| C14 local deployment bundle | digest-addressed offline services | malformed digest, missing inventory, online-only request | `ready` or `hold` |
| C15 federated execution | eligible site-local aggregate assignment | unavailable site, privacy budget, unsupported context | `ready` or `hold` |
| C16 release/rollback | all declared gates pass | failed gate, missing prior version, current-version repeat | `released` or `denied` |

Every row has a stable record ID, exact context key, source receipt links,
expected state, expected issue codes, and a content address. Every operation
adapter returns a safe output projection rather than serializing its complete
request.

## C13 privacy/security policy

The policy adapter evaluates each request against named rules. Matching is
explicit: an action must be listed, at least one request role must intersect
the rule roles, sensitive access must be explicitly enabled, network access
must be explicitly enabled, retention must be within the rule maximum, and
the request context must equal the declared context.

The positive row uses a public-reference read, a reviewer role, and a short
retention interval. The controls show three distinct denial mechanisms. The
role control carries both a missing required role and a disallowed-role
reason; the context control prevents a cross-context join; the sensitive
control remains denied because the rule does not grant sensitive access.

The output retains allowed and denied request IDs, decision count, state list,
normalized reason codes, and the report address. Principal labels are
operational role labels, not participant identifiers.

## C14 local deployment bundle

The bundle contract requires a bundle ID, platform, runtime, at least one
artifact, and at least one service. Each artifact retains an ID, version,
SHA-256-style digest, size, runtime requirement, and local-only flag. Each
service remains a declared dependency record; the adapter does not launch a
process.

The positive row is offline and contains two digest-addressed artifacts and a
two-service local inventory. The malformed-digest control transitions to
`hold` while retaining the artifact inventory. The missing-inventory control
returns a structured hold rather than raising an uninspectable failure. The
online-only control is held because the repository boundary is local-first.

The resulting manifest is a content address over the complete normalized
bundle. No environment value is copied into a secret field and no external
service is contacted.

## C15 federated execution

Federation is represented as a site-local eligibility calculation. A task
declares privacy cost, minimum sample count, optional site IDs, and the exact
context it needs through the plan. A site declares availability, aggregate
sample count, and supported contexts.

The coordinator emits assignments, eligible task IDs, denied task IDs, state,
and an aggregate address. It never emits a raw site payload. A task is
eligible only when the site is available, supports the requested context,
meets the minimum aggregate count, and fits under the declared privacy
budget.

The positive row has two eligible public aggregate sites. The controls isolate
availability, budget, and context failure so reviewers can distinguish a
capacity problem from a privacy or context problem.

## C16 release and rollback

Release decisions require named checks. The default set is tests, integrity,
compatibility, and policy. A release is ready only when every check is true
and the requested version differs from the current version. A rollback also
requires a previous version. Missing checks default to false rather than
silently passing.

The positive row releases version `1.0.0` over `0.9.0`. The controls isolate a
failed integrity gate, a missing prior version for rollback, and a request to
release the already-current version. The output exposes failed check names and
the decision address, not credentials or signing material.

## Runtime stages

`run_deployment_frontier_runtime` composes the operation surface into an
ordered receipt pipeline:

1. public data audit;
2. adapter and schema materialization;
3. fixture execution and metrics;
4. policy, lineage, and reconciliation;
5. quality gate, replay, and release manifest;
6. artifact inventory, review view, queue, SLA, and handoff;
7. integrity, scenario depth, operational response, and performance;
8. assurance, failure injection, compliance, diagnostics, and execution plan;
9. thresholds, validation matrix, access, compatibility, and release checks;
10. runbook, freshness, audit log, transcript, summary, package, bundle, and trace.

Each stage records sequence, state, duration, output address, detail, and its
own content address. The final report is accepted only if all required stage
receipts are accepted.

## Evidence boundary

The deployment frontier proves deterministic software boundaries and review
routing. It does not prove that a release is scientifically correct, that a
site is institutionally authorized, that an aggregate statistic is clinically
useful, or that a deployment is safe for patient care. Those claims require
external validation and institutional controls outside this fixture.
