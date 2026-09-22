"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const model = {
    runs: [], total: 0, selected: null, baseline: "", report: null, hypothesis: null,
    geoAnalyses: [], geoTotal: 0, selectedGeo: null, geoPage: null, geoResults: [],
    geoFilters: { feature_contains: "", effect_direction: "", min_abs_median_effect: "", fdr_significant: false, sign_test_fdr_significant: false },
    geoCompareIds: [], geoConsistency: null,
    sequenceAnalyses: [], sequenceTotal: 0, selectedSequence: null, sequenceReport: null, sequenceChanges: null,
    sequenceBatches: [], sequenceBatchTotal: 0, selectedSequenceBatch: null, sequenceBatchReport: null, sequenceBatchChanges: null,
    sequenceReviewSummary: null, sequenceReviewMotifs: null, sequenceReviewRequest: 0, sequenceReviewFilterTimer: null,
    activeView: "empty", runsLoaded: false, geoLoaded: false, sequenceLoaded: false,
    selectionRequest: 0, runListRequest: 0, geoListRequest: 0, sequenceListRequest: 0, geoFilterTimer: null, geoConsistencyRequest: 0,
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
      meta.append(element("span", "run-id", shortened(item.analysis_id, 28)), element("span", "", `${item.matched_pair_count} pairs · ${item.fdr_significant_feature_count} q-significant`));
      button.append(top, meta);
      button.addEventListener("click", () => openGeoAnalysis(item.analysis_id));
      choice.append(button);
      list.append(choice);
    }
    renderGeoCompareControls();
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
    button.disabled = model.geoCompareIds.length < 2 || features.length < 1;
    if (model.geoCompareIds.length < 2) {
      $("geo-compare-status").textContent = "Choose at least two saved analyses.";
    } else if (!features.length) {
      $("geo-compare-status").textContent = "Enter one or more exact source feature IDs.";
    } else {
      $("geo-compare-status").textContent = `${model.geoCompareIds.length} studies · ${features.length} feature IDs ready.`;
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
    $("geo-consistency-view").hidden = true;
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

  function geoResultQuery(offset) {
    const params = new URLSearchParams(geoFilterQuery());
    params.set("limit", "25");
    params.set("offset", String(offset));
    return params.toString();
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
    const params = new URLSearchParams();
    analysisIds.forEach((analysisId) => params.append("analysis_id", analysisId));
    featureIds.forEach((featureId) => params.append("feature_id", featureId));
    showEmpty("Comparing saved GEO reports", "Verifying compatible designs and preserving each study's aggregate results separately.");
    try {
      const report = await getJson(`/v1/geo-analyses/consistency?${params.toString()}`);
      if (request !== model.geoConsistencyRequest || model.activeView !== "geo-consistency") return;
      if (report.schema !== "glio-noncode.geo-count-consistency.v1" || report.status !== "completed" || !Array.isArray(report.features) || !Array.isArray(report.studies) || !report.summary || !report.comparison) {
        throw new Error("The local API returned an invalid GEO consistency projection.");
      }
      model.geoConsistency = report;
      $("empty-state").hidden = true;
      $("run-view").hidden = true;
      $("geo-analysis-view").hidden = true;
      $("geo-consistency-view").hidden = false;
      renderGeoConsistency();
      announceSelection(`Compared ${formatCount(report.summary.study_count)} GEO studies across ${formatCount(report.summary.feature_count)} exact source feature IDs.`);
    } catch (error) {
      if (request !== model.geoConsistencyRequest || model.activeView !== "geo-consistency") return;
      notice(`The GEO consistency comparison could not be verified. ${error.message}`, true);
      showEmpty("GEO comparison unavailable", "The selected reports were not comparable or could not be verified.");
    }
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
    $("geo-consistency-result-count").textContent = `${formatCount(report.features.length)} feature rows`;
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

  $("refresh-button").addEventListener("click", () => Promise.all([loadRuns(), loadGeoAnalyses(), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceReview()]));
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
  $("sequence-review-open").addEventListener("click", openSequenceReview);
  $("sequence-review-motif-filter").addEventListener("input", reloadSequenceReviewMotifs);
  $("sequence-review-change-filter").addEventListener("change", reloadSequenceReviewMotifs);
  $("sequence-batch-motif-filter").addEventListener("input", reloadSequenceBatchChanges);
  $("sequence-batch-change-filter").addEventListener("change", reloadSequenceBatchChanges);
  $("geo-consistency-features").addEventListener("input", updateGeoCompareControls);
  $("geo-compare-button").addEventListener("click", compareGeoAnalyses);
  $("markdown-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  $("geo-csv-export").addEventListener("click", (event) => {
    if (event.currentTarget.getAttribute("aria-disabled") === "true") event.preventDefault();
  });
  async function initializeWorkspace() {
    const initialSelectionRequest = model.selectionRequest || 0;
    await Promise.all([loadRuns(false, true), loadGeoAnalyses(false, true), loadSequenceAnalyses(), loadSequenceBatches(), loadSequenceReview()]);
    if (model.selectionRequest !== initialSelectionRequest || model.activeView !== "empty") return;
    if (model.runs.length) {
      await openRun(model.runs[0].run_id);
    } else if (model.geoAnalyses.length) {
      await openGeoAnalysis(model.geoAnalyses[0].analysis_id);
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
