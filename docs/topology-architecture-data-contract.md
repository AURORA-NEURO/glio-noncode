# D09 Data Contract

## Fixture envelope

The aggregate JSON object contains:

| Field | Shape | Rule |
| --- | --- | --- |
| `fixture_id` | string | stable public fixture identifier |
| `version` | string | D09 release version |
| `boundary` | string | `public_aggregate_3d_genome_regulatory_topology` |
| `context_key` | string | `GRCh38|glioma|adult|stem_like|tumor|unknown` |
| `sources` | array | exactly 17 source records, each marked `public_aggregate` |
| `operations` | array | exactly 16 ordered operation contracts |
| `cases` | array | exactly 64 case contracts |
| `content_address` | string | deterministic SHA-256 address of the envelope |

## Source records

Every source record contains a source ID, title, URL, retrieval date, version or release label, scope, an explicit `public_aggregate` flag, and content address. Source IDs are unique. Operation source joins and case source joins must resolve to the source registry before evaluation.

The D09 fixture records public source metadata and small public observations only. It does not embed restricted raw study files. Payloads are sanitized into review-safe summaries before artifact materialization.

## Operation records

Every operation contains an operation ID, capability ID, ordinal, family, plane, operation name, input contract, output contract, dependency IDs, source IDs, and a control policy. Ordinals are contiguous from 1 through 16. Dependency IDs must refer to earlier operation IDs or the fixture boundary.

## Case records

Every operation has four cases:

1. `positive`, using the exact aggregate context and a public family observation.
2. `foreign_context`, using a context key outside the D09 boundary.
3. `malformed_input`, using a payload that fails the operation input shape.
4. `identity_conflict`, using a declared identity that conflicts with the observation.

Cases retain expected state, expected result state, expected issue codes, expected count summaries, source IDs, aggregate `context_key`, delegated `delegate_context_key`, payload summary, and a content address. Raw payload keys that could expose unbounded study records or restricted identity/decision metadata are rejected recursively by the compliance gate.

## State and review rules

`accepted` is reserved for a valid positive observation. `review` is required for every control case. `blocked` is reserved for an unresolved join, invalid contract, unsafe payload, or failed release invariant. `published` applies only to the release manifest after all gates pass.

## Address rules

Addresses are derived from canonical JSON with sorted keys and stable separators. The same fixture and evaluation must produce the same addresses on replay. The replay check runs the complete evaluation twice and compares the resulting evaluation addresses.
