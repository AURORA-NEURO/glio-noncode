# Planning frontier runbook

1. Run `planning-frontier-data-audit` and confirm five sources, sixteen rows,
   four positives, and twelve controls.
2. Run `planning-frontier-evaluate` and confirm 80/80 checks.
3. Run `planning-frontier-quality` and inspect adapter, schema, boundary, and
   state-diversity checks.
4. Run `planning-frontier-provenance` and `planning-frontier-integrity`.
5. Run `planning-frontier-review-queue`; keep every non-ready row held.
6. Run `planning-frontier-pipeline` for the complete ordered runtime.
7. Run the focused unit tests and the full regression suite before release.

Do not turn a missing observation into a negative conclusion. Do not replace an
exact context mismatch with a fuzzy match. Do not treat the normal approximation
as a guarantee. All changes should preserve deterministic content addresses.
