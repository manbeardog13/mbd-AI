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
  ttsVoice: document.getElementById("tts-voice"),
  humor: document.getElementById("humor"),
  humorVal: document.getElementById("humor-val"),
};

let aiName = "Your AI";
let ownerName = "friend";
let busy = false;
let thinkingEnabled = false;

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

// Strip markdown so spoken replies sound natural.
function toSpeakable(text) {
  return text
    .replace(/```[\s\S]*?```/g, " (code) ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/[*_#>]/g, "")
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
      <p>I'm ${escapeHtml(aiName)} — your own AI, running entirely on your machine.
      Type or tap the mic to talk.</p>
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

// ---- Voice: speaking (text-to-speech) --------------------------------
// speechSynthesis is widely supported (including iOS Safari) and works
// over plain HTTP, so replies can be read aloud on any device.

const ttsSupported = "speechSynthesis" in window;

// Guess the language so replies are spoken with the right voice. Croatian
// uses these diacritics; if we see them, speak in Croatian, else English.
function detectLang(text) {
  return /[čćđšž]/i.test(text) ? "hr-HR" : "en-US";
}

// Names that tend to be smooth, natural female voices across Windows/Mac/mobile.
const FEMALE_HINTS = [
  "female", "natural", "zira", "jenny", "aria", "hazel", "amy", "eva", "emma",
  "sonia", "libby", "natasha", "michelle", "samantha", "victoria", "fiona",
  "tessa", "karen", "moira", "serena", "google uk english female", "google us english",
];

function femaleScore(name) {
  const n = (name || "").toLowerCase();
  let score = FEMALE_HINTS.reduce((s, k) => s + (n.includes(k) ? 1 : 0), 0);
  if (n.includes("male") && !n.includes("female")) score -= 2; // penalize clearly-male
  return score;
}

function allVoices() {
  return window.speechSynthesis.getVoices() || [];
}

// Choose the voice to speak `langCode` in: the user's pick if it fits the
// language, otherwise the smoothest female voice available for that language.
function chooseVoice(langCode) {
  const prefix = langCode.slice(0, 2).toLowerCase();
  const voices = allVoices();
  const inLang = voices.filter((v) => (v.lang || "").toLowerCase().startsWith(prefix));
  const pool = inLang.length ? inLang : voices;

  const picked = localStorage.getItem("ttsVoice");
  if (picked) {
    const match = pool.find((v) => v.name === picked);
    if (match) return match;
  }
  return [...pool].sort((a, b) => femaleScore(b.name) - femaleScore(a.name))[0] || null;
}

// Nero's own local neural voice (Kokoro) when available, else the browser voice.
let neuralVoice = false;    // set from GET /api/voice on boot
let audioCtx = null;        // Web Audio context — unlocked once by a user tap
let currentSource = null;   // the playing buffer source, so we can stop it (barge-in)

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
  // Also prime the browser's audio + speech (the Croatian / fallback path).
  try {
    const a = new Audio(SILENT_WAV);
    a.volume = 0;
    a.play().then(() => a.pause()).catch(() => {});
    if (ttsSupported) {
      const u = new SpeechSynthesisUtterance(" ");
      u.volume = 0;
      window.speechSynthesis.speak(u);
    }
  } catch (_) { /* ignore */ }
}
["pointerdown", "touchend", "keydown"].forEach((ev) =>
  window.addEventListener(ev, unlockAudio, { once: true }));

// Stop whatever Nero is currently saying — neural clip and/or browser speech.
function stopSpeaking() {
  if (currentSource) {
    try { currentSource.stop(); } catch (_) { /* already stopped */ }
    currentSource = null;   // 'onended' fires → resolves any awaiting speak()
  }
  if (ttsSupported) window.speechSynthesis.cancel();
}

// Speak via the browser's built-in voices — the fallback, and (for now) the
// path for Croatian, until Nero's local Croatian voice lands.
function speakBrowser(text) {
  if (!ttsSupported || !text.trim()) return Promise.resolve();
  return new Promise((resolve) => {
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = detectLang(text);
    const voice = chooseVoice(utter.lang);
    if (voice) utter.voice = voice;
    utter.rate = 0.98;   // a touch calmer
    utter.pitch = 1.05;  // a touch brighter — smoother, "glassier"
    utter.onend = resolve;
    utter.onerror = resolve;
    window.speechSynthesis.speak(utter);
  });
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

// Speak `text`, preferring Nero's local neural voice. It's English-only today,
// so Croatian falls back to the browser voice. Resolves when playback ENDS (or
// is interrupted), so hands-free re-listening doesn't start over her own voice.
async function speak(text) {
  if (!text.trim()) return;
  stopSpeaking();
  if (neuralVoice && detectLang(text) === "en-US") {
    try {
      const res = await fetch("/api/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.ok && res.status !== 204) {
        if (await playNeural(await res.arrayBuffer())) return;
        // Web Audio couldn't play it → fall through to the browser voice
      }
      // 204 = voice not ready → fall through to the browser voice
    } catch (_) { /* network/synthesis issue → browser voice */ }
  }
  await speakBrowser(text);
}

// Fill the voice picker with the installed voices, best female first.
function populateVoicePicker() {
  if (!ttsSupported) return;
  const voices = [...allVoices()].sort((a, b) => femaleScore(b.name) - femaleScore(a.name));
  if (!voices.length) return;
  const saved = localStorage.getItem("ttsVoice");
  els.ttsVoice.innerHTML = "";
  for (const v of voices) {
    const opt = document.createElement("option");
    opt.value = v.name;
    opt.textContent = `${v.name} (${v.lang})`;
    if (v.name === saved) opt.selected = true;
    els.ttsVoice.appendChild(opt);
  }
  if (!saved && voices[0]) localStorage.setItem("ttsVoice", voices[0].name);
}

// ---- Voice: listening (speech-to-text) -------------------------------
// The Web Speech API needs a *secure context* (HTTPS or localhost). Over
// Tailscale, enable HTTPS with `tailscale serve` (see docs) to use the mic.
// On iPhone, use the Siri Shortcut instead — it uses native dictation.

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const sttSupported = !!SpeechRecognition && window.isSecureContext;
let recognition = null;
let listening = false;

if (!sttSupported) {
  // Hide the mic if we can't use it here, so it's never a dead button.
  els.mic.style.display = "none";
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
    els.input.value = transcript;
    autoGrow();
  };

  recognition.onend = () => {
    listening = false;
    els.mic.classList.remove("listening");
    const text = els.input.value.trim();
    if (text) sendMessage(text);
  };

  recognition.onerror = () => {
    listening = false;
    els.mic.classList.remove("listening");
  };
}

function startListening() {
  if (!sttSupported || listening || busy) return;
  stopSpeaking(); // don't hear ourselves (neural clip or browser speech)
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

// After a reply finishes: optionally speak it, then optionally re-listen.
async function onReplyComplete(fullText) {
  const cleaned = cleanReply(fullText);
  const shouldSpeak = els.speakToggle.checked && cleaned.trim();
  if (shouldSpeak) await speak(toSpeakable(cleaned));
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

els.input.addEventListener("input", autoGrow);

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

// Remember voice preferences between visits.
function loadVoicePrefs() {
  els.speakToggle.checked = localStorage.getItem("speak") === "1";
  els.handsfreeToggle.checked = localStorage.getItem("handsfree") === "1";
  els.micLang.value = localStorage.getItem("micLang") || "en-US";
  if (ttsSupported) {
    populateVoicePicker();
    // Voices often load asynchronously; refresh the list when they arrive.
    window.speechSynthesis.onvoiceschanged = populateVoicePicker;
  } else {
    // No browser voices to pick from (the neural voice needs no picker).
    els.ttsVoice.parentElement.style.display = "none";
  }
  updateSpeakVisibility();
  if (!sttSupported) {
    els.handsfreeToggle.parentElement.style.display = "none";
    els.micLang.parentElement.style.display = "none";
  }
}

// Nero can speak if the browser has voices OR her local neural voice is ready.
function updateSpeakVisibility() {
  els.speakToggle.parentElement.style.display =
    (ttsSupported || neuralVoice) ? "" : "none";
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
els.ttsVoice.addEventListener("change", () => {
  localStorage.setItem("ttsVoice", els.ttsVoice.value);
  // This picker chooses the *browser* fallback voice, so preview that one.
  if (els.speakToggle.checked) { stopSpeaking(); speakBrowser("Hi, this is how I sound."); }
});

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
  detectNeuralVoice();   // flips on Nero's local voice once the server answers
  await loadConfig();
  showEmptyState();
  await Promise.all([loadStatus(), loadHistory(), loadMemories(), loadSettings()]);
  els.input.focus();
  setInterval(loadStatus, 30000);
})();
