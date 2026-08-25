# Provenance-first review workspace

The review workspace is the dossier review read model for GLIO-NONCODE. It
complements the searchable run workspace by keeping the reasoning graph
visible: hypotheses, decomposed edges, evidence states, alternatives, source
provenance, human-review work items, and explicit cross-run deltas are returned
as separate collections.

It is a replay-gated research projection. A failed current run or baseline run
withholds details. The projection never publishes raw evidence payloads,
producer metadata, direct subject/sample/contact fields, or a single aggregate
decision score.

## Review collections

- `hypotheses` retains mechanism, context, status, support, uncertainty, edge
  IDs, evidence IDs, alternatives, provenance IDs, and missing/negative
  evidence declarations.
- `edges` retains source/target identifiers, typed edge kind, support,
  uncertainty, context fit, support level, claim IDs, source IDs, and evidence
  state counts.
- `evidence` retains source, channel, tier, state, score, confidence, context,
  summary, dependency IDs, and supersession links. Payloads are withheld.
- `alternatives` keeps each declared branch as a separate reviewable object;
  an alternative is not folded into the primary hypothesis.
- `provenance` groups evidence by source and retains edge/claim coverage,
  tiers, states, contexts, dependencies, supersession, and declared receipt
  IDs.
- `review_queue` gives a bounded priority band and reasons for human review.
  Priority is workflow triage, not biological ranking.
- `deltas` compare common or introduced/removed hypotheses, edges, and evidence
  between two verified runs. Numeric deltas are per dimension (support,
  uncertainty, context fit, score, or confidence); state and presence changes
  remain categorical.

## CLI

```powershell
glio-noncode review-workspace RUN_ID --data-root .glio --output review-workspace.json
glio-noncode review-workspace RUN_ID --data-root .glio --baseline-run-id BASELINE_RUN_ID --output review-deltas.json
glio-noncode review-workspace-schema --output review-workspace-schema.json
glio-noncode review-workspace-capabilities --output review-workspace-capabilities.json
```

The command exits successfully when the public projection is safe to consume,
including when its review state is `review`. `abstained` and `blocked` are
content states that remain inspectable when the run itself is valid; failed
replay verification returns no reasoning collections.

## API

`GET /v1/review-workspace/schema` and
`GET /v1/review-workspace/capabilities` expose the contract. Use
`GET /v1/runs/{run_id}/review-workspace` for the current run and add
`baseline_run_id` to request verified cross-run deltas. Both runs must belong
to the same case and pass replay verification.

The API response contains independent content addresses for the complete
workspace and every review collection item. This allows a renderer or offline
handoff to verify exact receipts without trusting a summary score.

## Boundary and limitations

Review state indicates work to adjudicate, not truth. Evidence state remains
distinct from review state: supported, contradictory, measured-negative,
absent, out-of-domain, and abstained claims are not silently converted into a
positive or negative conclusion. Source IDs and receipt IDs are declarations;
they do not establish external validation or scientific reproducibility by
themselves.
