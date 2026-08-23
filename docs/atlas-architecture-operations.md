# D05 Operation Contract

## Shared case shape

Each D05 case contains:

- stable case identifier;
- one operation identifier from D05-C01 through D05-C16;
- scenario (`positive`, `foreign_context`, `malformed_input`, or `identity_conflict`);
- architecture context key;
- public source receipt identifiers;
- operation payload;
- expected state and expected issue codes;
- a content address derived from the canonical case mapping.

The fixture constructor rejects duplicate identifiers, missing source joins, unexpected operation counts, invalid state/scenario combinations, and content-address drift. Positive cases must expect `accepted`; controls must expect `review`.

## Adapter delegation

The aggregate operations module owns boundary routing and delegates positive payloads to the four existing public-data family adapters. The delegation map is stable:

| Family | D05 operations | Adapter boundary |
| --- | --- | --- |
| regulatory | C01-C04 | cCRE and cell-profile adapters |
| molecular | C05-C08 | molecular-state and histone adapters |
| alpha evidence | C09-C12 | chromatin, methylation, role, and enhancer adapters |
| frontier | C13-C16 | frontier territory, hotspot, tier, and publish adapters |

The architecture normalizes only the aggregate join context needed for frontier rows. It does not rewrite source titles, source URIs, release labels, licenses, or family result fields.

## Receipt semantics

An accepted receipt records:

- expected state `accepted`;
- observed state `accepted`;
- a supported family result state;
- primary and secondary evidence counts;
- preserved family issue codes, if any;
- a content address for the execution.

A held receipt records:

- expected state `review`;
- observed state `review`;
- one of `out_of_domain`, `invalid`, or `contradictory`;
- one of `context_mismatch`, `malformed_input`, or `identity_conflict`;
- an empty evidence count;
- the original control content address.

The evaluation gate checks every receipt, then checks aggregate cardinality, scenario balance, accepted count, review count, and issue closure. The expected result is 64 passed receipts and 325 passed checks.

## Validation matrix

Validation is intentionally broader than the operation list. Each of five planes—ingestion, regulatory, molecular, evidence, and frontier—is closed across all 16 operations. This produces 80 validation cells. A cell passes only when all four cases for the operation have passing receipts and the operation has a declared plane.

## Public source boundary

The source catalog is assembled from the four public aggregate family fixtures already present in this fresh repository. Each receipt preserves the public title, URI, release label, license, and family scope while receiving a D05-prefixed stable identifier. The aggregate source count is exactly 20 and source identifiers are unique after prefixing.

## Extension rules

New operations must provide all of the following before they can enter the D05 boundary:

1. one operation specification and one plane;
2. one positive case plus the three standard controls;
3. at least one public source receipt;
4. an adapter result mapping;
5. a validation closure across all declared planes;
6. deterministic replay and a content-addressed receipt;
7. focused tests, documentation, and a capability-registry evidence reference.

Changing the context key, operation count, source count, state vocabulary, or control policy is a versioned contract change rather than a fixture edit.
