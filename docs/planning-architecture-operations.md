# D13 Operation Catalog

| ID | Family | Operation | Delegate operation | Controls retained |
| --- | --- | --- | --- | --- |
| D13-C01 | validation design | evidence gap | gap_analysis | missing dimensions and context |
| D13-C02 | validation design | assay eligibility | assay_eligibility | unsupported assay and context |
| D13-C03 | validation design | MPRA construct | mpra_package | unchanged allele and budget |
| D13-C04 | validation design | STARR-seq construct | starrseq_package | missing fields and context |
| D13-C05 | editing design | CRISPR design | crispr_design | unsupported mode and missing targets |
| D13-C06 | editing design | base editing | base_editing | context and single-base substitution |
| D13-C07 | editing design | prime editing | prime_editing | context, length, and flank shortage |
| D13-C08 | editing design | allele reporter | allele_specific_reporter | allele pair, budget, and context |
| D13-C09 | planning | model eligibility | model_system_eligibility | context, evidence, and empty observations |
| D13-C10 | planning | guide adaptation | guide_oligo_adaptation | context, malformed row, and empty source |
| D13-C11 | planning | controls randomization | controls_randomization | context, missing target, and no targets |
| D13-C12 | planning | power replication | power_replication | context, malformed row, and no observations |
| D13-C13 | validation release | off-target risk | off_target_risk | burden, context, and invalid score |
| D13-C14 | validation release | value of information | value_of_information | budget, cycle, and context |
| D13-C15 | validation release | experiment package | experiment_package | empty package, identity, and context |
| D13-C16 | validation release | claim update | claim_update | unknown claim, context, and missing receipt |

Every operation receives a typed input contract, emits a bounded output
contract, declares dependency IDs, joins family sources, and retains a control
policy. Operation order is contiguous from one through sixteen.
