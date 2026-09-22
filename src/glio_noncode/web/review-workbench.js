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
    geoExpressionConsistencyRecords: [], geoExpressionConsistencyTotal: 0, selectedGeoExpressionConsistency: null, geoExpressionConsistencyListRequest: 0,
    geoFilters: { feature_contains: "", effect_direction: "", min_abs_median_effect: "", fdr_significant: false, sign_test_fdr_significant: false },
    geoCompareIds: [], geoConsistency: null, geoConsistencyRecords: [], geoConsistencyTotal: 0,
    selectedGeoConsistency: null, geoConsistencyListRequest: 0, geoConsistencyFilterTimer: null,
    geoConsistencyFilters: { feature_contains: "", direction_consistency: "", fdr_direction_consistency: "", sign_test_direction_consistency: "" },
    geoSensitivity: null, geoSensitivityRecords: [], geoSensitivityTotal: 0,
    selectedGeoSensitivity: null, geoSensitivityListRequest: 0, geoSensitivityRequest: 0, geoSensitivityFilterTimer: null,
    geoSensitivityFilters: { feature_contains: "", direction_sensitivity: "", fdr_sensitivity: "" },
    geoExpressionConsistencyFilters: { feature_contains: "", direction_consistency: "", fdr_direction_consistency: "" }, geoExpressionConsistencyFilterTimer: null,
    sequenceAnalyses: [], sequenceTotal: 0, selectedSequence: null, sequenceReport: null, sequenceChanges: null,
    sequenceBatches: [], sequenceBatchTotal: 0, selectedSequenceBatch: null, sequenceBatchReport: null, sequenceBatchChanges: null,
    sequenceReviewSummary: null, sequenceReviewMotifs: null, sequenceReviewRequest: 0, sequenceReviewFilterTimer: null,
    activeView: "empty", runsLoaded: false, geoLoaded: false, sequenceLoaded: false,
    selectionRequest: 0, runListRequest: 0, geoListRequest: 0, geoExpressionListRequest: 0, sequenceListRequest: 0, geoFilterTimer: null, geoExpressionFilterTimer: null, geoConsistencyRequest: 0,
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

  async function loadSequenceAnalyses() {
    const request = model.sequenceListRequest = (model.sequenceListRequest || 0) + 1;
    try {
      const page = await getJson("/v1/sequence-analyses?limit=50&offset=0");
      if (request !== model.sequenceListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) {
        throw new Error("The local API returned an invalid sequence analysis catalog.");
      }
      model.sequenceTotal = page.total_count;
      model.sequenceAnalyses = page.rows;
      model.sequenceLoaded = true;
      renderSequenceAnalyses();
    } catch (error) {
      if (request !== model.sequenceListRequest) return;
      model.sequenceLoaded = true;
      $("sequence-analysis-list").replaceChildren(element("p", "empty-inline", "Sequence analyses could not be loaded."));
      $("sequence-list-summary").textContent = "The local API could not verify a sequence analysis catalog.";
      notice(error.message, true);
    }
  }

  async function loadSequenceBatches() {
    try {
      const page = await getJson("/v1/sequence-batches?limit=50&offset=0");
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) throw new Error("The local API returned an invalid sequence batch catalog.");
      model.sequenceBatchTotal = page.total_count;
      model.sequenceBatches = page.rows;
      renderSequenceBatches();
    } catch (error) {
      $("sequence-batch-list").replaceChildren(element("p", "empty-inline", "Sequence batches could not be loaded."));
      $("sequence-batch-list-summary").textContent = "The local API could not verify a sequence batch catalog.";
      notice(error.message, true);
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
    const fdrCount = catalogs.reduce((total, item) => total + Number(item.fdr_significant_feature_count_total || 0), 0);
    $("geo-review-subtitle").textContent = `${formatCount(analysisCount)} analyses · ${formatCount(comparisonCount)} saved comparisons · ${summary.integrity?.report_objects || "review"}`;
    $("geo-review-address").textContent = summary.content_address || "Address unavailable";
    $("geo-review-analysis-count").textContent = formatCount(analysisCount);
    $("geo-review-comparison-count").textContent = formatCount(comparisonCount);
    $("geo-review-preflight-count").textContent = formatCount(preflightCount);
    $("geo-review-accession-count").textContent = formatCount(accessionCount);
    $("geo-review-tested-count").textContent = formatCount(testedCount);
    $("geo-review-fdr-count").textContent = formatCount(fdrCount);
    $("geo-review-integrity").textContent = summary.integrity?.verification_failure_count === 0 ? "Accepted" : "Review";
    renderGeoReviewBreakdown("geo-review-preflight-kinds", preflightCatalog.kind_counts, "No saved preflight kinds yet.");
    renderGeoReviewBreakdown("geo-review-preflight-states", preflightCatalog.design_state_counts, "No design-state reports yet.");
    const body = $("geo-review-catalog-table");
    body.replaceChildren();
    for (const catalog of catalogs) {
      const row = document.createElement("tr");
      row.append(cell(catalog.name), cell(formatCount(catalog.record_count)), cell(formatCount(catalog.verified_record_count)), cell(formatCount(catalog.feature_count_total)), cell(formatCount(catalog.tested_feature_count_total)), cell(formatCount(catalog.fdr_significant_feature_count_total)), cell(formatCount(catalog.accession_count)), cell(catalog.catalog_state));
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

  async function loadGeoConsistencyRecords() {
    const request = model.geoConsistencyListRequest = (model.geoConsistencyListRequest || 0) + 1;
    try {
      const page = await getJson("/v1/geo-count-consistency?limit=50&offset=0");
      if (request !== model.geoConsistencyListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) throw new Error("The local API returned an invalid GEO count consistency catalog.");
      model.geoConsistencyTotal = page.total_count;
      model.geoConsistencyRecords = page.rows;
      renderGeoConsistencyRecords();
      if (model.activeView === "geo-consistency" && model.selectedGeoConsistency) {
        if (model.geoConsistencyRecords.some((item) => item.comparison_id === model.selectedGeoConsistency)) await openGeoConsistency(model.selectedGeoConsistency);
        else showEmpty("No saved paired-count comparison", "The previously selected comparison is no longer present in the local catalog.");
      }
    } catch (error) {
      if (request !== model.geoConsistencyListRequest) return;
      $("geo-consistency-list").replaceChildren(element("p", "empty-inline", "Paired-count comparisons could not be loaded."));
      $("geo-consistency-list-summary").textContent = "The local API could not verify the paired-count consistency catalog.";
      notice(error.message, true);
    }
  }

  async function loadGeoSensitivityRecords() {
    const request = model.geoSensitivityListRequest = (model.geoSensitivityListRequest || 0) + 1;
    try {
      const page = await getJson("/v1/geo-count-sensitivity?limit=50&offset=0");
      if (request !== model.geoSensitivityListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) throw new Error("The local API returned an invalid GEO sensitivity catalog.");
      model.geoSensitivityTotal = page.total_count;
      model.geoSensitivityRecords = page.rows;
      renderGeoSensitivityRecords();
      if (model.activeView === "geo-sensitivity" && model.selectedGeoSensitivity) {
        if (model.geoSensitivityRecords.some((item) => item.comparison_id === model.selectedGeoSensitivity)) await openGeoSensitivity(model.selectedGeoSensitivity);
        else showEmpty("No saved normalization sensitivity", "The previously selected sensitivity comparison is no longer present in the local catalog.");
      }
    } catch (error) {
      if (request !== model.geoSensitivityListRequest) return;
      $("geo-sensitivity-list").replaceChildren(element("p", "empty-inline", "Normalization sensitivity comparisons could not be loaded."));
      $("geo-sensitivity-list-summary").textContent = "The local API could not verify the GEO sensitivity catalog.";
      notice(error.message, true);
    }
  }

  async function loadGeoExpressionConsistencyRecords() {
    const request = model.geoExpressionConsistencyListRequest = (model.geoExpressionConsistencyListRequest || 0) + 1;
    try {
      const page = await getJson("/v1/geo-expression-consistency?limit=50&offset=0");
      if (request !== model.geoExpressionConsistencyListRequest) return;
      if (!Array.isArray(page.rows) || !Number.isSafeInteger(page.total_count)) throw new Error("The local API returned an invalid GEO consistency catalog.");
      model.geoExpressionConsistencyTotal = page.total_count;
      model.geoExpressionConsistencyRecords = page.rows;
      renderGeoExpressionConsistencyRecords();
      if (model.activeView === "geo-expression-consistency" && model.selectedGeoExpressionConsistency) {
        if (model.geoExpressionConsistencyRecords.some((item) => item.comparison_id === model.selectedGeoExpressionConsistency)) {
          await openGeoExpressionConsistency(model.selectedGeoExpressionConsistency);
        } else {
          showEmpty("No saved expression comparison", "The previously selected comparison is no longer present in the local catalog.");
        }
      }
    } catch (error) {
      if (request !== model.geoExpressionConsistencyListRequest) return;
      $("geo-expression-consistency-list").replaceChildren(element("p", "empty-inline", "Expression comparisons could not be loaded."));
      $("geo-expression-consistency-list-summary").textContent = "The local API could not verify the expression consistency catalog.";
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
    $("geo-expression-analysis-view").hidden = true;
    $("geo-expression-consistency-view").hidden = true;
    $("geo-review-view").hidden = true;
    $("geo-preflight-view").hidden = true;
    $("geo-consistency-view").hidden = true;
    $("geo-sensitivity-view").hidden = true;
    $("sequence-analysis-view").hidden = true;
    $("sequence-review-view").hidden = true;
    $("sequence-batch-view").hidden = true;
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
      csvLink.href = `/v1/sequence-analyses/${encodeURIComponent(model.selectedSequence)}/changes.csv`;
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
      csvLink.href = "/v1/sequence-review/motifs.csv";
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
      csvLink.href = `/v1/sequence-batches/${encodeURIComponent(model.selectedSequenceBatch)}/changes.csv`;
      csvLink.textContent = "Download batch motif CSV";
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
    model.geoSensitivityFilters = { feature_contains: "", direction_sensitivity: "", fdr_sensitivity: "" };
    const feature = $("geo-sensitivity-feature-filter");
    const direction = $("geo-sensitivity-direction-filter");
    const fdr = $("geo-sensitivity-fdr-filter");
    if (feature) feature.value = "";
    if (direction) direction.value = "";
    if (fdr) fdr.value = "";
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
    model.activeView = "sequence";
    model.selectedSequence = analysisId;
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    model.sequenceReport = null;
    model.sequenceChanges = null;
    renderSequenceAnalyses();
    notice("");
    exportHref();
    showEmpty("Verifying sequence report", "Loading the immutable phased sequence report and its motif-change projection.");
    try {
      const [report, changes] = await Promise.all([
        getJson(`/v1/sequence-analyses/${encodeURIComponent(analysisId)}/report.json`),
        getJson(`/v1/sequence-analyses/${encodeURIComponent(analysisId)}?limit=50&offset=0`),
      ]);
      if (request !== model.selectionRequest || model.activeView !== "sequence" || model.selectedSequence !== analysisId) return;
      if (report.schema !== "glio-noncode.sequence-haplotype-analysis.v1" || report.status !== "completed" || !report.source || !report.inputs || !report.analysis || changes.schema !== "glio-noncode.sequence-haplotype-changes.v1" || !Array.isArray(changes.changes)) {
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
    model.activeView = "sequence-batch";
    model.selectedSequenceBatch = batchId;
    const request = model.selectionRequest = (model.selectionRequest || 0) + 1;
    model.sequenceBatchReport = null;
    model.sequenceBatchChanges = null;
    renderSequenceBatches();
    notice("");
    exportHref();
    showEmpty("Verifying sequence batch", "Loading the immutable aggregate batch report and its exact motif prevalence rows.");
    try {
      const [report, changes] = await Promise.all([
        getJson(`/v1/sequence-batches/${encodeURIComponent(batchId)}/report.json`),
        getJson(`/v1/sequence-batches/${encodeURIComponent(batchId)}?limit=50&offset=0`),
      ]);
      if (request !== model.selectionRequest || model.activeView !== "sequence-batch" || model.selectedSequenceBatch !== batchId) return;
      if (report.schema !== "glio-noncode.sequence-haplotype-batch-analysis.v1" || report.status !== "completed" || !report.source || !report.design || changes.schema !== "glio-noncode.sequence-haplotype-batch-changes.v1" || !Array.isArray(changes.changes)) throw new Error("The local API returned an invalid sequence batch projection.");
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
    const limitations = $("sequence-batch-limitations");
    limitations.replaceChildren();
    for (const limitation of report.limitations || []) limitations.append(element("p", "geo-limitation", limitation));
  }

  function reloadSequenceBatchChanges() {
    if (!model.selectedSequenceBatch) return;
    const params = new URLSearchParams({ limit: "50", offset: "0" });
    const motif = $("sequence-batch-motif-filter").value.trim();
    const change = $("sequence-batch-change-filter").value;
    if (motif) params.set("motif_contains", motif);
    if (change) params.set("change", change);
    getJson(`/v1/sequence-batches/${encodeURIComponent(model.selectedSequenceBatch)}?${params.toString()}`).then((changes) => {
      if (model.activeView === "sequence-batch" && changes.schema === "glio-noncode.sequence-haplotype-batch-changes.v1") {
        model.sequenceBatchChanges = changes;
        renderSequenceBatch();
      }
    }).catch((error) => { if (model.activeView === "sequence-batch") notice(error.message, true); });
  }

  async function openSequenceReview() {
    const request = model.sequenceReviewRequest = (model.sequenceReviewRequest || 0) + 1;
    model.activeView = "sequence-review";
    model.sequenceReviewSummary = null;
    model.sequenceReviewMotifs = null;
    notice("");
    exportHref();
    showEmpty("Verifying sequence archive", "Opening bounded catalog and motif-activity projections without exposing raw bases.");
    try {
      const [summary, motifs] = await Promise.all([
        getJson("/v1/sequence-review/summary"),
        getJson("/v1/sequence-review/motifs?limit=100&offset=0"),
      ]);
      if (request !== model.sequenceReviewRequest || model.activeView !== "sequence-review") return;
      if (summary.schema !== "glio-noncode.sequence-review-summary.v1" || motifs.schema !== "glio-noncode.sequence-review-motifs.v1" || !Array.isArray(motifs.rows)) throw new Error("The local API returned an invalid sequence review projection.");
      model.sequenceReviewSummary = summary;
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
      announceSelection(`Sequence archive review opened. ${formatCount(motifs.total_count)} exact motif activity rows.`);
    } catch (error) {
      if (request !== model.sequenceReviewRequest || model.activeView !== "sequence-review") return;
      notice(`The sequence archive review could not be verified. ${error.message}`, true);
      showEmpty("Sequence archive unavailable", "The saved sequence catalog could not be verified, so aggregate activity remains hidden.");
    }
  }

  function renderSequenceReview() {
    const summary = model.sequenceReviewSummary;
    const motifs = model.sequenceReviewMotifs;
    if (!summary || !motifs) return;
    const analyses = summary.catalogs.sequence_analyses;
    const batches = summary.catalogs.sequence_batches;
    const integrity = summary.integrity;
    const changes = Number(analyses.created_motif_count || 0) + Number(analyses.disrupted_motif_count || 0) + Number(batches.created_change_count || 0) + Number(batches.disrupted_change_count || 0);
    $("sequence-review-subtitle").textContent = `${formatCount(analyses.record_count || 0)} single analyses · ${formatCount(batches.record_count || 0)} aggregate batches · ${formatCount(changes)} saved change records`;
    $("sequence-review-address").textContent = summary.content_address || "Address unavailable";
    $("sequence-review-analyses").textContent = formatCount(analyses.record_count || 0);
    $("sequence-review-analysis-detail").textContent = `${formatCount(analyses.supported_count || 0)} supported · ${formatCount(analyses.abstained_count || 0)} abstained`;
    $("sequence-review-batches").textContent = formatCount(batches.record_count || 0);
    $("sequence-review-batch-detail").textContent = `${formatCount(batches.supported_count || 0)} supported analyses`;
    $("sequence-review-changes").textContent = formatCount(changes);
    $("sequence-review-integrity").textContent = integrity.catalog_records === "validated" ? "Catalog OK" : "Review";
    $("sequence-review-motif-count").textContent = `${formatCount(motifs.total_count)} exact rows`;
    const body = $("sequence-review-motif-table");
    body.replaceChildren();
    if (!motifs.rows.length) body.append(emptyRow(6, "No exact motif activity matches the selected filters."));
    for (const row of motifs.rows) {
      const tr = document.createElement("tr");
      tr.append(cell(consistencyText(row.change)), cell(row.name || row.motif_id), cell(row.matched_sequence), cell(formatCount(row.single_analysis_count)), cell(formatCount(row.batch_count)), cell(percent(row.max_batch_fraction)));
      body.append(tr);
    }
    const integrityCopy = $("sequence-review-integrity-copy");
    integrityCopy.replaceChildren();
    for (const text of [
      "Catalog records are validated before they enter this projection.",
      "Report objects are opened and independently checked by the verification endpoint.",
      "Raw bases, genotype strings, sample IDs, and subject IDs are not emitted here.",
    ]) integrityCopy.append(element("p", "geo-limitation", text));
    const limitations = $("sequence-review-limitations");
    limitations.replaceChildren();
    for (const text of summary.limitations || []) limitations.append(element("p", "geo-limitation", text));
  }

  function reloadSequenceReviewMotifs() {
    if (model.sequenceReviewFilterTimer !== null) clearTimeout(model.sequenceReviewFilterTimer);
    model.sequenceReviewFilterTimer = setTimeout(async () => {
      model.sequenceReviewFilterTimer = null;
      const params = new URLSearchParams({ limit: "100", offset: "0" });
      const motif = $("sequence-review-motif-filter").value.trim();
      const change = $("sequence-review-change-filter").value;
      if (motif) params.set("motif_contains", motif);
      if (change) params.set("change", change);
      try {
        const motifs = await getJson(`/v1/sequence-review/motifs?${params.toString()}`);
        if (model.activeView !== "sequence-review" || motifs.schema !== "glio-noncode.sequence-review-motifs.v1") return;
        model.sequenceReviewMotifs = motifs;
        renderSequenceReview();
      } catch (error) { if (model.activeView === "sequence-review") notice(error.message, true); }
    }, 180);
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
    $("sequence-change-count").textContent = `${formatCount(changes.total_changes)} motif changes`;
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
    const expressionFiltered = page.total_features !== page.unfiltered_feature_count;
    $("geo-expression-consistency-result-count").textContent = expressionFiltered
      ? `${formatCount(page.features.length)} shown · ${formatCount(page.total_features)} filtered`
      : `${formatCount(page.features.length)} feature rows`;
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
    const rows = [
      ["Series", comparison.accession],
      ["Left normalization", comparison.left_normalization],
      ["Right normalization", comparison.right_normalization],
      ["Case group", filterDescription(comparison.case_filters)],
      ["Reference group", filterDescription(comparison.reference_filters)],
      ["Pairing field", comparison.pair_key_column],
      ["Source count digest", comparison.count_matrix_source_sha256],
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
    const rows = [
      ["Studies", report.studies.map((study) => study.accession).join(" · ")],
      ["Case group", filterDescription(comparison.case_filters)],
      ["Reference group", filterDescription(comparison.reference_filters)],
      ["Pairing field", comparison.pair_key_column],
      ["Expression scale", comparison.expression_scale],
      ["Direction basis", comparison.effect_direction_basis],
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

  $("refresh-button").addEventListener("click", () => Promise.all([loadRuns(), loadGeoAnalyses(), loadGeoReviewSummary(), loadGeoPreflights(), loadGeoExpressionAnalyses(), loadGeoConsistencyRecords(), loadGeoSensitivityRecords(), loadGeoExpressionConsistencyRecords(), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceReview()]));
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
  $("sequence-review-change-filter").addEventListener("change", reloadSequenceReviewMotifs);
  $("sequence-batch-motif-filter").addEventListener("input", reloadSequenceBatchChanges);
  $("sequence-batch-change-filter").addEventListener("change", reloadSequenceBatchChanges);
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
  $("markdown-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  $("geo-csv-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  async function initializeWorkspace() {
    const initialSelectionRequest = model.selectionRequest || 0;
    await Promise.all([loadRuns(false, true), loadGeoAnalyses(false, true), loadGeoReviewSummary(), loadGeoPreflights(), loadGeoExpressionAnalyses(), loadGeoConsistencyRecords(), loadGeoSensitivityRecords(), loadGeoExpressionConsistencyRecords(), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceReview()]);
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
    } else {
      showEmpty("No saved research records", "Case runs and aggregate GEO reports appear here after they are saved to the local workspace.");
    }
  }

  initializeWorkspace();
})();
