# D05 Public Data Contract

## Source receipt requirements

Every source receipt must include a stable identifier, public title, public URI, release label, license label, family scope, and content address. A source is usable only when its identifier is joined by at least one case and its URI is non-empty. The D05 aggregate prefixes family identifiers so that equal identifiers from different family fixtures cannot silently collide.

## Context contract

The architecture context is:

```text
GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown
```

The fields are assembly, disease class, age band, cell state, territory, and treatment state. A control may intentionally carry a foreign context, but it must remain held and must report `context_mismatch`. Context is part of the case address and cannot be changed without changing the fixture version.

## Payload contract

Payloads are family-owned mappings. The aggregate layer requires only the fields needed to dispatch a positive case and to make the public receipt auditable. Unknown fields are retained in fixture output. Query and receipt views can remove payloads with the normalization module when only case identity and decision state are required.

Malformed payloads are not repaired silently. A malformed-input control is expected to return `invalid` with `malformed_input`, and the receipt remains in review.

## Identity contract

Identity conflict is a first-class control. It is used when an operation payload deliberately contradicts its declared identity fields. The expected result is `contradictory` with `identity_conflict`. The architecture holds this case before adapter delegation so a family adapter cannot accidentally convert a contradiction into evidence.

## Deterministic addressing

Canonical JSON serialization feeds SHA-256 content addresses for sources, cases, executions, ledger events, artifacts, and releases. Address inputs are sorted and use stable field names. Replaying the same fixture must reproduce the same fixture and receipt addresses.

## Counts and closure

The canonical D05 aggregate has:

| Entity | Required count |
| --- | ---: |
| Sources | 20 |
| Operations | 16 |
| Cases | 64 |
| Positive cases | 16 |
| Control cases | 48 |
| Evaluation receipts | 64 |
| Validation cells | 80 |
| Ledger events | 64 |
| Runtime stages | 20 |
| Artifacts | 6 |

These counts are checked at construction, evaluation, validation, quality, and release boundaries. A count change requires a contract review and focused test updates.
