"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const model = {
    runs: [], total: 0, selected: null, baseline: "", report: null, hypothesis: null,
    geoAnalyses: [], geoTotal: 0, selectedGeo: null, geoPage: null, geoResults: [],
    activeView: "empty", runsLoaded: false, geoLoaded: false,
    selectionRequest: 0, runListRequest: 0, geoListRequest: 0,
  };
  const pageSize = 50;

  function element(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  function notice(text, error = false) {
    const box = $("notice");
    box.textContent = text;
    box.className = error ? "notice error" : "notice";
    box.hidden = !text;
  }

  function announceSelection(text) {
    $("selection-announcement").textContent = text;
  }

  async function getJson(path) {
    const response = await fetch(path, { headers: { Accept: "application/json" }, cache: "no-store", credentials: "same-origin" });
    let body;
    try { body = await response.json(); }
    catch { throw new Error(`The local API returned HTTP ${response.status} without JSON.`); }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${body.message || "Request rejected."}`);
    return body;
  }

  function percent(value) { return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "Not available"; }
  function shortened(value, limit = 27) { const text = String(value ?? ""); return text.length > limit ? `${text.slice(0, limit - 1)}…` : text; }
  function time(value) {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? String(value || "Time unavailable") : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  function renderRuns() {
    const list = $("run-list");
    const query = $("run-search").value.trim().toLocaleLowerCase();
    const rows = model.runs.filter((run) => [run.run_id, run.case_id, run.status, run.dossier_id].join(" ").toLocaleLowerCase().includes(query));
    list.replaceChildren();
    $("run-count").textContent = String(model.total);
    $("run-list-summary").textContent = query ? `${rows.length} matches in loaded runs.` : `Showing ${model.runs.length} of ${model.total} saved runs.`;
    $("load-more").hidden = !model.runs.length || model.runs.length >= model.total;
    if (!rows.length) {
      list.append(element("p", "empty-inline", query ? "No loaded runs match this search." : "No saved runs yet."));
      return;
    }
    for (const run of rows) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(run.run_id === model.selected));
      button.setAttribute("aria-label", `Open ${run.case_id}, ${run.status}, ${run.hypothesis_count} candidate paths`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", run.case_id), element("span", "run-status", run.status));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(run.run_id, 29)), element("span", "", `${run.hypothesis_count} paths`));
      button.append(top, meta);
      button.addEventListener("click", () => openRun(run.run_id));
      list.append(button);
    }
  }

  function renderGeoAnalyses() {
    const list = $("geo-analysis-list");
    list.replaceChildren();
    $("geo-count").textContent = String(model.geoTotal);
    $("geo-list-summary").textContent = `Showing ${model.geoAnalyses.length} of ${model.geoTotal} saved aggregate analyses.`;
    $("geo-load-more-analyses").hidden = model.geoAnalyses.length >= model.geoTotal;
    if (!model.geoAnalyses.length) {
      list.append(element("p", "empty-inline", "No saved GEO analyses yet."));
      return;
    }
    for (const item of model.geoAnalyses) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.analysis_id === model.selectedGeo));
      button.setAttribute("aria-label", `Open aggregate GEO contrast ${item.accession}, ${item.matched_pair_count} matched pairs`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.accession), element("span", "run-status", "GEO"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.analysis_id, 28)), element("span", "", `${item.matched_pair_count} pairs · ${item.fdr_significant_feature_count} q-significant`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoAnalysis(item.analysis_id));
      list.append(button);
    }
  }

  async function loadGeoAnalyses(append = false, deferSelection = false) {
    const request = model.geoListRequest = (model.geoListRequest || 0) + 1;
    try {
      const offset = append ? model.geoAnalyses.length : 0;
      const page = await getJson(`/v1/geo-analyses?limit=50&offset=${offset}`);
      if (request !== model.geoListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) {
        throw new Error("The local API returned an invalid GEO analysis catalog.");
      }
      model.geoTotal = page.total_count;
      model.geoAnalyses = append ? model.geoAnalyses.concat(page.rows) : page.rows;
      model.geoLoaded = true;
      renderGeoAnalyses();
      if (!append && !deferSelection && model.activeView === "geo" && model.selectedGeo) {
        if (model.geoAnalyses.some((item) => item.analysis_id === model.selectedGeo)) {
          await openGeoAnalysis(model.selectedGeo);
        } else if (model.geoAnalyses.length) {
          await openGeoAnalysis(model.geoAnalyses[0].analysis_id);
        } else if (model.runs.length) {
          await openRun(model.runs[0].run_id);
        } else {
          showEmpty("No saved GEO analyses", "Run a paired GEO contrast with --save-to-workspace to review its aggregate results here.");
        }
      } else if (
        !append
        && !deferSelection
        && model.runsLoaded
        && !model.runs.length
        && (model.activeView === "empty" || (model.activeView === "case" && !model.selected))
      ) {
        if (model.geoAnalyses.length) {
          await openGeoAnalysis(model.geoAnalyses[0].analysis_id);
        } else {
          showEmpty("No saved research records", "Case runs and aggregate GEO reports appear here after they are saved to the local workspace.");
        }
      }
    } catch (error) {
      if (request !== model.geoListRequest) return;
      model.geoLoaded = true;
      $("geo-analysis-list").replaceChildren(element("p", "empty-inline", "GEO analyses could not be loaded."));
      $("geo-list-summary").textContent = "The local API could not verify the GEO analysis catalog.";
      notice(error.message, true);
    }
  }

  function renderBaseline() {
    const select = $("baseline-select");
    const prior = model.baseline;
    select.replaceChildren(new Option("No baseline", ""));
    for (const run of model.runs) {
      if (run.run_id !== model.selected) select.add(new Option(`${run.case_id} · ${shortened(run.run_id, 23)}`, run.run_id));
    }
    if ([...select.options].some((option) => option.value === prior)) select.value = prior;
    else { model.baseline = ""; select.value = ""; }
  }

  function showEmpty(title, copy) {
    $("run-view").hidden = true;
    $("geo-analysis-view").hidden = true;
    $("empty-state").hidden = false;
    $("empty-title").textContent = title;
    $("empty-copy").textContent = copy;
  }

  async function loadRuns(append = false, deferSelection = false) {
    const request = model.runListRequest = (model.runListRequest || 0) + 1;
    notice("");
    $("run-list-summary").textContent = "Checking saved runs and replay integrity…";
    try {
      const offset = append ? model.runs.length : 0;
      const page = await getJson(`/v1/runs?limit=${pageSize}&offset=${offset}`);
      if (request !== model.runListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) {
        throw new Error("The local API returned an invalid run catalog.");
      }
      model.total = page.total_count;
      model.runs = append ? model.runs.concat(page.rows) : page.rows;
      model.runsLoaded = true;
      renderRuns();
      renderBaseline();
      if (!model.runs.length && !deferSelection) {
        model.selected = null;
        model.report = null;
        if (model.activeView !== "geo") {
          if (model.geoLoaded && model.geoAnalyses.length) await openGeoAnalysis(model.geoAnalyses[0].analysis_id);
          else showEmpty("No saved case runs", "Case runs and aggregate GEO reports appear here after they are saved to the local workspace.");
        }
      } else if (!append && !deferSelection && model.runs.length && model.activeView !== "geo") {
        const selected = model.runs.some((run) => run.run_id === model.selected) ? model.selected : model.runs[0].run_id;
        await openRun(selected);
      }
    } catch (error) {
      if (request !== model.runListRequest) return;
      $("run-list").replaceChildren(element("p", "empty-inline", "Runs could not be loaded."));
      $("run-list-summary").textContent = "The local API could not verify a run catalog.";
      notice(error.message, true);
    }
  }

  function exportHref() {
    const link = $("markdown-export");
    if (model.activeView === "geo" && model.selectedGeo && model.geoPage?.analysis_id === model.selectedGeo) {
      link.href = `/v1/geo-analyses/${encodeURIComponent(model.selectedGeo)}/report.json`;
      link.textContent = "Download GEO JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      return;
    }
    if (model.activeView !== "case" || !model.selected || !model.report || model.report.accepted !== true) {
      link.href = "#"; link.textContent = "Export review"; link.classList.add("disabled"); link.setAttribute("aria-disabled", "true"); return;
    }
    const baseline = model.baseline ? `&baseline_run_id=${encodeURIComponent(model.baseline)}` : "";
    link.href = `/v1/runs/${encodeURIComponent(model.selected)}/review-workspace/export?format=markdown${baseline}`;
    link.textContent = "Export review";
    link.classList.remove("disabled");
    link.setAttribute("aria-disabled", "false");
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  }

  async function openRun(runId) {
    model.activeView = "case";
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    model.selected = runId; model.hypothesis = null; model.report = null;
    renderRuns(); renderBaseline(); exportHref(); notice(""); announceSelection("");
    const run = model.runs.find((item) => item.run_id === runId);
    showEmpty("Verifying selected run", "Loading its replay-checked review projection. Previous run details are hidden.");
    $("empty-state").hidden = false;
    if (run) $("empty-copy").textContent = `${run.run_id} · ${run.status}`;
    $("hypothesis-list").replaceChildren(element("p", "empty-inline", "Loading verified review projection…"));
    try {
      const query = model.baseline ? `?baseline_run_id=${encodeURIComponent(model.baseline)}` : "";
      const report = await getJson(`/v1/runs/${encodeURIComponent(runId)}/review-workspace${query}`);
      if (request !== model.selectionRequest || model.activeView !== "case" || model.selected !== runId) return;
      if (report.accepted !== true) {
        notice("The review projection did not pass its public-boundary checks. Details remain hidden.", true);
        showEmpty("Review projection withheld", "The projection failed its public-boundary checks. No run details are displayed.");
        return;
      }
      model.report = report;
      $("empty-state").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("run-view").hidden = false;
      renderWorkspace();
      announceSelection(`Case run ${run?.case_id || runId} opened. Replay-verified review details are displayed.`);
    } catch (error) {
      if (request !== model.selectionRequest || model.activeView !== "case" || model.selected !== runId) return;
      notice(`The selected run could not be opened as a verified review projection. ${error.message}`, true);
      showEmpty("Review projection unavailable", "The selected run could not be verified, so its detail panels remain hidden.");
    } finally {
      if (request === model.selectionRequest && model.activeView === "case" && model.selected === runId) exportHref();
    }
  }

  function formatCount(value) { return Number.isSafeInteger(value) ? new Intl.NumberFormat().format(value) : "—"; }
  function formatQ(value) { return Number.isFinite(value) ? value.toExponential(2) : "—"; }
  function formatEffect(value) { return Number.isFinite(value) ? value.toFixed(3) : "—"; }
  function filterDescription(filters) {
    return (filters || []).map((item) => `${item.field} = ${item.equals}`).join(" AND ") || "Not specified";
  }

  async function openGeoAnalysis(analysisId, { append = false } = {}) {
    model.activeView = "geo";
    model.selectedGeo = analysisId;
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    renderGeoAnalyses();
    notice("");
    if (!append) announceSelection("");
    exportHref();
    if (!append) {
      model.geoPage = null;
      model.geoResults = [];
      exportHref();
      showEmpty("Verifying GEO report", "Loading the immutable aggregate report and verifying its saved provenance.");
    }
    const offset = append ? model.geoResults.length : 0;
    try {
      const page = await getJson(`/v1/geo-analyses/${encodeURIComponent(analysisId)}?limit=25&offset=${offset}`);
      if (request !== model.selectionRequest || model.activeView !== "geo" || model.selectedGeo !== analysisId) return;
      if (page.schema !== "glio-noncode.geo-analysis-page.v1" || page.analysis_id !== analysisId || !Array.isArray(page.results)) {
        throw new Error("The local API returned an invalid GEO report projection.");
      }
      if (append && model.geoPage?.report_address !== page.report_address) {
        throw new Error("The saved GEO report changed while loading feature rows.");
      }
      model.geoPage = page;
      model.geoResults = append ? model.geoResults.concat(page.results) : page.results;
      exportHref();
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = false;
      renderGeoReport();
      if (append) {
        announceSelection(`Loaded ${formatCount(model.geoResults.length)} of ${formatCount(page.total_results)} reported features.`);
      } else {
        announceSelection(`GEO analysis ${page.summary.accession} opened. ${formatCount(page.summary.matched_pair_count)} matched pairs, ${formatCount(page.summary.tested_feature_count)} features tested.`);
      }
    } catch (error) {
      if (request !== model.selectionRequest || model.activeView !== "geo" || model.selectedGeo !== analysisId) return;
      notice(`The selected GEO report could not be verified. ${error.message}`, true);
      showEmpty("GEO report unavailable", "The stored aggregate report could not be verified, so its result details remain hidden.");
    }
  }

  function renderGeoReport() {
    const page = model.geoPage;
    if (!page) return;
    const summary = page.summary;
    const comparison = page.comparison;
    const source = page.provenance;
    $("geo-title").textContent = `${summary.accession} · paired count contrast`;
    $("geo-subtitle").textContent = `${summary.matched_pair_count} complete pairs · ${filterDescription(comparison.case_filters)} versus ${filterDescription(comparison.reference_filters)}`;
    $("geo-report-address").textContent = page.report_address;
    $("geo-metric-pairs").textContent = formatCount(summary.matched_pair_count);
    $("geo-metric-samples").textContent = `${formatCount(summary.case_sample_count_selected)} case · ${formatCount(summary.reference_sample_count_selected)} reference selected`;
    $("geo-metric-tested").textContent = formatCount(summary.tested_feature_count);
    $("geo-metric-fdr").textContent = formatCount(summary.fdr_significant_feature_count);
    $("geo-metric-fdr-method").textContent = `${String(summary.fdr_method).toUpperCase()} · q ≤ ${summary.fdr_threshold}`;
    $("geo-metric-sign").textContent = formatCount(summary.sign_test_fdr_significant_feature_count);
    $("geo-normalization").textContent = comparison.normalization || "Normalization not reported";

    const provenance = $("geo-provenance");
    provenance.replaceChildren();
    const provenanceRows = [
      ["NCBI GEO series", summary.accession],
      ["Count matrix", `${source.count_matrix.file_name || "unnamed"} · ${source.count_matrix.source_sha256}`],
      ["Sample metadata", `${source.sample_metadata.file_name || "unnamed"} · ${source.sample_metadata.source_sha256}`],
      ["Case group", filterDescription(comparison.case_filters)],
      ["Reference group", filterDescription(comparison.reference_filters)],
      ["Pairing field", summary.pair_key_column],
      ["FDR family", `${formatCount(summary.tested_feature_count)} features · ${String(summary.fdr_method).toUpperCase()}`],
    ];
    for (const [label, value] of provenanceRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }
    renderGeoResults();
    renderGeoQuality();
    renderGeoLimitations();
  }

  function renderGeoResults() {
    const body = $("geo-results-table");
    body.replaceChildren();
    const page = model.geoPage;
    if (!page || !model.geoResults.length) {
      body.append(emptyRow(6, "No reported feature rows are available."));
      $("geo-result-count").textContent = "0 reported rows";
      $("geo-load-more").hidden = true;
      return;
    }
    for (const item of model.geoResults) {
      const row = document.createElement("tr");
      const feature = cell(item.feature_id);
      if (item.feature_label_review?.manual_annotation_review_recommended === true) {
        const badge = element("span", "feature-review-badge", "Review source label");
        badge.title = item.feature_label_review.possible_date_like_source_label === true
          ? "The original matrix label resembles a spreadsheet-converted date. It is preserved as supplied; verify its annotation before biological interpretation."
          : "The source report recommends manual review of this feature label before biological interpretation.";
        feature.append(badge);
      }
      row.append(
        feature,
        cell(item.rank_biserial_effect_direction || item.effect_direction || "unresolved"),
        cell(formatEffect(item.median_paired_difference_log2_cpm)),
        cell(formatQ(item.q_value)),
        cell(formatQ(item.sign_test_q_value)),
        cell(`${formatCount(item.case_higher_pair_count)} / ${formatCount(item.case_lower_pair_count)} / ${formatCount(item.tied_pair_count)}`),
      );
      body.append(row);
    }
    $("geo-result-count").textContent = `Showing ${formatCount(model.geoResults.length)} of ${formatCount(page.total_results)} reported rows`;
    $("geo-load-more").hidden = !page.has_more;
  }

  function renderGeoQuality() {
    const box = $("geo-quality");
    box.replaceChildren();
    const page = model.geoPage;
    if (!page) return;
    const matrix = page.matrix;
    const comparison = page.comparison;
    const rows = [
      ["Matrix dimensions", `${formatCount(matrix.feature_row_count)} feature rows × ${formatCount(matrix.sample_count)} samples`],
      ["Repeated feature labels", `${formatCount(matrix.duplicate_feature_label_count)} labels; ${formatCount(matrix.duplicate_feature_id_count_excluded)} IDs excluded from testing`],
      ["Unmatched selected samples", `${formatCount(comparison.case_sample_count_unmatched)} case · ${formatCount(comparison.reference_sample_count_unmatched)} reference`],
      ["Automatic sample exclusion", "None"],
      ["Date-like labels in reported rows", formatCount(page.summary.reported_date_like_feature_label_count)],
      ["Curated feature annotations", formatCount(page.summary.reported_curated_feature_count)],
    ];
    for (const [label, value] of rows) {
      const card = element("article", "geo-quality-item");
      card.append(element("span", "control-label", label), element("p", "lineage-meta", value));
      box.append(card);
    }
  }

  function renderGeoLimitations() {
    const box = $("geo-limitations");
    box.replaceChildren();
    for (const limitation of model.geoPage?.limitations || []) {
      box.append(element("p", "geo-limitation", limitation));
    }
    if (!box.childElementCount) box.append(element("p", "muted", "No limitation notes were supplied."));
  }

  function makeTokens(values) {
    const wrap = element("div", "id-list");
    for (const value of values || []) wrap.append(element("span", "id-token", value));
    return wrap;
  }

  function visibleHypotheses() {
    const query = $("path-search").value.trim().toLocaleLowerCase();
    return (model.report?.hypotheses || []).filter((item) => [item.variant_id, item.element_id, item.gene_id, item.state_id, item.mechanism].join(" ").toLocaleLowerCase().includes(query));
  }

  function renderHypotheses() {
    const list = $("hypothesis-list");
    const rows = visibleHypotheses();
    if (!rows.some((item) => item.hypothesis_id === model.hypothesis)) model.hypothesis = rows[0]?.hypothesis_id || null;
    list.replaceChildren();
    if (!rows.length) list.append(element("p", "empty-inline", "No hypothesis paths match this filter."));
    for (const item of rows) {
      const button = element("button", "hypothesis-card");
      button.type = "button";
      button.setAttribute("aria-pressed", String(item.hypothesis_id === model.hypothesis));
      button.setAttribute("aria-label", `Inspect path ${item.variant_id} to ${item.element_id} to ${item.gene_id} to ${item.state_id}`);
      const chain = element("span", "path-chain");
      [item.variant_id, item.element_id, item.gene_id, item.state_id].forEach((value, index) => {
        if (index) chain.append(element("span", "path-arrow", "→"));
        chain.append(element("span", "path-node", value));
      });
      const foot = element("span", "hypothesis-foot");
      foot.append(element("span", "", item.status || "Review status not set"));
      const scores = element("span", "score-chips");
      scores.append(element("span", "score-chip", `Support ${percent(item.support)}`), element("span", "score-chip", `Uncertainty ${percent(item.uncertainty)}`));
      foot.append(scores); button.append(chain, foot);
      button.addEventListener("click", () => {
        model.hypothesis = item.hypothesis_id;
        renderHypotheses(); renderDetails(); renderEdges(); renderEvidence(); renderLineage();
      });
      list.append(button);
    }
    renderDetails(); renderEdges(); renderEvidence(); renderLineage();
  }

  function selectedHypothesis() {
    return (model.report?.hypotheses || []).find((item) => item.hypothesis_id === model.hypothesis) || null;
  }

  function renderDetails() {
    const box = $("path-detail"); box.replaceChildren();
    const item = selectedHypothesis();
    if (!item) { box.append(element("p", "muted", "Select a hypothesis above.")); return; }
    box.append(element("p", "detail-title", `${item.variant_id} → ${item.element_id} → ${item.gene_id} → ${item.state_id}`));
    box.append(element("p", "muted", item.mechanism || "No mechanism label supplied."));
    for (const [title, values] of [["Missing or abstained evidence", item.missing_evidence], ["Measured negative or conflicting", item.negative_evidence]]) {
      const block = element("div", "detail-block");
      block.append(element("h3", "", `${title} · ${(values || []).length}`));
      block.append(values?.length ? makeTokens(values) : element("span", "muted", "None declared"));
      box.append(block);
    }
    const context = element("div", "detail-block");
    context.append(element("h3", "", "Context"), element("span", "id-token", item.context_key || "Not supplied"));
    box.append(context);
  }

  function activeEdges() {
    const selected = selectedHypothesis();
    return (model.report?.edges || []).filter((item) => !selected || item.hypothesis_id === selected.hypothesis_id);
  }

  function cell(value) { const item = document.createElement("td"); item.textContent = String(value); return item; }
  function emptyRow(span, text) { const row = document.createElement("tr"); const td = cell(text); td.colSpan = span; td.className = "empty-inline"; row.append(td); return row; }

  function renderEdges() {
    const body = $("edge-table"); const rows = activeEdges(); body.replaceChildren();
    $("edge-filter-label").textContent = selectedHypothesis() ? "Selected path" : "All hypotheses";
    if (!rows.length) { body.append(emptyRow(6, "No edge records are available.")); return; }
    for (const edge of rows) {
      const row = document.createElement("tr"); const relation = document.createElement("td");
      relation.append(element("span", "edge-type", edge.edge_type), element("span", "edge-endpoints", `${edge.source_id} → ${edge.target_id}`));
      row.append(relation, cell(percent(edge.support)), cell(percent(edge.uncertainty)), cell(percent(edge.context_fit)));
      const states = element("span", "state-counts");
      for (const [name, count] of Object.entries(edge.evidence_state_counts || {})) states.append(element("span", "state-count", `${name.replaceAll("_", " ")} ${count}`));
      if (!states.childElementCount) states.append(element("span", "muted", "No claims"));
      const stateCell = document.createElement("td"); stateCell.append(states); row.append(stateCell, cell((edge.source_ids || []).join(", ") || "No source IDs")); body.append(row);
    }
  }

  function visibleEvidence() {
    const ids = new Set(activeEdges().map((edge) => edge.edge_id));
    const query = $("evidence-search").value.trim().toLocaleLowerCase();
    return (model.report?.evidence || []).filter((item) => ids.has(item.edge_id) && [item.evidence_id, item.source_id, item.channel, item.state, item.tier, item.summary].join(" ").toLocaleLowerCase().includes(query));
  }

  function renderEvidence() {
    const list = $("evidence-list"); const rows = visibleEvidence(); list.replaceChildren();
    if (!rows.length) { list.append(element("p", "empty-inline", "No evidence claims match this path or filter.")); return; }
    for (const item of rows) {
      const card = element("article", "evidence-item"); const top = element("div", "evidence-top");
      top.append(element("span", "evidence-title", item.channel || "Evidence claim"), element("span", `evidence-state ${item.state || ""}`, item.state || "state unavailable"));
      card.append(top, element("p", "evidence-summary", item.summary || "No summary supplied."));
      const meta = element("div", "evidence-meta");
      meta.append(element("span", "", `Tier ${item.tier || "not set"}`), element("span", "", `Score ${item.score == null ? "—" : percent(item.score)}`), element("span", "", `Confidence ${percent(item.confidence)}`), element("span", "", `Source ${item.source_id || "not declared"}`));
      card.append(meta, element("span", "evidence-id", item.evidence_id)); list.append(card);
    }
  }

  function renderQueue() {
    const list = $("review-queue"); const rows = model.report?.review_queue || []; list.replaceChildren();
    if (!rows.length) { list.append(element("p", "empty-inline", "No triage items were emitted.")); return; }
    for (const item of rows.slice(0, 20)) {
      const card = element("article", "queue-item"); const top = element("div", "queue-top");
      top.append(element("span", "queue-target", `${item.item_type}: ${item.target_id}`), element("span", "priority-tag", `Priority band ${item.priority}`));
      card.append(top, element("p", "queue-reasons", (item.reasons || []).join(" · ") || "Review reason not supplied.")); list.append(card);
    }
    if (rows.length > 20) list.append(element("p", "muted", `${rows.length - 20} additional items in this review projection.`));
  }

  function renderLineage() {
    const selected = selectedHypothesis(); const edgeIds = new Set(activeEdges().map((edge) => edge.edge_id));
    const sources = (model.report?.provenance || []).filter((item) => !selected || (item.edge_ids || []).some((id) => edgeIds.has(id)));
    const sourceList = $("provenance-list"); sourceList.replaceChildren();
    if (!sources.length) sourceList.append(element("p", "empty-inline", "No source lineage was declared for this route."));
    for (const item of sources) {
      const card = element("article", "provenance-item");
      card.append(element("span", "evidence-title", item.source_id), element("p", "lineage-meta", `${item.edge_ids.length} edges · ${item.evidence_ids.length} claims · tiers ${(item.tiers || []).join(", ") || "not set"}`));
      sourceList.append(card);
    }
    const alternatives = (model.report?.alternatives || []).filter((item) => !selected || item.hypothesis_id === selected.hypothesis_id);
    const altList = $("alternatives-list"); altList.replaceChildren();
    if (!alternatives.length) altList.append(element("p", "empty-inline", "No alternative explanations were declared."));
    for (const item of alternatives) {
      const card = element("article", "alternative-item");
      card.append(element("span", "evidence-title", item.label), element("p", "lineage-meta", `${item.state} · ${item.edge_ids.length} linked edges · ${item.evidence_ids.length} linked claims`));
      altList.append(card);
    }
  }

  function renderDeltas() {
    const section = $("delta-section"); const body = $("delta-table"); const deltas = model.report?.deltas || [];
    section.hidden = !model.report?.baseline_run_id; body.replaceChildren();
    if (!model.report?.baseline_run_id) return;
    if (!deltas.length) { body.append(emptyRow(5, "No per-item changes were emitted for this baseline.")); return; }
    for (const item of deltas) {
      const row = document.createElement("tr");
      row.append(cell(`${item.item_type} · ${item.item_id}`), cell(item.dimension), cell(JSON.stringify(item.before)), cell(JSON.stringify(item.after)), cell(item.delta == null ? item.direction : `${item.direction} · ${item.delta}`));
      body.append(row);
    }
  }

  function renderWorkspace() {
    const report = model.report; const run = model.runs.find((item) => item.run_id === model.selected);
    if (!report || !run) return;
    $("run-case-label").textContent = report.case_id || "Selected case";
    $("run-title").textContent = run.run_id;
    $("run-subtitle").textContent = `${time(run.created_at)} · ${run.status} · ${run.event_count} events`;
    $("review-state").textContent = report.state || "review unavailable";
    $("review-state").className = `state-pill${report.state === "ready_for_review" ? " ready" : ""}`;
    $("review-address").textContent = report.content_address || "Address unavailable";
    $("metric-hypotheses").textContent = String(report.hypotheses?.length || 0);
    $("metric-evidence").textContent = String(report.evidence?.length || 0);
    $("metric-queue").textContent = String(report.review_queue?.length || 0);
    const passed = run.integrity?.accepted === true && report.run_integrity?.accepted !== false;
    $("metric-integrity").textContent = passed ? "Accepted" : "Review";
    $("metric-integrity-detail").textContent = passed ? "Replay checks passed" : "See integrity warnings";
    if (report.warnings?.length) notice(report.warnings.join(" "));
    renderHypotheses(); renderQueue(); renderDeltas(); exportHref();
  }

  $("refresh-button").addEventListener("click", () => Promise.all([loadRuns(), loadGeoAnalyses()]));
  $("run-search").addEventListener("input", renderRuns);
  $("path-search").addEventListener("input", renderHypotheses);
  $("evidence-search").addEventListener("input", renderEvidence);
  $("load-more").addEventListener("click", () => loadRuns(true));
  $("baseline-select").addEventListener("change", (event) => {
    model.baseline = event.currentTarget.value;
    if (model.activeView === "case" && model.selected) openRun(model.selected);
  });
  $("geo-load-more-analyses").addEventListener("click", () => loadGeoAnalyses(true));
  $("geo-load-more").addEventListener("click", () => {
    if (model.selectedGeo) openGeoAnalysis(model.selectedGeo, { append: true });
  });
  $("markdown-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  async function initializeWorkspace() {
    const initialSelectionRequest = model.selectionRequest || 0;
    await Promise.all([loadRuns(false, true), loadGeoAnalyses(false, true)]);
    if (model.selectionRequest !== initialSelectionRequest || model.activeView !== "empty") return;
    if (model.runs.length) {
      await openRun(model.runs[0].run_id);
    } else if (model.geoAnalyses.length) {
      await openGeoAnalysis(model.geoAnalyses[0].analysis_id);
    } else {
      showEmpty("No saved research records", "Case runs and aggregate GEO reports appear here after they are saved to the local workspace.");
    }
  }

  initializeWorkspace();
})();
