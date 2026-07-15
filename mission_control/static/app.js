"use strict";

const $ = (selector) => document.querySelector(selector);
const state = {
  overview: null,
  git: null,
  tasks: [],
  workers: [],
  approvals: [],
  events: [],
  health: null,
  verificationCatalog: { profiles: [], execution_available: false },
  verificationRuns: [],
  attention: [],
};
let toastTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Nero-Local": "1",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

function text(selector, value, fallback = "—") {
  const element = $(selector);
  if (element) element.textContent = value ?? fallback;
}

function node(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined) element.textContent = content;
  return element;
}

function button(label, handler, className = "button button-secondary") {
  const element = node("button", className, label);
  element.type = "button";
  element.addEventListener("click", handler);
  return element;
}

function disabledButton(label, title) {
  const element = node("button", "button button-secondary", label);
  element.type = "button";
  element.disabled = true;
  element.title = title;
  return element;
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast is-visible${isError ? " is-error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = "toast"; }, 4200);
}

function friendlyTime(value) {
  if (!value) return "Never by Core";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}

function humanize(value, fallback = "unknown") {
  return String(value || fallback).replaceAll("_", " ");
}

function compactPayload(payload) {
  const entries = Object.entries(payload || {}).filter(([, value]) => value !== null && value !== "");
  return entries.slice(0, 3).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · ");
}

function profileForTask(task) {
  return state.verificationCatalog.profiles.find((profile) => (
    profile.profile_id === task.verification_profile_id
    && Number(profile.version) === Number(task.verification_profile_version)
  )) || state.verificationCatalog.profiles.find((profile) => profile.profile_id === task.verification_profile_id);
}

function runForTask(task) {
  return state.verificationRuns.find((run) => run.run_id === task.verified_run_id)
    || state.verificationRuns.find((run) => run.task_id === task.task_id);
}

async function fetchAttentionFeed() {
  let cursor = 0;
  let feed = { current_sequence: 0, next_cursor: 0, items: [] };
  const items = [];
  for (let page = 0; page < 100; page += 1) {
    feed = await api(`/api/mc/attention?after_sequence=${cursor}&limit=100`);
    items.push(...(feed.items || []));
    const next = Number(feed.next_cursor || cursor);
    const current = Number(feed.current_sequence || next);
    if (next >= current || next <= cursor) break;
    cursor = next;
  }
  return { ...feed, items: items.slice(-500) };
}

async function loadAll({ quiet = false } = {}) {
  try {
    await api("/api/mc/reconcile", { method: "POST" });
    const [overview, git, tasks, workers, approvals, events, health, catalog, runs, attentionFeed] = await Promise.all([
      api("/api/mc/overview"),
      api("/api/mc/git"),
      api("/api/mc/tasks"),
      api("/api/mc/workers"),
      api("/api/mc/approvals"),
      api("/api/mc/events?limit=150"),
      api("/api/mc/health"),
      api("/api/mc/verification/profiles"),
      api("/api/mc/verification/runs?limit=100"),
      fetchAttentionFeed(),
    ]);
    Object.assign(state, {
      overview,
      git,
      tasks: tasks.tasks || [],
      workers: workers.workers || [],
      approvals: approvals.approvals || [],
      events: events.events || [],
      health,
      verificationCatalog: { profiles: [], execution_available: false, ...catalog },
      verificationRuns: runs.runs || [],
      attention: attentionFeed.attention || attentionFeed.items || [],
    });
    renderAll();
    if (!quiet) showToast("Mission Control state refreshed");
  } catch (error) {
    setHealth(false, "Connection failed");
    showToast(error.message, true);
  }
}

function renderAll() {
  renderOverview();
  renderGit();
  renderWorkers();
  renderTasks();
  renderAttention();
  renderVerification();
  renderApprovals();
  renderEvents();
  renderHealth();
  syncTaskProfileOptions();
}

function renderOverview() {
  const overview = state.overview || {};
  text("#overview-title", overview.mission, "No active mission");
  text("#mission-detail", `${overview.authority || "Local Core"} · ${overview.launch_mode || "manual"} launch`);
  text("#active-step", overview.active_step);
  text("#decision-state", humanize(overview.decision_state));
  text("#verification-state", overview.verification?.confidence);
  text("#approval-count", overview.pending_approvals ?? 0);
  setHealth(
    overview.internal_state_health === "consistent",
    `Internal state ${overview.internal_state_health || "unknown"}`,
  );
}

function setHealth(ok, label) {
  const pill = $("#health-pill");
  pill.replaceChildren();
  const dot = node("span", `status-dot ${ok ? "status-ok" : "status-bad"}`);
  dot.setAttribute("aria-hidden", "true");
  pill.append(dot, document.createTextNode(humanize(label)));
}

function renderGit() {
  const git = state.git || {};
  const measured = git.inspection_ok === true;
  text("#git-relationship", git.relationship);
  text("#git-branch", git.branch || (git.detached_head ? "Detached HEAD" : null));
  text("#git-upstream", git.upstream, "None");
  text("#git-ahead", git.ahead);
  text("#git-behind", git.behind);
  text("#git-modified", measured ? git.modified_count : "Unavailable");
  text("#git-untracked", measured ? git.untracked_count : "Unavailable");
  text("#git-staged", measured ? git.staged_count : "Unavailable");
  text("#git-conflicts", measured ? git.conflict_count : "Unavailable");
  text("#git-worktree", git.worktree);
  text("#git-remote", git.remote_url, "Not configured");
  text("#git-fetch", friendlyTime(git.last_fetch_at));
  text("#git-auth", humanize(git.authentication, "not checked"));
  text("#git-fresh", git.remote_state_fresh ? "Fresh receipt" : "Not fresh");
  text("#git-lease", git.active_write_lease ? `${git.active_write_lease.owner} until ${friendlyTime(git.active_write_lease.expires_at)}` : "Available");
  text("#git-pending", measured
    ? `Commit ${git.pending_commit ? "yes" : "no"} · Push ${git.pending_push === null ? "unknown" : (git.pending_push ? "yes" : "no")}`
    : "Unavailable");
  text("#git-commit", git.last_commit);
  text(
    "#git-errors",
    (git.errors || []).length
      ? `Caution: ${(git.errors || []).join(" · ")}`
      : (measured ? "Required local Git probes passed." : "Required local Git probes unavailable."),
  );
}

function renderWorkers() {
  const root = $("#worker-list");
  root.replaceChildren();
  text("#worker-count", state.workers.length);
  for (const worker of state.workers) {
    const card = node("article", "worker-card");
    const title = node("div", "worker-title");
    title.append(node("strong", "", worker.display_name));
    const chip = node("span", "status-chip", `Packet/task state: ${humanize(worker.status)}`);
    chip.dataset.status = worker.status;
    title.append(chip);
    const provider = node("p", "", `${worker.provider} packet adapter · provider not contacted · no remote writes`);
    const task = node("p", "", worker.assigned_task ? `Packet prepared for task: ${worker.assigned_task}` : "No packet task");
    card.append(title, provider, task);
    if (worker.last_result) {
      card.append(node(
        "p",
        "helper",
        `Advisory ${humanize(worker.last_result.source, "unverified")} report · contacted by Mission Control: ${worker.last_result.provider_contacted === true ? "yes" : "no"}`,
      ));
    }
    root.append(card);
  }
}

function appendTaskVerification(main, task) {
  const legacyCompletion = task.status === "complete" && !task.verified_run_id;
  const profile = profileForTask(task);
  const profileLabel = profile
    ? `${profile.display_name} v${profile.version}`
    : (task.verification_profile_id ? `${task.verification_profile_id} v${task.verification_profile_version}` : "No verification profile pinned");
  const policy = node("div", "task-verification");
  policy.append(node("span", "verification-label", "Verification policy"), node("strong", "", profileLabel));
  if (task.verification_profile_digest) {
    policy.append(node("code", "hash-value", task.verification_profile_digest));
  }
  if (legacyCompletion) {
    const legacy = node("span", "status-chip", "Legacy completion — not Core-verified");
    legacy.dataset.status = "legacy";
    policy.append(legacy);
    main.append(policy);
    return;
  }

  const run = runForTask(task);
  if (run) {
    const runLine = node("div", "verification-run-line");
    const chip = node("span", "status-chip", humanize(run.status));
    chip.dataset.status = run.status;
    const integrityOk = state.health?.internal_state_ok === true && state.overview?.verification?.integrity_ok === true;
    const authority = run.authoritative
      ? (integrityOk ? "authoritative" : "authority claim — integrity unavailable")
      : "not authoritative";
    runLine.append(chip, node("span", "", `${run.backend_id || "No backend"} · ${authority}`));
    policy.append(runLine);
    if (run.evidence_hash) policy.append(node("code", "hash-value", run.evidence_hash));
  }
  main.append(policy);
}

function profileBindingControls(task) {
  const wrapper = node("div", "policy-binding");
  const select = node("select", "policy-select");
  select.setAttribute("aria-label", `Verification profile for ${task.objective}`);
  for (const profile of state.verificationCatalog.profiles) {
    const option = node("option", "", `${profile.display_name} v${profile.version}`);
    option.value = profile.profile_id;
    select.append(option);
  }
  const bind = button("Bind profile", () => bindVerificationProfile(task, select.value));
  if (!state.verificationCatalog.profiles.length) {
    const option = node("option", "", "No profiles available");
    option.value = "";
    select.append(option);
    select.disabled = true;
    bind.disabled = true;
  }
  wrapper.append(select, bind);
  return wrapper;
}

function renderTasks() {
  const root = $("#task-list");
  root.replaceChildren();
  if (!state.tasks.length) {
    root.append(node("div", "empty", "No queued tasks."));
    return;
  }
  for (const task of state.tasks) {
    const card = node("article", "task-card");
    const main = node("div", "task-main");
    main.append(node("strong", "", task.objective));
    const meta = node("div", "task-meta");
    const status = node("span", "status-chip", humanize(task.status));
    status.dataset.status = task.status;
    meta.append(status, node("span", "", `Priority ${task.priority}`), node("span", "", task.write_required ? "Write lease required" : "Read-only"));
    if (task.assigned_adapter) meta.append(node("span", "", `Packet adapter ${task.assigned_adapter}`));
    main.append(meta);
    if (task.blocker) main.append(node("p", "helper", task.blocker));
    appendTaskVerification(main, task);

    const actions = node("div", "task-actions");
    if (task.status === "queued") {
      actions.append(
        button("Prepare Claude packet", () => assignTask(task, "claude")),
        button("Prepare Codex packet", () => assignTask(task, "codex")),
      );
    }
    if (!task.verification_profile_id && ["queued", "preparing", "running", "waiting", "verifying"].includes(task.status)) {
      actions.append(profileBindingControls(task));
    }
    if (task.write_required && ["preparing", "running", "waiting", "verifying"].includes(task.status)) {
      actions.append(button("Keep lease", () => heartbeatTask(task)));
    }
    if (task.status === "preparing" || task.status === "waiting") {
      actions.append(button("Start", () => transitionTask(task, "running")));
    }
    if (task.status === "running") {
      if (task.verification_profile_id) actions.append(button("Enter verification", () => transitionTask(task, "verifying")));
      actions.append(button("Pause", () => transitionTask(task, "paused")));
    }
    if (task.status === "verifying") {
      if (task.verification_profile_id) {
        actions.append(button("Run Core verification", () => runCoreVerification(task), "button button-primary"));
      }
      actions.append(disabledButton("Direct complete unavailable", "Only an authoritative Nero Core verification run may complete this task."));
    }
    if (["blocked", "failed", "paused"].includes(task.status)) actions.append(button("Retry", () => retryTask(task)));
    card.append(main, actions);
    root.append(card);
  }
}

function renderAttention() {
  const root = $("#attention-list");
  root.replaceChildren();
  const items = state.attention;
  const actionable = items.filter((item) => item.requires_action !== false).length;
  text("#attention-count", actionable);
  if (!items.length) {
    root.append(node("div", "empty", "Nothing needs your attention."));
    return;
  }
  for (const item of items) {
    const card = node("article", "attention-card");
    const title = node("div", "worker-title");
    title.append(node("strong", "", item.title || humanize(item.kind, "Mission Control update")));
    const chip = node("span", "status-chip", humanize(item.status));
    chip.dataset.status = item.status;
    title.append(chip);
    card.append(title, node("p", "", item.summary || "Review the recorded evidence."), node("time", "attention-time", friendlyTime(item.created_at)));
    if (item.task_id) {
      const link = node("a", "button button-secondary attention-link", "Review task");
      link.href = "#planner";
      card.append(link);
    } else if (String(item.kind || "").startsWith("approval")) {
      const link = node("a", "button button-secondary attention-link", "Review approval");
      link.href = "#approvals";
      card.append(link);
    }
    root.append(card);
  }
}

function evidenceDetails(run) {
  const detail = node("details", "evidence-details");
  detail.append(node("summary", "", "Inspect Core evidence"));
  const payload = {
    run_id: run.run_id,
    task_version: run.task_version,
    profile_digest: run.profile_digest,
    head_before: run.head_before,
    head_after: run.head_after,
    lease_fencing_token: run.lease_fencing_token,
    evidence_hash: run.evidence_hash,
    evidence: run.evidence,
    backend_capabilities: run.backend_capabilities,
    error_code: run.error_code,
  };
  detail.append(node("pre", "evidence-json", JSON.stringify(payload, null, 2)));
  return detail;
}

function renderVerification() {
  const profilesRoot = $("#verification-profile-list");
  const runsRoot = $("#verification-run-list");
  profilesRoot.replaceChildren();
  runsRoot.replaceChildren();
  text("#verification-run-count", `${state.verificationRuns.length} runs`);
  const capabilities = state.verificationCatalog.backend || {};
  const availability = state.verificationCatalog.execution_available
    ? `${capabilities.backend_id || "Verification runner"} available`
    : "Backend unavailable";
  text("#verification-backend-state", availability);
  const availabilityChip = $("#verification-backend-state");
  availabilityChip.dataset.status = state.verificationCatalog.execution_available ? "passed" : "backend_unavailable";

  const profiles = state.verificationCatalog.profiles || [];
  if (!profiles.length) {
    profilesRoot.append(node("div", "empty", "No Core verification profiles are available."));
  }
  for (const profile of profiles) {
    const card = node("article", "verification-card");
    const title = node("div", "worker-title");
    title.append(node("strong", "", profile.display_name));
    title.append(node("span", "status-chip", `v${profile.version}`));
    card.append(title, node("p", "", profile.description));
    card.append(node("p", "verification-fact", `Required OS: ${humanize(profile.required_os_family)}`));
    card.append(node("code", "hash-value", profile.manifest_digest));
    profilesRoot.append(card);
  }

  if (!state.verificationRuns.length) {
    const message = state.verificationCatalog.execution_available
      ? "No verification runs have been recorded."
      : "Default verification backend unavailable; no result can be authoritative.";
    runsRoot.append(node("div", "empty", message));
  }
  for (const run of state.verificationRuns.slice(0, 12)) {
    const card = node("article", "verification-card");
    const title = node("div", "worker-title");
    title.append(node("strong", "", `Task ${run.task_id}`));
    const chip = node("span", "status-chip", humanize(run.status));
    chip.dataset.status = run.status;
    title.append(chip);
    card.append(title);
    const integrityOk = state.health?.internal_state_ok === true && state.overview?.verification?.integrity_ok === true;
    const authority = run.authoritative
      ? (integrityOk ? "Authoritative Core result" : "Recorded authority claim — integrity unavailable")
      : "Not authoritative";
    const backend = run.status === "backend_unavailable"
      ? "Backend unavailable · result not authoritative"
      : `${run.backend_id || "Unknown backend"} · ${authority}`;
    card.append(node("p", "", backend), node("time", "attention-time", friendlyTime(run.completed_at || run.started_at)));
    if (run.evidence_hash) card.append(node("code", "hash-value", run.evidence_hash));
    card.append(evidenceDetails(run));
    runsRoot.append(card);
  }
}

function renderApprovals() {
  const root = $("#approval-list");
  root.replaceChildren();
  const pending = state.approvals.filter((approval) => approval.status === "pending");
  if (!pending.length) {
    root.append(node("div", "empty", "No pending approvals · remote actions unavailable."));
    return;
  }
  for (const approval of pending) {
    const card = node("article", "approval-card");
    card.append(node("strong", "", approval.action), node("p", "", approval.summary));
    const actions = node("div", "task-actions");
    actions.append(
      button("Deny", () => decideApproval(approval.approval_id, false), "button button-danger"),
      button("Approve evidence", () => decideApproval(approval.approval_id, true), "button button-primary"),
    );
    card.append(actions);
    root.append(card);
  }
}

function renderEvents() {
  const root = $("#event-list");
  root.replaceChildren();
  const prefix = $("#event-filter").value;
  const events = prefix ? state.events.filter((event) => event.event_type.startsWith(prefix)) : state.events;
  if (!events.length) {
    root.append(node("li", "empty", "No matching events."));
    return;
  }
  for (const event of events.slice(0, 80)) {
    const item = node("li", "event-item");
    item.append(node("time", "", friendlyTime(event.created_at)));
    const body = node("div", "");
    body.append(node("strong", "", event.event_type), node("p", "", compactPayload(event.payload) || `Actor: ${event.actor}`));
    const detail = node("details", "");
    detail.append(node("summary", "", "Inspect evidence"), node("pre", "", JSON.stringify(event, null, 2)));
    body.append(detail);
    item.append(body);
    root.append(item);
  }
}

function renderHealth() {
  const root = $("#health-list");
  root.replaceChildren();
  for (const [key, value] of Object.entries(state.health || {})) {
    const row = node("div", "");
    row.append(node("dt", "", humanize(key)), node("dd", "", Array.isArray(value) ? (value.join(", ") || "None") : String(value)));
    root.append(row);
  }
}

function syncTaskProfileOptions() {
  const select = $("#task-profile");
  const current = select.value;
  select.replaceChildren();
  const empty = node("option", "", "No profile pinned yet");
  empty.value = "";
  select.append(empty);
  for (const profile of state.verificationCatalog.profiles || []) {
    const option = node("option", "", `${profile.display_name} v${profile.version}`);
    option.value = profile.profile_id;
    select.append(option);
  }
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

async function assignTask(task, adapterId) {
  try {
    await api(`/api/mc/tasks/${task.task_id}/assign`, {
      method: "POST",
      body: JSON.stringify({ adapter_id: adapterId, expected_version: task.version, bounded_context: {} }),
    });
    showToast(`${adapterId} packet prepared; provider not contacted`);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function transitionTask(task, status) {
  try {
    await api(`/api/mc/tasks/${task.task_id}/transition`, {
      method: "POST",
      body: JSON.stringify({ status, expected_version: task.version }),
    });
    showToast(`Task moved to ${status}`);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function bindVerificationProfile(task, profileId) {
  if (!profileId) return;
  try {
    await api(`/api/mc/tasks/${task.task_id}/verification-policy`, {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId, expected_version: task.version }),
    });
    showToast("Immutable profile binding pinned to task");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function runCoreVerification(task) {
  try {
    const result = await api(`/api/mc/tasks/${task.task_id}/verify`, {
      method: "POST",
      body: JSON.stringify({ expected_version: task.version }),
    });
    const status = humanize(result.run?.status, "recorded");
    showToast(`Core verification ${status}`, result.run?.status !== "passed");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function retryTask(task) {
  try {
    await api(`/api/mc/tasks/${task.task_id}/retry`, {
      method: "POST",
      body: JSON.stringify({ expected_version: task.version }),
    });
    showToast("Task returned to queue");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); }
}

async function heartbeatTask(task) {
  try {
    const result = await api(`/api/mc/tasks/${task.task_id}/lease/heartbeat`, {
      method: "POST",
      body: JSON.stringify({ expected_version: task.version }),
    });
    showToast(`Write lease renewed until ${friendlyTime(result.lease.expires_at)}`);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function decideApproval(approvalId, approved) {
  try {
    const result = await api(`/api/mc/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ approved, note: "Decision recorded in Mission Control" }),
    });
    showToast(result.message);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); }
}

$("#refresh-all").addEventListener("click", () => loadAll());
$("#fetch-state").addEventListener("click", async () => {
  const target = $("#fetch-state");
  target.disabled = true;
  target.textContent = "Fetching…";
  try {
    const payload = await api("/api/mc/git/refresh", { method: "POST" });
    state.git = payload;
    renderGit();
    showToast(payload.remote_state_fresh ? "Tracked evidence refreshed" : "Fetch failed; remote claims withheld", !payload.remote_state_fresh);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); }
  finally { target.disabled = false; target.textContent = "Fetch & refresh"; }
});

$("#event-filter").addEventListener("change", renderEvents);
const dialog = $("#task-dialog");
$("#new-task").addEventListener("click", () => dialog.showModal());
$("#close-task").addEventListener("click", () => dialog.close());
$("#cancel-task").addEventListener("click", () => dialog.close());
$("#task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const profileId = String(data.get("verification_profile_id") || "");
  const payload = {
    objective: String(data.get("objective") || "").trim(),
    priority: Number(data.get("priority") || 50),
    acceptance_criteria: String(data.get("criteria") || "").split("\n").map((line) => line.trim()).filter(Boolean),
    dependencies: [],
    write_required: data.get("write_required") === "on",
    verification_profile_id: profileId || null,
  };
  try {
    await api("/api/mc/tasks", { method: "POST", body: JSON.stringify(payload) });
    form.reset();
    dialog.close();
    showToast("Task queued and journaled");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); }
});

function updateClock() {
  const now = new Date();
  $("#clock").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const hour = now.getHours();
  const greeting = hour < 12 ? "Good morning" : (hour < 18 ? "Good afternoon" : "Good evening");
  $("#greeting").textContent = `${greeting}, Toni.`;
}

updateClock();
setInterval(updateClock, 30000);
loadAll({ quiet: true });
setInterval(() => loadAll({ quiet: true }), 15000);
