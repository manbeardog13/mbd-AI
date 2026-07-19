/* ============================================================
   Your Personal AI — browser logic
   Chat + streaming, long-term memories, and voice (talk & listen).
   ============================================================ */

const els = {
  messages: document.getElementById("messages"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  mic: document.getElementById("mic"),
  council: document.getElementById("council"),
  councilStatus: document.getElementById("council-status"),
  aiName: document.getElementById("ai-name"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  newChat: document.getElementById("new-chat"),
  memoryForm: document.getElementById("memory-form"),
  memoryInput: document.getElementById("memory-input"),
  memoryList: document.getElementById("memory-list"),
  menuToggle: document.getElementById("menu-toggle"),
  sidebar: document.getElementById("sidebar"),
  speakToggle: document.getElementById("speak-toggle"),
  handsfreeToggle: document.getElementById("handsfree-toggle"),
  micLang: document.getElementById("mic-lang"),
  humor: document.getElementById("humor"),
  humorVal: document.getElementById("humor-val"),
  convoMode: document.getElementById("convo-mode"),
  settingsClose: document.getElementById("settings-close"),
  scrim: document.getElementById("scrim"),
  convoOverlay: document.getElementById("convo-overlay"),
  orb: document.getElementById("orb"),
  convoStatus: document.getElementById("convo-status"),
  convoTranscript: document.getElementById("convo-transcript"),
  convoClose: document.getElementById("convo-close"),
};

let aiName = "Your AI";
let ownerName = "friend";
let busy = false;
let thinkingEnabled = false;
let councilReady = false;

// Hide <think>…</think> reasoning from the reply unless thinking is on.
// Also hides an unclosed <think> mid-stream so tags never flash on screen.
function cleanReply(text) {
  if (thinkingEnabled) return text;
  return text
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/<think>[\s\S]*$/i, "")
    .replace(/^\s+/, "");
}

// ---- Small helpers ----------------------------------------------------

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Very small, safe markdown: escape first, then add code blocks, inline
// code, and bold. Enough to make replies readable in the chat.
function renderMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.replace(/^\n/, "")}</code></pre>`);
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return html;
}

// Strip markdown + emoji so spoken replies sound natural (no "smiling face
// with sparkling eyes" read aloud mid-sentence).
function toSpeakable(text) {
  return text
    .replace(/```[\s\S]*?```/g, " (code) ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/[*_#>]/g, "")
    // Drop emoji, pictographs, skin-tone/flag modifiers, and their joiners.
    .replace(/[\p{Extended_Pictographic}\u{1F3FB}-\u{1F3FF}\u{1F1E6}-\u{1F1FF}\u200D\uFE0F]/gu, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/ +([,.;:!?\u2026])/g, "$1")   // tidy the gap a removed emoji leaves
    .trim();
}

function scrollToBottom() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function clearEmptyState() {
  const empty = els.messages.querySelector(".empty");
  if (empty) empty.remove();
}

function showEmptyState() {
  const greetName = ownerName && ownerName !== "friend" ? " " + escapeHtml(ownerName) : "";
  els.messages.innerHTML = `
    <div class="empty">
      <h1>Hey${greetName} 👋</h1>
      <p>What's on your mind?</p>
    </div>`;
}

function addMessage(role, text) {
  clearEmptyState();
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "ai");
  div.innerHTML = role === "user" ? escapeHtml(text) : renderMarkdown(cleanReply(text));
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
  stopSpeaking();   // if Nero's still talking, a new message cuts her off
  busy = true;
  els.send.disabled = true;

  addMessage("user", text);
  els.input.value = "";
  autoGrow();
  updateComposerButtons();

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
      aiDiv.innerHTML = renderMarkdown(cleanReply(full));
      scrollToBottom();
    }
  } catch (err) {
    full += `\n\n[Connection error: ${err}]`;
    aiDiv.innerHTML = renderMarkdown(cleanReply(full));
  } finally {
    aiDiv.classList.remove("thinking");
    busy = false;
    els.send.disabled = false;
    loadStatus();
    onReplyComplete(full);
  }
}

async function deleteMemory(id, li) {
  try {
    await fetch(`/api/memories/${id}`, { method: "DELETE" });
    li.remove();
  } catch (_) { /* ignore */ }
}

// ---- External Council: explicit, user-controlled cloud escalation -----

function stageLabel(stage) {
  return {
    architect: "OpenAI — Architect",
    builder: "Claude — Builder",
    reviewer: "OpenAI — Reviewer",
  }[stage] || stage;
}

function addCouncilResult(run) {
  clearEmptyState();
  const card = document.createElement("section");
  card.className = "msg ai council-result";

  const heading = document.createElement("h3");
  heading.textContent = "External Council";
  card.appendChild(heading);

  for (const turn of run.turns || []) {
    const turnEl = document.createElement("section");
    turnEl.className = "council-turn";
    const title = document.createElement("h4");
    title.textContent = stageLabel(turn.stage);
    const model = document.createElement("p");
    model.className = "council-model";
    model.textContent = turn.model ? `Model: ${turn.model}` : "";
    const output = document.createElement("pre");
    // Council text is remote, untrusted content: textContent keeps it inert.
    output.textContent = turn.text || "(No text returned.)";
    turnEl.append(title, model, output);
    card.appendChild(turnEl);
  }

  const sent = document.createElement("details");
  sent.className = "council-sent";
  const summary = document.createElement("summary");
  summary.textContent = "What Nero sent outside";
  sent.appendChild(summary);
  for (const transmission of run.transmissions || []) {
    const label = document.createElement("p");
    label.textContent = `${transmission.provider} · ${stageLabel(transmission.stage)}`;
    const content = document.createElement("pre");
    content.textContent = transmission.project_content || "";
    sent.append(label, content);
  }
  card.appendChild(sent);

  const note = document.createElement("p");
  note.className = "council-note";
  note.textContent = run.notice || "Council output is not stored in Nero's memory.";
  card.appendChild(note);
  els.messages.appendChild(card);
  scrollToBottom();
  return card;
}

function updateCouncilButton() {
  const hasText = els.input.value.trim().length > 0;
  els.council.disabled = busy || !councilReady || !hasText;
}

async function loadCouncilStatus() {
  try {
    const state = await (await fetch("/api/collaboration/status")).json();
    councilReady = !!state.configured;
    els.councilStatus.textContent = state.message || "External Council status unavailable.";
    els.council.title = councilReady
      ? "Ask OpenAI and Claude. Sends only the text you type after confirmation."
      : "Set up External Council in config.yaml to use it.";
  } catch (_) {
    councilReady = false;
    els.councilStatus.textContent = "External Council status could not be checked.";
  }
  updateCouncilButton();
}

async function runCouncil(text) {
  if (busy || !councilReady || !text.trim()) return;
  const approved = window.confirm(
    "External Council will send only the text you typed to OpenAI and Claude. " +
    "It will not send Nero's saved memories, normal chat history, local files, or API keys. Continue?"
  );
  if (!approved) return;

  stopSpeaking();
  busy = true;
  els.send.disabled = true;
  updateCouncilButton();
  addMessage("user", `External Council request:\n${text}`);
  els.input.value = "";
  autoGrow();
  updateComposerButtons();
  els.statusText.textContent = "External Council is coordinating OpenAI and Claude…";

  try {
    const response = await fetch("/api/collaboration", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: text, mode: "plan-build-review", confirmed: true }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "External Council could not complete the handoff.");
    addCouncilResult(body);
    els.statusText.textContent = "External Council handoff complete. Review it before acting.";
  } catch (err) {
    addMessage("ai", `**External Council stopped:** ${err.message}`);
    els.statusText.textContent = "External Council stopped before completing.";
  } finally {
    busy = false;
    els.send.disabled = false;
    updateComposerButtons();
    loadCouncilStatus();
  }
}

// ---- Voice: speaking (text-to-speech) --------------------------------
// Single production path: /api/speak -> Nero's canonical voice (nero_prime).
// No browser SpeechSynthesis fallback — the Voice Director is the ONLY path.
// If a sentence can't be voiced (unsupported language, engine unavailable),
// the server returns 204 with an X-Voice-Reason header and the frontend
// silently skips playback rather than substituting a foreign voice.

let neuralVoice = false;    // set from GET /api/voice on boot
let audioCtx = null;        // Web Audio context — unlocked once by a user tap
let currentSource = null;   // the playing buffer source, so we can stop it (barge-in)
let speechAbort = false;    // set on barge-in to halt a sentence-by-sentence read
let lastVoiceReason = null; // most recent X-Voice-Reason from /api/speak (for UI hints)

function getAudioCtx() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  if (!audioCtx) audioCtx = new AC();
  return audioCtx;
}

// --- Mobile audio unlock -------------------------------------------------
// Mobile browsers (especially iOS) refuse to play audio that wasn't started by
// a user gesture. Nero's reply plays *after* the speech→GPU round-trip, long
// after your tap, so the browser would silence it. We "prime" playback on your
// first interaction with the page — a tiny silent clip + a muted utterance —
// which grants audio permission for the rest of the session.
const SILENT_WAV = "data:audio/wav;base64,UklGRuQDAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YcADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
let audioUnlocked = false;
function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  // Unlock the Web Audio context — this is how Nero's neural voice plays, and
  // it's the reliable path on iOS (unlike a fresh <audio> element each time).
  try {
    const ctx = getAudioCtx();
    if (ctx) {
      if (ctx.state === "suspended") ctx.resume();
      const src = ctx.createBufferSource();       // 1-sample silent buffer
      src.buffer = ctx.createBuffer(1, 1, 22050);
      src.connect(ctx.destination);
      src.start(0);
    }
  } catch (_) { /* ignore */ }
  // Prime the browser's <audio> element too — a fresh Audio() call also
  // needs to have happened once inside a user gesture on iOS.
  try {
    const a = new Audio(SILENT_WAV);
    a.volume = 0;
    a.play().then(() => a.pause()).catch(() => {});
  } catch (_) { /* ignore */ }
}
["pointerdown", "touchend", "keydown"].forEach((ev) =>
  window.addEventListener(ev, unlockAudio, { once: true }));

// Stop whatever Nero is currently saying, and abort any pending
// sentence-by-sentence read. Neural audio only — there is no browser
// SpeechSynthesis path to cancel.
function stopSpeaking() {
  speechAbort = true;
  if (currentSource) {
    try { currentSource.stop(); } catch (_) { /* already stopped */ }
    currentSource = null;   // 'onended' fires → resolves any awaiting playback
  }
}

// Play WAV bytes through Web Audio (reliable on iOS once the context is
// unlocked). Resolves true when it finished (or was stopped), false if it
// couldn't play at all — so the caller can fall back to the browser voice.
async function playNeural(bytes) {
  const ctx = getAudioCtx();
  if (!ctx) return false;
  try {
    if (ctx.state === "suspended") await ctx.resume();
    const buffer = await ctx.decodeAudioData(bytes.slice(0));
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    currentSource = src;
    await new Promise((resolve) => {
      src.onended = () => {
        if (currentSource === src) currentSource = null;
        resolve();
      };
      src.start(0);
    });
    return true;
  } catch (_) {
    currentSource = null;
    return false;
  }
}

// Fetch synthesized audio for one sentence — Nero's canonical voice only.
// Returns ArrayBuffer on success, null on 204 (unsupported language, engine
// unavailable, etc.). Records the reason from the X-Voice-Reason header so
// the UI can eventually surface hints.
async function fetchSpeech(sentence) {
  if (!neuralVoice) return null;
  try {
    const res = await fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: sentence }),
    });
    if (res.ok && res.status !== 204) {
      lastVoiceReason = null;
      return await res.arrayBuffer();
    }
    // 204 — record why so the caller can decide whether to hint the user.
    lastVoiceReason = res.headers.get("X-Voice-Reason") || "unknown";
  } catch (_) {
    lastVoiceReason = "network-error";
  }
  return null;
}

// Split a reply into sentences. No look-behind (older Safari chokes on it).
function splitSentences(text) {
  return (text.match(/[^.!?…\n]+[.!?…]*|\n+/g) || [])
    .map((s) => s.trim())
    .filter(Boolean);
}

// Speak a reply sentence-by-sentence, so audio starts as soon as the FIRST
// sentence is synthesized instead of after the whole paragraph. Prefetches the
// next sentence's audio while the current one plays, so it flows without gaps.
// Sentences that come back 204 (unsupported language, engine unavailable) are
// simply skipped — the reply text stays visible on screen but goes silent for
// that sentence. Resolves when done (or interrupted).
async function speak(text) {
  const sentences = splitSentences(text);
  if (!sentences.length) return;
  stopSpeaking();
  speechAbort = false;
  let nextAudio = fetchSpeech(sentences[0]);
  for (let i = 0; i < sentences.length; i++) {
    if (speechAbort) break;
    const audio = await nextAudio;
    nextAudio = i + 1 < sentences.length ? fetchSpeech(sentences[i + 1]) : null;
    if (speechAbort) break;
    if (audio) {
      await playNeural(audio);
    }
    // else: silent skip. Text is already rendered in the chat pane.
  }
}

// ---- Voice: listening (speech-to-text) -------------------------------
// The Web Speech API needs a *secure context* (HTTPS or localhost). Over
// Tailscale, enable HTTPS with `tailscale serve` (see docs) to use the mic.
// On iPhone, use the Siri Shortcut instead — it uses native dictation.

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const sttSupported = !!SpeechRecognition && window.isSecureContext;
let recognition = null;
let listening = false;

let convoActive = false;      // are we in hands-free conversation mode?
let lastTranscript = "";      // most recent speech, for convo mode to send

if (!sttSupported) {
  // No speech recognition here — hide the voice buttons so they're never dead.
  els.mic.style.display = "none";
  els.convoMode.style.display = "none";
} else {
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    lastTranscript = transcript;
    if (convoActive) {
      els.convoTranscript.textContent = transcript;
    } else {
      els.input.value = transcript;
      autoGrow();
      updateComposerButtons();
    }
  };

  recognition.onend = () => {
    listening = false;
    els.mic.classList.remove("listening");
    if (convoActive) {
      const text = lastTranscript.trim();
      lastTranscript = "";
      if (text) {
        els.convoStatus.textContent = "Thinking…";
        setOrb("thinking");
        sendMessage(text);
      } else if (convoActive) {
        startListening();   // heard nothing — keep the ear open
      }
    } else {
      const text = els.input.value.trim();
      if (text) sendMessage(text);
    }
  };

  recognition.onerror = () => {
    listening = false;
    els.mic.classList.remove("listening");
    if (convoActive) {
      els.convoStatus.textContent = "Tap the orb to talk";
      setOrb("");
    }
  };
}

function startListening() {
  if (!sttSupported || listening || busy) return;
  stopSpeaking(); // don't hear ourselves — barge-in on any playing neural clip
  try {
    els.input.value = "";
    recognition.lang = els.micLang.value || "en-US"; // English or Croatian
    recognition.start();
    listening = true;
    els.mic.classList.add("listening");
  } catch (_) { /* already started */ }
}

function stopListening() {
  if (recognition && listening) recognition.stop();
}

// After a reply finishes: speak it, then (hands-free / convo) listen again.
async function onReplyComplete(fullText) {
  const speakable = toSpeakable(cleanReply(fullText));

  if (convoActive) {
    els.convoStatus.textContent = "";
    setOrb("speaking");
    await speak(speakable);
    if (!convoActive) return;            // user ended it mid-reply
    els.convoTranscript.textContent = "";
    els.convoStatus.textContent = "Listening…";
    setOrb("listening");
    startListening();
    return;
  }

  const shouldSpeak = els.speakToggle.checked && speakable;
  if (shouldSpeak) await speak(speakable);
  if (els.handsfreeToggle.checked && sttSupported) startListening();
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

els.input.addEventListener("input", () => { autoGrow(); updateComposerButtons(); });

// Show Send when there's text to send; otherwise the conversation-mode button
// (ChatGPT-style: left = voice recording, right = send / conversation mode).
function updateComposerButtons() {
  const hasText = els.input.value.trim().length > 0;
  els.send.hidden = !hasText;
  els.convoMode.hidden = hasText;
  updateCouncilButton();
}

// Enter to send, Shift+Enter for a new line.
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(els.input.value);
  }
});

els.mic.addEventListener("click", () => {
  if (listening) stopListening();
  else startListening();
});

els.council.addEventListener("click", () => runCouncil(els.input.value));

els.newChat.addEventListener("click", async () => {
  await fetch("/api/new", { method: "POST" });
  els.messages.innerHTML = "";
  showEmptyState();
  closeSettings();
});

// ---- Settings slide-over ----------------------------------------------
function openSettings() { els.sidebar.classList.add("open"); els.scrim.hidden = false; }
function closeSettings() { els.sidebar.classList.remove("open"); els.scrim.hidden = true; }
els.settingsClose.addEventListener("click", closeSettings);
els.scrim.addEventListener("click", closeSettings);

// ---- Conversational (hands-free voice) mode ---------------------------
function setOrb(state) {
  els.orb.className = "orb" + (state ? " " + state : "");
}

function enterConvo() {
  if (!sttSupported) return;
  convoActive = true;
  els.convoOverlay.hidden = false;
  els.convoTranscript.textContent = "";
  els.convoStatus.textContent = "Listening…";
  setOrb("listening");
  startListening();
}

function exitConvo() {
  convoActive = false;
  stopSpeaking();
  stopListening();
  els.convoOverlay.hidden = true;
  setOrb("");
}

els.convoMode.addEventListener("click", enterConvo);
els.convoClose.addEventListener("click", exitConvo);
// Tap the orb to (re)start listening if she's idle.
els.orb.addEventListener("click", () => {
  if (convoActive && !listening && !busy) {
    els.convoStatus.textContent = "Listening…";
    els.convoTranscript.textContent = "";
    setOrb("listening");
    startListening();
  }
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

els.menuToggle.addEventListener("click", openSettings);

// Remember voice preferences between visits.
function loadVoicePrefs() {
  els.speakToggle.checked = localStorage.getItem("speak") === "1";
  els.handsfreeToggle.checked = localStorage.getItem("handsfree") === "1";
  els.micLang.value = localStorage.getItem("micLang") || "en-US";
  updateSpeakVisibility();
  if (!sttSupported) {
    els.handsfreeToggle.parentElement.style.display = "none";
    els.micLang.parentElement.style.display = "none";
  }
}

// Nero can speak iff the neural voice (server-side Kokoro) is available.
// The browser SpeechSynthesis path was removed — Nero is one voice or none.
function updateSpeakVisibility() {
  els.speakToggle.parentElement.style.display = neuralVoice ? "" : "none";
}

// Ask the server whether Nero's local neural voice is available.
async function detectNeuralVoice() {
  try {
    const v = await (await fetch("/api/voice")).json();
    neuralVoice = !!(v.enabled && v.available);
  } catch (_) {
    neuralVoice = false;
  }
  updateSpeakVisibility();
}
els.speakToggle.addEventListener("change", () =>
  localStorage.setItem("speak", els.speakToggle.checked ? "1" : "0"));
els.handsfreeToggle.addEventListener("change", () =>
  localStorage.setItem("handsfree", els.handsfreeToggle.checked ? "1" : "0"));
els.micLang.addEventListener("change", () =>
  localStorage.setItem("micLang", els.micLang.value));

// ---- Humor dial (live, TARS-style) ----------------------------------

let humorTimer = null;

function reflectHumor(v) {
  els.humor.value = v;
  els.humorVal.textContent = v + "%";
}

async function loadSettings() {
  try {
    const s = await (await fetch("/api/settings")).json();
    if (typeof s.humor === "number") reflectHumor(s.humor);
    thinkingEnabled = !!s.thinking;
  } catch (_) { /* keep default */ }
}

els.humor.addEventListener("input", () => {
  els.humorVal.textContent = els.humor.value + "%";
  clearTimeout(humorTimer);
  humorTimer = setTimeout(async () => {
    try {
      await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ humor: Number(els.humor.value) }),
      });
    } catch (_) { /* ignore */ }
  }, 400);
});

// ---- Boot -------------------------------------------------------------

(async function init() {
  loadVoicePrefs();
  updateComposerButtons();
  detectNeuralVoice();   // flips on Nero's local voice once the server answers
  await loadConfig();
  showEmptyState();
  await Promise.all([loadStatus(), loadHistory(), loadMemories(), loadSettings()]);
  await loadCouncilStatus();
  els.input.focus();
  setInterval(loadStatus, 30000);
})();
