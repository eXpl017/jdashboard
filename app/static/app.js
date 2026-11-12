"use strict";

const DEFAULT_STATE = {
  q: "",
  source: "",
  role: "technical",
  language: "",
  location: "",
  location_scope: "japan",
  remote: "",
  visa: "",
  tag: "",
  days: "3",
  sort: "posted_desc",
  include_active: false,
};

const state = { ...DEFAULT_STATE };
const sources = [];
const sourceNames = new Map();
let tags = [];
let roles = [];
let refreshRunning = false;
let refreshPollTimer = null;
let jobsAbort = null;
let refreshLoadToken = 0;

const $ = (id) => document.getElementById(id);

/* ----------------------------- formatting ----------------------------- */

const JST_MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function jstNow() {
  const now = new Date();
  return new Date(now.getTime() + 9 * 60 * 60 * 1000);
}

function jstDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Date(d.getTime() + 9 * 60 * 60 * 1000);
}

function formatJst(iso) {
  const d = jstDate(iso);
  if (!d) return "";
  const pad = (n) => String(n).padStart(2, "0");
  const date = `${JST_MONTHS[d.getUTCMonth()]} ${pad(d.getUTCDate())}, ${d.getUTCFullYear()}`;
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  return `${date}, ${time} JST`;
}

function relativeJst(iso) {
  const from = jstDate(iso);
  const now = jstNow();
  if (!from) return "";
  const minutes = Math.max(0, Math.round((now.getTime() - from.getTime()) / 60000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return formatJst(iso);
}

function formatSalary(job) {
  if (job.salary_min != null && job.salary_max != null) {
    const min = Number(job.salary_min);
    const max = Number(job.salary_max);
    if (min > 0 && max > 0) {
      const fmt = (value) =>
        value >= 1_000_000 ? `¥${Math.round(value / 1_000_000)}M` : `¥${Math.round(value / 1000)}K`;
      return `${fmt(min)}–${fmt(max)}`;
    }
  }
  if (job.salary_text) return job.salary_text;
  return "";
}

/* --------------------------- label helpers --------------------------- */

function languageLabel(value) {
  switch (value) {
    case "en":
      return "EN";
    case "ja":
      return "JA";
    case "bilingual":
      return "EN/JA";
    case "unknown":
      return null;
    default:
      return null;
  }
}

function remoteLabel(value) {
  switch (value) {
    case "remote":
      return "Remote";
    case "hybrid":
      return "Hybrid";
    case "onsite":
      return "On-site";
    default:
      return null;
  }
}

function locationScopeLabel(value) {
  switch (value) {
    case "japan_onsite":
      return "Japan · onsite";
    case "japan_hybrid":
      return "Japan · hybrid";
    case "japan_remote":
      return "Japan · remote";
    case "international_remote":
      return "International remote";
    case "unknown":
      return "Unknown location";
    default:
      return null;
  }
}

function sourceName(sourceId) {
  return sourceNames.get(sourceId) || sourceId;
}

/* ------------------------- filter <-> state ------------------------- */

function readFiltersFromInputs() {
  state.q = $("filter-q")?.value ?? "";
  state.source = $("filter-source")?.value ?? "";
  state.role = $("filter-role")?.value ?? "technical";
  state.language = $("filter-language")?.value ?? "";
  state.location = $("filter-location")?.value ?? "";
  state.location_scope = $("filter-location-scope")?.value ?? "japan";
  state.remote = $("filter-remote")?.value ?? "";
  state.visa = $("filter-visa")?.value ?? "";
  state.tag = $("filter-tag")?.value ?? "";
  state.days = $("filter-days")?.value ?? "3";
  state.sort = $("filter-sort")?.value ?? "posted_desc";
  const include = $("filter-include-active");
  state.include_active = Boolean(include?.checked);
}

function paramsFromState() {
  const params = new URLSearchParams();
  const add = (key, value) => {
    const normalized = typeof value === "boolean" ? (value ? "1" : "") : String(value ?? "");
    if (normalized) params.set(key, normalized);
  };
  add("q", state.q);
  add("source", state.source);
  add("role", state.role);
  add("language", state.language);
  add("location", state.location);
  add("location_scope", state.location_scope);
  add("remote", state.remote);
  add("visa", state.visa);
  add("tag", state.tag);
  add("days", state.days);
  add("sort", state.sort);
  add("include_active", state.include_active);
  return params;
}

function syncUrl() {
  const params = paramsFromState();
  const qs = params.toString();
  const target = qs ? `?${qs}` : window.location.pathname;
  window.history.replaceState(null, "", target);
}

function writeStateFromInputs() {
  readFiltersFromInputs();
  syncUrl();
}

/* ------------------------------- API -------------------------------- */

async function fetchJson(url, options) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    ...(options || {}),
  });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json();
}

