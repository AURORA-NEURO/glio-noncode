# Local service surface

The local service exposes the certified product surfaces through a dependency-free
HTTP API. The service constructs one deterministic snapshot lazily and reuses it
for the lifetime of the server. Every projection carries the address of the
report or runtime from which it was derived.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Cheap process health response |
| GET | `/v1/schema` | Existing case contract summary |
| GET | `/v1/status` | Compact capability, program, operational, and boundary status |
| GET | `/v1/capabilities` | Certified capability query |
| GET | `/v1/architecture/program` | Architecture receipt query |
| GET | `/v1/architecture/operational` | Full stage, artifact, and check handoff trace |
| GET | `/v1/architecture/diff` | Baseline comparison with a named control |
| POST | `/v1/evaluate` | Existing case evaluation endpoint |

Capability queries accept `capability_id`, `domain_id`, `mvp_only`, `state`, and
`text`. Architecture queries accept `domain_id`, `accepted_only`, and `text`.
Boolean values accept `true`, `false`, `1`, `0`, `yes`, and `no`. Diff controls
are `none`, `missing-fixture`, and `missing-runtime`. Invalid query values return
HTTP 400 with the `invalid_query` error code.

## CLI and offline closure

Run the compact status projection:

```text
glio-noncode service-surface --output service-status.json
```

Run the detailed archival projection:

```text
glio-noncode service-surface --closure --output service-surface-closure.json
```

The closure includes the complete 256-row capability certification report, the
sixteen-domain architecture runtime, the twelve-stage operational trace, and
the common query projections. The closure is rejected if its public projection
contains a private-key field.
