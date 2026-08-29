# Assurance-history observatory archive

The archive boundary packages one current-format assurance-history observatory
directory into a deterministic single-file ZIP. It is a transport envelope,
not a new evidence authority. The nested observatory package remains the
source of the aggregate state, member projections, independent checks, and
metrics. The archive only preserves those exact bytes and their public links.

## Envelope

The archive contains exactly six regular ZIP members in this fixed order:

```text
manifest.json
observatory/manifest.json
observatory/observatory.json
observatory/members.json
observatory/verification.json
observatory/metrics.json
```

Every member is UTF-8 canonical JSON. ZIP member timestamps are fixed to the
minimum portable DOS timestamp, compression is fixed, permissions are fixed,
member comments are empty, and the archive comment is empty. Equal verified
observatory packages and archive IDs therefore produce equal archive bytes.

The public archive projection records the archive ID, archive version and
boundary, observatory ID, observatory and verification addresses, exact member
names, five artifact receipts, and the archive content address. Input paths
are process-edge arguments and never enter the manifest.

## Address graph

```text
history packages
      |
      v
observatory address
      |
      +--> verification address
      +--> metrics and member artifact bytes
      |
      v
archive artifact receipts
      |
      v
archive address --> archive manifest address
```

The archive address is computed from the public archive projection with its
content address removed. The manifest address is computed from the manifest
projection with its own address removed. Loading recomputes both. The nested
observatory manifest and all five payload files are independently verified
before the archive object is returned.

## Python surface

The module provides typed construction and file/byte operations:

```python
archive = build_archive_from_directory("review-output/observatory")
raw = archive_bytes(archive)
loaded = load_archive_bytes(raw)
assert loaded.content_address == archive.content_address
package = load_archive_package(raw)
write_archive(archive, "review-output/observatory.zip")
extract_archive("review-output/observatory.zip", "review-output/extracted")
```

`build_archive` accepts a typed observatory and reconstructs the exact upstream
package projection. `build_archive_from_directory` first loads and verifies an
exact current-format directory and then reads the five source bytes. The two
builders must produce the same public projection and deterministic ZIP bytes.

`load_archive` accepts a path or `bytes`; `load_archive_bytes` is the explicit
byte-only helper for upload and HTTP adapters. `verify_archive_file` and
`verify_archive_bytes` are named verification aliases. `archive_from_mapping`
is intentionally public-projection-only: a mapping can be inspected, but it
does not pretend to contain payload bytes and cannot be written until a real
package-backed archive is built.

## Fail-closed loading

The loader checks:

1. the input is a regular file or a byte string;
2. ZIP parsing succeeds and the archive has no comment;
3. the member set is exactly the six declared names;
4. no member is a directory, symlink, encrypted entry, or duplicate;
5. the archive manifest is canonical JSON and has no unknown fields;
6. manifest and archive addresses recompute exactly;
7. each payload byte sequence matches its size and content receipt;
8. the nested observatory package has the exact five-file shape;
9. nested observatory, verification, and metrics links agree; and
10. the independently recomputed package verifier accepts.

ZIP names are never extracted before the exact member set is checked. Archive
extraction writes a temporary exact observatory directory, verifies it through
the upstream loader, and atomically replaces only a destination that is either
new or explicitly authorized and already compatible. A failed extraction
leaves the destination untouched.

## Queries

Archive queries reload and verify the archive before selecting records. The
bounded resources are:

| Resource | Records |
| --- | --- |
| `summary` | one archive projection |
| `files` | five payload artifact receipts |
| `members` | source-scoped observatory members |
| `checks` | all independent verification checks |
| `failed` | failed verification checks |
| `required` | required verification checks |
| `optional` | optional verification checks |

Queries support severity, pass-state, case-insensitive canonical-text search,
offset, and bounded limit filters. The result address covers the archive
address, query filters, total count, and returned records. JSON, CSV, and
Markdown renderers project the same result; rendering cannot mutate or widen
the selection.

## CLI and API

The commands are nested below the long observatory command:

```powershell
python -m glio_noncode <observatory-command>-archive --input review-output/observatory --destination review-output/observatory.zip --format summary
python -m glio_noncode <observatory-command>-archive-verify --input review-output/observatory.zip
python -m glio_noncode <observatory-command>-archive-manifest --input review-output/observatory.zip
python -m glio_noncode <observatory-command>-archive-query --input review-output/observatory.zip --resource checks --severity required --passed --limit 50
python -m glio_noncode <observatory-command>-archive-extract --input review-output/observatory.zip --destination review-output/extracted
```

The archive HTTP route is nested under:

```text
.../decision-ledger/assurance-history/observatory/archive
```

It exposes build, verify, manifest, extract, query, schema, artifact-schema,
manifest-schema, query-schema, query-result-schema, and capabilities
operations. File and byte loading share the same verifier. The route does not
return source paths or attribution metadata.

## Demonstration and transfer

The archive demo accepts a current-format downloaded observatory package,
writes an archive, reloads it, and queries the archive. A second demo extends
that flow into the byte-oriented chunk transport. See
[the archive-transfer contract](RELEASE_REGISTRY_FEDERATION_GATE_REVIEW_DECISION_LEDGER_ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_TRANSFER.md)
for chunk ranges, reassembly, and transfer-directory operations.

The transfer boundary also has an independent audit surface. It emits eight
addressed checks over transfer identity, range conservation, public boundary,
manifest linkage, received chunk receipts, progress conservation, nested
archive linkage, and completion. Complete transfers pass all checks; partial
transfer directories remain inspectable with explicit incomplete status and
can be resumed without editing the original manifest.

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_demo.py --input review-output/observatory --destination review-output/observatory.zip --resource checks --severity required --passed --format summary
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_demo.py --input review-output/observatory.zip --destination review-output/transfer --chunk-size 65536 --resource chunks --limit 5 --format markdown
```

## Negative controls

The focused archive suite covers deterministic repeat bytes, in-memory and
directory builder parity, path-free mappings, fixed ZIP metadata, comment and
member-shape rejection, duplicate and traversal-like names, symlink members,
canonical JSON rejection, payload and manifest tamper, exact extraction,
explicit overwrite, all query resources, query filters, CLI, HTTP, schemas,
capabilities, and current-format downloaded-data demonstration.

The archive boundary intentionally rejects older package shapes. It does not
silently rename legacy files, convert old fields, or treat an invalid source as
an empty observatory. Operators must rebuild from an upstream current-format
history or observatory package.