async function loadSources() {
  const data = await fetchJson("/api/sources");
  sources = Array.isArray(data.sources) ? data.sources : [];
  sourceNames.clear();
  for (const source of sources) {
    sourceNames.set(source.id, source.name);
  }
  const sourceSelect = $("filter-source");
  if (sourceSelect) {
    sourceSelect.innerHTML = '<option value="">All sources</option>';
    for (const source of sources) {
      if (!source.enabled) continue;
      const option = document.createElement("option");
      option.value = source.id;
      option.textContent = source.name;
      sourceSelect.appendChild(option);
    }
  }
}

async function loadStats() {
  const params = paramsFromState();
  const query = params.toString();
  const data = await fetchJson(`/api/stats${query ? `?${query}` : ""}`);
  renderStats(data);
  return data;
}

function renderStats(stats) {
  const totalEl = $("stat-total-jobs");
  const newEl = $("stat-new-in-window");
  const sourcesHealthyEl = $("stat-sources-healthy");
  const lastRunEl = $("stat-last-run");

  if (totalEl) totalEl.textContent = String(stats?.total_jobs ?? 0);
  if (newEl) newEl.textContent = String(stats?.new_in_window ?? 0);

  const enabled = sources.filter((source) => source.enabled);
  const okSources = enabled.filter(
    (source) => !["error", "failed", "skipped"].includes(source.last_status),
  );
  if (sourcesHealthyEl) {
    sourcesHealthyEl.textContent = `${okSources.length}/${enabled.length || sources.length}`;
  }
  const healthyHint = $("stat-sources-healthy-hint");
  if (healthyHint) {
    healthyHint.textContent = `${okSources.length} of ${enabled.length || sources.length} sources healthy`;
  }

  const lastRun = stats?.last_run;
  const lastRunText = lastRun ? `${lastRun.status}` : "Never";
  if (lastRunEl) lastRunEl.textContent = lastRunText;
  const lastRunHint = $("stat-last-run-hint");
  if (lastRunHint) {
    lastRunHint.textContent = lastRun ? `finished ${lastRun.finished_at ? formatJst(lastRun.finished_at) : ""}`.trim() : "no refresh yet";
  }

  const lastRefresh = $("last-refresh");
  if (lastRefresh) {
    lastRefresh.textContent = lastRun
      ? `Last refresh: ${relativeJst(lastRun.finished_at || lastRun.started_at)}`
      : "Last refresh: never";
  }

  // Tags and role categories for filter dropdowns.
  const tagSelect = $("filter-tag");
  if (tagSelect) {
    tags = Object.keys(stats?.by_tag || {}).sort();
    tagSelect.innerHTML = '<option value="">Any</option>';
    for (const tag of tags) {
      const option = document.createElement("option");
      option.value = tag;
      option.textContent = tag;
      tagSelect.appendChild(option);
    }
  }

  const roleSelect = $("filter-role");
  if (roleSelect) {
    roles = Object.keys(stats?.by_role_category || {}).sort();
    roleSelect.innerHTML = "";
    const technical = document.createElement("option");
    technical.value = "technical";
    technical.textContent = "Technical (engineering / operations)";
    roleSelect.appendChild(technical);
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = "All roles";
    roleSelect.appendChild(all);
    for (const role of roles) {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = role;
      roleSelect.appendChild(option);
    }
    if (state.role && [...roleSelect.options].some((option) => option.value === state.role)) {
      roleSelect.value = state.role;
    }
  }
}

async function loadJobs() {
  const list = $("job-list");
  list.setAttribute("aria-busy", "true");
  setListState({ kind: "loading" });

  const controller = new AbortController();
  jobsAbort = controller;
  const params = paramsFromState();
  const query = params.toString();
  const url = `/api/jobs${query ? `?${query}` : ""}`;
  try {
    const data = await fetchJson(url, { signal: controller.signal });
    if (jobsAbort !== controller) return;
    renderJobs(data.items || []);
  } catch (error) {
    if (jobsAbort === controller) {
      setListState({
        kind: "error",
        message: error?.name === "AbortError" ? null : "Could not load jobs. Please try again.",
      });
    }
  } finally {
    if (jobsAbort === controller) {
      list.setAttribute("aria-busy", "false");
      jobsAbort = null;
    }
  }
}

/* ------------------------------ states ------------------------------- */

