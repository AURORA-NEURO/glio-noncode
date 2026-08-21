# C09-C12 release format

`AtlasAlphaEvidenceReleaseManifest` is the publication boundary for the
open-chromatin, methylation, role-classification, and super-enhancer tranche.
It contains:

- release and fixture versions;
- exact context key;
- operation IDs and source IDs;
- bundle, quality-gate, and runtime content addresses;
- accepted or rejected status;
- an explicit non-causal acceptance statement.

The release can be built only after data audit, adapter evaluation, replay,
scenario, policy, lineage, and reconciliation checks have been produced. A
strict runtime may still reject the run when review records exist; the default
runtime accepts a quality-gated research bundle while retaining all review
states.

The release is a research artifact. It is not a clinical report, a treatment
recommendation, an activity probability, or a claim that any aggregate fixture
row is present in an upstream public release.
