# Planning frontier release boundary

The release contains public HTTPS source receipts, aggregate scenario payloads,
typed operation results, five checks per row, provenance edges, review
dispositions, and content addresses.

Ready rows can enter a bounded review release. Blocked, review, rejected, and
abstained rows remain held and are listed in the review queue. The release
explicitly excludes efficacy, safety, clinical, causal, patient-level, and
institutional conclusions.

The runtime accepts only when source audit, scenario evaluation, quality gate,
depth report, and assurance report all accept. A release address is derived
from the fixture, evaluation, provenance, and exclusion list.
