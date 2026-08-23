# D16 coordination architecture operations

This document describes the functional coordination architecture for the
Agentic Platform, Quality & Deployment domain without adding attribution,
assistant, model-generation, or language metadata to repository artifacts. The
architecture is a public aggregate control surface. It compiles declared work,
admits typed local tools, applies policy and resource gates, routes controls to
review, and emits addressed release evidence.

It does not diagnose, classify an individual, infer treatment, assert model
performance, or transform a held control into a positive result.

## Operational denominator

The checked-in fixture contains:

| Quantity | Denominator |
| --- | ---: |
| Public HTTPS source receipts | 5 |
| D16 operation specifications | 16 |
| Scenarios per operation | 4 |
| Positive cases | 16 |
| Control cases | 48 |
| Runtime stages | 20 |
| Validation cells | 112 |
| Event-ledger events | 64 |
| Offline deployment artifacts | 5 |
| Public federated assignments | 16 |

The four scenarios are `positive`, `foreign_context`, `budget_exceeded`, and
`contract_mismatch`. The positive case is accepted only when all declared
identity, context, contract, budget, network, and public-scope predicates hold.
Each control has an expected review state and explicit issue code.

## Operation sequence

The runtime compiles these operations in dependency order:

1. mission plan;
2. workflow compile;
3. typed tool registry;
4. execution sandbox;
5. policy and claim gate;
6. budget and resource schedule;
7. deterministic fallback route;
8. human-review route;
9. event-sourced execution ledger;
10. compute registry;
11. public reference registry;
12. drift and out-of-domain monitor;
13. privacy and security policy;
14. local deployment bundle;
15. federated execution assignment;
16. release and rollback controller.

The dependencies are explicit in each operation specification. The compiler uses
a deterministic topological sort and reports missing dependencies and cycles.
The canonical plan consumes 168 budget units against a 192-unit capacity. A
caller may supply a lower capacity to produce a blocking schedule result.

## Typed tools and sandbox

Every operation receives one typed tool specification. A tool has an input
contract, output contract, deterministic flag, network flag, public-scope flag,
and content address. The canonical registry has 16 tools and requires:

- deterministic execution;
- no network access;
- public aggregate scope;
- one-to-one operation identity;
- an addressed registry entry.

The sandbox checks tool-operation identity, deterministic execution, network
requests, private-key-shaped payload keys, and aggregate scope. It returns a
sanitized receipt containing state and reasons. It never copies the case
payload into the sandbox projection.

## Policy, resources, and fallback

The policy gate requires the exact context key, the closed coordination claim
boundary, no network request, and public aggregate scope. A failed predicate
produces a review decision with stable reasons.

The scheduler consumes the compiled plan, checks total budget against capacity,
retains operation order, and refuses an empty or cyclic plan. It does not start
external work.

Fallback is deterministic and non-promotional:

| Issue | Route | Retryability |
| --- | --- | --- |
| no issue | `primary_local` | no |
| foreign context | `manual_context_review` | no |
| budget exceeded | `capacity_review` | yes |
| contract mismatch | `contract_repair_review` | no |
| other boundary issue | `manual_boundary_review` | no |

The route state remains review for every control. Retryability describes queue
handling only; it never changes the observed case state.

## Review and event ledger

Every non-positive execution enters the review queue. The queue preserves case
ID, operation ID, issue codes, priority, SLA band, state, and an address. It
contains 48 canonical items. Contract mismatches receive the urgent band;
foreign-context and budget controls receive standard routing according to the
stable priority function.

The event ledger is append-only in projection. Each of the 64 execution events
stores an ordinal, event type, case ID, observed state, previous event address,
and its own address. Verification checks contiguous ordinals, a closed genesis
link, intact previous-address links, and unique event IDs.

## Registries and monitoring

The compute registry contains four bounded local profiles. It records digest,
version, contract, scope, and address. The reference registry projects the five
public source receipts into the same addressed form.

Monitoring emits one exact-context observation per operation with reference
rate, drift score, and out-of-domain flag. The canonical observations have a
reference rate of `1.0`, drift score `0.0`, and `out_of_domain=false`. These are
fixture controls for monitoring behavior, not empirical performance claims.

## Security and deployment

Security decisions are evaluated on the 16 positive projections. Private key
shaped keys, network requests, and non-aggregate scope are review boundaries.
The checked-in payloads contain no individual identifiers or contact fields.

The offline deployment projection contains five artifacts: runtime contract,
schema contract, source index, test vectors, and release notes. The federation
projection creates 16 public aggregate assignments with zero privacy cost and
the exact context. Site-local eligibility is represented as a receipt, not as a
claim about an external institution.

## Release and rollback

Release requires non-empty offline artifacts, no blockers, unique artifact
addresses, and a rollback version. A release with any blocker is review. The
release object always retains the rollback version so a future controller can
address a reversal without rewriting the original run.

## Failure controls

`coordination-failures` executes six negative controls:

- foreign context;
- budget overflow;
- contract mismatch;
- private-key-shaped payload;
- attempted control promotion;
- release blocker.

Each probe must produce a non-accepted state and a non-empty issue code, except
the explicit control-promotion probe, which verifies that controls remain held
and that the attempted promotion is treated as a detected boundary condition.

## Command surface

```text
python -m glio_noncode coordination-fixture --output coordination.json
python -m glio_noncode coordination-data-audit --input coordination.json
python -m glio_noncode coordination-plan
python -m glio_noncode coordination-tools
python -m glio_noncode coordination-runtime --output coordination-runtime.json
python -m glio_noncode coordination-quality
python -m glio_noncode coordination-depth
python -m glio_noncode coordination-validation
python -m glio_noncode coordination-runbook
python -m glio_noncode coordination-trace
python -m glio_noncode coordination-review-csv
python -m glio_noncode coordination-query --state review
python -m glio_noncode coordination-failures
```

The runtime command returns state `accepted` only when the canonical positive
and control expectations reconcile, the pipeline remains aggregate-only, and
all release gates close. The quality, depth, validation, and failure commands
return nonzero when their blocking checks fail.
