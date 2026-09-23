"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const model = {
    runs: [], total: 0, selected: null, baseline: "", report: null, hypothesis: null,
    geoAnalyses: [], geoTotal: 0, selectedGeo: null, geoPage: null, geoResults: [], geoReviewSummary: null, geoReviewRequest: 0, geoReviewViewRequest: 0,
    geoPreflights: [], geoPreflightTotal: 0, geoPreflightHasMore: false, selectedGeoPreflight: null, geoPreflightReport: null, geoPreflightListRequest: 0, geoPreflightRequest: 0, geoPreflightFilterTimer: null,
    geoPreflightFilters: { accession: "", kind: "" },
    geoExpressionAnalyses: [], geoExpressionTotal: 0, selectedGeoExpression: null, geoExpressionPage: null, geoExpressionResults: [],
    geoExpressionCompareIds: [], geoExpressionConsistency: null, geoExpressionConsistencyRequest: 0,
    geoExpressionConsistencyRecords: [], geoExpressionConsistencyTotal: 0, geoExpressionConsistencyHasMore: false, selectedGeoExpressionConsistency: null, geoExpressionConsistencyListRequest: 0,
    geoFilters: { feature_contains: "", effect_direction: "", min_abs_median_effect: "", fdr_significant: false, sign_test_fdr_significant: false },
    geoCompareIds: [], geoConsistency: null, geoConsistencyRecords: [], geoConsistencyTotal: 0, geoConsistencyHasMore: false,
    selectedGeoConsistency: null, geoConsistencyListRequest: 0, geoConsistencyFilterTimer: null,
    geoConsistencyFilters: { feature_contains: "", direction_consistency: "", fdr_direction_consistency: "", sign_test_direction_consistency: "" },
    geoSensitivity: null, geoSensitivityRecords: [], geoSensitivityTotal: 0, geoSensitivityHasMore: false,
    selectedGeoSensitivity: null, geoSensitivityListRequest: 0, geoSensitivityRequest: 0, geoSensitivityFilterTimer: null,
    geoSensitivityFilters: { feature_contains: "", direction_sensitivity: "", fdr_sensitivity: "", sign_test_fdr_sensitivity: "" },
    geoExpressionConsistencyFilters: { feature_contains: "", direction_consistency: "", fdr_direction_consistency: "" }, geoExpressionConsistencyFilterTimer: null,
    sequenceAnalyses: [], sequenceTotal: 0, sequenceHasMore: false, selectedSequence: null, sequenceReport: null, sequenceChanges: null, sequenceAnalysisChangesRequest: 0, sequenceAnalysisFilterTimer: null,
    sequenceBatches: [], sequenceBatchTotal: 0, sequenceBatchHasMore: false, selectedSequenceBatch: null, sequenceBatchReport: null, sequenceBatchChanges: null, sequenceBatchChangesRequest: 0, sequenceBatchFilterTimer: null,
    sequenceComparisons: [], sequenceComparisonTotal: 0, sequenceComparisonHasMore: false, selectedSequenceComparison: null, sequenceComparisonReport: null, sequenceComparisonChanges: null, sequenceComparisonListRequest: 0, sequenceComparisonRequest: 0, sequenceComparisonFilterTimer: null,
    sequenceReviewSummary: null, sequenceReviewVerification: null, sequenceReviewMotifs: null, sequenceReviewRequest: 0, sequenceReviewMotifRequest: 0, sequenceReviewFilterTimer: null,
    moduleAssessments: [], moduleTotal: 0, moduleHasMore: false, selectedModule: null, moduleDetail: null, moduleListRequest: 0, moduleDetailRequest: 0, moduleFilterTimer: null,
    moduleTriageItems: [], moduleTriageTotal: 0, moduleTriageHasMore: false, moduleTriageListRequest: 0, moduleTriageFilterTimer: null, moduleTriageByModule: new Map(), selectedModuleTriage: null,
    moduleExecution: null, moduleExecutionRequest: 0, moduleExecutionPlan: null, moduleExecutionPlanRequest: 0, modulePortfolio: null, modulePortfolioRequest: 0,
    moduleWorkbenchSummary: null, moduleExecutionSummary: null, moduleExecutionPreview: null, moduleWorkbenchSummaryRequest: 0, moduleExecutionPreviewRequest: 0,
    moduleFilters: { q: "", risk: "", depth_band: "" }, moduleTriageFilters: { risk: "", reason: "" },
    activeView: "empty", runsLoaded: false, geoLoaded: false, sequenceLoaded: false,
    selectionRequest: 0, runListRequest: 0, geoListRequest: 0, geoExpressionListRequest: 0, sequenceListRequest: 0, sequenceBatchListRequest: 0, geoFilterTimer: null, geoExpressionFilterTimer: null, geoConsistencyRequest: 0,
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

  async function postJson(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      credentials: "same-origin",
    });
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
      renderGeoCompareControls();
      return;
    }
    for (const item of model.geoAnalyses) {
      const choice = element("div", "geo-analysis-choice");
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.analysis_id === model.selectedGeo));
      button.setAttribute("aria-label", `Open aggregate GEO contrast ${item.accession}, ${item.matched_pair_count} matched pairs`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.accession), element("span", "run-status", "GEO"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.analysis_id, 28)), element("span", "", `${item.matched_pair_count} pairs · ${item.fdr_significant_feature_count} q-significant · ${consistencyText(item.normalization || "normalization unavailable")}`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoAnalysis(item.analysis_id));
      choice.append(button);
      list.append(choice);
    }
    renderGeoCompareControls();
  }

  function renderGeoPreflights() {
    const list = $("geo-preflight-list");
    list.replaceChildren();
    $("geo-preflight-count").textContent = String(model.geoPreflightTotal);
    const filterText = [model.geoPreflightFilters.accession && `accession ${model.geoPreflightFilters.accession}`, model.geoPreflightFilters.kind && consistencyText(model.geoPreflightFilters.kind)].filter(Boolean).join(" · ");
    $("geo-preflight-list-summary").textContent = `Showing ${model.geoPreflights.length} of ${model.geoPreflightTotal} saved preparation preflights${filterText ? ` · ${filterText}` : ""}.`;
    $("geo-preflight-load-more").hidden = !model.geoPreflightHasMore;
    if (!model.geoPreflights.length) {
      list.append(element("p", "empty-inline", "No saved GEO preflights yet."));
      return;
    }
    for (const item of model.geoPreflights) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.preflight_id === model.selectedGeoPreflight));
      button.setAttribute("aria-label", `Open ${item.kind || "GEO"} preflight for ${item.accession}`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.accession), element("span", "run-status", "Preflight"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", consistencyText(item.kind)), element("span", "", `${formatCount(item.sample_count)} samples · ${formatCount(item.feature_count)} features`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoPreflight(item.preflight_id));
      list.append(button);
    }
  }

  function renderGeoExpressionAnalyses() {
    const list = $("geo-expression-analysis-list");
    list.replaceChildren();
    $("geo-expression-count").textContent = String(model.geoExpressionTotal);
    $("geo-expression-list-summary").textContent = `Showing ${model.geoExpressionAnalyses.length} of ${model.geoExpressionTotal} saved expression contrasts.`;
    if (!model.geoExpressionAnalyses.length) {
      list.append(element("p", "empty-inline", "No saved GEO expression contrasts yet."));
      renderGeoExpressionCompareControls();
      return;
    }
    for (const item of model.geoExpressionAnalyses) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.analysis_id === model.selectedGeoExpression));
      button.setAttribute("aria-label", `Open GEO expression contrast ${item.accession}, ${item.fdr_significant_feature_count} FDR significant features`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.accession), element("span", "run-status", "Expression"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.analysis_id, 28)), element("span", "", `${item.case_sample_count}/${item.reference_sample_count} samples · ${item.fdr_significant_feature_count} q-significant`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoExpressionAnalysis(item.analysis_id));
      list.append(button);
    }
    renderGeoExpressionCompareControls();
  }

  function expressionConsistencyFeatureIds() {
    return [...new Set($("geo-expression-consistency-features").value.split(/[\s,]+/).map((value) => value.trim()).filter(Boolean))];
  }

  function updateGeoExpressionCompareControls() {
    const checked = [...document.querySelectorAll("#geo-expression-compare-selection input[type=checkbox]:checked")];
    model.geoExpressionCompareIds = checked.map((input) => input.value);
    const features = expressionConsistencyFeatureIds();
    const button = $("geo-expression-compare-button");
    button.disabled = model.geoExpressionCompareIds.length < 2 || features.length < 1;
    if (model.geoExpressionCompareIds.length < 2) $("geo-expression-compare-status").textContent = "Choose at least two saved expression studies.";
    else if (!features.length) $("geo-expression-compare-status").textContent = "Enter one or more exact source feature IDs.";
    else $("geo-expression-compare-status").textContent = `${model.geoExpressionCompareIds.length} studies · ${features.length} feature IDs ready.`;
  }

  function renderGeoExpressionCompareControls() {
    const box = $("geo-expression-compare-selection");
    box.replaceChildren();
    const available = new Set(model.geoExpressionAnalyses.map((item) => item.analysis_id));
    model.geoExpressionCompareIds = model.geoExpressionCompareIds.filter((analysisId) => available.has(analysisId));
    if (!model.geoExpressionAnalyses.length) {
      box.append(element("p", "empty-inline", "Saved expression contrasts will appear here when available."));
      updateGeoExpressionCompareControls();
      return;
    }
    for (const item of model.geoExpressionAnalyses) {
      const label = element("label", "geo-compare-option");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = item.analysis_id;
      checkbox.checked = model.geoExpressionCompareIds.includes(item.analysis_id);
      checkbox.setAttribute("aria-label", `Include ${item.accession} in expression comparison`);
      checkbox.addEventListener("change", updateGeoExpressionCompareControls);
      label.append(checkbox, element("span", "geo-compare-label", `${item.accession} · ${formatCount(item.case_sample_count)} / ${formatCount(item.reference_sample_count)} samples`));
      box.append(label);
    }
    updateGeoExpressionCompareControls();
  }

  function renderGeoExpressionConsistencyRecords() {
    const list = $("geo-expression-consistency-list");
    list.replaceChildren();
    $("geo-expression-consistency-count").textContent = String(model.geoExpressionConsistencyTotal);
    $("geo-expression-consistency-list-summary").textContent = `Showing ${model.geoExpressionConsistencyRecords.length} of ${model.geoExpressionConsistencyTotal} saved comparisons.`;
    const loadMore = $("geo-expression-consistency-list-load-more");
    loadMore.hidden = !model.geoExpressionConsistencyHasMore;
    if (!model.geoExpressionConsistencyRecords.length) {
      list.append(element("p", "empty-inline", "No saved expression comparisons yet."));
      return;
    }
    for (const item of model.geoExpressionConsistencyRecords) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.comparison_id === model.selectedGeoExpressionConsistency));
      button.setAttribute("aria-label", `Open expression comparison of ${item.study_count} studies and ${item.feature_count} features`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", (item.accessions || []).join(" · ")), element("span", "run-status", "Comparison"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.comparison_id, 28)), element("span", "", `${item.feature_count} features · ${item.concordant_feature_count} concordant · ${item.discordant_feature_count} discordant`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoExpressionConsistency(item.comparison_id));
      list.append(button);
    }
  }

  function renderSequenceAnalyses() {
    const list = $("sequence-analysis-list");
    list.replaceChildren();
    $("sequence-count").textContent = String(model.sequenceTotal);
    $("sequence-list-summary").textContent = `Showing ${model.sequenceAnalyses.length} of ${model.sequenceTotal} saved sequence analyses.`;
    $("sequence-analysis-load-more").hidden = !model.sequenceHasMore;
    if (!model.sequenceAnalyses.length) {
      list.append(element("p", "empty-inline", "No saved sequence analyses yet."));
      return;
    }
    for (const item of model.sequenceAnalyses) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.analysis_id === model.selectedSequence));
      button.setAttribute("aria-label", `Open sequence analysis ${item.source_id}, ${item.analysis_state}`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.source_id), element("span", "run-status", item.analysis_state));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.analysis_id, 28)), element("span", "", `${item.variant_count} variants · ${item.created_motif_count + item.disrupted_motif_count} motif changes`));
      button.append(top, meta);
      button.addEventListener("click", () => openSequenceAnalysis(item.analysis_id));
      list.append(button);
    }
  }

  function renderSequenceBatches() {
    const list = $("sequence-batch-list");
    list.replaceChildren();
    $("sequence-batch-count").textContent = String(model.sequenceBatchTotal);
    $("sequence-batch-list-summary").textContent = `Showing ${model.sequenceBatches.length} of ${model.sequenceBatchTotal} saved sequence batches.`;
    $("sequence-batch-load-more").hidden = !model.sequenceBatchHasMore;
    if (!model.sequenceBatches.length) {
      list.append(element("p", "empty-inline", "No saved sequence batches yet."));
      return;
    }
    for (const item of model.sequenceBatches) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.batch_id === model.selectedSequenceBatch));
      button.setAttribute("aria-label", `Open sequence batch ${item.source_id}, ${item.analysis_count} analyses`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.source_id), element("span", "run-status", `${item.supported_count}/${item.analysis_count}`));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.batch_id, 28)), element("span", "", `${item.created_change_count + item.disrupted_change_count} motif rows`));
      button.append(top, meta);
      button.addEventListener("click", () => openSequenceBatch(item.batch_id));
      list.append(button);
    }
  }

  function renderSequenceComparisons() {
    const list = $("sequence-comparison-list");
    list.replaceChildren();
    $("sequence-comparison-count").textContent = String(model.sequenceComparisonTotal);
    $("sequence-comparison-list-summary").textContent = `Showing ${model.sequenceComparisons.length} of ${model.sequenceComparisonTotal} saved sequence comparisons.`;
    $("sequence-comparison-list-load-more").hidden = !model.sequenceComparisonHasMore;
    if (!model.sequenceComparisons.length) {
      list.append(element("p", "empty-inline", "No saved sequence comparisons yet."));
      return;
    }
    for (const item of model.sequenceComparisons) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.comparison_id === model.selectedSequenceComparison));
      button.setAttribute("aria-label", `Open sequence comparison with ${item.change_count} motif changes`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", "Batch comparison"), element("span", "run-status", `${item.left_analysis_count} vs ${item.right_analysis_count}`));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.comparison_id, 28)), element("span", "", `${item.change_count} prevalence deltas`));
      button.append(top, meta);
      button.addEventListener("click", () => openSequenceComparison(item.comparison_id));
      list.append(button);
    }
  }

  function renderModuleWorkbenchOverview() {
    const summary = model.moduleWorkbenchSummary;
    const execution = model.moduleExecutionSummary;
    const accepted = summary?.accepted === true;
    $("module-workbench-overview-state").textContent = summary ? (accepted ? "Accepted" : "Review") : "—";
    $("module-workbench-overview-state").className = `quiet-tag${accepted ? " ready" : ""}`;
    $("module-workbench-overall-score").textContent = summary ? percent(summary.overall_score) : "—";
    $("module-workbench-depth-percent").textContent = summary ? `${Number(summary.depth_percent).toFixed(1)}%` : "—";
    $("module-workbench-high-risk-count").textContent = summary ? formatCount(summary.high_risk_count) : "—";
    $("module-workbench-blocked-count").textContent = summary ? formatCount(summary.blocked_count) : "—";
    $("module-workbench-overview-summary").textContent = summary
      ? `${formatCount(summary.module_count)} modules · ${formatCount(summary.task_count)} planned tasks · ${formatCount(summary.family_count)} families · ${shortened(summary.content_address, 50)}`
      : "Verifying addressed workbench summary…";
    const executionAccepted = execution?.accepted === true;
    $("module-execution-overview-state").textContent = execution ? (executionAccepted ? "Accepted" : "Review") : "—";
    $("module-execution-overview-state").className = `quiet-tag${executionAccepted ? " ready" : ""}`;
    $("module-execution-task-count").textContent = execution ? formatCount(execution.task_count) : "—";
    $("module-execution-completion").textContent = execution ? `${Number(execution.completion_percent).toFixed(1)}%` : "—";
    $("module-execution-evidence").textContent = execution ? `${Number(execution.evidence_coverage_percent).toFixed(1)}%` : "—";
    $("module-execution-event-count").textContent = execution ? formatCount(execution.event_count) : "—";
    $("module-execution-overview-summary").textContent = execution
      ? `${formatCount(execution.completed_count)} completed · ${formatCount(execution.in_progress_count)} in progress · ${formatCount(execution.blocked_count)} blocked · ${shortened(execution.content_address, 50)}`
      : "Verifying durable execution state…";
  }

  async function loadModuleWorkbenchOverview() {
    const request = model.moduleWorkbenchSummaryRequest = (model.moduleWorkbenchSummaryRequest || 0) + 1;
    try {
      const [summary, execution] = await Promise.all([
        getJson("/v1/module-workbench?format=summary"),
        getJson("/v1/module-workbench/execution?include_items=false&include_events=false"),
      ]);
      if (request !== model.moduleWorkbenchSummaryRequest) return;
      if (typeof summary.content_address !== "string" || typeof summary.accepted !== "boolean" || !Number.isFinite(summary.overall_score) || !Number.isFinite(summary.depth_percent) || !Number.isSafeInteger(summary.module_count) || !Number.isSafeInteger(summary.task_count) || !Number.isSafeInteger(summary.family_count) || !Number.isSafeInteger(summary.high_risk_count) || !Number.isSafeInteger(summary.blocked_count)) {
        throw new Error("The local API returned an invalid module workbench summary.");
      }
      if (execution.version !== "module-workbench-execution-v1" || typeof execution.content_address !== "string" || typeof execution.portfolio_address !== "string" || typeof execution.accepted !== "boolean" || !Number.isSafeInteger(execution.task_count) || !Number.isSafeInteger(execution.event_count) || !Number.isSafeInteger(execution.completed_count) || !Number.isSafeInteger(execution.in_progress_count) || !Number.isSafeInteger(execution.blocked_count) || !Number.isFinite(execution.completion_percent) || !Number.isFinite(execution.evidence_coverage_percent)) {
        throw new Error("The local API returned an invalid durable execution summary.");
      }
      model.moduleWorkbenchSummary = summary;
      model.moduleExecutionSummary = execution;
      renderModuleWorkbenchOverview();
    } catch (error) {
      if (request !== model.moduleWorkbenchSummaryRequest) return;
      model.moduleWorkbenchSummary = null;
      model.moduleExecutionSummary = null;
      renderModuleWorkbenchOverview();
      notice(error.message, true);
    }
  }

  function renderModuleExecutionPreview() {
    const preview = model.moduleExecutionPreview;
    const box = $("module-execution-preview-summary");
    box.replaceChildren();
    if (!preview) {
      $("module-execution-preview-state").textContent = "Read-only";
      $("module-execution-preview-text").textContent = "Change the bounds to inspect a dependency-aware wave without changing durable execution state.";
      return;
    }
    const summary = preview.items?.[0] || {};
    const comparison = preview.comparison || {};
    const safe = summary.dependency_safe === true;
    $("module-execution-preview-state").textContent = safe ? "Safe preview" : "Attention";
    $("module-execution-preview-state").className = `quiet-tag${safe ? " ready" : ""}`;
    $("module-execution-preview-text").textContent = `${formatCount(summary.node_count)} selected nodes · ${formatCount(summary.dependency_edge_count)} prerequisite edges · ${formatCount(comparison.added_task_count)} added / ${formatCount(comparison.removed_task_count)} removed versus durable wave · durable ledger unchanged.`;
    const rows = [
      ["Selection", `${formatCount(preview.selection.capacity)} capacity · ${formatCount(preview.selection.max_tasks_per_module)} per module`],
      ["Plan depth", `${formatCount(summary.max_depth)} · ${safe ? "dependency-safe" : "requires prerequisite review"}`],
      ["Task delta", `${formatCount(comparison.added_task_count)} added · ${formatCount(comparison.removed_task_count)} removed · ${formatCount(comparison.shared_task_count)} shared`],
      ["Edge delta", `${formatCount(comparison.added_dependency_edge_count)} added · ${formatCount(comparison.removed_dependency_edge_count)} removed`],
      ["Portfolio", shortened(preview.plan_summary?.portfolio_address || "", 46)],
      ["Preview address", shortened(preview.preview_address, 46)],
    ];
    for (const [label, value] of rows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", displayValue(value)));
      box.append(block);
    }
  }

  async function previewModuleExecutionPlan() {
    const capacity = Number($("module-execution-preview-capacity").value);
    const moduleLimit = Number($("module-execution-preview-module-limit").value);
    if (!Number.isSafeInteger(capacity) || capacity < 1 || !Number.isSafeInteger(moduleLimit) || moduleLimit < 1) {
      notice("Preview capacity and per-module limit must be positive whole numbers.", true);
      return;
    }
    const request = model.moduleExecutionPreviewRequest = (model.moduleExecutionPreviewRequest || 0) + 1;
    const button = $("module-execution-preview-button");
    button.disabled = true;
    try {
      const params = new URLSearchParams({ resource: "summary", capacity: String(capacity), max_tasks_per_module: String(moduleLimit), limit: "1" });
      const preview = await getJson(`/v1/module-workbench/execution/plan/preview/query?${params.toString()}`);
      if (request !== model.moduleExecutionPreviewRequest) return;
      if (preview.mode !== "preview" || typeof preview.preview_address !== "string" || typeof preview.plan_address !== "string" || !preview.selection || preview.selection.capacity !== capacity || preview.selection.max_tasks_per_module !== moduleLimit || !Array.isArray(preview.items) || preview.items.length !== 1 || preview.items[0].content_address !== preview.plan_address || !preview.plan_summary || preview.plan_summary.content_address !== preview.plan_address || !preview.comparison || preview.comparison.candidate_plan_address !== preview.plan_address || typeof preview.comparison.content_address !== "string") {
        throw new Error("The local API returned an invalid planning preview.");
      }
      model.moduleExecutionPreview = preview;
      renderModuleExecutionPreview();
      notice("Read-only execution planning preview updated.");
    } catch (error) {
      if (request !== model.moduleExecutionPreviewRequest) return;
      model.moduleExecutionPreview = null;
      renderModuleExecutionPreview();
      notice(`The planning preview could not be verified. ${error.message}`, true);
    } finally {
      if (request === model.moduleExecutionPreviewRequest) button.disabled = false;
    }
  }

  function displayValue(value) {
    if (value === undefined || value === null || value === "") return "—";
    if (Array.isArray(value)) return value.length ? value.join(" · ") : "—";
    if (typeof value === "object") {
      try { return JSON.stringify(value); } catch { return "—"; }
    }
    return String(value);
  }

  function renderModuleAssessments() {
    const list = $("module-workbench-list");
    list.replaceChildren();
    $("module-count").textContent = formatCount(model.moduleTotal);
    const filters = [model.moduleFilters.q && `search “${model.moduleFilters.q}”`, model.moduleFilters.risk && `risk ${model.moduleFilters.risk}`, model.moduleFilters.depth_band && `depth ${model.moduleFilters.depth_band}`].filter(Boolean);
    $("module-list-summary").textContent = `Showing ${model.moduleAssessments.length} of ${formatCount(model.moduleTotal)} modules · ${filters.length ? filters.join(" · ") : "static workbench signals"}.`;
    $("module-workbench-load-more").hidden = !model.moduleHasMore;
    if (!model.moduleAssessments.length) {
      list.append(element("p", "empty-inline", "No module workbench records yet."));
      return;
    }
    for (const item of model.moduleAssessments) {
      const moduleId = item.module_id || "Unknown module";
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(moduleId === model.selectedModule));
      button.setAttribute("aria-label", `Open module ${moduleId}, ${item.depth_band || "unrated"} depth, ${item.risk || "unknown"} risk`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", shortened(moduleId, 34)), element("span", "run-status", item.depth_band || "unrated"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", `${item.risk || "risk unavailable"} · ${percent(item.score)}`), element("span", "", `${formatCount(item.nonblank_lines)} lines · ${formatCount(item.fan_in)} in / ${formatCount(item.fan_out)} out`));
      button.append(top, meta);
      button.addEventListener("click", () => openModuleWorkbenchDetail(moduleId));
      list.append(button);
    }
  }

  function moduleAssessmentQuery(offset) {
    const params = new URLSearchParams({ resource: "modules", limit: String(pageSize), offset: String(offset) });
    for (const [key, value] of Object.entries(model.moduleFilters)) if (value) params.set(key === "q" ? "q" : key, value);
    return params.toString();
  }

  async function loadModuleAssessments(append = false) {
    const request = model.moduleListRequest = (model.moduleListRequest || 0) + 1;
    const offset = append ? model.moduleAssessments.length : 0;
    const button = $("module-workbench-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/module-workbench/query?${moduleAssessmentQuery(offset)}`);
      if (request !== model.moduleListRequest) return;
      if (!Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.offset !== offset || page.limit !== pageSize || page.accepted !== true || typeof page.workbench_address !== "string") {
        throw new Error("The local API returned an invalid module workbench catalog.");
      }
      model.moduleTotal = page.total;
      model.moduleAssessments = append ? model.moduleAssessments.concat(page.items) : page.items;
      model.moduleHasMore = model.moduleAssessments.length < page.total;
      renderModuleAssessments();
    } catch (error) {
      if (request !== model.moduleListRequest) return;
      if (!append) {
        model.moduleHasMore = false;
        button.hidden = true;
        $("module-workbench-list").replaceChildren(element("p", "empty-inline", "Module workbench could not be loaded."));
        $("module-list-summary").textContent = "The local API could not verify a module workbench catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.moduleListRequest) button.disabled = false;
    }
  }

  function reloadModuleAssessments() {
    if (model.moduleFilterTimer !== null) clearTimeout(model.moduleFilterTimer);
    model.moduleFilterTimer = setTimeout(() => loadModuleAssessments(false), 180);
  }

  function triageReasonLabel(value) {
    return String(value || "").replaceAll("_", " ");
  }

  function renderModuleTriage() {
    const list = $("module-triage-list");
    list.replaceChildren();
    $("module-triage-count").textContent = formatCount(model.moduleTriageTotal);
    const filters = [model.moduleTriageFilters.risk && `risk ${model.moduleTriageFilters.risk}`, model.moduleTriageFilters.reason && triageReasonLabel(model.moduleTriageFilters.reason)].filter(Boolean);
    $("module-triage-list-summary").textContent = `Showing ${model.moduleTriageItems.length} of ${formatCount(model.moduleTriageTotal)} priority modules${filters.length ? ` · ${filters.join(" · ")}` : ""}.`;
    $("module-triage-load-more").hidden = !model.moduleTriageHasMore;
    if (!model.moduleTriageItems.length) {
      list.append(element("p", "empty-inline", "No priority modules match these filters."));
      return;
    }
    for (const item of model.moduleTriageItems) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.module_id === model.selectedModule));
      button.setAttribute("aria-label", `Open priority module ${item.module_id}, rank ${item.rank}, ${item.risk} risk`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", shortened(item.module_id, 34)), element("span", "run-status", `#${item.rank}`));
      const meta = element("span", "run-meta");
      const reasons = (item.reasons || []).map(triageReasonLabel).join(" · ") || "no reason code";
      meta.append(element("span", "run-id", `${percent(item.priority_score)} priority`), element("span", "", `${item.risk} · ${shortened(reasons, 40)}`));
      button.append(top, meta);
      button.addEventListener("click", () => {
        model.selectedModuleTriage = item;
        openModuleWorkbenchDetail(item.module_id);
      });
      list.append(button);
    }
  }

  function moduleTriageQuery(offset) {
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset) });
    for (const [key, value] of Object.entries(model.moduleTriageFilters)) if (value) params.set(key, value);
    return params.toString();
  }

  async function loadModuleTriage(append = false) {
    const request = model.moduleTriageListRequest = (model.moduleTriageListRequest || 0) + 1;
    const offset = append ? model.moduleTriageItems.length : 0;
    const button = $("module-triage-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/module-workbench/triage/query?${moduleTriageQuery(offset)}`);
      if (request !== model.moduleTriageListRequest) return;
      if (!Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.offset !== offset || page.limit !== pageSize || page.accepted !== true || typeof page.triage_address !== "string") {
        throw new Error("The local API returned an invalid module priority queue.");
      }
      model.moduleTriageTotal = page.total;
      model.moduleTriageItems = append ? model.moduleTriageItems.concat(page.items) : page.items;
      model.moduleTriageHasMore = model.moduleTriageItems.length < page.total;
      if (!append) model.moduleTriageByModule = new Map();
      for (const item of page.items) model.moduleTriageByModule.set(item.module_id, item);
      renderModuleTriage();
      if (model.selectedModule) renderModuleWorkbenchDetail();
    } catch (error) {
      if (request !== model.moduleTriageListRequest) return;
      if (!append) {
        model.moduleTriageHasMore = false;
        button.hidden = true;
        $("module-triage-list").replaceChildren(element("p", "empty-inline", "The priority queue could not be verified."));
        $("module-triage-list-summary").textContent = "The local API could not verify a module priority queue.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.moduleTriageListRequest) button.disabled = false;
    }
  }

  function reloadModuleTriage() {
    if (model.moduleTriageFilterTimer !== null) clearTimeout(model.moduleTriageFilterTimer);
    model.moduleTriageFilterTimer = setTimeout(() => loadModuleTriage(false), 180);
  }

  const executionActionsByState = Object.freeze({
    planned: ["block", "skip", "supersede"],
    ready: ["start", "block", "skip", "supersede"],
    in_progress: ["complete", "block", "skip", "supersede"],
    blocked: ["unblock", "skip", "supersede"],
    completed: ["reopen"],
    skipped: ["reopen"],
    superseded: [],
  });

  function validateModuleExecution(page, moduleId) {
    if (page.version !== "module-workbench-execution-v1" || page.accepted !== true || typeof page.ledger_address !== "string" || !Array.isArray(page.items) || page.offset !== 0 || page.limit !== 50 || page.query?.module_id !== moduleId || !Number.isSafeInteger(page.total)) {
      throw new Error("The local API returned an invalid module execution projection.");
    }
    return page;
  }

  async function loadModuleExecution(moduleId) {
    const request = model.moduleExecutionRequest = (model.moduleExecutionRequest || 0) + 1;
    const [rawPage, rawEvents] = await Promise.all([
      getJson(`/v1/module-workbench/execution/query?resource=items&module_id=${encodeURIComponent(moduleId)}&limit=50&offset=0`),
      getJson(`/v1/module-workbench/execution/query?resource=events&module_id=${encodeURIComponent(moduleId)}&limit=512&offset=0`),
    ]);
    const page = validateModuleExecution(rawPage, moduleId);
    if (rawEvents.version !== "module-workbench-execution-v1" || rawEvents.accepted !== true || typeof rawEvents.ledger_address !== "string" || rawEvents.ledger_address !== page.ledger_address || !Array.isArray(rawEvents.items) || rawEvents.offset !== 0 || rawEvents.limit !== 512 || rawEvents.query?.resource !== "events" || rawEvents.query?.module_id !== moduleId || !Number.isSafeInteger(rawEvents.total)) {
      throw new Error("The local API returned an invalid module execution history projection.");
    }
    if (request !== model.moduleExecutionRequest || model.selectedModule !== moduleId) return null;
    return { ...page, events: rawEvents.items, event_total: rawEvents.total };
  }

  async function loadModulePortfolio(moduleId) {
    const request = model.modulePortfolioRequest = (model.modulePortfolioRequest || 0) + 1;
    const page = await getJson(`/v1/module-workbench/portfolio/query?module_id=${encodeURIComponent(moduleId)}&limit=50&offset=0`);
    if (page.version !== "module-workbench-portfolio-v1" || page.accepted !== true || typeof page.portfolio_address !== "string" || !Array.isArray(page.items) || page.offset !== 0 || page.limit !== 50 || page.query?.module_id !== moduleId || !Number.isSafeInteger(page.total) || !page.portfolio_summary || page.portfolio_summary.content_address !== page.portfolio_address) {
      throw new Error("The local API returned an invalid module portfolio projection.");
    }
    if (request !== model.modulePortfolioRequest || model.selectedModule !== moduleId) return null;
    return page;
  }

  async function loadModuleExecutionPlan(moduleId) {
    const request = model.moduleExecutionPlanRequest = (model.moduleExecutionPlanRequest || 0) + 1;
    const page = await getJson(`/v1/module-workbench/execution/plan/query?resource=nodes&module_id=${encodeURIComponent(moduleId)}&limit=50&offset=0`);
    if (page.version !== "module-workbench-execution-plan-v1" || page.accepted !== true || typeof page.plan_address !== "string" || !Array.isArray(page.items) || page.offset !== 0 || page.limit !== 50 || page.query?.resource !== "nodes" || page.query?.module_id !== moduleId || !Number.isSafeInteger(page.total) || !page.plan_summary || page.plan_summary.content_address !== page.plan_address || typeof page.plan_summary.ledger_address !== "string") {
      throw new Error("The local API returned an invalid dependency-aware execution plan.");
    }
    if (request !== model.moduleExecutionPlanRequest || model.selectedModule !== moduleId) return null;
    return page;
  }

  function renderExecutionControls(item, moduleId) {
    const td = document.createElement("td");
    const actions = executionActionsByState[item.state] || [];
    if (!actions.length) {
      td.append(element("span", "muted", "Terminal"));
      return td;
    }
    const controls = element("div", "execution-controls");
    const select = document.createElement("select");
    select.className = "execution-action";
    select.setAttribute("aria-label", `Choose a transition for ${item.task_id}`);
    const placeholder = element("option", "", "Choose action");
    placeholder.value = "";
    placeholder.selected = true;
    select.append(placeholder);
    for (const action of actions) {
      const option = element("option", "", displayValue(action));
      option.value = action;
      select.append(option);
    }
    const detail = document.createElement("input");
    detail.className = "execution-detail";
    detail.type = "text";
    detail.maxLength = 4096;
    detail.placeholder = "Transition detail (required)";
    detail.setAttribute("aria-label", `Detail for ${item.task_id}`);
    const evidence = document.createElement("input");
    evidence.className = "execution-evidence";
    evidence.type = "text";
    evidence.maxLength = 4096;
    evidence.placeholder = `${formatCount(item.required_evidence_count)} evidence address${item.required_evidence_count === 1 ? "" : "es"} for completion`;
    evidence.setAttribute("aria-label", `Evidence addresses for ${item.task_id}`);
    evidence.hidden = true;
    const apply = element("button", "button quiet", "Apply");
    apply.type = "button";
    apply.disabled = true;
    apply.addEventListener("click", async () => {
      const action = select.value;
      const detailText = detail.value.trim();
      if (!action || !detailText) {
        notice("Choose a transition and enter its required detail.", true);
        return;
      }
      const addresses = evidence.value.split(/[\s,]+/).map((value) => value.trim()).filter(Boolean);
      const payload = {
        task_id: item.task_id,
        action,
        detail: detailText,
        expected_ledger_address: model.moduleExecution?.ledger_address,
      };
      if (addresses.length) payload.evidence_addresses = [...new Set(addresses)].sort();
      apply.disabled = true;
      select.disabled = true;
      detail.disabled = true;
      evidence.disabled = true;
      try {
        const result = await postJson("/v1/module-workbench/execution/command", payload);
        if (model.selectedModule !== moduleId) return;
        const refreshed = await loadModuleExecution(moduleId);
        const refreshedPlan = await loadModuleExecutionPlan(moduleId);
        if (refreshed) {
          model.moduleExecution = refreshed;
          if (refreshedPlan) model.moduleExecutionPlan = refreshedPlan;
          renderModuleExecution();
          renderModuleExecutionPlan();
          announceSelection(`Execution transition ${displayValue(result.event?.to_state)} recorded for ${item.task_id}.`);
          notice(`Transition recorded for ${item.task_id}.`);
        }
      } catch (error) {
        notice(`The execution transition could not be recorded. ${error.message}`, true);
        apply.disabled = false;
        select.disabled = false;
        detail.disabled = false;
        evidence.disabled = false;
      }
    });
    select.addEventListener("change", () => {
      const selected = select.value;
      evidence.hidden = selected !== "complete";
      apply.disabled = !selected;
    });
    controls.append(select, detail, evidence, apply);
    td.append(controls);
    return td;
  }

  function renderModulePortfolio() {
    const page = model.modulePortfolio;
    const summaryBox = $("module-workbench-portfolio-summary");
    const body = $("module-workbench-portfolio-table");
    summaryBox.replaceChildren();
    body.replaceChildren();
    if (!page) {
      $("module-workbench-portfolio-label").textContent = "—";
      $("module-workbench-portfolio-summary-text").textContent = "Verifying portfolio selection…";
      body.append(emptyRow(5, "Portfolio selection has not been verified."));
      return;
    }
    const summary = page.portfolio_summary || {};
    const familyCounts = Object.entries(summary.selected_family_counts || {}).map(([family, count]) => `${displayValue(family)} ${formatCount(count)}`).join(" · ");
    const summaryRows = [
      ["Portfolio", shortened(page.portfolio_address, 46)],
      ["Capacity", `${formatCount(summary.task_count)} selected of ${formatCount(summary.capacity)} allowed`],
      ["Deferred", `${formatCount(summary.deferred_task_count)} planned tasks outside this wave`],
      ["Module limit", `${formatCount(summary.max_tasks_per_module)} tasks per module`],
      ["Dependency closure", summary.dependency_safe === true ? "All selected tasks include their full prerequisite chain" : "Selected tasks contain deferred prerequisites"],
      ["Families / impact", `${familyCounts || "None selected"} · ${percent(summary.total_estimated_impact)} mean estimated impact`],
    ];
    for (const [label, value] of summaryRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", displayValue(value)));
      summaryBox.append(block);
    }
    $("module-workbench-portfolio-label").textContent = `${formatCount(page.total)} selected here`;
    $("module-workbench-portfolio-summary-text").textContent = page.total
      ? "These tasks are the deterministic intersection between the full plan and the current execution wave."
      : "This module has planned depth work but no task in the current bounded execution wave.";
    if (!page.items.length) {
      body.append(emptyRow(5, "No planned tasks from this module are selected for the current execution wave."));
      return;
    }
    for (const task of page.items) {
      const row = document.createElement("tr");
      row.append(
        cell(shortened(task.task_id, 48)),
        cell(displayValue(task.kind)),
        cell(task.priority),
        cell(percent(task.estimated_impact)),
        cell(displayValue(task.acceptance)),
      );
      body.append(row);
    }
  }

  function renderModuleExecution() {
    const page = model.moduleExecution;
    const body = $("module-workbench-execution-table");
    const ledgerSummary = $("module-workbench-execution-ledger-summary");
    const eventBody = $("module-workbench-execution-events-table");
    body.replaceChildren();
    ledgerSummary.replaceChildren();
    eventBody.replaceChildren();
    if (!page) {
      $("module-workbench-execution-label").textContent = "—";
      $("module-workbench-execution-summary").textContent = "Verifying bounded execution state…";
      $("module-workbench-execution-events-label").textContent = "—";
      $("module-workbench-execution-events-summary").textContent = "Verifying transition history…";
      body.append(emptyRow(7, "Execution state has not been verified."));
      eventBody.append(emptyRow(5, "Transition history has not been verified."));
      return;
    }
    const rows = page.items || [];
    const events = page.events || [];
    const moduleId = model.selectedModule;
    const counts = rows.reduce((result, item) => {
      result[item.state] = (result[item.state] || 0) + 1;
      return result;
    }, {});
    const completion = rows.length ? rows.reduce((total, item) => total + (Number.isFinite(item.completion_percent) ? item.completion_percent : 0), 0) / rows.length : 0;
    const evidencePresent = rows.reduce((total, item) => total + (item.evidence_addresses || []).length, 0);
    const evidenceRequired = rows.reduce((total, item) => total + (Number.isSafeInteger(item.required_evidence_count) ? item.required_evidence_count : 0), 0);
    const summaryRows = [
      ["Ledger", shortened(page.ledger_address, 46)],
      ["State distribution", Object.entries(counts).map(([state, count]) => `${displayValue(state)} ${formatCount(count)}`).join(" · ") || "No selected tasks"],
      ["Completion", `${completion.toFixed(1)}% average · ${evidencePresent}/${evidenceRequired} evidence receipts`],
      ["History", `${formatCount(page.event_total ?? events.length)} module events${page.event_total > events.length ? " · display capped at 512" : ""}`],
    ];
    for (const [label, value] of summaryRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", displayValue(value)));
      ledgerSummary.append(block);
    }
    $("module-workbench-execution-label").textContent = `${formatCount(page.total)} selected`;
    $("module-workbench-execution-summary").textContent = rows.length
      ? `${formatCount(rows.length)} of ${formatCount(page.total)} selected ledger items · transitions are detail-required, evidence-gated, and concurrency-checked.`
      : "This module is not included in the current bounded execution portfolio; its planned tasks remain visible above.";
    $("module-workbench-execution-events-label").textContent = `${formatCount(page.event_total ?? events.length)} events`;
    $("module-workbench-execution-events-summary").textContent = events.length
      ? "Events are ordered by contiguous ledger sequence and include the evidence supplied at transition time."
      : "No transitions have been recorded for this module.";
    if (!events.length) eventBody.append(emptyRow(5, "No append-only transition events are recorded for this module."));
    for (const event of events) {
      const row = document.createElement("tr");
      row.append(
        cell(event.sequence),
        cell(shortened(event.task_id, 48)),
        cell(`${displayValue(event.from_state)} → ${displayValue(event.to_state)}`),
        cell(formatCount((event.evidence_addresses || []).length)),
        cell(displayValue(event.detail)),
      );
      eventBody.append(row);
    }
    if (!rows.length) {
      body.append(emptyRow(7, "No execution ledger items are selected for this module."));
      return;
    }
    for (const item of rows) {
      const row = document.createElement("tr");
      const evidence = `${formatCount((item.evidence_addresses || []).length)}/${formatCount(item.required_evidence_count)}`;
      row.append(
        cell(`${shortened(item.task_id, 48)} · ${displayValue(item.kind)}`),
        cell(displayValue(item.state)),
        cell(`${Number.isFinite(item.completion_percent) ? Number(item.completion_percent).toFixed(1) : "—"}%`),
        cell(evidence),
        cell(formatCount((item.prerequisites || []).length)),
        cell(displayValue(item.detail)),
        renderExecutionControls(item, moduleId),
      );
      body.append(row);
    }
  }

  function renderModuleExecutionPlan() {
    const page = model.moduleExecutionPlan;
    const summaryBox = $("module-workbench-plan-summary");
    const body = $("module-workbench-plan-table");
    summaryBox.replaceChildren();
    body.replaceChildren();
    if (!page) {
      $("module-workbench-plan-label").textContent = "—";
      $("module-workbench-plan-summary-text").textContent = "Verifying dependency-aware execution planning…";
      body.append(emptyRow(8, "Dependency plan has not been verified."));
      return;
    }
    const summary = page.plan_summary || {};
    const safe = summary.dependency_safe === true;
    const summaryRows = [
      ["Plan", shortened(page.plan_address, 46)],
      ["Dependency safety", safe ? "No selected task depends on a deferred prerequisite" : `${formatCount(summary.deferred_prerequisite_count)} deferred prerequisite edges require attention`],
      ["Edges / depth", `${formatCount(summary.dependency_edge_count)} edges · depth ${formatCount(summary.max_depth)}`],
      ["Critical path", (summary.critical_path_task_ids || []).join(" → ") || "No selected critical path"],
      ["Ledger", shortened(summary.ledger_address, 46)],
    ];
    for (const [label, value] of summaryRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", displayValue(value)));
      summaryBox.append(block);
    }
    $("module-workbench-plan-label").textContent = `${formatCount(page.total)} nodes · ${safe ? "safe" : "attention"}`;
    $("module-workbench-plan-summary-text").textContent = page.total
      ? "This view compares the selected execution wave with the complete per-module task chain, including prerequisites deferred outside the wave."
      : "This module has no selected execution nodes in the current wave; its full task plan remains visible above.";
    if (!page.items.length) {
      body.append(emptyRow(8, "No selected dependency-plan nodes for this module."));
      return;
    }
    for (const node of page.items) {
      const row = document.createElement("tr");
      row.append(
        cell(node.sequence),
        cell(shortened(node.task_id, 48)),
        cell(node.depth),
        cell(displayValue(node.execution_state)),
        cell(displayValue(node.dependency_status)),
        cell(formatCount((node.prerequisite_task_ids || []).length)),
        cell((node.deferred_prerequisite_task_ids || []).join(" · ") || "—"),
        cell(node.downstream_count),
      );
      body.append(row);
    }
  }

  function renderModuleWorkbenchDetail() {
    const detail = model.moduleDetail;
    if (!detail) return;
    const module = detail.module || {};
    const assessment = detail.assessment || {};
    const certification = detail.certification || {};
    const summary = detail.summary || {};
    const moduleId = detail.module_id || module.module_id || model.selectedModule;
    $("module-workbench-title").textContent = moduleId || "Module dossier";
    $("module-workbench-subtitle").textContent = `${displayValue(module.relative_path)} · ${displayValue(module.family)} · ${displayValue(module.role)} · ${formatCount(module.physical_lines)} physical lines`;
    $("module-workbench-state").textContent = displayValue(certification.state);
    $("module-workbench-state").className = `state-pill${certification.state === "certified" ? " ready" : ""}`;
    $("module-workbench-address").textContent = displayValue(detail.content_address);
    $("module-workbench-score").textContent = percent(assessment.score);
    $("module-workbench-band").textContent = `${displayValue(assessment.depth_band)} · ${formatCount(assessment.nonblank_lines)} nonblank lines`;
    $("module-workbench-risk").textContent = displayValue(assessment.risk);
    $("module-workbench-certification").textContent = displayValue(certification.state);
    $("module-workbench-certification-detail").textContent = `${formatCount(certification.passed_count)} passed · ${formatCount(certification.failed_count)} failed`;
    $("module-workbench-task-count").textContent = formatCount((detail.tasks || []).length);
    $("module-workbench-evidence-count").textContent = formatCount((detail.evidence || []).length);
    $("module-workbench-gap-count").textContent = formatCount((detail.certification_gaps || []).length);
    $("module-workbench-summary-state").textContent = `${displayValue(assessment.state)} · ${displayValue(assessment.family)}`;
    const triage = model.moduleTriageByModule.get(moduleId) || (model.selectedModuleTriage?.module_id === moduleId ? model.selectedModuleTriage : null);
    $("module-workbench-triage-score").textContent = triage ? percent(triage.priority_score) : "—";
    $("module-workbench-triage-detail").textContent = triage ? `Rank #${formatCount(triage.rank)} · ${triage.risk} risk` : "Not in loaded priority page";
    $("module-workbench-triage-label").textContent = triage ? `Rank #${formatCount(triage.rank)}` : "Not loaded";
    const triageBox = $("module-workbench-triage-summary");
    triageBox.replaceChildren();
    const triageRows = triage ? [
      ["Priority score", percent(triage.priority_score)],
      ["Reason codes", (triage.reasons || []).map(triageReasonLabel).join(" · ") || "None emitted"],
      ["Rank / risk", `#${formatCount(triage.rank)} · ${displayValue(triage.risk)}`],
      ["Fan-in / fan-out", `${formatCount(triage.fan_in)} / ${formatCount(triage.fan_out)}`],
      ["Gaps / evidence / unresolved", `${formatCount(triage.gap_count)} / ${formatCount(triage.evidence_count)} / ${formatCount(triage.unresolved_edge_count)}`],
      ["Recommended task IDs", (triage.recommended_task_ids || []).join(" · ") || "No task IDs emitted"],
    ] : [["Queue status", "This module is outside the currently loaded priority page. Use the priority filters or load more to inspect its ranked reasons."]];
    for (const [label, value] of triageRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", displayValue(value)));
      triageBox.append(block);
    }

    const summaryBox = $("module-workbench-summary");
    summaryBox.replaceChildren();
    const summaryRows = [
      ["Module path", module.relative_path],
      ["Package", module.package],
      ["Source state", module.state],
      ["Physical / nonblank", `${formatCount(module.physical_lines)} / ${formatCount(module.nonblank_lines)}`],
      ["Functions / classes", `${formatCount(module.function_count)} / ${formatCount(module.class_count)}`],
      ["Public symbols", module.public_symbol_count],
      ["Imports / local dependencies", `${formatCount(module.import_count)} / ${formatCount(module.local_dependency_count)}`],
      ["Fan-in / fan-out", `${formatCount(assessment.fan_in)} / ${formatCount(assessment.fan_out)}`],
      ["Test references", module.test_reference_count],
      ["Strengths", assessment.strengths],
      ["Blockers", assessment.blockers?.length ? assessment.blockers : "None reported"],
      ["Source digest", module.source_digest],
    ];
    for (const [label, value] of summaryRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", displayValue(value)));
      summaryBox.append(block);
    }

    const certificationBody = $("module-workbench-certification-table");
    certificationBody.replaceChildren();
    const checks = certification.checks || [];
    $("module-workbench-certification-count").textContent = `${formatCount(certification.passed_count)} passed · ${formatCount(certification.gap_count)} gaps`;
    if (!checks.length) certificationBody.append(emptyRow(5, "No certification checks were reported."));
    for (const check of checks) {
      const row = document.createElement("tr");
      row.append(cell(check.kind), cell(check.state), cell(displayValue(check.observed)), cell(displayValue(check.required)), cell(check.detail));
      certificationBody.append(row);
    }

    const evidenceBody = $("module-workbench-evidence-table");
    evidenceBody.replaceChildren();
    const evidence = detail.evidence || [];
    $("module-workbench-evidence-label").textContent = `${formatCount(evidence.length)} receipts`;
    if (!evidence.length) evidenceBody.append(emptyRow(5, "No linked evidence receipts were reported."));
    for (const item of evidence) {
      const row = document.createElement("tr");
      row.append(cell(item.kind), cell(item.relation), cell(item.relative_path), cell(formatCount(item.line_count)), cell(item.detail));
      evidenceBody.append(row);
    }

    const lineageBody = $("module-workbench-lineage-table");
    lineageBody.replaceChildren();
    const lineage = detail.lineage_edges || [];
    $("module-workbench-lineage-label").textContent = `${formatCount(lineage.length)} edges`;
    if (!lineage.length) lineageBody.append(emptyRow(5, "No lineage edges were reported."));
    for (const edge of lineage) {
      const row = document.createElement("tr");
      row.append(cell(edge.relation), cell(edge.source_module), cell(edge.target_id), cell(edge.target_kind), cell(edge.resolved === true ? "Resolved" : "Unresolved"));
      lineageBody.append(row);
    }

    const tasksBody = $("module-workbench-tasks-table");
    tasksBody.replaceChildren();
    const tasks = detail.tasks || [];
    $("module-workbench-task-label").textContent = `${formatCount(tasks.length)} planned tasks`;
    if (!tasks.length) tasksBody.append(emptyRow(5, "No planned module tasks were reported."));
    for (const task of tasks) {
      const row = document.createElement("tr");
      row.append(cell(task.priority), cell(`${displayValue(task.title)} · ${displayValue(task.kind)}`), cell(task.rationale), cell(task.acceptance), cell(percent(task.estimated_impact)));
      tasksBody.append(row);
    }
    renderModulePortfolio();
    renderModuleExecutionPlan();
    renderModuleExecution();

    const limitations = $("module-workbench-limitations");
    limitations.replaceChildren();
    for (const limitation of detail.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
    if (!limitations.children.length) limitations.append(element("p", "muted", "No additional limitations were reported."));
  }

  async function openModuleWorkbenchDetail(moduleId) {
    model.activeView = "module-workbench";
    model.selectedModule = moduleId;
    if (model.selectedModuleTriage?.module_id !== moduleId) model.selectedModuleTriage = model.moduleTriageByModule.get(moduleId) || null;
    model.moduleDetail = null;
    model.moduleExecution = null;
    model.moduleExecutionPlan = null;
    model.modulePortfolio = null;
    const request = model.moduleDetailRequest = (model.moduleDetailRequest || 0) + 1;
    renderModuleAssessments();
    notice("");
    exportHref();
    showEmpty("Verifying module dossier", "Loading static implementation evidence, certification checks, lineage, and planned depth work.");
    try {
      const [detail, execution, executionPlan, portfolio] = await Promise.all([
        getJson(`/v1/module-workbench/detail?module_id=${encodeURIComponent(moduleId)}`),
        loadModuleExecution(moduleId),
        loadModuleExecutionPlan(moduleId),
        loadModulePortfolio(moduleId),
      ]);
      if (request !== model.moduleDetailRequest || model.activeView !== "module-workbench" || model.selectedModule !== moduleId) return;
      if (detail.schema !== "module-workbench-detail-v1" || detail.accepted !== true || detail.module_id !== moduleId || !detail.module || !detail.assessment || !detail.certification || !Array.isArray(detail.evidence) || !Array.isArray(detail.lineage_edges) || !Array.isArray(detail.tasks)) {
        throw new Error("The local API returned an invalid module dossier.");
      }
      if (!execution) return;
      if (!executionPlan) return;
      if (!portfolio) return;
      model.moduleDetail = detail;
      model.moduleExecution = execution;
      model.moduleExecutionPlan = executionPlan;
      model.modulePortfolio = portfolio;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-review-view").hidden = true;
      $("geo-preflight-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("geo-sensitivity-view").hidden = true;
      $("sequence-analysis-view").hidden = true;
      $("sequence-review-view").hidden = true;
      $("sequence-batch-view").hidden = true;
      $("sequence-comparison-view").hidden = true;
      $("module-workbench-view").hidden = false;
      renderModuleWorkbenchDetail();
      announceSelection(`Module ${moduleId} opened. ${formatCount(detail.evidence.length)} evidence receipts, ${formatCount(detail.tasks.length)} planned tasks, ${formatCount(portfolio.total)} selected portfolio tasks, and ${formatCount(execution.total)} selected execution items are displayed.`);
    } catch (error) {
      if (request !== model.moduleDetailRequest || model.activeView !== "module-workbench" || model.selectedModule !== moduleId) return;
      notice(`The selected module dossier could not be verified. ${error.message}`, true);
      showEmpty("Module dossier unavailable", "The selected module dossier could not be verified, so its evidence panels remain hidden.");
    }
  }

  async function loadSequenceAnalyses(append = false) {
    const request = model.sequenceListRequest = (model.sequenceListRequest || 0) + 1;
    const offset = append ? model.sequenceAnalyses.length : 0;
    const button = $("sequence-analysis-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/sequence-analyses?limit=50&offset=${offset}`);
      if (request !== model.sequenceListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") {
        throw new Error("The local API returned an invalid sequence analysis catalog.");
      }
      model.sequenceTotal = page.total_count;
      model.sequenceAnalyses = append ? model.sequenceAnalyses.concat(page.rows) : page.rows;
      model.sequenceHasMore = page.has_more;
      model.sequenceLoaded = true;
      renderSequenceAnalyses();
    } catch (error) {
      if (request !== model.sequenceListRequest) return;
      model.sequenceLoaded = true;
      if (!append) {
        model.sequenceHasMore = false;
        button.hidden = true;
        $("sequence-analysis-list").replaceChildren(element("p", "empty-inline", "Sequence analyses could not be loaded."));
        $("sequence-list-summary").textContent = "The local API could not verify a sequence analysis catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.sequenceListRequest) button.disabled = false;
    }
  }

  async function loadSequenceBatches(append = false) {
    const request = model.sequenceBatchListRequest = (model.sequenceBatchListRequest || 0) + 1;
    const offset = append ? model.sequenceBatches.length : 0;
    const button = $("sequence-batch-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/sequence-batches?limit=50&offset=${offset}`);
      if (request !== model.sequenceBatchListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") throw new Error("The local API returned an invalid sequence batch catalog.");
      model.sequenceBatchTotal = page.total_count;
      model.sequenceBatches = append ? model.sequenceBatches.concat(page.rows) : page.rows;
      model.sequenceBatchHasMore = page.has_more;
      renderSequenceBatches();
    } catch (error) {
      if (request !== model.sequenceBatchListRequest) return;
      if (!append) {
        model.sequenceBatchHasMore = false;
        button.hidden = true;
        $("sequence-batch-list").replaceChildren(element("p", "empty-inline", "Sequence batches could not be loaded."));
        $("sequence-batch-list-summary").textContent = "The local API could not verify a sequence batch catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.sequenceBatchListRequest) button.disabled = false;
    }
  }

  async function loadSequenceComparisons(append = false) {
    const request = model.sequenceComparisonListRequest = (model.sequenceComparisonListRequest || 0) + 1;
    const offset = append ? model.sequenceComparisons.length : 0;
    const button = $("sequence-comparison-list-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/sequence-comparisons?limit=50&offset=${offset}`);
      if (request !== model.sequenceComparisonListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") throw new Error("The local API returned an invalid sequence comparison catalog.");
      model.sequenceComparisonTotal = page.total_count;
      model.sequenceComparisons = append ? model.sequenceComparisons.concat(page.rows) : page.rows;
      model.sequenceComparisonHasMore = page.has_more;
      renderSequenceComparisons();
    } catch (error) {
      if (request !== model.sequenceComparisonListRequest) return;
      if (!append) {
        model.sequenceComparisonHasMore = false;
        button.hidden = true;
        $("sequence-comparison-list").replaceChildren(element("p", "empty-inline", "Sequence comparisons could not be loaded."));
        $("sequence-comparison-list-summary").textContent = "The local API could not verify a sequence comparison catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.sequenceComparisonListRequest) button.disabled = false;
    }
  }

  function renderSequenceReviewSummary() {
    const summary = model.sequenceReviewSummary;
    if (!summary) return;
    const analyses = summary.catalogs?.sequence_analyses || {};
    const batches = summary.catalogs?.sequence_batches || {};
    const changes = Number(analyses.created_motif_count || 0) + Number(analyses.disrupted_motif_count || 0) + Number(batches.created_change_count || 0) + Number(batches.disrupted_change_count || 0);
    $("sequence-review-summary").textContent = `${formatCount(analyses.record_count || 0)} analyses · ${formatCount(batches.record_count || 0)} batches · ${formatCount(changes)} saved motif changes.`;
  }

  async function loadSequenceReview() {
    try {
      const summary = await getJson("/v1/sequence-review/summary");
      if (summary.schema !== "glio-noncode.sequence-review-summary.v1" || !summary.catalogs || !summary.integrity) throw new Error("The local API returned an invalid sequence review summary.");
      model.sequenceReviewSummary = summary;
      renderSequenceReviewSummary();
    } catch (error) {
      $("sequence-review-summary").textContent = "The local API could not verify the saved sequence archive.";
      notice(error.message, true);
    }
  }

  function consistencyFeatureIds() {
    return [...new Set($("geo-consistency-features").value.split(/[\s,]+/).map((value) => value.trim()).filter(Boolean))];
  }

  function updateGeoCompareControls() {
    const checked = [...document.querySelectorAll("#geo-compare-selection input[type=checkbox]:checked")];
    model.geoCompareIds = checked.map((input) => input.value);
    const features = consistencyFeatureIds();
    const button = $("geo-compare-button");
    const sensitivityButton = $("geo-sensitivity-button");
    button.disabled = model.geoCompareIds.length < 2 || features.length < 1;
    sensitivityButton.disabled = model.geoCompareIds.length !== 2 || features.length < 1;
    if (model.geoCompareIds.length < 2) {
      $("geo-compare-status").textContent = "Choose at least two saved analyses.";
      $("geo-sensitivity-status").textContent = "Select two runs from the same Series to review normalization stability.";
    } else if (!features.length) {
      $("geo-compare-status").textContent = "Enter one or more exact source feature IDs.";
      $("geo-sensitivity-status").textContent = "Enter one or more exact source feature IDs.";
    } else {
      $("geo-compare-status").textContent = `${model.geoCompareIds.length} studies · ${features.length} feature IDs ready.`;
      $("geo-sensitivity-status").textContent = model.geoCompareIds.length === 2
        ? "Two runs ready for same-source normalization sensitivity review."
        : "Select exactly two runs for normalization sensitivity review.";
    }
  }

  function renderGeoCompareControls() {
    const box = $("geo-compare-selection");
    box.replaceChildren();
    const available = new Set(model.geoAnalyses.map((item) => item.analysis_id));
    model.geoCompareIds = model.geoCompareIds.filter((analysisId) => available.has(analysisId));
    if (!model.geoAnalyses.length) {
      box.append(element("p", "empty-inline", "Saved analyses will appear here when available."));
      updateGeoCompareControls();
      return;
    }
    for (const item of model.geoAnalyses) {
      const label = element("label", "geo-compare-option");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = item.analysis_id;
      checkbox.checked = model.geoCompareIds.includes(item.analysis_id);
      checkbox.setAttribute("aria-label", `Include ${item.accession} in cross-study comparison`);
      checkbox.addEventListener("change", updateGeoCompareControls);
      label.append(checkbox, element("span", "geo-compare-label", `${item.accession} · ${formatCount(item.matched_pair_count)} pairs`));
      box.append(label);
    }
    updateGeoCompareControls();
  }

  function renderGeoConsistencyRecords() {
    const list = $("geo-consistency-list");
    list.replaceChildren();
    $("geo-consistency-count").textContent = String(model.geoConsistencyTotal);
    $("geo-consistency-list-summary").textContent = `Showing ${model.geoConsistencyRecords.length} of ${model.geoConsistencyTotal} saved comparisons.`;
    const loadMore = $("geo-consistency-list-load-more");
    loadMore.hidden = !model.geoConsistencyHasMore;
    if (!model.geoConsistencyRecords.length) {
      list.append(element("p", "empty-inline", "No saved paired-count comparisons yet."));
      return;
    }
    for (const item of model.geoConsistencyRecords) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.comparison_id === model.selectedGeoConsistency));
      button.setAttribute("aria-label", `Open paired-count comparison of ${item.study_count} studies and ${item.feature_count} features`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", (item.accessions || []).join(" · ")), element("span", "run-status", "Comparison"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.comparison_id, 28)), element("span", "", `${item.feature_count} features · ${item.concordant_feature_count} concordant · ${item.discordant_feature_count} discordant`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoConsistency(item.comparison_id));
      list.append(button);
    }
  }

  function renderGeoSensitivityRecords() {
    const list = $("geo-sensitivity-list");
    list.replaceChildren();
    $("geo-sensitivity-count").textContent = String(model.geoSensitivityTotal);
    $("geo-sensitivity-list-summary").textContent = `Showing ${model.geoSensitivityRecords.length} of ${model.geoSensitivityTotal} saved sensitivity comparisons.`;
    const loadMore = $("geo-sensitivity-list-load-more");
    loadMore.hidden = !model.geoSensitivityHasMore;
    if (!model.geoSensitivityRecords.length) {
      list.append(element("p", "empty-inline", "No saved normalization sensitivity comparisons yet."));
      return;
    }
    for (const item of model.geoSensitivityRecords) {
      const button = element("button", "run-item");
      button.type = "button";
      button.setAttribute("aria-current", String(item.comparison_id === model.selectedGeoSensitivity));
      button.setAttribute("aria-label", `Open normalization sensitivity for ${item.accession}, ${item.feature_count} features`);
      const top = element("span", "run-top");
      top.append(element("span", "run-case", item.accession), element("span", "run-status", "Sensitivity"));
      const meta = element("span", "run-meta");
      meta.append(element("span", "run-id", shortened(item.comparison_id, 28)), element("span", "", `${item.feature_count} features · ${item.stable_direction_feature_count} stable · ${item.changed_direction_feature_count} changed`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoSensitivity(item.comparison_id));
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

  async function loadGeoPreflights(append = false) {
    const request = model.geoPreflightListRequest = (model.geoPreflightListRequest || 0) + 1;
    try {
      const offset = append ? model.geoPreflights.length : 0;
      const page = await getJson(`/v1/geo-preflights?${geoPreflightQuery(offset)}`);
      if (request !== model.geoPreflightListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") {
        throw new Error("The local API returned an invalid GEO preflight catalog.");
      }
      model.geoPreflightTotal = page.total_count;
      model.geoPreflightHasMore = page.has_more;
      model.geoPreflights = append ? model.geoPreflights.concat(page.rows) : page.rows;
      renderGeoPreflights();
      if (!append && model.activeView === "geo-preflight" && model.selectedGeoPreflight && model.geoPreflights.some((item) => item.preflight_id === model.selectedGeoPreflight)) {
        await openGeoPreflight(model.selectedGeoPreflight);
      }
    } catch (error) {
      if (request !== model.geoPreflightListRequest) return;
      model.geoPreflightHasMore = false;
      $("geo-preflight-list").replaceChildren(element("p", "empty-inline", "GEO preflights could not be loaded."));
      $("geo-preflight-list-summary").textContent = "The local API could not verify the GEO preflight catalog.";
      notice(error.message, true);
    }
  }

  function renderGeoReviewSummary() {
    const summary = model.geoReviewSummary;
    if (!summary) return;
    const catalogs = summary.catalogs || {};
    const count = catalogs.paired_count_analyses || {};
    const expression = catalogs.expression_analyses || {};
    const countComparisons = catalogs.paired_count_comparisons || {};
    const sensitivityComparisons = catalogs.paired_count_sensitivity_comparisons || {};
    const expressionComparisons = catalogs.expression_comparisons || {};
    const preflights = catalogs.preflights || {};
    const comparisonCount = Number(countComparisons.record_count || 0) + Number(sensitivityComparisons.record_count || 0) + Number(expressionComparisons.record_count || 0);
    const analysisCount = Number(count.record_count || 0) + Number(expression.record_count || 0);
    $("geo-review-summary").textContent = `${formatCount(analysisCount)} analyses · ${formatCount(comparisonCount)} comparisons · ${formatCount(Number(preflights.record_count || 0))} preflights · ${summary.integrity?.report_objects || "review"}`;
    $("geo-review-status").textContent = summary.status === "ready" ? "Verified" : "Review required";
  }

  function renderGeoReviewBreakdown(id, values, emptyText) {
    const target = $(id);
    target.replaceChildren();
    const entries = Object.entries(values || {}).filter(([key, value]) => typeof key === "string" && Number.isSafeInteger(value) && value >= 0);
    if (!entries.length) {
      target.append(element("p", "muted", emptyText));
      return;
    }
    for (const [key, value] of entries) {
      const item = element("div", "geo-quality-item");
      item.append(element("span", "control-label", consistencyText(key)), element("span", "lineage-meta", `${formatCount(value)} record${value === 1 ? "" : "s"}`));
      target.append(item);
    }
  }

  function renderGeoReviewDetail() {
    const summary = model.geoReviewSummary;
    if (!summary) return;
    const catalogs = Object.values(summary.catalogs || {});
    const analysisCount = catalogs.filter((item) => item.name.endsWith("analyses")).reduce((total, item) => total + Number(item.record_count || 0), 0);
    const comparisonCount = catalogs.filter((item) => item.name.endsWith("comparisons")).reduce((total, item) => total + Number(item.record_count || 0), 0);
    const preflightCount = catalogs.find((item) => item.name === "preflights")?.record_count || 0;
    const preflightCatalog = catalogs.find((item) => item.name === "preflights") || {};
    const accessionValues = new Set();
    for (const catalog of catalogs) {
      for (const accession of catalog.accessions || []) {
        if (typeof accession === "string" && accession.trim()) accessionValues.add(accession);
      }
    }
    const accessionCount = accessionValues.size;
    const testedCount = catalogs.reduce((total, item) => total + Number(item.tested_feature_count_total || 0), 0);
    const reportedCount = catalogs.reduce((total, item) => total + Number(item.reported_feature_count_total || 0), 0);
    const fdrCount = catalogs.reduce((total, item) => total + Number(item.fdr_significant_feature_count_total || 0), 0);
    const sensitivityRankedCount = Number(sensitivityComparisons.ranked_feature_count_total || 0);
    const sensitivityTrackedCount = Number(sensitivityComparisons.additional_tracked_feature_count_total || 0);
    const sensitivityTrackedIdCount = Number(sensitivityComparisons.tracked_feature_id_count_total || 0);
    const consistencyRankedCount = Number(countComparisons.ranked_feature_count_total || 0);
    const consistencyTrackedCount = Number(countComparisons.additional_tracked_feature_count_total || 0);
    const consistencyTrackedIdCount = Number(countComparisons.tracked_feature_id_count_total || 0);
    const expressionComparisonCatalog = catalogs.find((item) => item.name === "expression_comparisons") || {};
    const expressionRankedCount = Number(expression.ranked_feature_count_total || 0) + Number(expressionComparisonCatalog.ranked_feature_count_total || 0);
    const expressionTrackedCount = Number(expression.additional_tracked_feature_count_total || 0) + Number(expressionComparisonCatalog.additional_tracked_feature_count_total || 0);
    const expressionTrackedIdCount = Number(expression.tracked_feature_id_count_total || 0) + Number(expressionComparisonCatalog.tracked_feature_id_count_total || 0);
    $("geo-review-subtitle").textContent = `${formatCount(analysisCount)} analyses · ${formatCount(comparisonCount)} saved comparisons · ${summary.integrity?.report_objects || "review"}`;
    $("geo-review-address").textContent = summary.content_address || "Address unavailable";
    $("geo-review-analysis-count").textContent = formatCount(analysisCount);
    $("geo-review-comparison-count").textContent = formatCount(comparisonCount);
    $("geo-review-consistency-coverage").textContent = `${formatCount(consistencyRankedCount)} + ${formatCount(consistencyTrackedCount)}`;
    $("geo-review-consistency-coverage-detail").textContent = `${formatCount(consistencyTrackedIdCount)} tracked IDs across studies`;
    $("geo-review-expression-coverage").textContent = `${formatCount(expressionRankedCount)} + ${formatCount(expressionTrackedCount)}`;
    $("geo-review-expression-coverage-detail").textContent = `${formatCount(expressionTrackedIdCount)} tracked IDs across studies`;
    $("geo-review-preflight-count").textContent = formatCount(preflightCount);
    $("geo-review-accession-count").textContent = formatCount(accessionCount);
    $("geo-review-tested-count").textContent = formatCount(testedCount);
    $("geo-review-reported-count").textContent = formatCount(reportedCount);
    $("geo-review-sensitivity-coverage").textContent = `${formatCount(sensitivityRankedCount)} + ${formatCount(sensitivityTrackedCount)}`;
    $("geo-review-sensitivity-coverage-detail").textContent = `${formatCount(sensitivityTrackedIdCount)} tracked IDs across runs`;
    $("geo-review-fdr-count").textContent = formatCount(fdrCount);
    $("geo-review-integrity").textContent = summary.integrity?.verification_failure_count === 0 ? "Accepted" : "Review";
    renderGeoReviewBreakdown("geo-review-preflight-kinds", preflightCatalog.kind_counts, "No saved preflight kinds yet.");
    renderGeoReviewBreakdown("geo-review-preflight-states", preflightCatalog.design_state_counts, "No design-state reports yet.");
    const body = $("geo-review-catalog-table");
    body.replaceChildren();
    for (const catalog of catalogs) {
      const row = document.createElement("tr");
      row.append(cell(catalog.name), cell(formatCount(catalog.record_count)), cell(formatCount(catalog.verified_record_count)), cell(formatCount(catalog.feature_count_total)), cell(formatCount(catalog.tested_feature_count_total)), cell(formatCount(catalog.reported_feature_count_total)), cell(`${formatCount(catalog.ranked_feature_count_total)} + ${formatCount(catalog.additional_tracked_feature_count_total)} (${formatCount(catalog.tracked_feature_id_count_total)} IDs)`), cell(formatCount(catalog.fdr_significant_feature_count_total)), cell(formatCount(catalog.accession_count)), cell(catalog.catalog_state));
      body.append(row);
    }
    const limitations = $("geo-review-limitations");
    limitations.replaceChildren();
    for (const limitation of summary.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  async function loadGeoReviewSummary() {
    const request = model.geoReviewRequest = (model.geoReviewRequest || 0) + 1;
    try {
      const summary = await getJson("/v1/geo-review/summary");
      if (request !== model.geoReviewRequest) return;
      if (summary.schema !== "glio-noncode.geo-review-summary.v1" || !summary.catalogs || !summary.integrity) throw new Error("The local API returned an invalid GEO workspace summary.");
      model.geoReviewSummary = summary;
      renderGeoReviewSummary();
      if (model.activeView === "geo-review") renderGeoReviewDetail();
    } catch (error) {
      if (request !== model.geoReviewRequest) return;
      $("geo-review-summary").textContent = "The GEO archive summary could not be verified.";
      $("geo-review-status").textContent = "Unavailable";
      notice(error.message, true);
    }
  }

  async function loadGeoExpressionAnalyses() {
    const request = model.geoExpressionListRequest = (model.geoExpressionListRequest || 0) + 1;
    try {
      const page = await getJson("/v1/geo-expression-analyses?limit=50&offset=0");
      if (request !== model.geoExpressionListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) throw new Error("The local API returned an invalid GEO expression catalog.");
      model.geoExpressionTotal = page.total_count;
      model.geoExpressionAnalyses = page.rows;
      renderGeoExpressionAnalyses();
    } catch (error) {
      if (request !== model.geoExpressionListRequest) return;
      $("geo-expression-analysis-list").replaceChildren(element("p", "empty-inline", "GEO expression contrasts could not be loaded."));
      $("geo-expression-list-summary").textContent = "The local API could not verify the GEO expression catalog.";
      notice(error.message, true);
    }
  }

  async function loadGeoConsistencyRecords(append = false) {
    const request = model.geoConsistencyListRequest = (model.geoConsistencyListRequest || 0) + 1;
    const offset = append ? model.geoConsistencyRecords.length : 0;
    const button = $("geo-consistency-list-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/geo-count-consistency?limit=50&offset=${offset}`);
      if (request !== model.geoConsistencyListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") throw new Error("The local API returned an invalid GEO count consistency catalog.");
      model.geoConsistencyTotal = page.total_count;
      model.geoConsistencyRecords = append ? model.geoConsistencyRecords.concat(page.rows) : page.rows;
      model.geoConsistencyHasMore = page.has_more;
      renderGeoConsistencyRecords();
      if (!append && model.activeView === "geo-consistency" && model.selectedGeoConsistency) {
        if (model.geoConsistencyRecords.some((item) => item.comparison_id === model.selectedGeoConsistency)) await openGeoConsistency(model.selectedGeoConsistency);
        else showEmpty("No saved paired-count comparison", "The previously selected comparison is no longer present in the local catalog.");
      }
    } catch (error) {
      if (request !== model.geoConsistencyListRequest) return;
      if (!append) {
        model.geoConsistencyHasMore = false;
        button.hidden = true;
        $("geo-consistency-list").replaceChildren(element("p", "empty-inline", "Paired-count comparisons could not be loaded."));
        $("geo-consistency-list-summary").textContent = "The local API could not verify the paired-count consistency catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.geoConsistencyListRequest) button.disabled = false;
    }
  }

  async function loadGeoSensitivityRecords(append = false) {
    const request = model.geoSensitivityListRequest = (model.geoSensitivityListRequest || 0) + 1;
    const offset = append ? model.geoSensitivityRecords.length : 0;
    const button = $("geo-sensitivity-list-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/geo-count-sensitivity?limit=50&offset=${offset}`);
      if (request !== model.geoSensitivityListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") throw new Error("The local API returned an invalid GEO sensitivity catalog.");
      model.geoSensitivityTotal = page.total_count;
      model.geoSensitivityRecords = append ? model.geoSensitivityRecords.concat(page.rows) : page.rows;
      model.geoSensitivityHasMore = page.has_more;
      renderGeoSensitivityRecords();
      if (!append && model.activeView === "geo-sensitivity" && model.selectedGeoSensitivity) {
        if (model.geoSensitivityRecords.some((item) => item.comparison_id === model.selectedGeoSensitivity)) await openGeoSensitivity(model.selectedGeoSensitivity);
        else showEmpty("No saved normalization sensitivity", "The previously selected sensitivity comparison is no longer present in the local catalog.");
      }
    } catch (error) {
      if (request !== model.geoSensitivityListRequest) return;
      if (!append) {
        model.geoSensitivityHasMore = false;
        button.hidden = true;
        $("geo-sensitivity-list").replaceChildren(element("p", "empty-inline", "Normalization sensitivity comparisons could not be loaded."));
        $("geo-sensitivity-list-summary").textContent = "The local API could not verify the GEO sensitivity catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.geoSensitivityListRequest) button.disabled = false;
    }
  }

  async function loadGeoExpressionConsistencyRecords(append = false) {
    const request = model.geoExpressionConsistencyListRequest = (model.geoExpressionConsistencyListRequest || 0) + 1;
    const offset = append ? model.geoExpressionConsistencyRecords.length : 0;
    const button = $("geo-expression-consistency-list-load-more");
    button.disabled = append;
    try {
      const page = await getJson(`/v1/geo-expression-consistency?limit=50&offset=${offset}`);
      if (request !== model.geoExpressionConsistencyListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count) || page.offset !== offset || typeof page.has_more !== "boolean") throw new Error("The local API returned an invalid GEO consistency catalog.");
      model.geoExpressionConsistencyTotal = page.total_count;
      model.geoExpressionConsistencyRecords = append ? model.geoExpressionConsistencyRecords.concat(page.rows) : page.rows;
      model.geoExpressionConsistencyHasMore = page.has_more;
      renderGeoExpressionConsistencyRecords();
      if (!append && model.activeView === "geo-expression-consistency" && model.selectedGeoExpressionConsistency) {
        if (model.geoExpressionConsistencyRecords.some((item) => item.comparison_id === model.selectedGeoExpressionConsistency)) {
          await openGeoExpressionConsistency(model.selectedGeoExpressionConsistency);
        } else {
          showEmpty("No saved expression comparison", "The previously selected comparison is no longer present in the local catalog.");
        }
      }
    } catch (error) {
      if (request !== model.geoExpressionConsistencyListRequest) return;
      if (!append) {
        model.geoExpressionConsistencyHasMore = false;
        button.hidden = true;
        $("geo-expression-consistency-list").replaceChildren(element("p", "empty-inline", "Expression comparisons could not be loaded."));
        $("geo-expression-consistency-list-summary").textContent = "The local API could not verify the expression consistency catalog.";
      }
      notice(error.message, true);
    } finally {
      if (request === model.geoExpressionConsistencyListRequest) button.disabled = false;
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
    $("geo-expression-analysis-view").hidden = true;
    $("geo-expression-consistency-view").hidden = true;
    $("geo-review-view").hidden = true;
    $("geo-preflight-view").hidden = true;
    $("geo-consistency-view").hidden = true;
    $("geo-sensitivity-view").hidden = true;
    $("sequence-analysis-view").hidden = true;
    $("sequence-review-view").hidden = true;
    $("sequence-batch-view").hidden = true;
    $("sequence-comparison-view").hidden = true;
    $("module-workbench-view").hidden = true;
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
    const csvLink = $("geo-csv-export");
    const runCsvLink = $("geo-run-csv-export");
    const ledgerJsonLink = $("geo-ledger-json-export");
    runCsvLink.href = "#";
    runCsvLink.hidden = true;
    runCsvLink.classList.add("disabled");
    runCsvLink.setAttribute("aria-disabled", "true");
    ledgerJsonLink.href = "#";
    ledgerJsonLink.hidden = true;
    ledgerJsonLink.classList.add("disabled");
    ledgerJsonLink.setAttribute("aria-disabled", "true");
    if (model.activeView === "geo" && model.selectedGeo && model.geoPage?.analysis_id === model.selectedGeo) {
      link.href = `/v1/geo-analyses/${encodeURIComponent(model.selectedGeo)}/report.json`;
      link.textContent = "Download GEO JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = geoFilterQuery().toString();
      csvLink.href = `/v1/geo-analyses/${encodeURIComponent(model.selectedGeo)}/results.csv${filterQuery ? `?${filterQuery}` : ""}`;
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      ledgerJsonLink.href = "/v1/geo-review/ledger.json?verify_reports=true";
      ledgerJsonLink.textContent = "Download ledger JSON";
      ledgerJsonLink.hidden = false;
      ledgerJsonLink.classList.remove("disabled");
      ledgerJsonLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "geo-review" && model.geoReviewSummary?.content_address) {
      link.href = "/v1/geo-review/summary";
      link.textContent = "Download GEO health summary";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      csvLink.href = "/v1/geo-review/summary.csv?verify_reports=true";
      csvLink.textContent = "Download health ledger";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "geo-preflight" && model.selectedGeoPreflight && model.geoPreflightReport?.content_address) {
      link.href = `/v1/geo-preflights/${encodeURIComponent(model.selectedGeoPreflight)}/report.json`;
      link.textContent = "Download preflight JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      csvLink.href = "#";
      csvLink.hidden = true;
      csvLink.classList.add("disabled");
      csvLink.setAttribute("aria-disabled", "true");
      return;
    }
    if (model.activeView === "geo-expression-consistency" && model.geoExpressionConsistency?.comparison_id) {
      const comparisonId = model.geoExpressionConsistency.comparison_id;
      link.href = `/v1/geo-expression-consistency/${encodeURIComponent(comparisonId)}/report.json`;
      link.textContent = "Download comparison JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = geoExpressionConsistencyFilterQuery().toString();
      csvLink.href = `/v1/geo-expression-consistency/${encodeURIComponent(comparisonId)}/features.csv${filterQuery ? `?${filterQuery}` : ""}`;
      csvLink.textContent = "Download comparison CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      runCsvLink.href = `/v1/geo-expression-consistency/${encodeURIComponent(comparisonId)}/studies.csv`;
      runCsvLink.textContent = "Download study coverage CSV";
      runCsvLink.hidden = false;
      runCsvLink.classList.remove("disabled");
      runCsvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "geo-consistency" && model.geoConsistency?.comparison_id) {
      const comparisonId = model.geoConsistency.comparison_id;
      link.href = `/v1/geo-count-consistency/${encodeURIComponent(comparisonId)}/report.json`;
      link.textContent = "Download comparison JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = geoConsistencyFilterQuery().toString();
      csvLink.href = `/v1/geo-count-consistency/${encodeURIComponent(comparisonId)}/features.csv${filterQuery ? `?${filterQuery}` : ""}`;
      csvLink.textContent = "Download comparison CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      runCsvLink.href = `/v1/geo-count-consistency/${encodeURIComponent(comparisonId)}/studies.csv`;
      runCsvLink.textContent = "Download study coverage CSV";
      runCsvLink.hidden = false;
      runCsvLink.classList.remove("disabled");
      runCsvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "geo-sensitivity" && model.geoSensitivity?.comparison_id) {
      const comparisonId = model.geoSensitivity.comparison_id;
      link.href = `/v1/geo-count-sensitivity/${encodeURIComponent(comparisonId)}/report.json`;
      link.textContent = "Download sensitivity JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filters = geoSensitivityFilterQuery().toString();
      csvLink.href = `/v1/geo-count-sensitivity/${encodeURIComponent(comparisonId)}/features.csv${filters ? `?${filters}` : ""}`;
      csvLink.textContent = "Download sensitivity CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      runCsvLink.href = `/v1/geo-count-sensitivity/${encodeURIComponent(comparisonId)}/runs.csv`;
      runCsvLink.textContent = "Download run coverage CSV";
      runCsvLink.hidden = false;
      runCsvLink.classList.remove("disabled");
      runCsvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "geo-expression" && model.selectedGeoExpression && model.geoExpressionPage?.analysis_id === model.selectedGeoExpression) {
      link.href = `/v1/geo-expression-analyses/${encodeURIComponent(model.selectedGeoExpression)}/report.json`;
      link.textContent = "Download expression JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = geoExpressionFilterQuery().toString();
      csvLink.href = `/v1/geo-expression-analyses/${encodeURIComponent(model.selectedGeoExpression)}/results.csv${filterQuery ? `?${filterQuery}` : ""}`;
      csvLink.textContent = "Download expression CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "sequence" && model.selectedSequence && model.sequenceReport?.content_address) {
      link.href = `/v1/sequence-analyses/${encodeURIComponent(model.selectedSequence)}/report.json`;
      link.textContent = "Download sequence JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = sequenceAnalysisFilterQuery();
      filterQuery.delete("limit");
      filterQuery.delete("offset");
      csvLink.href = `/v1/sequence-analyses/${encodeURIComponent(model.selectedSequence)}/changes.csv${filterQuery.toString() ? `?${filterQuery.toString()}` : ""}`;
      csvLink.textContent = "Download motif CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "sequence-review" && model.sequenceReviewSummary?.content_address) {
      link.href = "/v1/sequence-review/summary";
      link.textContent = "Download archive summary";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = sequenceReviewMotifQuery();
      filterQuery.delete("limit");
      filterQuery.delete("offset");
      csvLink.href = `/v1/sequence-review/motifs.csv${filterQuery.toString() ? `?${filterQuery.toString()}` : ""}`;
      csvLink.textContent = "Download motif activity CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "sequence-batch" && model.selectedSequenceBatch && model.sequenceBatchReport?.content_address) {
      link.href = `/v1/sequence-batches/${encodeURIComponent(model.selectedSequenceBatch)}/report.json`;
      link.textContent = "Download batch JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = sequenceBatchFilterQuery();
      filterQuery.delete("limit");
      filterQuery.delete("offset");
      csvLink.href = `/v1/sequence-batches/${encodeURIComponent(model.selectedSequenceBatch)}/changes.csv${filterQuery.toString() ? `?${filterQuery.toString()}` : ""}`;
      csvLink.textContent = "Download batch motif CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      return;
    }
    if (model.activeView === "sequence-comparison" && model.selectedSequenceComparison && model.sequenceComparisonReport?.content_address) {
      link.href = `/v1/sequence-comparisons/${encodeURIComponent(model.selectedSequenceComparison)}/report.json`;
      link.textContent = "Download comparison JSON";
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
      link.removeAttribute("target");
      link.removeAttribute("rel");
      const filterQuery = sequenceComparisonFilterQuery().toString();
      csvLink.href = `/v1/sequence-comparisons/${encodeURIComponent(model.selectedSequenceComparison)}/changes.csv${filterQuery ? `?${filterQuery}` : ""}`;
      csvLink.textContent = "Download comparison CSV";
      csvLink.hidden = false;
      csvLink.classList.remove("disabled");
      csvLink.setAttribute("aria-disabled", "false");
      return;
    }
    csvLink.href = "#";
    csvLink.hidden = true;
    csvLink.classList.add("disabled");
    csvLink.setAttribute("aria-disabled", "true");
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

  function hideSequenceComparisonView() { $("sequence-comparison-view").hidden = true; }

  async function openRun(runId) {
    hideSequenceComparisonView();
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
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
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

  function geoFilterQuery() {
    const params = new URLSearchParams();
    const filters = model.geoFilters;
    if (filters.feature_contains) params.set("feature_contains", filters.feature_contains);
    if (filters.effect_direction) params.set("effect_direction", filters.effect_direction);
    if (filters.min_abs_median_effect) params.set("min_abs_median_effect", filters.min_abs_median_effect);
    if (filters.fdr_significant) params.set("fdr_significant", "true");
    if (filters.sign_test_fdr_significant) params.set("sign_test_fdr_significant", "true");
    return params.toString();
  }

  function geoPreflightQuery(offset) {
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (model.geoPreflightFilters.accession) params.set("accession", model.geoPreflightFilters.accession);
    if (model.geoPreflightFilters.kind) params.set("kind", model.geoPreflightFilters.kind);
    return params.toString();
  }

  function reloadGeoPreflights() {
    if (model.geoPreflightFilterTimer !== null) clearTimeout(model.geoPreflightFilterTimer);
    model.geoPreflightFilterTimer = setTimeout(() => {
      model.geoPreflightFilterTimer = null;
      loadGeoPreflights();
    }, 180);
  }

  function geoResultQuery(offset) {
    const params = new URLSearchParams(geoFilterQuery());
    params.set("limit", "25");
    params.set("offset", String(offset));
    return params.toString();
  }

  function geoExpressionFilterQuery() {
    const params = new URLSearchParams();
    const feature = $("geo-expression-feature-filter")?.value.trim();
    const direction = $("geo-expression-direction-filter")?.value;
    const fdr = $("geo-expression-fdr-filter")?.checked;
    if (feature) params.set("feature_contains", feature);
    if (direction) params.set("effect_direction", direction);
    if (fdr) params.set("fdr_significant", "true");
    return params;
  }

  function geoExpressionResultQuery(offset) {
    const params = new URLSearchParams(geoExpressionFilterQuery());
    params.set("limit", "25");
    params.set("offset", String(offset));
    return params.toString();
  }

  function geoConsistencyFilterQuery() {
    const params = new URLSearchParams();
    const filters = model.geoConsistencyFilters;
    if (filters.feature_contains) params.set("feature_contains", filters.feature_contains);
    if (filters.direction_consistency) params.set("direction_consistency", filters.direction_consistency);
    if (filters.fdr_direction_consistency) params.set("fdr_direction_consistency", filters.fdr_direction_consistency);
    if (filters.sign_test_direction_consistency) params.set("sign_test_direction_consistency", filters.sign_test_direction_consistency);
    return params;
  }

  function geoSensitivityFilterQuery() {
    const params = new URLSearchParams();
    const filters = model.geoSensitivityFilters;
    if (filters.feature_contains) params.set("feature_contains", filters.feature_contains);
    if (filters.direction_sensitivity) params.set("direction_sensitivity", filters.direction_sensitivity);
    if (filters.fdr_sensitivity) params.set("fdr_sensitivity", filters.fdr_sensitivity);
    if (filters.sign_test_fdr_sensitivity) params.set("sign_test_fdr_sensitivity", filters.sign_test_fdr_sensitivity);
    return params;
  }

  function geoExpressionConsistencyFilterQuery() {
    const params = new URLSearchParams();
    const filters = model.geoExpressionConsistencyFilters;
    if (filters.feature_contains) params.set("feature_contains", filters.feature_contains);
    if (filters.direction_consistency) params.set("direction_consistency", filters.direction_consistency);
    if (filters.fdr_direction_consistency) params.set("fdr_direction_consistency", filters.fdr_direction_consistency);
    return params;
  }

  function resetGeoConsistencyFilters() {
    model.geoConsistencyFilters = { feature_contains: "", direction_consistency: "", fdr_direction_consistency: "", sign_test_direction_consistency: "" };
    const feature = $("geo-consistency-feature-filter");
    const direction = $("geo-consistency-direction-filter");
    const fdr = $("geo-consistency-fdr-filter");
    const sign = $("geo-consistency-sign-fdr-filter");
    if (feature) feature.value = "";
    if (direction) direction.value = "";
    if (fdr) fdr.value = "";
    if (sign) sign.value = "";
  }

  function resetGeoSensitivityFilters() {
    model.geoSensitivityFilters = { feature_contains: "", direction_sensitivity: "", fdr_sensitivity: "", sign_test_fdr_sensitivity: "" };
    const feature = $("geo-sensitivity-feature-filter");
    const direction = $("geo-sensitivity-direction-filter");
    const fdr = $("geo-sensitivity-fdr-filter");
    const sign = $("geo-sensitivity-sign-fdr-filter");
    if (feature) feature.value = "";
    if (direction) direction.value = "";
    if (fdr) fdr.value = "";
    if (sign) sign.value = "";
  }

  function resetGeoExpressionConsistencyFilters() {
    model.geoExpressionConsistencyFilters = { feature_contains: "", direction_consistency: "", fdr_direction_consistency: "" };
    const feature = $("geo-expression-consistency-feature-filter");
    const direction = $("geo-expression-consistency-direction-filter");
    const fdr = $("geo-expression-consistency-fdr-filter");
    if (feature) feature.value = "";
    if (direction) direction.value = "";
    if (fdr) fdr.value = "";
  }

  function reloadGeoConsistencyPage() {
    if (model.geoConsistencyFilterTimer !== null) clearTimeout(model.geoConsistencyFilterTimer);
    model.geoConsistencyFilterTimer = setTimeout(() => {
      model.geoConsistencyFilterTimer = null;
      if (model.selectedGeoConsistency) openGeoConsistency(model.selectedGeoConsistency);
    }, 180);
  }

  function reloadGeoSensitivityPage() {
    if (model.geoSensitivityFilterTimer !== null) clearTimeout(model.geoSensitivityFilterTimer);
    model.geoSensitivityFilterTimer = setTimeout(() => {
      model.geoSensitivityFilterTimer = null;
      if (model.selectedGeoSensitivity) openGeoSensitivity(model.selectedGeoSensitivity);
    }, 180);
  }

  function reloadGeoExpressionConsistencyPage() {
    if (model.geoExpressionConsistencyFilterTimer !== null) clearTimeout(model.geoExpressionConsistencyFilterTimer);
    model.geoExpressionConsistencyFilterTimer = setTimeout(() => {
      model.geoExpressionConsistencyFilterTimer = null;
      if (model.selectedGeoExpressionConsistency) openGeoExpressionConsistency(model.selectedGeoExpressionConsistency);
    }, 180);
  }

  async function openGeoAnalysis(analysisId, { append = false } = {}) {
    hideSequenceComparisonView();
    model.activeView = "geo";
    model.selectedGeo = analysisId;
    model.geoConsistency = null;
    $("geo-consistency-view").hidden = true;
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
      const page = await getJson(`/v1/geo-analyses/${encodeURIComponent(analysisId)}?${geoResultQuery(offset)}`);
      if (request !== model.selectionRequest || model.activeView !== "geo" || model.selectedGeo !== analysisId) return;
      if (page.schema !== "glio-noncode.geo-analysis-page.v1" || page.analysis_id !== analysisId || !Array.isArray(page.results) || !page.filters || !Number.isSafeInteger(page.unfiltered_result_count)) {
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
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
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

  async function openGeoExpressionAnalysis(analysisId, { append = false } = {}) {
    hideSequenceComparisonView();
    model.activeView = "geo-expression";
    model.selectedGeoExpression = analysisId;
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    renderGeoExpressionAnalyses();
    notice("");
    if (!append) {
      model.geoExpressionPage = null;
      model.geoExpressionResults = [];
      showEmpty("Verifying GEO expression report", "Loading the immutable expression contrast and its aggregate-only result projection.");
    }
    const offset = append ? model.geoExpressionResults.length : 0;
    try {
      const page = await getJson(`/v1/geo-expression-analyses/${encodeURIComponent(analysisId)}?${geoExpressionResultQuery(offset)}`);
      if (request !== model.selectionRequest || model.activeView !== "geo-expression" || model.selectedGeoExpression !== analysisId) return;
      if (page.schema !== "glio-noncode.geo-expression-analysis-page.v1" || page.analysis_id !== analysisId || !Array.isArray(page.results) || !page.summary || !page.provenance) throw new Error("The local API returned an invalid GEO expression projection.");
      if (append && model.geoExpressionPage?.report_address !== page.report_address) throw new Error("The saved GEO expression report changed while loading feature rows.");
      model.geoExpressionPage = page;
      model.geoExpressionResults = append ? model.geoExpressionResults.concat(page.results) : page.results;
      exportHref();
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = false;
      $("geo-consistency-view").hidden = true;
      $("sequence-analysis-view").hidden = true;
      $("sequence-review-view").hidden = true;
      $("sequence-batch-view").hidden = true;
      renderGeoExpressionReport();
      announceSelection(`GEO expression analysis ${page.summary.accession} opened. ${formatCount(page.summary.tested_feature_count)} features tested.`);
    } catch (error) {
      if (request !== model.selectionRequest || model.activeView !== "geo-expression" || model.selectedGeoExpression !== analysisId) return;
      notice(`The selected GEO expression report could not be verified. ${error.message}`, true);
      showEmpty("GEO expression report unavailable", "The stored aggregate expression report could not be verified, so its result details remain hidden.");
    }
  }

  function renderGeoExpressionReport() {
    const page = model.geoExpressionPage;
    if (!page) return;
    const summary = page.summary;
    const comparison = page.comparison;
    $("geo-expression-title").textContent = `${summary.accession} · ${summary.platform_id}`;
    $("geo-expression-subtitle").textContent = `${summary.model_type.replaceAll("_", " ")} · ${String(summary.fdr_method).toUpperCase()} q ≤ ${summary.fdr_threshold}`;
    $("geo-expression-report-address").textContent = page.report_address;
    $("geo-expression-metric-samples").textContent = formatCount(summary.sample_count);
    $("geo-expression-metric-groups").textContent = `${formatCount(summary.case_sample_count)} case · ${formatCount(summary.reference_sample_count)} reference`;
    $("geo-expression-metric-tested").textContent = formatCount(summary.tested_feature_count);
    $("geo-expression-metric-fdr").textContent = formatCount(summary.fdr_significant_feature_count);
    $("geo-expression-metric-fdr-method").textContent = `${String(summary.fdr_method).toUpperCase()} at ${summary.fdr_threshold}`;
    $("geo-expression-metric-reported").textContent = formatCount(summary.reported_feature_count + summary.additional_feature_result_count);
    $("geo-expression-scale").textContent = summary.scale;
    const provenance = $("geo-expression-provenance");
    provenance.replaceChildren();
    const rows = [["Series", summary.accession], ["Platform", summary.platform_id], ["Source file", summary.source_file_name || "Remote GEO response"], ["Source digest", summary.source_sha256], ["Case filters", filterDescription(comparison.case_filters)], ["Reference filters", filterDescription(comparison.reference_filters)]];
    for (const [label, value] of rows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }
    $("geo-expression-result-count").textContent = `${formatCount(page.total_results)} of ${formatCount(page.unfiltered_result_count)} rows`;
    const expressionFilteredSummary = page.filtered_result_summary || {};
    const expressionDirections = expressionFilteredSummary.effect_direction_counts || {};
    $("geo-expression-filter-summary").textContent = `${formatCount(expressionFilteredSummary.result_count || 0)} filtered rows · ${formatCount(expressionFilteredSummary.fdr_significant_count || 0)} FDR significant · directions ${formatCount(expressionDirections.case_higher || 0)} higher / ${formatCount(expressionDirections.case_lower || 0)} lower / ${formatCount(expressionDirections.no_rank_shift || 0)} unchanged`;
    $("geo-expression-load-more").hidden = !page.has_more;
    const body = $("geo-expression-results-table");
    body.replaceChildren();
    if (!model.geoExpressionResults.length) body.append(emptyRow(6, "No expression rows match the selected filters."));
    for (const result of model.geoExpressionResults) {
      const effect = result.adjusted_mean_difference ?? result.mean_difference ?? result.median_difference;
      const row = document.createElement("tr");
      row.append(cell(result.feature_id), cell(consistencyText(result.effect_direction)), cell(formatEffect(effect)), cell(formatQ(result.p_value)), cell(formatQ(result.q_value)), cell(`${result.case_n ?? "—"} / ${result.reference_n ?? "—"}`));
      body.append(row);
    }
    const limitations = $("geo-expression-limitations");
    limitations.replaceChildren();
    for (const limitation of page.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  async function openSequenceAnalysis(analysisId) {
    hideSequenceComparisonView();
    model.activeView = "sequence";
    model.selectedSequence = analysisId;
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    const changesRequest = model.sequenceAnalysisChangesRequest = (model.sequenceAnalysisChangesRequest || 0) + 1;
    model.sequenceReport = null;
    model.sequenceChanges = null;
    renderSequenceAnalyses();
    notice("");
    exportHref();
    showEmpty("Verifying sequence report", "Loading the immutable phased sequence report and its motif-change projection.");
    try {
      const [report, changes] = await Promise.all([
        getJson(`/v1/sequence-analyses/${encodeURIComponent(analysisId)}/report.json`),
        getJson(`/v1/sequence-analyses/${encodeURIComponent(analysisId)}?${sequenceAnalysisFilterQuery(0).toString()}`),
      ]);
      if (request !== model.selectionRequest || changesRequest !== model.sequenceAnalysisChangesRequest || model.activeView !== "sequence" || model.selectedSequence !== analysisId) return;
      if (report.schema !== "glio-noncode.sequence-haplotype-analysis.v1" || report.status !== "completed" || !report.source || !report.inputs || !report.analysis || changes.schema !== "glio-noncode.sequence-haplotype-changes.v1" || changes.offset !== 0 || typeof changes.has_more !== "boolean" || !Array.isArray(changes.changes)) {
        throw new Error("The local API returned an invalid sequence report projection.");
      }
      model.sequenceReport = report;
      model.sequenceChanges = changes;
      exportHref();
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("sequence-analysis-view").hidden = false;
      $("sequence-review-view").hidden = true;
      $("sequence-batch-view").hidden = true;
      renderSequenceReport();
      announceSelection(`Sequence analysis ${analysisId} opened. ${formatCount(report.inputs.variant_count)} phased variants and ${formatCount(changes.total_changes)} motif changes.`);
    } catch (error) {
      if (request !== model.selectionRequest || model.activeView !== "sequence" || model.selectedSequence !== analysisId) return;
      notice(`The selected sequence report could not be verified. ${error.message}`, true);
      showEmpty("Sequence report unavailable", "The selected sequence report could not be verified, so its detail panels remain hidden.");
    }
  }

  async function openSequenceBatch(batchId) {
    hideSequenceComparisonView();
    model.activeView = "sequence-batch";
    model.selectedSequenceBatch = batchId;
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    const changesRequest = model.sequenceBatchChangesRequest = (model.sequenceBatchChangesRequest || 0) + 1;
    model.sequenceBatchReport = null;
    model.sequenceBatchChanges = null;
    renderSequenceBatches();
    notice("");
    exportHref();
    showEmpty("Verifying sequence batch", "Loading the immutable aggregate batch report and its exact motif prevalence rows.");
    try {
      const [report, changes] = await Promise.all([
        getJson(`/v1/sequence-batches/${encodeURIComponent(batchId)}/report.json`),
        getJson(`/v1/sequence-batches/${encodeURIComponent(batchId)}?${sequenceBatchFilterQuery(0).toString()}`),
      ]);
      if (request !== model.selectionRequest || changesRequest !== model.sequenceBatchChangesRequest || model.activeView !== "sequence-batch" || model.selectedSequenceBatch !== batchId) return;
      if (report.schema !== "glio-noncode.sequence-haplotype-batch-analysis.v1" || report.status !== "completed" || !report.source || !report.design || changes.schema !== "glio-noncode.sequence-haplotype-batch-changes.v1" || changes.offset !== 0 || typeof changes.has_more !== "boolean" || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid sequence batch projection.");
      model.sequenceBatchReport = report;
      model.sequenceBatchChanges = changes;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("sequence-analysis-view").hidden = true;
      $("sequence-review-view").hidden = true;
      $("sequence-batch-view").hidden = false;
      renderSequenceBatch();
      exportHref();
      announceSelection(`Sequence batch ${batchId} opened. ${formatCount(report.design.analysis_count)} analyses and ${formatCount(changes.total_changes)} motif rows.`);
    } catch (error) {
      if (request !== model.selectionRequest || model.activeView !== "sequence-batch" || model.selectedSequenceBatch !== batchId) return;
      notice(`The selected sequence batch could not be verified. ${error.message}`, true);
      showEmpty("Sequence batch unavailable", "The selected aggregate batch report could not be verified, so its detail panels remain hidden.");
    }
  }

  async function openSequenceComparison(comparisonId) {
    hideSequenceComparisonView();
    model.activeView = "sequence-comparison";
    model.selectedSequenceComparison = comparisonId;
    const request = model.sequenceComparisonRequest = (model.sequenceComparisonRequest || 0) + 1;
    model.sequenceComparisonReport = null;
    model.sequenceComparisonChanges = null;
    renderSequenceComparisons();
    notice("");
    exportHref();
    showEmpty("Verifying sequence comparison", "Loading the immutable batch comparison and its aggregate motif prevalence deltas.");
    try {
      const params = sequenceComparisonFilterQuery();
      params.set("limit", "50");
      params.set("offset", "0");
      const [report, changes] = await Promise.all([
        getJson(`/v1/sequence-comparisons/${encodeURIComponent(comparisonId)}/report.json`),
        getJson(`/v1/sequence-comparisons/${encodeURIComponent(comparisonId)}?${params.toString()}`),
      ]);
      if (request !== model.sequenceComparisonRequest || model.activeView !== "sequence-comparison" || model.selectedSequenceComparison !== comparisonId) return;
      if (report.schema !== "glio-noncode.sequence-haplotype-batch-comparison.v1" || report.status !== "completed" || !report.source || !report.left || !report.right || changes.schema !== "glio-noncode.sequence-batch-comparison-changes.v1" || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid sequence comparison projection.");
      model.sequenceComparisonReport = report;
      model.sequenceComparisonChanges = changes;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("geo-review-view").hidden = true;
      $("geo-preflight-view").hidden = true;
      $("sequence-analysis-view").hidden = true;
      $("sequence-review-view").hidden = true;
      $("sequence-batch-view").hidden = true;
      $("sequence-comparison-view").hidden = false;
      renderSequenceComparison();
      exportHref();
      announceSelection(`Sequence comparison opened. ${formatCount(changes.total_changes)} aggregate prevalence changes.`);
    } catch (error) {
      if (request !== model.sequenceComparisonRequest || model.activeView !== "sequence-comparison" || model.selectedSequenceComparison !== comparisonId) return;
      notice(`The selected sequence comparison could not be verified. ${error.message}`, true);
      showEmpty("Sequence comparison unavailable", "The selected aggregate comparison could not be verified, so its change details remain hidden.");
    }
  }

  function renderSequenceBatch() {
    const report = model.sequenceBatchReport;
    const changes = model.sequenceBatchChanges;
    if (!report || !changes) return;
    const source = report.source;
    const design = report.design;
    $("sequence-batch-title").textContent = `${source.source_id} · ${design.genome_build}`;
    $("sequence-batch-subtitle").textContent = `${source.sequence_interval[0]}:${source.sequence_interval[1]}-${source.sequence_interval[2]} · shared context ${design.shared_context_hash}`;
    $("sequence-batch-address").textContent = report.content_address;
    $("sequence-batch-metric-analyses").textContent = formatCount(design.analysis_count);
    $("sequence-batch-metric-supported").textContent = `${formatCount(design.supported_count)} supported · ${formatCount(design.abstained_count)} abstained`;
    $("sequence-batch-metric-variants").textContent = formatCount(report.records.reduce((total, item) => total + item.variant_count, 0));
    $("sequence-batch-metric-created").textContent = formatCount(report.motif_changes.filter((item) => item.change === "created").length);
    $("sequence-batch-metric-disrupted").textContent = formatCount(report.motif_changes.filter((item) => item.change === "disrupted").length);
    $("sequence-batch-source-version").textContent = source.source_version;
    const provenance = $("sequence-batch-provenance");
    provenance.replaceChildren();
    for (const [label, value] of [["Source", source.source_id], ["Retrieved", source.retrieved_at], ["Sequence hash", source.sequence_hash], ["Response hash", source.response_hash], ["Analyses", design.analysis_count]]) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }
    $("sequence-batch-change-count").textContent = `${formatCount(changes.total_changes)} motif rows`;
    const body = $("sequence-batch-changes-table");
    body.replaceChildren();
    if (!changes.changes.length) body.append(emptyRow(6, "No motif prevalence rows were reported for this batch."));
    for (const item of changes.changes) {
      const row = document.createElement("tr");
      row.append(cell(consistencyText(item.change)), cell(item.name || item.motif_id), cell(item.matched_sequence), cell(formatCount(item.analysis_count)), cell(percent(item.analysis_fraction)), cell(item.source_id));
      body.append(row);
    }
    const changeSummary = changes.filtered_change_summary || {};
    $("sequence-batch-change-filter-summary").textContent = `${formatCount(changeSummary.change_count ?? 0)} filtered change rows · ${formatCount(changeSummary.analysis_count_total ?? 0)} aggregate analyses · ${formatCount(changeSummary.created_count ?? 0)} created / ${formatCount(changeSummary.disrupted_count ?? 0)} disrupted · mean prevalence ${percent(changeSummary.mean_analysis_fraction ?? 0)} · max ${percent(changeSummary.max_analysis_fraction ?? 0)}`;
    $("sequence-batch-change-load-more").hidden = !changes.has_more;
    const limitations = $("sequence-batch-limitations");
    limitations.replaceChildren();
    for (const limitation of report.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  function renderSequenceComparison() {
    const report = model.sequenceComparisonReport;
    const changes = model.sequenceComparisonChanges;
    if (!report || !changes) return;
    const source = report.source;
    const summary = changes.filtered_change_summary || {};
    $("sequence-comparison-title").textContent = `${source.source_id} · batch comparison`;
    $("sequence-comparison-subtitle").textContent = `${formatCount(report.left.analysis_count)} left analyses versus ${formatCount(report.right.analysis_count)} right analyses · ${formatCount(changes.total_changes)} filtered changes`;
    $("sequence-comparison-address").textContent = report.content_address || "Address unavailable";
    $("sequence-comparison-left").textContent = formatCount(report.left.analysis_count);
    $("sequence-comparison-right").textContent = formatCount(report.right.analysis_count);
    $("sequence-comparison-changes").textContent = formatCount(summary.change_count ?? changes.total_changes);
    $("sequence-comparison-change-detail").textContent = `${formatCount(summary.increased_count ?? 0)} increased · ${formatCount(summary.decreased_count ?? 0)} decreased · ${formatCount(summary.not_reported_count ?? 0)} not reported`;
    $("sequence-comparison-delta").textContent = percent(summary.mean_absolute_delta_fraction ?? 0);
    $("sequence-comparison-source-version").textContent = source.source_version || "Version unavailable";
    const provenance = $("sequence-comparison-provenance");
    provenance.replaceChildren();
    const rows = [
      ["Source", source.source_id],
      ["Retrieved", source.retrieved_at],
      ["Sequence interval", `${source.sequence_interval[0]}:${source.sequence_interval[1]}-${source.sequence_interval[2]}`],
      ["Sequence hash", source.sequence_hash],
      ["Left batch report", report.left.content_address],
      ["Right batch report", report.right.content_address],
    ];
    for (const [label, value] of rows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }
    $("sequence-comparison-change-count").textContent = `${formatCount(changes.total_changes)} filtered rows`;
    const body = $("sequence-comparison-changes-table");
    body.replaceChildren();
    if (!changes.changes.length) body.append(emptyRow(8, "No prevalence changes match the selected filters."));
    for (const item of changes.changes) {
      const row = document.createElement("tr");
      row.append(
        cell(consistencyText(item.change)),
        cell(item.name || item.motif_id),
        cell(item.matched_sequence),
        cell(percent(item.left_analysis_fraction)),
        cell(percent(item.right_analysis_fraction)),
        cell(percent(item.delta_fraction)),
        cell(consistencyText(item.direction)),
        cell(item.source_id),
      );
      body.append(row);
    }
    $("sequence-comparison-filter-summary").textContent = `${formatCount(summary.change_count ?? 0)} filtered rows · ${formatCount(summary.created_count ?? 0)} created / ${formatCount(summary.disrupted_count ?? 0)} disrupted · ${formatCount(summary.delta_count ?? 0)} reported deltas · mean absolute delta ${percent(summary.mean_absolute_delta_fraction ?? 0)}`;
    $("sequence-comparison-load-more").hidden = !changes.has_more;
    const limitations = $("sequence-comparison-limitations");
    limitations.replaceChildren();
    for (const limitation of report.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  function sequenceAnalysisFilterQuery(offset = 0) {
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    const motif = $("sequence-analysis-motif-filter").value.trim();
    const change = $("sequence-analysis-change-filter").value;
    if (motif) params.set("motif_contains", motif);
    if (change) params.set("change", change);
    return params;
  }

  function sequenceBatchFilterQuery(offset = 0) {
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    const motif = $("sequence-batch-motif-filter").value.trim();
    const change = $("sequence-batch-change-filter").value;
    if (motif) params.set("motif_contains", motif);
    if (change) params.set("change", change);
    return params;
  }

  function reloadSequenceAnalysisChanges() {
    if (!model.selectedSequence) return;
    if (model.sequenceAnalysisFilterTimer !== null) clearTimeout(model.sequenceAnalysisFilterTimer);
    const request = model.sequenceAnalysisChangesRequest = (model.sequenceAnalysisChangesRequest || 0) + 1;
    model.sequenceAnalysisFilterTimer = setTimeout(async () => {
      model.sequenceAnalysisFilterTimer = null;
      const analysisId = model.selectedSequence;
      try {
        const changes = await getJson(`/v1/sequence-analyses/${encodeURIComponent(analysisId)}?${sequenceAnalysisFilterQuery(0).toString()}`);
        if (request !== model.sequenceAnalysisChangesRequest || model.activeView !== "sequence" || model.selectedSequence !== analysisId) return;
      if (changes.schema !== "glio-noncode.sequence-haplotype-changes.v1" || changes.analysis_id !== analysisId || changes.offset !== 0 || typeof changes.has_more !== "boolean" || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid sequence analysis change page.");
        model.sequenceChanges = changes;
        renderSequenceReport();
        exportHref();
      } catch (error) { if (model.activeView === "sequence") notice(error.message, true); }
    }, 180);
  }

  async function loadMoreSequenceAnalysisChanges() {
    const current = model.sequenceChanges;
    const analysisId = model.selectedSequence;
    if (!current || !analysisId || model.activeView !== "sequence" || !current.has_more) return;
    const request = model.sequenceAnalysisChangesRequest;
    const offset = current.offset + current.changes.length;
    const button = $("sequence-analysis-change-load-more");
    button.disabled = true;
    try {
      const changes = await getJson(`/v1/sequence-analyses/${encodeURIComponent(analysisId)}?${sequenceAnalysisFilterQuery(offset).toString()}`);
      if (request !== model.sequenceAnalysisChangesRequest || model.activeView !== "sequence" || model.selectedSequence !== analysisId) return;
      if (changes.schema !== "glio-noncode.sequence-haplotype-changes.v1" || changes.analysis_id !== analysisId || changes.offset !== offset || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid next sequence analysis change page.");
      model.sequenceChanges = { ...changes, changes: current.changes.concat(changes.changes), offset: 0, limit: current.changes.length + changes.changes.length };
      renderSequenceReport();
      exportHref();
    } catch (error) {
      if (model.activeView === "sequence") notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function reloadSequenceBatchChanges() {
    if (!model.selectedSequenceBatch) return;
    if (model.sequenceBatchFilterTimer !== null) clearTimeout(model.sequenceBatchFilterTimer);
    const request = model.sequenceBatchChangesRequest = (model.sequenceBatchChangesRequest || 0) + 1;
    model.sequenceBatchFilterTimer = setTimeout(async () => {
      model.sequenceBatchFilterTimer = null;
      const batchId = model.selectedSequenceBatch;
      try {
        const changes = await getJson(`/v1/sequence-batches/${encodeURIComponent(batchId)}?${sequenceBatchFilterQuery(0).toString()}`);
        if (request !== model.sequenceBatchChangesRequest || model.activeView !== "sequence-batch" || model.selectedSequenceBatch !== batchId) return;
        if (changes.schema !== "glio-noncode.sequence-haplotype-batch-changes.v1" || changes.batch_id !== batchId || changes.offset !== 0 || typeof changes.has_more !== "boolean" || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid sequence batch change page.");
        model.sequenceBatchChanges = changes;
        renderSequenceBatch();
        exportHref();
      } catch (error) { if (model.activeView === "sequence-batch") notice(error.message, true); }
    }, 180);
  }

  async function loadMoreSequenceBatchChanges() {
    const current = model.sequenceBatchChanges;
    const batchId = model.selectedSequenceBatch;
    if (!current || !batchId || model.activeView !== "sequence-batch" || !current.has_more) return;
    const request = model.sequenceBatchChangesRequest;
    const offset = current.offset + current.changes.length;
    const button = $("sequence-batch-change-load-more");
    button.disabled = true;
    try {
      const changes = await getJson(`/v1/sequence-batches/${encodeURIComponent(batchId)}?${sequenceBatchFilterQuery(offset).toString()}`);
      if (request !== model.sequenceBatchChangesRequest || model.activeView !== "sequence-batch" || model.selectedSequenceBatch !== batchId) return;
      if (changes.schema !== "glio-noncode.sequence-haplotype-batch-changes.v1" || changes.batch_id !== batchId || changes.offset !== offset || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid next sequence batch change page.");
      model.sequenceBatchChanges = { ...changes, changes: current.changes.concat(changes.changes), offset: 0, limit: current.changes.length + changes.changes.length };
      renderSequenceBatch();
      exportHref();
    } catch (error) {
      if (model.activeView === "sequence-batch") notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function sequenceComparisonFilterQuery() {
    const params = new URLSearchParams();
    const motif = $("sequence-comparison-motif-filter").value.trim();
    const change = $("sequence-comparison-change-filter").value;
    const direction = $("sequence-comparison-direction-filter").value;
    if (motif) params.set("motif_contains", motif);
    if (change) params.set("change", change);
    if (direction) params.set("direction", direction);
    return params;
  }

  function reloadSequenceComparisonChanges() {
    if (!model.selectedSequenceComparison) return;
    if (model.sequenceComparisonFilterTimer !== null) clearTimeout(model.sequenceComparisonFilterTimer);
    model.sequenceComparisonFilterTimer = setTimeout(async () => {
      model.sequenceComparisonFilterTimer = null;
      const params = sequenceComparisonFilterQuery();
      params.set("limit", "50");
      params.set("offset", "0");
      try {
        const changes = await getJson(`/v1/sequence-comparisons/${encodeURIComponent(model.selectedSequenceComparison)}?${params.toString()}`);
        if (model.activeView !== "sequence-comparison" || changes.schema !== "glio-noncode.sequence-batch-comparison-changes.v1") return;
        model.sequenceComparisonChanges = changes;
        renderSequenceComparison();
        exportHref();
      } catch (error) { if (model.activeView === "sequence-comparison") notice(error.message, true); }
    }, 180);
  }

  async function loadMoreSequenceComparisonChanges() {
    const current = model.sequenceComparisonChanges;
    const comparisonId = model.selectedSequenceComparison;
    if (!current || !comparisonId || !current.has_more) return;
    const request = model.sequenceComparisonRequest;
    const button = $("sequence-comparison-load-more");
    button.disabled = true;
    try {
      const params = sequenceComparisonFilterQuery();
      params.set("limit", "50");
      params.set("offset", String(current.changes.length));
      const page = await getJson(`/v1/sequence-comparisons/${encodeURIComponent(comparisonId)}?${params.toString()}`);
      if (request !== model.sequenceComparisonRequest || model.activeView !== "sequence-comparison" || model.selectedSequenceComparison !== comparisonId) return;
      if (page.schema !== "glio-noncode.sequence-batch-comparison-changes.v1" || page.comparison_id !== comparisonId || page.offset !== current.changes.length || !Array.isArray(page.changes)) throw new Error("The local API returned an invalid next comparison page.");
      model.sequenceComparisonChanges = { ...page, changes: current.changes.concat(page.changes), offset: 0, limit: current.changes.length + page.changes.length };
      renderSequenceComparison();
    } catch (error) {
      if (model.activeView === "sequence-comparison") notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function openSequenceReview() {
    hideSequenceComparisonView();
    const request = model.sequenceReviewRequest = (model.sequenceReviewRequest || 0) + 1;
    const motifRequest = model.sequenceReviewMotifRequest = (model.sequenceReviewMotifRequest || 0) + 1;
    model.activeView = "sequence-review";
    model.sequenceReviewSummary = null;
    model.sequenceReviewVerification = null;
    model.sequenceReviewMotifs = null;
    notice("");
    exportHref();
    showEmpty("Verifying sequence archive", "Opening bounded catalog and motif-activity projections without exposing raw bases.");
    try {
      const [summary, verification, motifs] = await Promise.all([
        getJson("/v1/sequence-review/summary"),
        getJson("/v1/sequence-review/verify"),
        getJson("/v1/sequence-review/motifs?limit=100&offset=0"),
      ]);
      if (request !== model.sequenceReviewRequest || motifRequest !== model.sequenceReviewMotifRequest || model.activeView !== "sequence-review") return;
      if (summary.schema !== "glio-noncode.sequence-review-summary.v1" || verification.schema !== "glio-noncode.sequence-review-verification.v1" || !Array.isArray(verification.results) || !Number.isSafeInteger(verification.record_count) || !Number.isSafeInteger(verification.verified_count) || !Number.isSafeInteger(verification.failed_count) || motifs.schema !== "glio-noncode.sequence-review-motifs.v1" || motifs.offset !== 0 || typeof motifs.has_more !== "boolean" || !Array.isArray(motifs.rows)) throw new Error("The local API returned an invalid sequence review projection.");
      model.sequenceReviewSummary = summary;
      model.sequenceReviewVerification = verification;
      model.sequenceReviewMotifs = motifs;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("sequence-analysis-view").hidden = true;
      $("sequence-batch-view").hidden = true;
      $("sequence-review-view").hidden = false;
      renderSequenceReview();
      exportHref();
      announceSelection(`Sequence archive review opened. ${formatCount(verification.verified_count)} objects verified, ${formatCount(verification.failed_count)} failed, and ${formatCount(motifs.total_count)} exact motif activity rows.`);
    } catch (error) {
      if (request !== model.sequenceReviewRequest || model.activeView !== "sequence-review") return;
      notice(`The sequence archive review could not be verified. ${error.message}`, true);
      showEmpty("Sequence archive unavailable", "The saved sequence catalog could not be verified, so aggregate activity remains hidden.");
    }
  }

  function renderSequenceReview() {
    const summary = model.sequenceReviewSummary;
    const verification = model.sequenceReviewVerification;
    const motifs = model.sequenceReviewMotifs;
    if (!summary || !verification || !motifs) return;
    const analyses = summary.catalogs.sequence_analyses;
    const batches = summary.catalogs.sequence_batches;
    const comparisons = summary.catalogs.sequence_comparisons || {};
    const changes = Number(analyses.created_motif_count || 0) + Number(analyses.disrupted_motif_count || 0) + Number(batches.created_change_count || 0) + Number(batches.disrupted_change_count || 0);
    $("sequence-review-subtitle").textContent = `${formatCount(analyses.record_count || 0)} single analyses · ${formatCount(batches.record_count || 0)} aggregate batches · ${formatCount(comparisons.record_count || 0)} saved comparisons · ${formatCount(changes)} saved change records`;
    $("sequence-review-address").textContent = summary.content_address || "Address unavailable";
    $("sequence-review-analyses").textContent = formatCount(analyses.record_count || 0);
    const completeReceipts = Number(analyses.reports_with_complete_download_receipts_count || 0);
    const analysisCount = Number(analyses.record_count || 0);
    $("sequence-review-analysis-detail").textContent = `${formatCount(analyses.supported_count || 0)} supported · ${formatCount(analyses.abstained_count || 0)} abstained · ${formatCount(completeReceipts)}/${formatCount(analysisCount)} complete download receipts`;
    $("sequence-review-batches").textContent = formatCount(batches.record_count || 0);
    $("sequence-review-batch-detail").textContent = `${formatCount(batches.supported_count || 0)} supported analyses`;
    $("sequence-review-changes").textContent = formatCount(changes);
    $("sequence-review-integrity").textContent = verification.failed_count ? `${formatCount(verification.failed_count)} failed` : `${formatCount(verification.verified_count)} verified`;
    $("sequence-review-motif-count").textContent = `${formatCount(motifs.total_count)} exact rows`;
    const body = $("sequence-review-motif-table");
    body.replaceChildren();
    if (!motifs.rows.length) body.append(emptyRow(6, "No exact motif activity matches the selected filters."));
    for (const row of motifs.rows) {
      const tr = document.createElement("tr");
      tr.append(cell(consistencyText(row.change)), cell(row.name || row.motif_id), cell(row.matched_sequence), cell(formatCount(row.single_analysis_count)), cell(formatCount(row.batch_count)), cell(percent(row.max_batch_fraction)));
      body.append(tr);
    }
    const motifSummary = motifs.filtered_motif_summary || {};
    const sourceCounts = motifSummary.motif_source_id_counts || {};
    const sourceCountText = Object.entries(sourceCounts).map(([source, count]) => `${source}: ${formatCount(count)}`).join(" · ") || "none";
    $("sequence-review-motif-filter-summary").textContent = `${formatCount(motifSummary.row_count ?? 0)} filtered motif rows · ${formatCount(motifSummary.occurrence_count ?? 0)} occurrences · ${formatCount(motifSummary.created_row_count ?? 0)} created / ${formatCount(motifSummary.disrupted_row_count ?? 0)} disrupted · sources ${sourceCountText}`;
    $("sequence-review-motif-load-more").hidden = !motifs.has_more;
    const integrityCopy = $("sequence-review-integrity-copy");
    integrityCopy.replaceChildren();
    for (const text of [
      "Catalog records are validated before they enter this projection.",
      `The verification endpoint independently reopened ${formatCount(verification.verified_count)} object(s) and reported ${formatCount(verification.failed_count)} failure(s).`,
      "Raw bases, genotype strings, sample IDs, and subject IDs are not emitted here.",
    ]) integrityCopy.append(element("p", "geo-limitation", text));
    const verificationBody = $("sequence-review-verification-table");
    verificationBody.replaceChildren();
    if (!verification.results.length) verificationBody.append(emptyRow(4, "No saved report objects require verification."));
    for (const result of verification.results) {
      const detail = result.status === "verified" ? result.content_address : `${result.error?.code || "verification_failure"}: ${result.error?.message || "Object could not be reopened."}`;
      const row = document.createElement("tr");
      row.append(cell(consistencyText(result.kind)), cell(shortened(result.record_id, 34)), cell(consistencyText(result.status)), cell(detail));
      verificationBody.append(row);
    }
    $("sequence-review-verification-summary").textContent = `${formatCount(verification.record_count)} objects reviewed · ${formatCount(verification.verified_count)} verified · ${formatCount(verification.failed_count)} failed · aggregate-only ledger`;
    const limitations = $("sequence-review-limitations");
    limitations.replaceChildren();
    for (const text of summary.limitations || []) limitations.append(element("p", "geo-limitation", text));
  }

  function sequenceReviewMotifQuery(offset = 0) {
    const params = new URLSearchParams({ limit: "100", offset: String(offset) });
    const motif = $("sequence-review-motif-filter").value.trim();
    const sourceId = $("sequence-review-source-filter").value.trim();
    const genomeBuild = $("sequence-review-genome-filter").value.trim();
    const change = $("sequence-review-change-filter").value;
    if (motif) params.set("motif_contains", motif);
    if (sourceId) params.set("source_id", sourceId);
    if (genomeBuild) params.set("genome_build", genomeBuild);
    if (change) params.set("change", change);
    return params;
  }

  function reloadSequenceReviewMotifs() {
    if (model.sequenceReviewFilterTimer !== null) clearTimeout(model.sequenceReviewFilterTimer);
    const request = model.sequenceReviewMotifRequest = (model.sequenceReviewMotifRequest || 0) + 1;
    model.sequenceReviewFilterTimer = setTimeout(async () => {
      model.sequenceReviewFilterTimer = null;
      const params = sequenceReviewMotifQuery(0);
      try {
        const motifs = await getJson(`/v1/sequence-review/motifs?${params.toString()}`);
        if (request !== model.sequenceReviewMotifRequest || model.activeView !== "sequence-review" || motifs.schema !== "glio-noncode.sequence-review-motifs.v1" || motifs.offset !== 0 || !Array.isArray(motifs.rows)) return;
        model.sequenceReviewMotifs = motifs;
        renderSequenceReview();
        exportHref();
      } catch (error) { if (model.activeView === "sequence-review") notice(error.message, true); }
    }, 180);
  }

  async function loadMoreSequenceReviewMotifs() {
    const current = model.sequenceReviewMotifs;
    if (!current || model.activeView !== "sequence-review" || !current.has_more) return;
    const request = model.sequenceReviewMotifRequest;
    const offset = current.offset + current.rows.length;
    const button = $("sequence-review-motif-load-more");
    button.disabled = true;
    try {
      const motifs = await getJson(`/v1/sequence-review/motifs?${sequenceReviewMotifQuery(offset).toString()}`);
      if (request !== model.sequenceReviewMotifRequest || model.activeView !== "sequence-review") return;
      if (motifs.schema !== "glio-noncode.sequence-review-motifs.v1" || motifs.offset !== offset || !Array.isArray(motifs.rows)) throw new Error("The local API returned an invalid next sequence motif page.");
      model.sequenceReviewMotifs = { ...motifs, rows: current.rows.concat(motifs.rows), offset: 0, limit: current.rows.length + motifs.rows.length };
      renderSequenceReview();
      exportHref();
    } catch (error) {
      if (model.activeView === "sequence-review") notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function renderSequenceReport() {
    const report = model.sequenceReport;
    const changes = model.sequenceChanges;
    if (!report || !changes) return;
    const source = report.source;
    const inputs = report.inputs;
    const analysis = report.analysis;
    $("sequence-title").textContent = `${source.source_id} · ${inputs.genome_build}`;
    $("sequence-subtitle").textContent = `${source.sequence_interval[0]}:${source.sequence_interval[1]}-${source.sequence_interval[2]} · ${analysis.phase_set} · haplotype ${analysis.haplotype_index}`;
    $("sequence-state").textContent = report.analysis_state;
    $("sequence-report-address").textContent = report.content_address;
    $("sequence-metric-variants").textContent = formatCount(inputs.variant_count);
    $("sequence-metric-motifs").textContent = formatCount(inputs.motif_count);
    $("sequence-metric-created").textContent = formatCount(analysis.created_hits.length);
    $("sequence-metric-disrupted").textContent = formatCount(analysis.disrupted_hits.length);
    $("sequence-source-version").textContent = source.source_version;
    const provenance = $("sequence-provenance");
    provenance.replaceChildren();
    for (const [label, value] of [["Source", source.source_id], ["Retrieved", source.retrieved_at], ["Sequence hash", source.sequence_hash], ["Variant IDs", inputs.variants.map((item) => item.variant_id).join(" · ")]]) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }
    const downloadProvenance = $("sequence-download-provenance");
    downloadProvenance.replaceChildren();
    const downloadedInputs = Array.isArray(source.downloaded_inputs) ? source.downloaded_inputs : [];
    if (!downloadedInputs.length) {
      downloadProvenance.append(element("div", "geo-provenance-item", "No per-file download receipts were supplied."));
    } else {
      for (const receipt of downloadedInputs) {
        const block = element("div", "geo-provenance-item");
        const role = String(receipt.role || "input").toUpperCase();
        const sourceText = [receipt.source_id, receipt.source_version].filter(Boolean).join(" · ") || "Source unavailable";
        const digestText = receipt.sha256 || "Digest unavailable";
        const sizeText = Number.isSafeInteger(receipt.size_bytes) ? `${formatCount(receipt.size_bytes)} bytes` : "size unavailable";
        const compressionText = receipt.compression || "compression unavailable";
        block.append(
          element("span", "control-label", `${role} download receipt`),
          element("span", "geo-provenance-value", `${sourceText} · ${sizeText} · ${compressionText} · ${digestText}`),
        );
        downloadProvenance.append(block);
      }
    }
    const body = $("sequence-changes-table");
    body.replaceChildren();
    if (!changes.changes.length) {
      body.append(emptyRow(6, "No motif changes were reported for this phased haplotype."));
    } else {
      for (const hit of changes.changes) {
        const row = document.createElement("tr");
        row.append(cell(consistencyText(hit.change)), cell(hit.name || hit.motif_id), cell(hit.matched_sequence), cell(hit.strand), cell((hit.variant_ids || []).join(", ")), cell(hit.reference_interval ? hit.reference_interval.join(":") : "Not contiguous"));
        body.append(row);
      }
    }
    const changeSummary = changes.filtered_change_summary || {};
    $("sequence-change-count").textContent = `${formatCount(changes.total_changes)} motif changes`;
    $("sequence-analysis-change-filter-summary").textContent = `${formatCount(changeSummary.change_count ?? changes.total_changes)} filtered motif changes · ${formatCount(changeSummary.created_count ?? 0)} created · ${formatCount(changeSummary.disrupted_count ?? 0)} disrupted · ${formatCount(changes.unfiltered_change_count)} total changes in the verified report`;
    $("sequence-analysis-change-load-more").hidden = !changes.has_more;
    const limitations = $("sequence-limitations");
    limitations.replaceChildren();
    for (const limitation of report.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  function consistencyText(value) {
    return String(value || "—").replaceAll("_", " ");
  }

  function preflightMetricRows(summary) {
    const rows = [];
    const append = (key, value) => {
      if (/(agent|language|sample[_-]?id|pair[_-]?id|url|uri)/i.test(key)) return;
      if (value === null || ["string", "number", "boolean"].includes(typeof value)) rows.push([key, value]);
    };
    for (const [key, value] of Object.entries(summary || {})) {
      if (value === null || ["string", "number", "boolean"].includes(typeof value)) append(key, value);
      else if (value && typeof value === "object" && !Array.isArray(value)) {
        for (const [nestedKey, nestedValue] of Object.entries(value)) {
          if (nestedKey === "field" || nestedKey === "values") continue;
          append(`${key}_${nestedKey}`, nestedValue);
        }
      }
    }
    return rows;
  }

  function renderGeoPreflight() {
    const report = model.geoPreflightReport;
    if (!report) return;
    const source = report.source || {};
    const summary = report.summary || {};
    const catalogRow = model.geoPreflights.find((item) => item.preflight_id === model.selectedGeoPreflight) || {};
    const kind = catalogRow.kind || consistencyText(report.schema?.replace("glio-noncode.geo-", "").replace(".v1", ""));
    const sampleCount = source.sample_count ?? catalogRow.sample_count ?? summary.sample_count;
    const featureCount = source.feature_count ?? catalogRow.feature_count ?? summary.feature_row_count;
    const retrieval = source.retrieval || source.count_matrix?.retrieval || source.sample_metadata?.retrieval;
    const provenanceRows = [
      ["Accession", source.accession],
      ["Retrieval", retrieval],
      ["Sample count", sampleCount],
      ["Feature count", featureCount],
    ];
    if (source.source_sha256) {
      provenanceRows.push(["Source digest", source.source_sha256]);
    } else {
      provenanceRows.push(
        ["Count matrix digest", source.count_matrix?.source_sha256],
        ["Metadata digest", source.sample_metadata?.source_sha256],
      );
    }
    $("geo-preflight-title").textContent = `${source.accession || "GEO"} · ${consistencyText(kind)}`;
    $("geo-preflight-subtitle").textContent = `${retrieval || "retrieval unavailable"} · ${formatCount(sampleCount)} samples · ${formatCount(featureCount)} features`;
    $("geo-preflight-state").textContent = report.status || "Unavailable";
    $("geo-preflight-address").textContent = report.content_address || "Address unavailable";
    $("geo-preflight-samples").textContent = formatCount(sampleCount);
    $("geo-preflight-features").textContent = formatCount(featureCount);
    $("geo-preflight-kind").textContent = consistencyText(kind);
    $("geo-preflight-retrieval").textContent = retrieval || "—";
    const provenance = $("geo-preflight-provenance");
    provenance.replaceChildren();
    for (const [label, value] of provenanceRows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value ?? "—"));
      provenance.append(block);
    }
    const metricRows = preflightMetricRows(summary);
    const designState = report.design?.state;
    if (typeof designState === "string") metricRows.push(["design_state", designState]);
    $("geo-preflight-metric-count").textContent = `${formatCount(metricRows.length)} metrics`;
    const metrics = $("geo-preflight-metrics");
    metrics.replaceChildren();
    if (!metricRows.length) metrics.append(emptyRow(2, "No bounded scalar metrics were reported."));
    for (const [key, value] of metricRows) {
      const row = document.createElement("tr");
      row.append(cell(consistencyText(key)), cell(value == null ? "Not available" : value));
      metrics.append(row);
    }
    const limitations = $("geo-preflight-limitations");
    limitations.replaceChildren();
    for (const limitation of report.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
    if (!limitations.childElementCount) limitations.append(element("p", "muted", "No limitation notes were supplied."));
  }

  async function openGeoPreflight(preflightId) {
    hideSequenceComparisonView();
    model.activeView = "geo-preflight";
    model.selectedGeoPreflight = preflightId;
    model.geoPreflightReport = null;
    const request = model.geoPreflightRequest = (model.geoPreflightRequest || 0) + 1;
    renderGeoPreflights();
    notice("");
    exportHref();
    showEmpty("Verifying GEO preflight", "Reopening the preparation report through its content address. Private detail fields remain outside the catalog projection.");
    try {
      const report = await getJson(`/v1/geo-preflights/${encodeURIComponent(preflightId)}/report.json`);
      if (request !== model.geoPreflightRequest || model.activeView !== "geo-preflight" || model.selectedGeoPreflight !== preflightId) return;
      const catalogRow = model.geoPreflights.find((item) => item.preflight_id === preflightId);
      if (!report.schema || report.status !== "completed" || !report.content_address || !report.source || !report.summary || (catalogRow?.report_schema && catalogRow.report_schema !== report.schema)) {
        throw new Error("The local API returned an invalid GEO preflight report.");
      }
      model.geoPreflightReport = report;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("geo-review-view").hidden = true;
      $("geo-preflight-view").hidden = false;
      renderGeoPreflight();
      exportHref();
      announceSelection(`GEO ${consistencyText(catalogRow?.kind || "preflight")} opened for ${report.source.accession || "the selected Series"}.`);
    } catch (error) {
      if (request !== model.geoPreflightRequest || model.activeView !== "geo-preflight") return;
      notice(`The GEO preflight could not be verified. ${error.message}`, true);
      showEmpty("GEO preflight unavailable", "The selected preparation report could not be verified, so its details remain hidden.");
    }
  }

  async function openGeoReview() {
    hideSequenceComparisonView();
    model.activeView = "geo-review";
    const request = model.geoReviewViewRequest = (model.geoReviewViewRequest || 0) + 1;
    notice("");
    showEmpty("Verifying GEO workspace", "Reopening every saved GEO catalog record and report object through its content address.");
    try {
      const summary = await getJson("/v1/geo-review/summary?verify_reports=true");
      if (request !== model.geoReviewViewRequest || model.activeView !== "geo-review") return;
      if (summary.schema !== "glio-noncode.geo-review-summary.v1" || !summary.catalogs || !summary.integrity) throw new Error("The local API returned an invalid GEO workspace summary.");
      model.geoReviewSummary = summary;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-review-view").hidden = false;
      renderGeoReviewSummary();
      renderGeoReviewDetail();
      exportHref();
      announceSelection(`GEO workspace health opened. ${formatCount(summary.integrity.verification_failure_count)} verification failures.`);
    } catch (error) {
      if (request !== model.geoReviewViewRequest || model.activeView !== "geo-review") return;
      notice(`The GEO workspace could not be verified. ${error.message}`, true);
      showEmpty("GEO workspace unavailable", "The saved GEO catalogs could not be verified, so archive details remain hidden.");
    }
  }

  async function openGeoConsistency(comparisonId) {
    hideSequenceComparisonView();
    if (model.selectedGeoConsistency !== comparisonId) resetGeoConsistencyFilters();
    model.activeView = "geo-consistency";
    model.selectedGeoConsistency = comparisonId;
    const request = model.geoConsistencyRequest = (model.geoConsistencyRequest || 0) + 1;
    model.geoConsistency = null;
    renderGeoConsistencyRecords();
    notice("");
    showEmpty("Verifying paired-count comparison", "Loading the immutable cross-study record and its aggregate direction projection.");
    try {
      const params = geoConsistencyFilterQuery();
      params.set("limit", "100");
      params.set("offset", "0");
      const page = await getJson(`/v1/geo-count-consistency/${encodeURIComponent(comparisonId)}?${params.toString()}`);
      if (request !== model.geoConsistencyRequest || model.activeView !== "geo-consistency" || model.selectedGeoConsistency !== comparisonId) return;
      if (page.schema !== "glio-noncode.geo-count-consistency-page.v1" || page.comparison_id !== comparisonId || !Array.isArray(page.features) || !page.summary) throw new Error("The local API returned an invalid paired-count consistency projection.");
      model.geoConsistency = page;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-consistency-view").hidden = false;
      renderGeoConsistency();
      exportHref();
      announceSelection(`Paired-count comparison opened. ${formatCount(page.summary.study_count)} studies and ${formatCount(page.summary.feature_count)} exact source feature IDs.`);
    } catch (error) {
      if (request !== model.geoConsistencyRequest || model.activeView !== "geo-consistency" || model.selectedGeoConsistency !== comparisonId) return;
      notice(`The GEO paired-count comparison could not be verified. ${error.message}`, true);
      showEmpty("Paired-count comparison unavailable", "The saved paired-count comparison could not be verified, so its feature details remain hidden.");
    }
  }

  async function openGeoExpressionConsistency(comparisonId) {
    hideSequenceComparisonView();
    if (model.selectedGeoExpressionConsistency !== comparisonId) resetGeoExpressionConsistencyFilters();
    model.activeView = "geo-expression-consistency";
    model.selectedGeoExpressionConsistency = comparisonId;
    const request = model.geoExpressionConsistencyRequest = (model.geoExpressionConsistencyRequest || 0) + 1;
    model.geoExpressionConsistency = null;
    renderGeoExpressionConsistencyRecords();
    notice("");
    showEmpty("Verifying expression comparison", "Loading the immutable cross-study record and its aggregate direction projection.");
    try {
      const params = geoExpressionConsistencyFilterQuery();
      params.set("limit", "100");
      params.set("offset", "0");
      const page = await getJson(`/v1/geo-expression-consistency/${encodeURIComponent(comparisonId)}?${params.toString()}`);
      if (request !== model.geoExpressionConsistencyRequest || model.activeView !== "geo-expression-consistency" || model.selectedGeoExpressionConsistency !== comparisonId) return;
      if (page.schema !== "glio-noncode.geo-expression-consistency-page.v1" || page.comparison_id !== comparisonId || !Array.isArray(page.features) || !page.summary) throw new Error("The local API returned an invalid expression consistency projection.");
      model.geoExpressionConsistency = page;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("geo-expression-consistency-view").hidden = false;
      renderGeoExpressionConsistency();
      exportHref();
      announceSelection(`Expression comparison opened. ${formatCount(page.summary.study_count)} studies and ${formatCount(page.summary.feature_count)} exact source feature IDs.`);
    } catch (error) {
      if (request !== model.geoExpressionConsistencyRequest || model.activeView !== "geo-expression-consistency" || model.selectedGeoExpressionConsistency !== comparisonId) return;
      notice(`The GEO expression comparison could not be verified. ${error.message}`, true);
      showEmpty("Expression comparison unavailable", "The saved expression comparison could not be verified, so its feature details remain hidden.");
    }
  }

  async function compareGeoExpressionAnalyses() {
    const analysisIds = [...new Set(model.geoExpressionCompareIds)];
    const featureIds = expressionConsistencyFeatureIds();
    if (analysisIds.length < 2 || !featureIds.length) {
      updateGeoExpressionCompareControls();
      return;
    }
    const request = model.geoExpressionConsistencyRequest = (model.geoExpressionConsistencyRequest || 0) + 1;
    model.activeView = "geo-expression-consistency";
    model.geoExpressionConsistency = null;
    notice("");
    showEmpty("Saving expression comparison", "Verifying compatible saved studies and preserving each source effect separately.");
    try {
      const response = await fetch("/v1/geo-expression-consistency", {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ analysis_ids: analysisIds, feature_ids: featureIds }),
      });
      const created = await response.json();
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${created.message || "Comparison rejected."}`);
      if (!created.record?.comparison_id) throw new Error("The local API returned an invalid consistency record.");
      await loadGeoExpressionConsistencyRecords();
      await openGeoExpressionConsistency(created.record.comparison_id);
    } catch (error) {
      if (request !== model.geoExpressionConsistencyRequest || model.activeView !== "geo-expression-consistency") return;
      notice(`The GEO expression comparison could not be verified. ${error.message}`, true);
      showEmpty("Expression comparison unavailable", "The selected studies were not compatible or could not be verified.");
    }
  }

  function renderGeoExpressionConsistency() {
    const page = model.geoExpressionConsistency;
    if (!page) return;
    const summary = page.summary;
    const body = $("geo-expression-consistency-table");
    $("geo-expression-consistency-subtitle").textContent = `${formatCount(summary.study_count)} studies · ${formatCount(summary.feature_count)} exact source feature IDs · ${String(summary.fdr_method).toUpperCase()} q ≤ ${summary.fdr_threshold}`;
    $("geo-expression-consistency-address").textContent = page.report_address || "Address unavailable";
    $("geo-expression-consistency-studies").textContent = formatCount(summary.study_count);
    $("geo-expression-consistency-features-count").textContent = formatCount(summary.feature_count);
    $("geo-expression-consistency-concordant").textContent = formatCount(summary.concordant_feature_count);
    $("geo-expression-consistency-discordant").textContent = formatCount(summary.discordant_feature_count);
    $("geo-expression-consistency-coverage").textContent = `${formatCount(summary.ranked_feature_count_total || 0)} + ${formatCount(summary.additional_tracked_feature_count_total || 0)}`;
    const expressionFiltered = page.total_features !== page.unfiltered_feature_count;
    $("geo-expression-consistency-result-count").textContent = expressionFiltered
      ? `${formatCount(page.features.length)} shown · ${formatCount(page.total_features)} filtered`
      : `${formatCount(page.features.length)} feature rows`;
    const filteredSummary = page.filtered_feature_summary || {};
    const directionCounts = filteredSummary.direction_consistency_counts || {};
    const fdrDirectionCounts = filteredSummary.fdr_direction_consistency_counts || {};
    $("geo-expression-consistency-filter-summary").textContent = `${formatCount(filteredSummary.feature_count ?? 0)} filtered rows · directions ${formatCount(directionCounts.concordant_among_reported || 0)} concordant / ${formatCount(directionCounts.discordant_among_reported || 0)} discordant · FDR ${formatCount(fdrDirectionCounts.concordant_among_fdr_significant || 0)} concordant / ${formatCount(fdrDirectionCounts.discordant_among_fdr_significant || 0)} discordant`;
    body.replaceChildren();
    if (!page.features.length) body.append(emptyRow(5, "No requested feature IDs were reported."));
    for (const feature of page.features) {
      const featureSummary = feature.summary || {};
      const observations = (feature.studies || []).map((study) => `${study.accession}: ${consistencyText(study.effect_direction || study.result_state)}`).join(" · ");
      const row = document.createElement("tr");
      row.append(cell(feature.feature_id), cell((featureSummary.distinct_directions || []).map(consistencyText).join(", ") || "—"), cell(consistencyText(featureSummary.direction_consistency)), cell(consistencyText(featureSummary.fdr_significant_direction_consistency)), cell(observations));
      body.append(row);
    }
    const limitations = $("geo-expression-consistency-limitations");
    limitations.replaceChildren();
    for (const limitation of page.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  async function compareGeoAnalyses() {
    const analysisIds = [...new Set(model.geoCompareIds)];
    const featureIds = consistencyFeatureIds();
    if (analysisIds.length < 2 || !featureIds.length) {
      updateGeoCompareControls();
      return;
    }
    const request = model.geoConsistencyRequest = (model.geoConsistencyRequest || 0) + 1;
    model.activeView = "geo-consistency";
    model.geoConsistency = null;
    notice("");
    exportHref();
    showEmpty("Saving paired-count comparison", "Verifying compatible saved studies and preserving each study's aggregate results separately.");
    try {
      const response = await fetch("/v1/geo-count-consistency", {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ analysis_ids: analysisIds, feature_ids: featureIds }),
      });
      const created = await response.json();
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${created.message || "Comparison rejected."}`);
      if (!created.record?.comparison_id) throw new Error("The local API returned an invalid paired-count consistency record.");
      await loadGeoConsistencyRecords();
      await openGeoConsistency(created.record.comparison_id);
    } catch (error) {
      if (request !== model.geoConsistencyRequest || model.activeView !== "geo-consistency") return;
      notice(`The GEO consistency comparison could not be verified. ${error.message}`, true);
      showEmpty("GEO comparison unavailable", "The selected reports were not comparable or could not be verified.");
    }
  }

  async function openGeoSensitivity(comparisonId) {
    hideSequenceComparisonView();
    if (model.selectedGeoSensitivity !== comparisonId) resetGeoSensitivityFilters();
    model.activeView = "geo-sensitivity";
    model.selectedGeoSensitivity = comparisonId;
    const request = model.geoSensitivityRequest = (model.geoSensitivityRequest || 0) + 1;
    model.geoSensitivity = null;
    renderGeoSensitivityRecords();
    notice("");
    exportHref();
    showEmpty("Verifying normalization sensitivity", "Loading the immutable same-source comparison and its aggregate stability projection.");
    try {
      const params = geoSensitivityFilterQuery();
      params.set("limit", "100");
      params.set("offset", "0");
      const page = await getJson(`/v1/geo-count-sensitivity/${encodeURIComponent(comparisonId)}?${params.toString()}`);
      if (request !== model.geoSensitivityRequest || model.activeView !== "geo-sensitivity" || model.selectedGeoSensitivity !== comparisonId) return;
      if (page.schema !== "glio-noncode.geo-count-sensitivity-page.v1" || page.comparison_id !== comparisonId || !Array.isArray(page.features) || !page.summary || !page.comparison) throw new Error("The local API returned an invalid GEO normalization sensitivity projection.");
      model.geoSensitivity = page;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-expression-analysis-view").hidden = true;
      $("geo-consistency-view").hidden = true;
      $("geo-expression-consistency-view").hidden = true;
      $("geo-review-view").hidden = true;
      $("geo-preflight-view").hidden = true;
      $("geo-sensitivity-view").hidden = false;
      renderGeoSensitivity();
      exportHref();
      announceSelection(`GEO normalization sensitivity opened for ${page.comparison.accession}. ${formatCount(page.summary.feature_count)} source feature IDs reviewed.`);
    } catch (error) {
      if (request !== model.geoSensitivityRequest || model.activeView !== "geo-sensitivity" || model.selectedGeoSensitivity !== comparisonId) return;
      notice(`The GEO normalization sensitivity could not be verified. ${error.message}`, true);
      showEmpty("Normalization sensitivity unavailable", "The saved same-source comparison could not be verified, so its feature details remain hidden.");
    }
  }

  async function compareGeoSensitivity() {
    const analysisIds = [...new Set(model.geoCompareIds)];
    const featureIds = consistencyFeatureIds();
    if (analysisIds.length !== 2 || !featureIds.length) {
      updateGeoCompareControls();
      return;
    }
    const request = model.geoSensitivityRequest = (model.geoSensitivityRequest || 0) + 1;
    model.activeView = "geo-sensitivity";
    model.geoSensitivity = null;
    notice("");
    exportHref();
    showEmpty("Saving normalization sensitivity", "Verifying the same source, design, and feature contract before comparing transforms.");
    try {
      const response = await fetch("/v1/geo-count-sensitivity", {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ analysis_ids: analysisIds, feature_ids: featureIds }),
      });
      const created = await response.json();
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${created.message || "Sensitivity comparison rejected."}`);
      if (!created.record?.comparison_id) throw new Error("The local API returned an invalid sensitivity record.");
      await loadGeoSensitivityRecords();
      await openGeoSensitivity(created.record.comparison_id);
    } catch (error) {
      if (request !== model.geoSensitivityRequest || model.activeView !== "geo-sensitivity") return;
      notice(`The GEO normalization sensitivity could not be verified. ${error.message}`, true);
      showEmpty("Normalization sensitivity unavailable", "The selected runs were not compatible or could not be verified.");
    }
  }

  function renderGeoSensitivity() {
    const page = model.geoSensitivity;
    if (!page) return;
    const summary = page.summary;
    const comparison = page.comparison;
    $("geo-sensitivity-subtitle").textContent = `${comparison.accession} · ${formatCount(summary.feature_count)} exact source feature IDs · ${comparison.left_normalization_method} versus ${comparison.right_normalization_method}`;
    $("geo-sensitivity-address").textContent = page.report_address || "Address unavailable";
    $("geo-sensitivity-runs").textContent = formatCount(summary.run_count);
    $("geo-sensitivity-features-count").textContent = formatCount(summary.feature_count);
    $("geo-sensitivity-stable").textContent = formatCount(summary.stable_direction_feature_count);
    $("geo-sensitivity-changed").textContent = formatCount(summary.changed_direction_feature_count);
    $("geo-sensitivity-settings").textContent = `${String(comparison.fdr_method).toUpperCase()} q ≤ ${comparison.fdr_threshold}`;
    const provenance = $("geo-sensitivity-provenance");
    provenance.replaceChildren();
    const runCoverage = (page.runs || []).map((run) => (
      `${run.role}: ${formatCount(run.ranked_feature_count ?? run.reported_feature_count)} ranked · ` +
      `${formatCount(run.additional_tracked_feature_count ?? 0)} tracked`
    )).join(" · ");
    const rows = [
      ["Series", comparison.accession],
      ["Left normalization", comparison.left_normalization],
      ["Right normalization", comparison.right_normalization],
      ["Case group", filterDescription(comparison.case_filters)],
      ["Reference group", filterDescription(comparison.reference_filters)],
      ["Pairing field", comparison.pair_key_column],
      ["Source count digest", comparison.count_matrix_source_sha256],
      ["Report coverage", runCoverage || "Not reported"],
    ];
    for (const [label, value] of rows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }
    const body = $("geo-sensitivity-table");
    body.replaceChildren();
    if (!page.features.length) body.append(emptyRow(6, "No requested feature IDs match the sensitivity filters."));
    for (const feature of page.features) {
      const featureSummary = feature.summary || {};
      const observations = (feature.runs || []).map((run) => {
        const aggregate = run.aggregate_result;
        return `${run.role}: ${consistencyText(aggregate?.effect_direction || run.result_state)}`;
      }).join(" · ");
      const row = document.createElement("tr");
      row.append(
        cell(feature.feature_id),
        cell(consistencyText(featureSummary.direction_sensitivity)),
        cell(consistencyText(featureSummary.fdr_sensitivity)),
        cell(consistencyText(featureSummary.sign_test_fdr_sensitivity)),
        cell(formatEffect(featureSummary.median_effect_delta_right_minus_left)),
        cell(observations),
      );
      body.append(row);
    }
    const filtered = page.total_features !== page.unfiltered_feature_count;
    $("geo-sensitivity-result-count").textContent = filtered
      ? `${formatCount(page.features.length)} shown · ${formatCount(page.total_features)} filtered`
      : `${formatCount(page.features.length)} feature rows`;
    const filteredSummary = page.filtered_feature_summary || {};
    const directionCounts = filteredSummary.direction_sensitivity_counts || {};
    const fdrCounts = filteredSummary.fdr_sensitivity_counts || {};
    const signFdrCounts = filteredSummary.sign_test_fdr_sensitivity_counts || {};
    $("geo-sensitivity-filter-summary").textContent = `${formatCount(filteredSummary.feature_count ?? 0)} filtered rows · direction ${formatCount(directionCounts.stable_direction || 0)} stable / ${formatCount(directionCounts.changed_direction || 0)} changed · FDR ${formatCount(fdrCounts.stable_fdr_significance || 0)} stable / ${formatCount(fdrCounts.changed_fdr_significance || 0)} changed · sign-test FDR ${formatCount(signFdrCounts.stable_sign_test_fdr_significance || 0)} stable / ${formatCount(signFdrCounts.changed_sign_test_fdr_significance || 0)} changed`;
    const limitations = $("geo-sensitivity-limitations");
    limitations.replaceChildren();
    for (const limitation of page.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  function renderGeoConsistency() {
    const report = model.geoConsistency;
    if (!report) return;
    const summary = report.summary;
    const comparison = report.comparison;
    $("geo-consistency-subtitle").textContent = `${formatCount(summary.study_count)} studies · ${formatCount(summary.feature_count)} exact source feature IDs · ${String(comparison.fdr_method).toUpperCase()} q ≤ ${comparison.fdr_threshold}`;
    $("geo-consistency-address").textContent = report.content_address || "Address unavailable";
    $("geo-consistency-studies").textContent = formatCount(summary.study_count);
    $("geo-consistency-features-count").textContent = formatCount(summary.feature_count);
    $("geo-consistency-concordant").textContent = formatCount(summary.concordant_feature_count);
    $("geo-consistency-discordant").textContent = formatCount(summary.discordant_feature_count);
    $("geo-consistency-settings").textContent = `${comparison.normalization_method} · ${String(comparison.fdr_method).toUpperCase()}`;

    const provenance = $("geo-consistency-provenance");
    provenance.replaceChildren();
    const studyCoverage = report.studies.map((study) => (
      `${study.accession}: ${formatCount(study.ranked_feature_count ?? study.reported_feature_count)} ranked · ` +
      `${formatCount(study.additional_tracked_feature_count ?? 0)} tracked`
    )).join(" · ");
    const rows = [
      ["Studies", report.studies.map((study) => study.accession).join(" · ")],
      ["Case group", filterDescription(comparison.case_filters)],
      ["Reference group", filterDescription(comparison.reference_filters)],
      ["Pairing field", comparison.pair_key_column],
      ["Expression scale", comparison.expression_scale],
      ["Direction basis", comparison.effect_direction_basis],
      ["Study coverage", studyCoverage || "Not reported"],
    ];
    for (const [label, value] of rows) {
      const block = element("div", "geo-provenance-item");
      block.append(element("span", "control-label", label), element("span", "geo-provenance-value", value));
      provenance.append(block);
    }

    const body = $("geo-consistency-table");
    body.replaceChildren();
    if (!report.features.length) {
      body.append(emptyRow(6, "No requested feature IDs were reported."));
    } else {
      for (const feature of report.features) {
        const featureSummary = feature.summary || {};
        const observations = (feature.studies || []).map((study) => {
          const aggregate = study.aggregate_result;
          const state = aggregate?.effect_direction || study.result_state;
          return `${study.accession}: ${consistencyText(state)}`;
        }).join(" · ");
        const row = document.createElement("tr");
        row.append(
          cell(feature.feature_id),
          cell((featureSummary.distinct_directions || []).map(consistencyText).join(", ") || "—"),
          cell(consistencyText(featureSummary.direction_consistency)),
          cell(consistencyText(featureSummary.fdr_significant_direction_consistency)),
          cell(consistencyText(featureSummary.sign_test_fdr_significant_direction_consistency)),
          cell(observations),
        );
        body.append(row);
      }
    }
    const countFiltered = report.total_features !== report.unfiltered_feature_count;
    $("geo-consistency-result-count").textContent = countFiltered
      ? `${formatCount(report.features.length)} shown · ${formatCount(report.total_features)} filtered`
      : `${formatCount(report.features.length)} feature rows`;
    const filteredSummary = report.filtered_feature_summary || {};
    const directionCounts = filteredSummary.direction_consistency_counts || {};
    const fdrDirectionCounts = filteredSummary.fdr_direction_consistency_counts || {};
    const signDirectionCounts = filteredSummary.sign_test_direction_consistency_counts || {};
    $("geo-consistency-filter-summary").textContent = `${formatCount(filteredSummary.feature_count ?? 0)} filtered rows · directions ${formatCount(directionCounts.concordant_among_tested || 0)} concordant / ${formatCount(directionCounts.discordant_among_tested || 0)} discordant · FDR ${formatCount(fdrDirectionCounts.concordant_among_fdr_significant || 0)} concordant / ${formatCount(fdrDirectionCounts.discordant_among_fdr_significant || 0)} discordant · sign-test FDR ${formatCount(signDirectionCounts.concordant_among_sign_test_fdr_significant || 0)} concordant / ${formatCount(signDirectionCounts.discordant_among_sign_test_fdr_significant || 0)} discordant`;
    const limitations = $("geo-consistency-limitations");
    limitations.replaceChildren();
    for (const limitation of report.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
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
    const rankedFeatureCount = summary.ranked_feature_count ?? summary.reported_feature_count;
    const additionalTrackedFeatureCount = summary.additional_tracked_feature_count ?? 0;
    $("geo-metric-reported").textContent = formatCount(summary.reported_feature_count);
    $("geo-metric-reported-detail").textContent = `${formatCount(rankedFeatureCount)} ranked · ${formatCount(additionalTrackedFeatureCount)} tracked extras`;
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
    const filteredSummary = page?.filtered_result_summary || {};
    const directionCounts = filteredSummary.effect_direction_counts || {};
    $("geo-result-filter-summary").textContent = `${formatCount(filteredSummary.result_count || 0)} filtered rows · ${formatCount(filteredSummary.fdr_significant_count || 0)} signed-rank FDR significant · ${formatCount(filteredSummary.sign_test_fdr_significant_count || 0)} sign-test FDR significant · directions ${formatCount(directionCounts.case_higher || 0)} higher / ${formatCount(directionCounts.case_lower || 0)} lower / ${formatCount(directionCounts.no_mean_difference || 0)} no mean difference`;
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
    const filtered = page.total_results !== page.unfiltered_result_count;
    const totalLabel = filtered
      ? `${formatCount(page.total_results)} filtered · ${formatCount(page.unfiltered_result_count)} total`
      : `${formatCount(page.total_results)} reported rows`;
    $("geo-result-count").textContent = `Showing ${formatCount(model.geoResults.length)} of ${totalLabel}`;
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
      ["Reported row coverage", `${formatCount(page.summary.ranked_feature_count ?? page.summary.reported_feature_count)} ranked · ${formatCount(page.summary.additional_tracked_feature_count ?? 0)} explicitly tracked`],
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

  $("refresh-button").addEventListener("click", () => Promise.all([loadRuns(), loadGeoAnalyses(), loadGeoReviewSummary(), loadGeoPreflights(), loadGeoExpressionAnalyses(), loadGeoConsistencyRecords(), loadGeoSensitivityRecords(), loadGeoExpressionConsistencyRecords(), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceComparisons(), loadSequenceReview(), loadModuleWorkbenchOverview(), loadModuleAssessments(), loadModuleTriage()]));
  $("run-search").addEventListener("input", renderRuns);
  $("path-search").addEventListener("input", renderHypotheses);
  $("evidence-search").addEventListener("input", renderEvidence);
  $("load-more").addEventListener("click", () => loadRuns(true));
  $("baseline-select").addEventListener("change", (event) => {
    model.baseline = event.currentTarget.value;
    if (model.activeView === "case" && model.selected) openRun(model.selected);
  });
  $("geo-load-more-analyses").addEventListener("click", () => loadGeoAnalyses(true));
  $("geo-review-open").addEventListener("click", openGeoReview);
  $("geo-preflight-accession-filter").addEventListener("input", (event) => {
    model.geoPreflightFilters.accession = event.currentTarget.value.trim();
    reloadGeoPreflights();
  });
  $("geo-preflight-kind-filter").addEventListener("change", (event) => {
    model.geoPreflightFilters.kind = event.currentTarget.value;
    reloadGeoPreflights();
  });
  $("geo-preflight-load-more").addEventListener("click", () => loadGeoPreflights(true));
  $("geo-expression-consistency-list-load-more").addEventListener("click", () => loadGeoExpressionConsistencyRecords(true));
  $("geo-consistency-list-load-more").addEventListener("click", () => loadGeoConsistencyRecords(true));
  $("geo-sensitivity-list-load-more").addEventListener("click", () => loadGeoSensitivityRecords(true));

  $("geo-load-more").addEventListener("click", () => {
    if (model.selectedGeo) openGeoAnalysis(model.selectedGeo, { append: true });
  });
  $("geo-expression-load-more").addEventListener("click", () => {
    if (model.selectedGeoExpression) openGeoExpressionAnalysis(model.selectedGeoExpression, { append: true });
  });
  function reloadFilteredGeoResults() {
    if (model.geoFilterTimer !== null) clearTimeout(model.geoFilterTimer);
    model.geoFilterTimer = setTimeout(() => {
      model.geoFilterTimer = null;
      if (model.selectedGeo) openGeoAnalysis(model.selectedGeo);
    }, 180);
  }
  $("geo-feature-filter").addEventListener("input", (event) => {
    model.geoFilters.feature_contains = event.currentTarget.value.trim();
    reloadFilteredGeoResults();
  });
  $("geo-direction-filter").addEventListener("change", (event) => {
    model.geoFilters.effect_direction = event.currentTarget.value;
    reloadFilteredGeoResults();
  });
  $("geo-effect-filter").addEventListener("input", (event) => {
    model.geoFilters.min_abs_median_effect = event.currentTarget.value.trim();
    reloadFilteredGeoResults();
  });
  $("geo-fdr-filter").addEventListener("change", (event) => {
    model.geoFilters.fdr_significant = event.currentTarget.checked;
    reloadFilteredGeoResults();
  });
  $("geo-sign-filter").addEventListener("change", (event) => {
    model.geoFilters.sign_test_fdr_significant = event.currentTarget.checked;
    reloadFilteredGeoResults();
  });
  function reloadFilteredGeoExpressionResults() {
    if (model.geoExpressionFilterTimer !== null) clearTimeout(model.geoExpressionFilterTimer);
    model.geoExpressionFilterTimer = setTimeout(() => {
      model.geoExpressionFilterTimer = null;
      if (model.selectedGeoExpression) openGeoExpressionAnalysis(model.selectedGeoExpression);
    }, 180);
  }
  $("geo-expression-feature-filter").addEventListener("input", reloadFilteredGeoExpressionResults);
  $("geo-expression-direction-filter").addEventListener("change", reloadFilteredGeoExpressionResults);
  $("geo-expression-fdr-filter").addEventListener("change", reloadFilteredGeoExpressionResults);
  $("geo-expression-consistency-features").addEventListener("input", updateGeoExpressionCompareControls);
  $("geo-expression-compare-button").addEventListener("click", compareGeoExpressionAnalyses);
  $("geo-expression-consistency-feature-filter").addEventListener("input", (event) => {
    model.geoExpressionConsistencyFilters.feature_contains = event.currentTarget.value.trim();
    reloadGeoExpressionConsistencyPage();
  });
  $("geo-expression-consistency-direction-filter").addEventListener("change", (event) => {
    model.geoExpressionConsistencyFilters.direction_consistency = event.currentTarget.value;
    reloadGeoExpressionConsistencyPage();
  });
  $("geo-expression-consistency-fdr-filter").addEventListener("change", (event) => {
    model.geoExpressionConsistencyFilters.fdr_direction_consistency = event.currentTarget.value;
    reloadGeoExpressionConsistencyPage();
  });
  $("sequence-review-open").addEventListener("click", openSequenceReview);
  $("sequence-review-motif-filter").addEventListener("input", reloadSequenceReviewMotifs);
  $("sequence-review-source-filter").addEventListener("input", reloadSequenceReviewMotifs);
  $("sequence-review-genome-filter").addEventListener("input", reloadSequenceReviewMotifs);
  $("sequence-review-change-filter").addEventListener("change", reloadSequenceReviewMotifs);
  $("sequence-review-motif-load-more").addEventListener("click", loadMoreSequenceReviewMotifs);
  $("sequence-analysis-motif-filter").addEventListener("input", reloadSequenceAnalysisChanges);
  $("sequence-analysis-change-filter").addEventListener("change", reloadSequenceAnalysisChanges);
  $("sequence-analysis-change-load-more").addEventListener("click", loadMoreSequenceAnalysisChanges);
  $("sequence-batch-motif-filter").addEventListener("input", reloadSequenceBatchChanges);
  $("sequence-batch-change-filter").addEventListener("change", reloadSequenceBatchChanges);
  $("sequence-batch-change-load-more").addEventListener("click", loadMoreSequenceBatchChanges);
  $("sequence-comparison-motif-filter").addEventListener("input", reloadSequenceComparisonChanges);
  $("sequence-comparison-change-filter").addEventListener("change", reloadSequenceComparisonChanges);
  $("sequence-comparison-direction-filter").addEventListener("change", reloadSequenceComparisonChanges);
  $("sequence-comparison-load-more").addEventListener("click", loadMoreSequenceComparisonChanges);
  $("sequence-analysis-load-more").addEventListener("click", () => loadSequenceAnalyses(true));
  $("sequence-batch-load-more").addEventListener("click", () => loadSequenceBatches(true));
  $("sequence-comparison-list-load-more").addEventListener("click", () => loadSequenceComparisons(true));
  $("module-workbench-load-more").addEventListener("click", () => loadModuleAssessments(true));
  $("module-workbench-search").addEventListener("input", (event) => {
    model.moduleFilters.q = event.currentTarget.value.trim();
    reloadModuleAssessments();
  });
  $("module-workbench-risk-filter").addEventListener("change", (event) => {
    model.moduleFilters.risk = event.currentTarget.value;
    reloadModuleAssessments();
  });
  $("module-workbench-depth-filter").addEventListener("change", (event) => {
    model.moduleFilters.depth_band = event.currentTarget.value;
    reloadModuleAssessments();
  });
  $("module-execution-preview-button").addEventListener("click", previewModuleExecutionPlan);
  $("module-triage-load-more").addEventListener("click", () => loadModuleTriage(true));
  $("module-triage-risk-filter").addEventListener("change", (event) => {
    model.moduleTriageFilters.risk = event.currentTarget.value;
    reloadModuleTriage();
  });
  $("module-triage-reason-filter").addEventListener("change", (event) => {
    model.moduleTriageFilters.reason = event.currentTarget.value;
    reloadModuleTriage();
  });
  $("geo-consistency-features").addEventListener("input", updateGeoCompareControls);
  $("geo-compare-button").addEventListener("click", compareGeoAnalyses);
  $("geo-sensitivity-button").addEventListener("click", compareGeoSensitivity);
  $("geo-consistency-feature-filter").addEventListener("input", (event) => {
    model.geoConsistencyFilters.feature_contains = event.currentTarget.value.trim();
    reloadGeoConsistencyPage();
  });
  $("geo-consistency-direction-filter").addEventListener("change", (event) => {
    model.geoConsistencyFilters.direction_consistency = event.currentTarget.value;
    reloadGeoConsistencyPage();
  });
  $("geo-consistency-fdr-filter").addEventListener("change", (event) => {
    model.geoConsistencyFilters.fdr_direction_consistency = event.currentTarget.value;
    reloadGeoConsistencyPage();
  });
  $("geo-consistency-sign-fdr-filter").addEventListener("change", (event) => {
    model.geoConsistencyFilters.sign_test_direction_consistency = event.currentTarget.value;
    reloadGeoConsistencyPage();
  });
  $("geo-sensitivity-feature-filter").addEventListener("input", (event) => {
    model.geoSensitivityFilters.feature_contains = event.currentTarget.value.trim();
    reloadGeoSensitivityPage();
  });
  $("geo-sensitivity-direction-filter").addEventListener("change", (event) => {
    model.geoSensitivityFilters.direction_sensitivity = event.currentTarget.value;
    reloadGeoSensitivityPage();
  });
  $("geo-sensitivity-fdr-filter").addEventListener("change", (event) => {
    model.geoSensitivityFilters.fdr_sensitivity = event.currentTarget.value;
    reloadGeoSensitivityPage();
  });
  $("geo-sensitivity-sign-fdr-filter").addEventListener("change", (event) => {
    model.geoSensitivityFilters.sign_test_fdr_sensitivity = event.currentTarget.value;
    reloadGeoSensitivityPage();
  });
  $("markdown-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  $("geo-csv-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  async function initializeWorkspace() {
    const initialSelectionRequest = model.selectionRequest || 0;
    await Promise.all([loadRuns(false, true), loadGeoAnalyses(false, true), loadGeoReviewSummary(), loadGeoPreflights(), loadGeoExpressionAnalyses(), loadGeoConsistencyRecords(), loadGeoSensitivityRecords(), loadGeoExpressionConsistencyRecords(), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceComparisons(), loadSequenceReview(), loadModuleWorkbenchOverview(), loadModuleAssessments(), loadModuleTriage()]);
    if (model.selectionRequest !== initialSelectionRequest || model.activeView !== "empty") return;
    if (model.runs.length) {
      await openRun(model.runs[0].run_id);
    } else if (model.geoAnalyses.length) {
      await openGeoAnalysis(model.geoAnalyses[0].analysis_id);
    } else if (model.geoExpressionAnalyses.length) {
      await openGeoExpressionAnalysis(model.geoExpressionAnalyses[0].analysis_id);
    } else if (model.geoPreflights.length) {
      await openGeoPreflight(model.geoPreflights[0].preflight_id);
    } else if (model.sequenceAnalyses.length) {
      await openSequenceAnalysis(model.sequenceAnalyses[0].analysis_id);
    } else if (model.sequenceBatches.length) {
      await openSequenceBatch(model.sequenceBatches[0].batch_id);
    } else if (model.sequenceComparisons.length) {
      await openSequenceComparison(model.sequenceComparisons[0].comparison_id);
    } else if (model.moduleAssessments.length) {
      await openModuleWorkbenchDetail(model.moduleAssessments[0].module_id);
    } else {
      showEmpty("No saved research records", "Case runs and aggregate GEO reports appear here after they are saved to the local workspace.");
    }
  }

  initializeWorkspace();
})();
