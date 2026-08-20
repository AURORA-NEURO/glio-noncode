# Uncertainty and out-of-domain checks

`glio_noncode.uncertainty` keeps uncertainty decomposed and reviewable.
`DomainProfile` declares required features, supported ranges, context key, and
source/model versions. `OutOfDomainDetector` reports in-domain, watch,
out-of-domain, and abstained states with missing and out-of-range feature IDs.

`UncertaintyPropagator` derives visible components for missingness,
contradiction, context transport, source dependence, and optional OOD distance.
The aggregate is a research-use uncertainty view, not a clinical probability.
An OOD abstention forces the aggregate band to `abstain`.

`CalibrationEvaluator` computes descriptive mean absolute error, Brier score,
expected calibration error, and per-group metrics from pre-specified held-out
prediction/outcome pairs. It does not declare a model calibrated without an
independent evaluation design.
