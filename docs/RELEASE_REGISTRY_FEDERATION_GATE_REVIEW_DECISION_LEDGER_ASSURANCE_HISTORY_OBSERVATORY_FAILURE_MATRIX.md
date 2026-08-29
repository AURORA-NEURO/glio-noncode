# Assurance-history observatory failure matrix

This matrix defines expected failure behavior for the cross-history
observatory. A failure is a review signal and must not be silently converted
into an empty or promoted package.

| Boundary | Fault | Expected result | Why it matters |
| --- | --- | --- | --- |
| build | A plain mapping is passed instead of `AssuranceHistory`. | `ValidationError`. | Prevents structural duck typing from bypassing upstream verification. |
| build | More than `MAX_MEMBERS` histories are supplied. | `ValidationError`. | Keeps memory, persistence, and query windows bounded. |
| build | Member IDs do not align one-for-one with histories. | `ValidationError`. | Avoids ambiguous source identity. |
| build | A member ID is duplicated. | `ValidationError` from aggregate construction. | Two source histories must not share one review identity. |
| build | Two histories have the same content address. | `ValidationError` from aggregate construction. | Avoids double-counting one source as independent evidence. |
| build | A current history has a held terminal gate. | Valid package with `held` state and `release_ready=false`. | Holds are reviewable outcomes, not parse errors. |
| build | A current history has a blocked terminal gate. | Valid package with `blocked` state and `release_ready=false`. | Blockers remain visible and fail closed. |
| build | A current empty history is included. | Valid member with `empty` state; aggregate cannot promote. | Empty source coverage is explicit. |
| build | Aggregate counters are edited after construction. | Constructor or verifier rejects conservation/address mismatch. | Summary fields are derived, not authoritative inputs. |
| verification | Member address is tampered. | Required check fails or package load rejects. | A member cannot be substituted without changing its address. |
| verification | Aggregate state is tampered. | Required state-projection check fails or load rejects. | Readiness follows source posture. |
| verification | Verification `passed_count` is edited. | Verification loader rejects count mismatch. | Counts must equal actual checks. |
| verification | Verification check address is edited. | Loader rejects address mismatch. | Every check is content addressed. |
| persistence | Destination exists without overwrite permission. | `ValidationError`. | Destructive replacement requires explicit authorization. |
| persistence | Existing destination contains an extra file. | `ValidationError`. | Package shape is exact and reviewable. |
| persistence | Package contains a symlink. | `ValidationError`. | Avoids filesystem indirection at the trust boundary. |
| persistence | JSON bytes are semantically valid but non-canonical. | `ValidationError`. | Reproducible bytes are part of the address contract. |
| persistence | Artifact size or hash differs from the manifest. | `ValidationError`. | Prevents partial or replaced artifact acceptance. |
| persistence | Manifest address differs from its recomputation. | `ValidationError`. | Manifest itself is addressed. |
| persistence | `members.json` links to a different observatory ID. | `ValidationError`. | Prevents cross-package member grafting. |
| persistence | `metrics.json` differs from recomputed metrics. | `ValidationError`. | Metrics cannot become a parallel authority. |
| persistence | Verification is valid JSON but for another observatory. | `ValidationError`. | Verification must bind to the exact aggregate address. |
| compatibility | A legacy history directory is supplied. | `ValidationError`. | No silent legacy conversion at this boundary. |
| query | Resource is unsupported. | `ValidationError`. | Query vocabulary is closed. |
| query | Limit is zero, negative, or over the bound. | `ValidationError`. | Prevents accidental unbounded or invalid windows. |
| query | Offset is negative or over the bound. | `ValidationError`. | Window semantics remain deterministic. |
| query | Text filter is unbounded. | `ValidationError`. | Search inputs are bounded and public. |
| diff | Baseline or candidate is not a typed observatory. | `ValidationError`. | Diffs compare verified current objects only. |
| diff | A member is removed. | `removed` plus `regressed`. | Loss of a source member is conservative. |
| diff | A member is added and ready. | `added` plus `improved`. | New ready coverage is visible. |
| diff | A member changes without strict quality ordering. | `changed` plus `mixed`; overall state may remain `unchanged`. | Detail changes are not invented into improvement. |
| diff | Diff item address is tampered. | `ValidationError`. | Item identity is reproducible. |
| public | A forbidden key such as `agent`, `language`, or `model` is introduced. | `ValidationError` or public-boundary check failure. | Published objects must not expose attribution metadata. |
| public | A Windows or user-home path appears in a report. | Public-boundary rejection or test failure. | Input paths stay at the process edge. |

## Archive and transfer controls

