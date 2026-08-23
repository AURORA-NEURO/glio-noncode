# Editing-design frontier operations

D13 C05–C08 is an independent public aggregate planning boundary for:

- CRISPRi and CRISPRa guide-window design
- single-base editing-window design
- prime-edit PBS, RTT, flank, and edit-length packaging
- paired reference/alternate reporter construct design

The operation result preserves state, issue codes, safe output, and a content address. It is a planning receipt and does not claim guide efficacy, editing rate, safety, or clinical meaning.

## States

| Operation family | Success | Held |
| --- | --- | --- |
| CRISPRi/CRISPRa | designed | review, blocked, rejected |
| base editing | designed | review, blocked, rejected |
| prime editing | designed | review, blocked, rejected |
| allele reporter | designed | review, blocked, rejected |

Foreign contexts are blocked. Empty inventories, unsupported modes, invalid substitutions, edit-length overflow, flank shortage, missing allele pairs, and construct-budget overflow remain review conditions.

## Full runtime

```text
glio-noncode editing-design-frontier-pipeline --output editing-design-runtime.json
```

The runtime executes 79 ordered stages and 70 named assurance planes over 16 rows and 80 checks.
