# Observatory archive registry audit

The registry audit is an independent operator surface for an exact persisted
observatory archive registry. The registry loader answers whether a package
can be rehydrated as a typed registry. The audit answers which package
properties pass when each artifact is inspected as raw evidence.

## Twelve checks

The report always emits the same ordered check set:

1. `exact-members` — the directory contains exactly the five declared files.
2. `canonical-json` — every artifact is canonical UTF-8 JSON.
3. `manifest-contract` — version, boundary, file list, count, and manifest address reproduce.
4. `artifact-receipts` — manifest receipts reproduce each non-manifest artifact byte sequence.
5. `registry-linkage` — manifest identity and address fields link to `registry.json`.
6. `entry-linkage` — `entries.json` matches the registry entry projection and count.
7. `verification-linkage` — verification identity and back-reference match the registry.
8. `metrics-conservation` — metrics equal recomputed entry totals.
9. `posture-projection` — state, acceptance, and readiness are derived from entries.
10. `public-boundary` — decoded artifacts contain no private or attribution fields.
11. `content-address` — registry and verification content addresses reproduce.
12. `verification-checks` — nested verification checks pass and reproduce.

The report is `complete` and `accepted` only when all twelve checks pass. A
malformed or damaged package produces an `incomplete` report with failed
checks and bounded unresolved evidence addresses. The audit never repairs a
package and never includes the source path in its public projection.

## Python

```python
from glio_noncode import (
    audit_assurance_history_observatory_archive_registry_directory,
    render_assurance_history_observatory_archive_registry_audit_markdown,
)

report = audit_assurance_history_observatory_archive_registry_directory(
    "review-output/registry"
)
print(render_assurance_history_observatory_archive_registry_audit_markdown(report))
```

For a verified in-memory registry with an attached verification artifact,
`audit_assurance_history_observatory_archive_registry(value)` runs the same
public checks over the canonical generated package projection.

## CLI and HTTP

The CLI audit command is the registry command with `-audit` appended:

```powershell
python -m glio_noncode <registry-command>-audit --input review-output/registry --format markdown
python -m glio_noncode <registry-command>-audit-schema
python -m glio_noncode <registry-command>-audit-check-schema
python -m glio_noncode <registry-command>-audit-capabilities
```

The HTTP audit route is:

```text
<registry-route>/audit
<registry-route>/audit/schema
<registry-route>/audit/check-schema
<registry-route>/audit/capabilities
```

Valid packages return HTTP 200. An incomplete audit returns HTTP 422 while
still returning the structured report, allowing operators to see which checks
failed without relying on exception text.

## Safety properties

The audit has no network dependency and accepts no old repository or framework
input. It reads only the registry directory in scope, rejects symlinked
members, checks canonical bytes and content addresses, and uses the same
public-key exclusions as the archive and registry boundaries. It is an
inspection layer; it does not expand the scientific or clinical claims of the
underlying observatory data.
