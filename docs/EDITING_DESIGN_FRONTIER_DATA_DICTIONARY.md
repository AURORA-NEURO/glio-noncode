# Editing-design frontier data dictionary

| Field | Meaning |
| --- | --- |
| design_id | stable planning identity |
| context_key | exact genome, disease, age, state, territory, and treatment context |
| targets | sequence-bearing edit or guide targets |
| sequence | declared aggregate reference window |
| reference | expected target allele |
| alternate | proposed edit allele |
| variant_offset | zero-based target offset |
| modes | CRISPRi or CRISPRa design modes |
| guide_length | candidate window length |
| editing_window | base-editing interval |
| pbs_length | prime-editing primer-binding length |
| rtt_length | prime-editing reverse-transcription length |
| flank_length | available prime-editing flank |
| constructs | reporter construct rows |
| controls | required negative and positive controls |
| readouts | declared measurement outputs |
| expected_state | fixture expectation |
| issue_codes | visible hold reasons |
| content_address | deterministic identity |

The fixture has five public receipts, sixteen records, four positive scenarios, twelve controls, and eighty checks.
