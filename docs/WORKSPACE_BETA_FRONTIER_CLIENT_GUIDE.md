# Workspace beta frontier client guide

Clients consume four projection views and one release package. The safest
rendering order is:

1. package boundary
2. release state
3. quality gate
4. operation summaries
5. review queue
6. detailed projection rows

## Topology client

Render nodes and edges only after checking the viewport state. Display focus
coordinates, edge kind, source IDs, source versions, observation IDs, and
warnings together. Keep loop, promoter-capture, contact-score, and
activity-by-contact kinds distinct. If the viewport is out of domain, show the
context warning instead of drawing an empty supported state.

## Chain client

Render the chain as a directed graph with one card per edge. Show mediator kind,
support, uncertainty, source IDs, evidence IDs, negative evidence IDs, and
reason. Display missing mediator kinds beside the graph. Alternative edge IDs
must remain selectable, and contradiction must be visible at both edge and
chain level.

## Posterior client

Render prior, support, proxy, calibration status, component total, residual,
and normalized shares as separate fields. A residual is not a component. A
foreign component is not silently included in the local total. If support is
missing, render abstention rather than zero.

## Table client

Render filter controls for text, context, channel, tier, state, source,
confidence, offset, and limit. Show total matches and facets above the page.
Rows keep state, source IDs, tags, fields, and confidence. A page containing
partial rows remains partial even when the filter is narrow.

## Review client

Use the review view for stable rows and the queue for action ordering. Ready
rows can be summarized; held and abstained rows require visible rationale.
Queue priority is a routing hint, not an evidence ranking. Keep the release
manifest address attached to each review export.

## Error client

Render issue codes as structured badges with explanatory text. Do not map
`absent`, `abstained`, `out_of_domain`, `partial`, or `contradictory` to a
negative evidence color without a separate legend. Preserve the exact context
key and content address in an expandable receipt panel.

## Export client

Use canonical JSON for machine exchange and the stable CSV export for review
workflows. CSV columns are fixed and issue/source lists use semicolon
delimiters. Do not infer a new field from a display label; use the schema
manifest and data dictionary.

## Accessibility client

Use the report's accessible labels, descriptions, section order, keyboard order,
and focus boundary. Table filters must have a visible label. Review state must
be announced with text as well as color. Keep warnings in reading order after
the primary state and before detailed rows.