| Boundary | Fault | Expected result | Why it matters |
| --- | --- | --- | --- |
| archive | ZIP has an extra, missing, duplicate, encrypted, directory, symlink, or traversal-like member. | `ValidationError`. | The single-file envelope has an exact trusted shape. |
| archive | Archive manifest is non-canonical or has an unknown field. | `ValidationError`. | Equivalent JSON spellings must not create ambiguous bytes. |
| archive | Payload bytes differ from an artifact receipt. | `ValidationError`. | The archive must preserve the exact verified package. |
| archive | Archive is loaded from a byte string. | Same verification as file loading. | Upload and in-memory adapters cannot bypass the boundary. |
| archive | Extraction target exists without overwrite permission. | `ValidationError`. | Reversible review artifacts are not silently replaced. |
| transfer | Chunk size is below 256 bytes, above 4 MiB, a string, or a boolean. | `ValidationError`. | Resource policy is explicit and typed. |
| transfer | Chunk count, offsets, sizes, or total bytes do not conserve. | `ValidationError`. | Range math cannot hide missing or overlapping bytes. |
| transfer | A chunk is changed after its receipt is written. | `ValidationError`. | Transport copies are independently addressed. |
| transfer | Manifest-only transfer is assembled without every chunk. | `ValidationError`. | Inventory is not confused with complete evidence. |
| transfer | Reassembled ZIP has a different archive address. | `ValidationError`. | A transfer cannot launder another archive. |
| transfer | Transfer directory has an extra file or symlink. | `ValidationError`. | Receiver shape is exact and filesystem-safe. |
| transfer | Transfer manifest address or transfer address is edited. | `ValidationError`. | Both the envelope and its manifest are linked. |
| transfer | Existing transfer destination is overwritten without explicit permission. | `ValidationError`. | Destructive replacement remains opt-in. |

## Transfer audit controls

| Boundary | Fault | Expected result | Why it matters |
| --- | --- | --- | --- |
| audit | A complete transfer is supplied as a plain mapping. | `ValidationError` at the byte-backed directory boundary. | An audit must begin from a typed transfer or verified receiver. |
| audit | A partial transfer has valid manifest and received chunks. | Valid `incomplete` report with deferred nested checks. | Progress is observable without pretending gaps are safe. |
| audit | A complete report has a failed assembly check. | Report construction rejects the state/check disagreement. | Completion cannot be asserted independently of its evidence. |
| audit | Check order, check address, or count is edited. | `ValidationError`. | Audit receipts are independently reproducible. |
| audit | A partial transfer includes an extra or symlinked member. | `ValidationError` before audit output. | Diagnostics inherit the exact filesystem boundary. |

## Verification-query controls

| Boundary | Fault | Expected result | Why it matters |
| --- | --- | --- | --- |
| verification-query | A plain mapping is passed as the verification. | `ValidationError`. | Queries must start from a verified typed artifact. |
| verification-query | A plain mapping is passed as the query. | `ValidationError`. | Filter vocabulary and bounds are closed. |
| verification-query | `summary` is requested with no matching checks. | One summary record. | Summary is the gate projection, not a check search. |
| verification-query | `checks` is requested. | All checks after filtering. | The complete independent check set remains inspectable. |
| verification-query | `failed` is requested. | Only failed checks. | Blockers and warnings can be triaged directly. |
| verification-query | `required` is requested. | Only required checks. | Required release conditions remain explicit. |
| verification-query | `optional` is requested. | Only optional checks. | Optional findings do not disappear into required totals. |
| verification-query | `failed` and `passed=true` are combined. | Addressed empty result. | Contradictory filters do not widen selection. |
| verification-query | Severity is unknown. | `ValidationError`. | Check severity is an exact enum. |
| verification-query | Pass state is not boolean. | `ValidationError`. | Truthy strings cannot change gate meaning. |
| verification-query | Text exceeds the declared bound. | `ValidationError`. | Search input remains bounded and public. |
| verification-query | Offset or limit exceeds the bound. | `ValidationError`. | No unbounded export is possible. |
| verification-query | Offset is past the filtered total. | Addressed empty window. | Pagination is stable at the end of a result set. |
| verification-query | Result records are edited after selection. | Address mismatch on validation. | Export receipts bind selected bytes. |
| verification-query | Package is tampered before query. | Package loader rejects first. | Querying cannot launder invalid source evidence. |
| verification-query | No check matches. | `200`/status `0` with zero records. | A valid absence is distinct from a malformed package. |
| verification-query | JSON, CSV, and Markdown are selected. | Same records and window. | Presentation format cannot alter review semantics. |

## Exit and HTTP status mapping

The CLI uses three statuses:

| Status | Meaning |
| --- | --- |
| `0` | Promoted and release-ready result, or successful schema/query/diff operation. |
| `1` | Input, type, filesystem, JSON, or contract failure. |
| `2` | Valid hold, mixed, blocked, or empty review result. |

The HTTP adapter uses:

| Status | Meaning |
| --- | --- |
| `200` | Successful operation or promoted result. |
| `400` | Invalid request, missing input, unsupported value, or validation error. |
| `422` | Valid non-promoted build or verification result. |

Query and schema operations remain `200` when their input package is valid,
even if the package's aggregate posture is held or blocked. This allows a
reviewer to inspect the failure details without treating a valid hold as an
HTTP transport fault.

## Operator response

When a package fails to load, preserve the original directory and error text,
repair the source or rerun the producing step, and rebuild into a new output
directory. Do not hand-edit a manifest, copy a missing artifact, or rename a
legacy file into the current shape. If the result is a valid hold or block,
retain the exact package and query its `members` and `metrics` resources for
review rather than deleting it.
