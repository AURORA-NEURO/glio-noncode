# Validation design

`glio_noncode.validation_design` turns an existing research hypothesis and
uncertainty report into bounded next actions.

`AssayRouter` ranks declared `ExperimentOption` objects using expected
information gain, feasibility, and unresolved uncertainty. It preserves each
option's controls, readouts, and blockers. It does not invent an assay menu or
recommend treatment.

`GuideDesigner` enumerates local SpCas9-like `NGG` candidates spanning a
verified variant in a retrieved reference window. It checks the declared
reference allele, records coordinate/strand/PAM/GC details, and labels
off-target status `unassessed` until a reference-aware search is supplied.
No guide sequence is presented as efficient, safe, or ready to synthesize.

`PowerPlanner` gives a normal-approximation planning envelope and requires
explicit effect, baseline, alpha, and target-power assumptions. Its controls
and limitations remain attached; batch effects, dropout, dispersion, and
multiple-testing design require a later statistical review.