function setListState(next) {
  const list = $("job-list");
  list.innerHTML = "";
  const container = document.createElement("div");
  container.className = "job-list__state";

  if (next.kind === "loading") {
    container.classList.add("job-list__state--loading");
    const paragraph = document.createElement("p");
    paragraph.className = "job-list__empty-text";
    paragraph.textContent = next.message || "Loading jobs…";
    container.appendChild(paragraph);
  } else if (next.kind === "error") {
    container.className = "job-list__state job-list__error";
    const paragraph = document.createElement("p");
    paragraph.className = "job-list__empty-text";
    paragraph.textContent = next.message || "Could not load jobs.";
    container.appendChild(paragraph);
    const button = document.createElement("button");
    button.type = "button";
    button.id = "jobs-retry";
    button.className = "button";
    button.textContent = "Retry";
    button.addEventListener("click", () => loadJobs());
    container.appendChild(button);
  } else {
    container.className = "job-list__state job-list__state--empty";
    const title = document.createElement("p");
    title.className = "job-list__empty-title";
    title.textContent = next.title || "No jobs found";
    const text = document.createElement("p");
    text.className = "job-list__empty-text";
    text.textContent = next.text || "";
    container.appendChild(title);
    container.appendChild(text);
  }

  list.appendChild(container);
  list.setAttribute("aria-busy", next.kind === "loading" ? "true" : "false");
}

function renderEmpty() {
  const list = $("job-list");
  list.innerHTML = "";
  setListState({
    kind: "empty",
    title: "No jobs found",
    text: emptyStateText(),
  });
}

function emptyStateText() {
  const parts = [];
  const days = Number(state.days || 0);
  if (days > 0) {
    parts.push(`No listings were posted in the last ${days} days.`);
  }
  if (state.role && state.role !== "all") {
    parts.push(`No ${state.role.replaceAll("_", " ")} roles matched.`);
  }
  if (state.location_scope && state.location_scope !== "" && state.location_scope !== "all") {
    parts.push("Only Japan-based roles are shown by default; international remote roles are hidden.");
  }
  if (parts.length === 0) {
    parts.push("Try widening the filters or refreshing.");
  }
  return parts.join(" ");
}

function renderJobs(items) {
  const list = $("job-list");
  list.innerHTML = "";
  list.setAttribute("aria-busy", "false");

  const jobs = items || [];
  if (jobs.length === 0) {
    renderEmpty();
    return;
  }

  const template = document.getElementById("job-card-template");
  for (const job of jobs) {
    const card = template.content.firstElementChild.cloneNode(true);
    fillJobCard(card, job);
    list.appendChild(card);
  }
}

function fillJobCard(card, job) {
  const link = card.querySelector(".job-card__link");
  if (link) {
    link.href = job.url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = job.title || "";
  }

  const newBadge = card.querySelector(".job-card__new");
  if (newBadge) newBadge.hidden = !job.is_new;

  const company = card.querySelector(".job-card__company");
  if (company) company.textContent = job.company || "Unknown company";

  const location = card.querySelector(".job-card__location");
  if (location) location.textContent = job.location || "Location unknown";

  const salary = card.querySelector(".job-card__salary");
  if (salary) salary.textContent = formatSalary(job);

  const source = card.querySelector(".job-card__source");
  if (source) source.textContent = job.source_name || job.source;

  const posted = card.querySelector(".job-card__posted");
  if (posted) {
    posted.setAttribute("datetime", job.posted_at || "");
    posted.textContent = relativeJst(job.posted_at);
  }

  const badges = card.querySelector(".job-card__badges");
  if (badges) {
    badges.innerHTML = "";
    for (const [cls, text] of buildBadges(job)) {
      const badge = document.createElement("span");
      badge.className = `badge ${cls}`.trim();
      badge.textContent = text;
      badges.appendChild(badge);
    }
  }

  const description = card.querySelector(".job-card__description");
  if (description) {
    description.textContent = job.description_text || "No description available.";
  }
}

function buildBadges(job) {
  const result = [];
  if (job.is_new) result.push(["badge--accent", "New"]);
  const language = languageLabel(job.language);
  if (language) result.push(["badge--neutral", language]);
  const remote = remoteLabel(job.remote_type);
  if (remote) result.push(["badge--neutral", remote]);
  const scope = locationScopeLabel(job.location_scope);
  if (scope) result.push(["badge--neutral", scope]);
  if (job.overseas_eligible != null || job.visa_sponsorship) {
    result.push(
      job.overseas_eligible === 1
        ? ["badge--ok", "Overseas eligible"]
        : ["badge--warn", "Japan residents only"],
    );
  }
  for (const tag of job.security_tags || []) {
    if (tag) result.push(["badge--neutral", tag]);
  }
  return result;
}

/* ------------------------------ refresh ------------------------------ */

