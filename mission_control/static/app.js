"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { overview: null, git: null, tasks: [], workers: [], approvals: [], events: [], health: null };
let toastTimer;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
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

function compactPayload(payload) {
  const entries = Object.entries(payload || {}).filter(([, value]) => value !== null && value !== "");
  return entries.slice(0, 3).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · ");
}

async function loadAll({ quiet = false } = {}) {
  try {
    const [overview, git, tasks, workers, approvals, events, health] = await Promise.all([
      api("/api/mc/overview"), api("/api/mc/git"), api("/api/mc/tasks"),
      api("/api/mc/workers"), api("/api/mc/approvals"), api("/api/mc/events?limit=150"),
      api("/api/mc/health"),
    ]);
    Object.assign(state, {
      overview, git, tasks: tasks.tasks, workers: workers.workers,
      approvals: approvals.approvals, events: events.events, health,
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
  renderApprovals();
  renderEvents();
  renderHealth();
}

function renderOverview() {
  const overview = state.overview || {};
  text("#overview-title", overview.mission, "No active mission");
  text("#mission-detail", `${overview.authority || "Local Core"} · ${overview.launch_mode || "manual"} launch`);
  text("#active-step", overview.active_step);
  text("#decision-state", (overview.decision_state || "").replaceAll("_", " "));
  text("#verification-state", overview.verification?.confidence);
  text("#approval-count", overview.pending_approvals ?? 0);
  setHealth(overview.system_health === "healthy", overview.system_health || "unknown");
}

function setHealth(ok, label) {
  const pill = $("#health-pill");
  pill.replaceChildren();
  const dot = node("span", `status-dot ${ok ? "status-ok" : "status-bad"}`);
  dot.setAttribute("aria-hidden", "true");
  pill.append(dot, document.createTextNode(label.replaceAll("_", " ")));
}

function renderGit() {
  const git = state.git || {};
  text("#git-relationship", git.relationship);
  text("#git-branch", git.branch || (git.detached_head ? "Detached HEAD" : null));
  text("#git-upstream", git.upstream, "None");
  text("#git-ahead", git.ahead);
  text("#git-behind", git.behind);
  text("#git-modified", git.modified_count);
  text("#git-untracked", git.untracked_count);
  text("#git-staged", git.staged_count);
  text("#git-conflicts", git.conflict_count);
  text("#git-worktree", git.worktree);
  text("#git-remote", git.remote_url, "Not configured");
  text("#git-fetch", friendlyTime(git.last_fetch_at));
  text("#git-auth", (git.authentication || "not checked").replaceAll("_", " "));
  text("#git-fresh", git.remote_state_fresh ? "Fresh receipt" : "Not fresh");
  text("#git-lease", git.active_write_lease ? `${git.active_write_lease.owner} until ${friendlyTime(git.active_write_lease.expires_at)}` : "Available");
  text("#git-pending", `Commit ${git.pending_commit ? "yes" : "no"} · Push ${git.pending_push === null ? "unknown" : (git.pending_push ? "yes" : "no")}`);
  text("#git-commit", git.last_commit);
}

function renderWorkers() {
  const root = $("#worker-list");
  root.replaceChildren();
  text("#worker-count", state.workers.length);
  for (const worker of state.workers) {
    const card = node("article", "worker-card");
    const title = node("div", "worker-title");
    title.append(node("strong", "", worker.display_name));
    const chip = node("span", "status-chip", worker.status);
    chip.dataset.status = worker.status;
    title.append(chip);
    const provider = node("p", "", `${worker.provider} · ${worker.local_repository_access ? "local repository" : "bounded context"} · no remote writes`);
    const task = node("p", "", worker.assigned_task ? `Assigned task: ${worker.assigned_task}` : "No assigned task");
    card.append(title, provider, task);
    root.append(card);
  }
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
    const status = node("span", "status-chip", task.status);
    status.dataset.status = task.status;
    meta.append(status, node("span", "", `Priority ${task.priority}`), node("span", "", task.write_required ? "Write lease required" : "Read-only"));
    if (task.assigned_adapter) meta.append(node("span", "", `Worker ${task.assigned_adapter}`));
    main.append(meta);
    if (task.blocker) main.append(node("p", "helper", task.blocker));
    const actions = node("div", "task-actions");
    if (task.status === "queued") {
      actions.append(
        button("Claude", () => assignTask(task, "claude")),
        button("Codex", () => assignTask(task, "codex")),
      );
    }
    if (task.write_required && ["preparing", "running", "waiting", "verifying"].includes(task.status)) actions.append(button("Keep lease", () => heartbeatTask(task)));
    if (task.status === "preparing" || task.status === "waiting") actions.append(button("Start", () => transitionTask(task, "running")));
    if (task.status === "running") actions.append(button("Verify", () => transitionTask(task, "verifying")), button("Pause", () => transitionTask(task, "paused")));
    if (task.status === "verifying") actions.append(button("Complete", () => openCompletion(task), "button button-primary"));
    if (["blocked", "failed", "paused"].includes(task.status)) actions.append(button("Retry", () => retryTask(task)));
    card.append(main, actions);
    root.append(card);
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
    row.append(node("dt", "", key.replaceAll("_", " ")), node("dd", "", Array.isArray(value) ? (value.join(", ") || "None") : String(value)));
    root.append(row);
  }
}

async function assignTask(task, adapterId) {
  try {
    await api(`/api/mc/tasks/${task.task_id}/assign`, { method: "POST", body: JSON.stringify({ adapter_id: adapterId, expected_version: task.version, bounded_context: {} }) });
    showToast(`Task assigned to ${adapterId}`);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function transitionTask(task, status, result = null) {
  try {
    await api(`/api/mc/tasks/${task.task_id}/transition`, { method: "POST", body: JSON.stringify({ status, expected_version: task.version, result }) });
    showToast(`Task moved to ${status}`);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function retryTask(task) {
  try {
    await api(`/api/mc/tasks/${task.task_id}/retry`, { method: "POST", body: JSON.stringify({ expected_version: task.version }) });
    showToast("Task returned to queue");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); }
}

async function heartbeatTask(task) {
  try {
    const result = await api(`/api/mc/tasks/${task.task_id}/lease/heartbeat`, { method: "POST", body: JSON.stringify({ expected_version: task.version }) });
    showToast(`Write lease renewed until ${friendlyTime(result.lease.expires_at)}`);
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
}

async function decideApproval(approvalId, approved) {
  try {
    const result = await api(`/api/mc/approvals/${approvalId}/decision`, { method: "POST", body: JSON.stringify({ approved, note: "Decision recorded in Mission Control" }) });
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
    showToast(payload.remote_state_fresh ? "Remote refs refreshed" : "Fetch failed; remote claims withheld", !payload.remote_state_fresh);
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
  const payload = {
    objective: String(data.get("objective") || "").trim(),
    priority: Number(data.get("priority") || 50),
    acceptance_criteria: String(data.get("criteria") || "").split("\n").map((line) => line.trim()).filter(Boolean),
    dependencies: [],
    write_required: data.get("write_required") === "on",
  };
  try {
    await api("/api/mc/tasks", { method: "POST", body: JSON.stringify(payload) });
    form.reset();
    dialog.close();
    showToast("Task queued and journaled");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); }
});

const completeDialog = $("#complete-dialog");
function openCompletion(task) {
  const form = $("#complete-form");
  form.elements.task_id.value = task.task_id;
  form.elements.expected_version.value = String(task.version);
  completeDialog.showModal();
  form.elements.summary.focus();
}
$("#close-complete").addEventListener("click", () => completeDialog.close());
$("#cancel-complete").addEventListener("click", () => completeDialog.close());
$("#complete-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const evidence = String(data.get("evidence") || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const payload = {
    status: "complete",
    expected_version: Number(data.get("expected_version")),
    result: {
      summary: String(data.get("summary") || "").trim(),
      tests_run: evidence,
    },
  };
  try {
    await api(`/api/mc/tasks/${data.get("task_id")}/transition`, { method: "POST", body: JSON.stringify(payload) });
    form.reset();
    completeDialog.close();
    showToast("Task completed with verification evidence");
    await loadAll({ quiet: true });
  } catch (error) { showToast(error.message, true); await loadAll({ quiet: true }); }
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
