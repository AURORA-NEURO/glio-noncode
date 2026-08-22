# Reference release frontier changelog

## 2026-08-22 — C13-C16 release frontier

Added a fresh public aggregate package for Domain 04 C13-C16:

- source provenance closure with checksum, license, URI, and context checks;
- annotation drift comparison with ignored receipt fields and new-row drift;
- reproducible reference bundle assembly with availability and exact-context
  gates;
- reference release integrity gate with explicit required checks;
- typed contracts and field schemas;
- 23 source and fixture checks plus 48 execution checks;
- independent output projection and raw-row redaction assertions;
- operation metrics, issue counts, policy decisions, and reconciliation;
- 111-node/133-edge source-to-receipt lineage;
- deterministic replay with twelve comparison checks;
- nine-stage runtime rehearsal;
- ready release manifest, accepted bundle, artifact inventory, review view,
  review queue, observability, accessibility, compliance, invariants,
  scenarios, thresholds, validation matrix, adapters, and runbook;
- twenty-six root CLI commands and JSON/CSV exports;
- focused regression tests and capability-ledger promotion.

The fixture uses public source receipts and aggregate metadata only. No
downloaded reference bytes or subject-level data are checked in.
