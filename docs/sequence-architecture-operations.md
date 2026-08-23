# D06 Operation and Evidence Contract

## Case structure

Each case contains a stable case ID, operation ID, capability ID, family, plane, scenario, exact context key, prefixed public source IDs, family record payload, expected aggregate state, expected family result, expected issue codes, bounded expected counts, description, and content address.

Positive payloads retain the original public family record. Controls use aggregate-only payloads and are held before family delegation. The control paths are:

| Scenario | Result | Issue | Delegation |
| --- | --- | --- | --- |
| positive | family-supported, accepted, or published | family receipt | yes |
| foreign context | out_of_domain | context_mismatch | no |
| malformed input | invalid | malformed_input | no |
| identity conflict | contradictory | identity_conflict | no |

## Family delegation

The runtime executes the four family fixtures and indexes their positive results by the D06 operation record ID. The original family result is retained as the D06 summary, including state, warnings, measurements, issue codes, source identifiers, and family content address. The aggregate receipt adds the D06 decision and bounded primary/secondary counts.

This separation is important: the aggregate boundary is not a replacement adapter. It is a typed composition layer that makes cross-family joins and controls inspectable.

## Public provenance

The 17 source receipts are assembled from the four public fixtures:

- four sequence-effect sources;
- four sequence-grammar sources;
- four sequence-regulation sources;
- five sequence-frontier sources.

Identifiers are prefixed with their family boundary before operation joins are created. URI, release, source kind, scope, and checksum or content address are preserved in the public receipt. No subject-level fields are introduced.

## Validation planes

Each of the five planes checks every operation for four passing receipts. This yields 80 cells. The plane matrix validates operational closure, while the operation spec retains the family’s declared plane. Ingestion is a cross-cutting closure plane; it does not change family ownership.

## Release semantics

The release remains blocked if any receipt, evaluation check, audit check, policy check, validation cell, schema check, access check, replay check, invariant, or runbook check fails. A held control is expected and does not block publication when it passes its declared control receipt. A malformed positive or missing family receipt does block release.
