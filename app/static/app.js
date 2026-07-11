/* ============================================================
   Your Personal AI — browser logic
   Talks to the local server, streams replies, manages memories.
   ============================================================ */

const els = {
  messages: document.getElementById("messages"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  aiName: document.getElementById("ai-name"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  newChat: document.getElementById("new-chat"),
  memoryForm: document.getElementById("memory-form"),
  memoryInput: document.getElementById("memory-input"),
  memoryList: document.getElementById("memory-list"),
  menuToggle: document.getElementById("menu-toggle"),
  sidebar: document.getElementById("sidebar"),
};

let aiName = "Your AI";
let ownerName = "friend";
let busy = false;

// ---- Small helpers ----------------------------------------------------

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Very small, safe markdown: escapes everything first, then adds code
// blocks, inline code, and bold. Enough to make replies readable.
function renderMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.replace(/^\n/, "")}</code></pre>`);
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return html;
}

function scrollToBottom() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function clearEmptyState() {
  const empty = els.messages.querySelector(".empty");
  if (empty) empty.remove();
}

function showEmptyState() {
  els.messages.innerHTML = `
    <div class="empty">
      <h1>Hey${ownerName && ownerName !== "friend" ? " " + escapeHtml(ownerName) : ""} 👋</h1>
      <p>I'm ${escapeHtml(aiName)} — your own AI, running entirely on your machine.
      Say anything to get started.</p>
    </div>`;
}

function addMessage(role, text) {
  clearEmptyState();
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "ai");
  div.innerHTML = role === "user" ? escapeHtml(text) : renderMarkdown(text);
  els.messages.appendChild(div);
  scrollToBottom();
  return div;
}

// ---- Loading existing state ------------------------------------------

async function loadConfig() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    aiName = cfg.ai_name || aiName;
    ownerName = cfg.owner_name || ownerName;
    els.aiName.textContent = aiName;
    document.title = aiName;
  } catch (_) { /* keep defaults */ }
}

async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    els.statusDot.className = "status-dot " + (s.ok ? "ok" : "bad");
    els.statusText.textContent = s.message;
    els.statusDot.title = s.message;
  } catch (_) {
    els.statusDot.className = "status-dot bad";
    els.statusText.textContent = "Server unreachable.";
  }
}

async function loadHistory() {
  try {
    const data = await (await fetch("/api/history")).json();
    els.messages.innerHTML = "";
    if (!data.messages.length) {
      showEmptyState();
      return;
    }
    for (const m of data.messages) addMessage(m.role, m.content);
    scrollToBottom();
  } catch (_) {
    showEmptyState();
  }
}

async function loadMemories() {
  try {
    const data = await (await fetch("/api/memories")).json();
    els.memoryList.innerHTML = "";
    for (const m of data.memories) {
      const li = document.createElement("li");
      const span = document.createElement("span");
      span.textContent = m.content;
      const btn = document.createElement("button");
      btn.textContent = "✕";
      btn.title = "Forget this";
      btn.onclick = () => deleteMemory(m.id, li);
      li.append(span, btn);
      els.memoryList.appendChild(li);
    }
  } catch (_) { /* ignore */ }
}

// ---- Sending a message (streaming) -----------------------------------

async function sendMessage(text) {
  if (busy || !text.trim()) return;
  busy = true;
  els.send.disabled = true;

  addMessage("user", text);
  els.input.value = "";
  autoGrow();

  const aiDiv = addMessage("ai", "");
  aiDiv.classList.add("thinking");
  let full = "";

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      full += decoder.decode(value, { stream: true });
      aiDiv.innerHTML = renderMarkdown(full);
      scrollToBottom();
    }
  } catch (err) {
    full += `\n\n[Connection error: ${err}]`;
    aiDiv.innerHTML = renderMarkdown(full);
  } finally {
    aiDiv.classList.remove("thinking");
    busy = false;
    els.send.disabled = false;
    els.input.focus();
    // Refresh the status dot in case the model just went up/down.
    loadStatus();
  }
}

async function deleteMemory(id, li) {
  try {
    await fetch(`/api/memories/${id}`, { method: "DELETE" });
    li.remove();
  } catch (_) { /* ignore */ }
}

// ---- UI wiring --------------------------------------------------------

function autoGrow() {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 200) + "px";
}

els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(els.input.value);
});

els.input.addEventListener("input", autoGrow);

// Enter to send, Shift+Enter for a new line.
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(els.input.value);
  }
});

els.newChat.addEventListener("click", async () => {
  await fetch("/api/new", { method: "POST" });
  els.messages.innerHTML = "";
  showEmptyState();
  els.sidebar.classList.remove("open");
});

els.memoryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const content = els.memoryInput.value.trim();
  if (!content) return;
  await fetch("/api/memories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  els.memoryInput.value = "";
  loadMemories();
});

els.menuToggle.addEventListener("click", () => {
  els.sidebar.classList.toggle("open");
});

// ---- Boot -------------------------------------------------------------

(async function init() {
  await loadConfig();
  showEmptyState();
  await Promise.all([loadStatus(), loadHistory(), loadMemories()]);
  els.input.focus();
  // Re-check the model connection every 30s.
  setInterval(loadStatus, 30000);
})();
