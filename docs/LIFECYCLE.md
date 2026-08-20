# Review and lifecycle

`glio_noncode.lifecycle` makes the human and operational lifecycle explicit.

`ReviewPacketBuilder` runs the release gate, counts every evidence state,
collects open questions and alternative explanations, and names the expertise
needed to review the evidence channels. It does not accept or reject a claim.

`LifecycleReclassifier` compares immutable dossier snapshots through the
existing append-only evidence delta engine. Changes in evidence state/score or
source version create a reclassification plan and mark review as required;
affected hypotheses and edge IDs remain named for selective recomputation.

`DriftMonitor` compares baseline/current metrics and reuses the operational
monitor registry. Missing metrics become `unknown`, coarse changes become
watch/alert signals, and monitoring alerts are operational review signals—not
proof that a scientific result is invalid.
