# Runtime Registry Federation Archive

The runtime-registry federation archive is the portable handoff boundary above a verified recovery execution runtime registry federation. It converts the federation's exact five-file directory into one deterministic ZIP while retaining the federation's public identity, member provenance, flattened runtime entries, state folding, and content addresses.

The archive is an interchange format, not a second source of truth. A ZIP is accepted only when its complete byte stream, member order, metadata, canonical JSON, embedded federation projection, receipts, manifest, and addresses all replay. The public projection remains value-free: it exposes identifiers, states, counts, addresses, and bounded descriptions rather than source paths, raw records, or embedded payload bytes.

## Contract

The archive has a fixed six-member vocabulary and fixed order:

1. `manifest.json` — archive identity, federation link, member list, artifact receipts, and manifest address;
2. `federation/manifest.json` — the embedded federation manifest;
3. `federation/federation.json` — the complete addressed federation projection;
4. `federation/members.json` — source-scoped registry members;
5. `federation/entries.json` — flattened runtime-entry provenance; and
6. `federation/summary.json` — conserved federation counters and state totals.

Every member is UTF-8 canonical JSON. ZIP timestamps are fixed to the DOS epoch used by the implementation, regular members use a fixed permission envelope, the archive comment is empty, and compression settings are stable. The archive content address is derived from the public archive envelope while excluding only the circular ZIP byte size and address fields. The serialized ZIP size is then recorded in the archive object and checked on every byte export.

The archive builder accepts a typed federation or an exact persisted federation directory. Directory loading inherits the federation boundary's regular-file, symlink, exact-member, canonical-byte, and nested-address checks. `build_archive_from_directory` therefore cannot silently package an incomplete or legacy federation directory.

Atomic writes use a temporary sibling file and replacement. Existing destinations require explicit overwrite permission and must remain regular files. Archive loading rejects invalid ZIPs, duplicate or unexpected members, reordered members, absolute or traversal names, directories, symlink entries, encrypted entries, non-empty comments, oversized members, oversized aggregate bytes, non-canonical JSON, stale receipts, stale manifest addresses, stale federation addresses, and mismatched embedded projections.

## Assurance

The independent archive audit recomputes 18 addressed checks:

- fixed version and boundary;
- archive address and archive identity;
- artifact count, fixed file order, artifact order, and byte receipts;
- outer manifest linkage;
- embedded federation loading and identity;
- federation projection equality;
- ZIP byte-size conservation and ZIP safety;
- deterministic byte replay;
- public-boundary safety; and
- public mapping and byte round trips.

The audit is independent of archive construction. It reads the complete serialized ZIP member set when checking outer-manifest linkage, so a successful in-memory build cannot mask a damaged persisted envelope. Failed audits remain diagnosable as public check records, while CLI and HTTP audit commands return a nonzero result when the archive is not accepted.

## Query boundary

The archive query exposes ten bounded resources:

- `summary` — archive and federation counters;
- `manifest` — the public outer manifest;
- `artifacts` — five embedded byte receipts;
- `federation` — the embedded federation summary;
- `members` — source-scoped registry member projections;
- `entries` — flattened runtime-entry projections;
- `states` — state counts;
- `readiness` — readiness and acceptance counters;
- `addresses` — archive, federation, member, and entry addresses; and
- `bounds` — fixed limits and archive vocabulary.

Queries accept resource, state, key, text, offset, and limit filters. Rows have stable addresses and deterministic order. Query results do not expose the private embedded byte map. A separate twelve-check query audit replays filters, counts, row order, row addresses, membership, resource semantics, archive linkage, public-boundary safety, and mapping round trips.

## Interfaces

The long-form CLI command prefix is:

```text
downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive
```

Build a ZIP from an exact federation directory:

```powershell
python -m glio_noncode.cli `
  downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive `
  C:\data\federation `
  --destination C:\data\federation.zip `
  --format summary
```

Inspect the ZIP, audit it, or query a bounded resource:

```powershell
python -m glio_noncode.cli <prefix>-verify C:\data\federation.zip --format summary
python -m glio_noncode.cli <prefix>-audit C:\data\federation.zip --format markdown
python -m glio_noncode.cli <prefix>-query C:\data\federation.zip --resource entries --limit 20 --format json
python -m glio_noncode.cli <prefix>-query-audit C:\data\query.json --archive-input C:\data\federation.zip --format summary
```

The local HTTP API mirrors build, verify, audit, query, and query-audit below the federation archive route. Schema and capability routes are available for the archive, artifact, manifest, audit, query, and query-audit contracts.

## Downloaded-data demonstration

The downloaded-data example builds two runtime entries from the supplied downloaded archive workflow, persists the exact five-file runtime-registry federation, packages that federation as the six-member ZIP, reloads it, audits the archive, queries every archive resource, and audits the query result. The generated summary records archive byte size, five artifact receipts, 18/18 archive checks, bounded query counts, and 12/12 query-audit checks. The demo output remains suitable for offline review because no local source paths, raw source records, or embedded byte payloads are placed in the public JSON/CSV/Markdown projections.

Focused regression coverage exercises real downloaded-derived federation fixtures, deterministic byte replay, exact ZIP metadata, extra/reordered/comment/non-canonical/symlink/encrypted rejection, atomic persistence, CLI commands, HTTP routes, schema closure, and the public-surface inventory.
