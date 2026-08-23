# Planning frontier failure modes

The fixture deliberately exercises the following boundaries:

- foreign model, guide, control, and power contexts become `blocked`;
- undeclared or weak model evidence becomes `review`;
- malformed guide rows are quarantined as `invalid_guide_oligo_row`;
- an empty guide source becomes `abstained`;
- missing target identity becomes `review`;
- an empty controls plan becomes `abstained`;
- non-positive variance becomes `invalid_power_row`;
- an empty power observation set becomes `abstained`;
- missing required payload structure becomes `rejected` with `invalid_payload`.

The failure-injection command executes all four adapters with an empty payload
and verifies that rejection and the issue code remain visible. Negative rows are
not erased from the public evaluation or review queue.
