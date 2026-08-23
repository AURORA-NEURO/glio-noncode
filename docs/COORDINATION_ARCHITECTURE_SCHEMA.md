# D16 coordination schema

The coordination schema is a closed public projection. It keeps identifiers,
state, counts, contracts, addresses, and review routing while excluding raw
payloads and private subject fields.

## Fixture schema

`CoordinationFixture` has a fixture ID, version, boundary, exact context key,
source receipts, operation specifications, case rows, and a content address.
The constructor enforces 16 operations and 64 cases. Sources must be HTTPS and
public aggregate. Case IDs, operation IDs, and addresses must be non-empty.

## Operation schema

Each `CoordinationOperationSpec` carries:

- operation and capability identity;
- ordinal and role;
- input and output contract names;
- dependency IDs;
- budget units;
- review requirement;
- public source joins;
- content address.

No dependency is implicit. The compiler validates the complete graph before a
schedule is produced.

## Case projection

Case payloads are restricted to aggregate control fields: operation identity,
capability identity, context key, contract names, budget values, network flag,
scope flag, schema version, route, and claim boundary. The support boundary
rejects private-key-shaped mapping keys such as subject, participant, contact,
email, and phone identifiers.

The operation output is narrower still. It includes case identity, observed
state, issue codes, reference count, public-projection flag, and claim boundary.
It does not copy the input payload.

## Runtime schema

The runtime exposes:

- ordered addressed stages;
- evaluation and plan reports;
- typed tool registry and budget schedule;
- hash-chained ledger;
- compute and public-reference registries;
- monitoring observations and security decisions;
- deployment artifacts and federated assignments;
- release/rollback manifest;
- runtime content address.

The CLI report projection further reduces this to run ID, fixture ID, state,
stage and operation counts, case counts, review summary, quality counts, and
runtime address.

## Validation schema

The validation matrix has seven planes for every operation:

1. identity;
2. contract;
3. policy;
4. resource;
5. review;
6. integrity;
7. release.

The canonical matrix therefore contains 112 addressed cells. A matrix mutation
is visible in its cell projection and cannot be hidden by the aggregate runtime
state.

## Versioning

Fixture and runtime versions are explicit. Content addresses are derived from
the complete public projection. A fixture revision must create a new address;
callers must not edit a checked-in fixture in place and retain the old address.