function renderRefreshPanel(status) {
  const statusLine = $("refresh-status-line");
  if (statusLine) {
    if (status.status === "running") {
      statusLine.textContent = `Refresh running${status.current_source ? `: ${status.current_source}` : ""}.`;
    } else if (status.status === "success") {
      statusLine.textContent = "Refresh finished successfully.";
    } else if (status.status === "partial") {
      statusLine.textContent = "Refresh finished with source errors.";
    } else if (status.status === "failed") {
      statusLine.textContent = "Refresh failed.";
    } else {
      statusLine.textContent = "No refresh yet.";
    }
  }

  const list = $("refresh-source-list");
  if (list) {
    list.innerHTML = "";
    const entries = Object.entries(status.sources || {});
    if (entries.length === 0) {
      const empty = document.createElement("li");
      empty.className = "refresh-source";
      empty.textContent = "No source results reported.";
      list.appendChild(empty);
    }
    for (const [sourceId, progress] of entries) {
      const item = document.createElement("li");
      item.className = "refresh-source";
      const name = document.createElement("span");
      name.className = "refresh-source__name";
      name.textContent = sourceName(sourceId);
      const statusText = document.createElement("span");
      statusText.className = "refresh-source__status";
      statusText.textContent = `${progress.status} · found ${progress.found} · new ${progress.new} · updated ${progress.updated} · skipped ${progress.skipped} · errors ${progress.errors}`;
      item.appendChild(name);
      item.appendChild(statusText);
      if (progress.error_message) {
        const error = document.createElement("div");
        error.className = "refresh-source__error";
        error.textContent = progress.error_message;
        item.appendChild(error);
      }
      list.appendChild(item);
    }
  }

  const again = $("refresh-again");
  if (again) again.hidden = status.status === "running";
}

async function pollRefreshStatus() {
  const status = await fetchJson("/api/refresh/status");
  renderRefreshPanel(status);
  if (status.status !== "running") {
    stopRefreshPolling();
    refreshRunning = false;
    setRefreshButtonState(false);
    await Promise.all([loadStats(), loadJobs()]);
    return;
  }
  refreshPollTimer = setTimeout(() => {
    void pollRefreshStatus();
  }, 1000);
}

function stopRefreshPolling() {
  if (refreshPollTimer) {
    clearTimeout(refreshPollTimer);
    refreshPollTimer = null;
  }
}

function setRefreshButtonState(running) {
  const button = $("refresh-button");
  if (!button) return;
  refreshRunning = running;
  button.disabled = running;
  const label = $("refresh-button-label");
  if (label) label.textContent = running ? "Refreshing…" : "Refresh now";
}

async function startRefresh() {
  if (refreshRunning) return;
  refreshRunning = true;
  setRefreshButtonState(true);
  const button = $("refresh-button");
  if (button) button.disabled = true;
  try {
    const data = await fetchJson("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ window_days: Number(state.days) > 0 ? Number(state.days) : 30 }),
    });
    renderRefreshPanel({
      status: data.status || "running",
      current_source: null,
      sources: {},
    });
    if (data.status === "running") {
      void pollRefreshStatus();
    }
  } catch (error) {
    // A 409 means another refresh owns the lock; either way, poll until settled.
    void pollRefreshStatus();
  }
}

/* ------------------------------ events ------------------------------- */

let reloadTimer = null;
function scheduleReload() {
  if (reloadTimer) clearTimeout(reloadTimer);
  reloadTimer = setTimeout(() => {
    void Promise.all([loadJobs(), loadStats()]);
  }, 250);
}

function onFilterChange() {
  writeStateFromInputs();
  scheduleReload();
}

function init() {
  readFiltersFromInputs();
  syncUrl();

  document.getElementById("filters")?.addEventListener("input", onFilterChange);
  document.getElementById("filters")?.addEventListener("change", onFilterChange);
  document.getElementById("filters")?.addEventListener("click", onFilterChange);
  document.getElementById("filters-clear")?.addEventListener("click", () => {
    const defaults = {
      q: "",
      source: "",
      role: "technical",
      language: "",
      location: "",
      location_scope: "japan",
      remote: "",
      visa: "",
      tag: "",
      days: "3",
      sort: "posted_desc",
      include_active: false,
    };
    Object.assign(state, defaults);
    writeStateFromInputs();
    void Promise.all([loadJobs(), loadStats()]);
  });
  document.getElementById("refresh-button")?.addEventListener("click", () => {
    void startRefresh();
  });
  document.getElementById("refresh-again")?.addEventListener("click", () => {
    void startRefresh();
  });
  $("job-list")?.addEventListener("click", (event) => {
    const retry = event.target.closest("#jobs-retry");
    if (retry) {
      retry.remove();
      void loadJobs();
    }
  });

  void (async () => {
    try {
      await loadSources();
      const status = await fetchJson("/api/refresh/status");
      renderRefreshPanel(status);
      if (status.status === "running") {
        refreshRunning = true;
        setRefreshButtonState(true);
        void pollRefreshStatus();
      }
      await loadStats();
      await loadJobs();
    } catch (error) {
      setListState({
        kind: "error",
        message: "Could not load dashboard data. Press Refresh to try fetching from sources.",
      });
    }
  })();
}

document.addEventListener("DOMContentLoaded", init);
