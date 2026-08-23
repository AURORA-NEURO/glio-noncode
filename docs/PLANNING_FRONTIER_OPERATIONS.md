# D13 C09–C12 planning operations

This frontier is a typed, deterministic planning surface for four independent
capabilities:

1. Model-system eligibility matches an exact context key, declared support,
   cell state, evidence strength, and blockers.
2. Guide/oligo adaptation parses JSON, CSV, and TSV rows while retaining source
   identity, sequence, strand, offsets, PAM, and a row address.
3. Controls/randomization builds deterministic biological and technical
   assignments from an explicit seed and control inventory.
4. Power/replication exposes a transparent normal-approximation requirement,
   achieved-power proxy, assumptions, and replicate shortfall.

Each operation returns a state, issue codes, bounded output, and a content
address. The runtime never treats a blocked or held row as a negative biological
finding. All calculations are planning transformations of supplied aggregate
inputs.

The command surface is:

```text
planning-frontier-data-audit
planning-frontier-evaluate
planning-frontier-pipeline
planning-frontier-depth
planning-frontier-quality
planning-frontier-provenance
planning-frontier-replay
planning-frontier-integrity
planning-frontier-review-queue
planning-frontier-data-dictionary
planning-frontier-report
planning-frontier-failure-injection
planning-frontier-review-csv
```
