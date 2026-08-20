# Data model notes

The canonical graph is intentionally decomposed. A variant identity is not a regulatory element; a regulatory element is not a target gene; and a target gene is not a cell-state mechanism. Each relationship is represented by an edge with its own claims, context fit, support, uncertainty, and alternatives.

The object store records immutable JSON. Corrections create a new claim that can supersede an earlier claim, while evidence-delta records explain which hypotheses require selective recomputation. A reviewer can therefore reconstruct both the current view and the sequence of changes that produced it.

Structural events preserve breakend pairs, phased segments, and alternate paths. Cohort recurrence uses callable local backgrounds and reports control gaps. Workflow compilation preserves dependencies and declared resources. These objects are foundations for larger adapters and models, not proof that an external dataset has been validated.
