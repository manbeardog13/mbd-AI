/* ============================================================================
   NERO — Mission Control  ·  offline vanilla port of the Claude Design source
   ----------------------------------------------------------------------------
   No framework, no CDN, no runtime — this runs from app/static/ on the local
   Companion. It preserves every interaction from the design source:
     • the deterministic projected-3D Nero field (seed 0x4E45524F, 84 particles);
     • nine field states with distinct geometry/color/motion;
     • honest /api/host telemetry — a gauge renders ONLY when the response
       attests {"simulated": false}; a null GPU draws no gauge and states why;
     • real local file staging + multipart POST to /api/council/dispatch, with
       "Not sent" + file retention on any adapter failure;
     • approvals, orchestration/Council selection, pointer parallax, reduced
       motion, and count-up / liquid-bar polish.
   Colour law: structure is grayscale; Nero (the field, core, brand orb, her
   filaments, the cursor light) keeps her colours; amber/red/green appear only
   as operator-authority / block / safe signals.
   ============================================================================ */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  // ---- Field-state configuration (mirrors nero-core-states.json) ----------
  var CFG = {
    idle:      { hue: 188, label: 'Idle',      desc: 'Systems nominal · standing by',        speed: .32, intensity: .90, wire: 1.00 },
    listening: { hue: 188, label: 'Listening', desc: 'Capturing operator intent',            speed: .55, intensity: 1.08, wire: 1.08, ripple: true },
    thinking:  { hue: 207, label: 'Thinking',  desc: 'Exploring the solution space',         speed: 1.10, intensity: 1.14, wire: 1.20, dense: true },
    planning:  { hue: 253, label: 'Planning',  desc: 'Sequencing the work',                  speed: .76, intensity: 1.00, wire: 1.10, branch: true },
    reviewing: { hue: 268, label: 'Reviewing', desc: 'Auditing Council output',              speed: .55, intensity: .96, wire: 1.00, scan: true },
    executing: { hue: 194, label: 'Executing', desc: 'Routing work through the Council',     speed: 1.38, intensity: 1.24, wire: 1.20, beam: true },
    speaking:  { hue: 186, label: 'Speaking',  desc: 'Responding to the operator',           speed: .66, intensity: 1.12, wire: 1.04, ripple: true },
    waiting:   { hue: 37,  label: 'Waiting',   desc: 'Operator authority is required',       speed: .18, intensity: .72, wire: .72 },
    offline:   { hue: 210, label: 'Offline',   desc: 'Companion detached · Core sealed',     speed: .04, intensity: .22, wire: .42, gray: true }
  };
  // Council status → label + dot colour. Structure stays grey; only the
  // meaning-bearing states borrow signal colour (authority / block / safe).
  var GREY = '#9a9c9c';
  var COUNCIL = {
    idle:      { l: 'Idle',      c: '#7f8180' },
    reading:   { l: 'Reading',   c: GREY },
    thinking:  { l: 'Thinking',  c: GREY },
    reviewing: { l: 'Reviewing', c: GREY },
    executing: { l: 'Executing', c: GREY },
    waiting:   { l: 'Waiting',   c: '#f0a34a' }, // operator authority
    blocked:   { l: 'Blocked',   c: '#ff6d73' }, // genuine block
    completed: { l: 'Completed', c: '#5fe0b0' }  // safe / done
  };
  var STATE_KEYS = ['idle', 'listening', 'thinking', 'planning', 'reviewing', 'executing', 'speaking', 'waiting', 'offline'];

  // Preview/fixture scenario data (labelled as such in the UI). Not measured.
  var COUNCIL_NODES = [
    { id: 'orc', role: 'Orchestrator', model: 'NERO Companion', st: 'thinking',  sx: 25, sy: 27 },
    { id: 'arc', role: 'Architect',    model: 'Claude',         st: 'reviewing', sx: 79, sy: 25 },
    { id: 'rev', role: 'Reviewer',     model: 'Gemini',         st: 'reading',   sx: 86, sy: 61 },
    { id: 'exe', role: 'Executor',     model: 'Codex',          st: 'executing', sx: 23, sy: 72 },
    { id: 'grd', role: 'Guardian',     model: 'Constitution',   st: 'idle',      sx: 67, sy: 80 }
  ];
  var ORCH = [
    { id: 'arc', role: 'Architect',     model: 'Claude',          st: 'reviewing', action: 'plan.md' },
    { id: 'exe', role: 'Executor',      model: 'Codex',           st: 'executing', action: 'build step 3/5' },
    { id: 'rev', role: 'Reviewer',      model: 'Gemini',          st: 'reading',   action: 'diff summary' },
    { id: 'run', role: 'Local Runtime', model: 'Llama · on-device', st: 'embedding', action: 'memory index' }
  ];

  // ---- Mutable UI state ---------------------------------------------------
  var app = {
    nero: 'idle',
    selected: 'arc',
    files: [],
    dragging: false,
    telemetry: { status: 'connecting', reason: 'Connecting to Companion host adapter…', cpu: null, ram: null, ramTotal: null, disk: null, diskTotal: null, gpu: null, gpuReason: 'No vendor-neutral GPU source is connected on this host.', runtime: 'Unknown' },
    approvals: [
      { id: 'a1', title: 'Merge auth-refactor → main', by: 'Executor · Codex', risk: 'Low risk', riskColor: '#5fe0b0' },
      { id: 'a2', title: 'Grant filesystem scope to Workflow #12', by: 'Orchestrator', risk: 'Elevated', riskColor: '#f0a34a' }
    ]
  };

  // ---- Element refs -------------------------------------------------------
  var stage = $('#stage'), aura = $('#cursor-aura'), canvas = $('#field-canvas');
  var clockEl = $('#clock'), fieldState = $('#field-state'), fieldDesc = $('#field-desc'), fieldScan = $('#field-scan');
  var orchList = $('#orch-list'), councilLayer = $('#council-layer'), filaments = $('#filaments'), stateControl = $('#state-control');
  var command = $('#command'), dropOverlay = $('#drop-overlay'), fileInput = $('#file-input'), promptEl = $('#prompt');
  var sendBtn = $('#send'), dispatchNote = $('#dispatch-note'), fileChips = $('#file-chips');
  var telemetryBadge = $('#telemetry-badge'), telemetryBody = $('#telemetry-body');
  var approvalsEl = $('#approvals'), approvalCount = $('#approval-count'), overlap = $('#overlap');

  var scale = 1;

  // ========================================================================
  //  Fixed 1820×780 operating environment — scale to fit, centred, letterbox
  // ========================================================================
  function computeScale() {
    scale = Math.min(window.innerWidth / 1820, window.innerHeight / 780);
    if (stage) stage.style.transform = 'translate(-50%,-50%) scale(' + scale + ')';
  }

  // ---- Clock (local device time — the one genuinely "live" value) ---------
  function pad(n) { return String(n).padStart(2, '0'); }
  function tick() {
    var d = new Date();
    if (clockEl) clockEl.textContent = pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  // ========================================================================
  //  Deterministic projected-3D Nero field (visual only — never a measurement)
  // ========================================================================
  var cw = 0, ch = 0, t = 0, last = 0, raf = 0, px = 0, py = 0, parts = [], flyWrap = null;

  function seeded(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var x = Math.imul(seed ^ seed >>> 15, 1 | seed);
      x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x;
      return ((x ^ x >>> 14) >>> 0) / 4294967296;
    };
  }
  function sizeCanvas() {
    if (!canvas) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2), w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w) return;
    canvas.width = w * dpr; canvas.height = h * dpr;
    var ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cw = w; ch = h;
  }
  function initCanvas() {
    t = 0; last = performance.now(); px = 0; py = 0;
    flyWrap = canvas ? canvas.parentElement : null;   // the .field-canvas-wrap she rides in
    var rnd = seeded(0x4E45524F);
    parts = Array.from({ length: 84 }, function () {
      return { theta: rnd() * Math.PI * 2, phi: Math.acos(2 * rnd() - 1), r: .36 + rnd() * .46, speed: .16 + rnd() * .45, size: .45 + rnd() * 1.25, phase: rnd() * Math.PI * 2 };
    });
    sizeCanvas();
    var loop = function (now) { var dt = Math.min(48, now - last); last = now; draw(dt); updateFlight(); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
  }

  // She flies: the whole light-body drifts around the field on a slow wandering
  // path, banks into her turns, breathes, and leans toward the operator's cursor.
  function updateFlight() {
    if (!flyWrap) return;
    if (reduceMotion) { flyWrap.style.transform = 'translate(-50%,-50%)'; return; }
    var cfg = CFG[app.nero] || CFG.idle;
    var roam = cfg.gray ? 0.3 : 1;                       // offline: she barely drifts
    var wx = (Math.sin(t * 0.13) * 96 + Math.sin(t * 0.071 + 1.3) * 54) * roam + px * 46;
    var wy = (Math.cos(t * 0.11) * 54 + Math.cos(t * 0.083 + 0.7) * 30) * roam + py * 30;
    var tilt = Math.sin(t * 0.17) * 2.6 * roam;          // banks as she turns
    var breath = 1 + Math.sin(t * 0.6) * 0.02;
    flyWrap.style.transform = 'translate(-50%,-50%) translate(' + wx.toFixed(1) + 'px,' + wy.toFixed(1) + 'px) rotate(' + tilt.toFixed(2) + 'deg) scale(' + breath.toFixed(3) + ')';
  }
  function rotate3(p, ax, ay, az) {
    var x = p[0], y = p[1], z = p[2];
    var cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax), cz = Math.cos(az), sz = Math.sin(az);
    var x1 = x * cy - z * sy, z1 = x * sy + z * cy, y1 = y;
    var y2 = y1 * cx - z1 * sx, z2 = y1 * sx + z1 * cx, x2 = x1;
    return [x2 * cz - y2 * sz, x2 * sz + y2 * cz, z2];
  }
  function project(p, cx, cy, s) { var f = 2.8 / (3.2 - p[2]); return [cx + p[0] * s * f, cy + p[1] * s * f, p[2], f]; }
  function path3(ctx, points, ax, ay, az, cx, cy, s, hue, alpha, width) {
    var prev = null;
    for (var i = 0; i < points.length; i++) {
      var r = rotate3(points[i], ax, ay, az), q = project(r, cx, cy, s);
      if (prev) {
        var depth = (q[2] + 1.2) / 2.4;
        ctx.beginPath(); ctx.moveTo(prev[0], prev[1]); ctx.lineTo(q[0], q[1]);
        ctx.strokeStyle = 'hsla(' + (hue + depth * 12) + ',92%,78%,' + (alpha * (.45 + depth * .55)) + ')';
        ctx.lineWidth = width * (.76 + q[3] * .16); ctx.stroke();
      }
      prev = q;
    }
  }
  function draw(dt) {
    if (!canvas || !cw) return;
    var ctx = canvas.getContext('2d'), w = cw, h = ch, cx = w / 2, cy = h / 2, md = Math.min(w, h);
    var cfg = CFG[app.nero] || CFG.idle;
    var motion = reduceMotion ? 0 : 1;
    var hue = (app.nero === 'idle' || app.nero === 'listening' || app.nero === 'speaking') ? 188 : cfg.hue;
    if (cfg.gray) hue = 210;
    t += dt * .001 * cfg.speed * (motion || .00001);
    var ax = t * .37 + py * .16, ay = t * .51 + px * .2, az = t * .16;
    // "life": a gentle breath + a slow one-sided swell — a warm smile of light.
    var life = reduceMotion ? 1 : (1 + Math.sin(t * .5) * .05 + Math.max(0, Math.sin(t * .19)) * .06);
    var glow = cfg.intensity * life;
    ctx.clearRect(0, 0, w, h); ctx.globalCompositeOperation = 'lighter';

    var aur = ctx.createRadialGradient(cx, cy, 0, cx, cy, md * .44);
    aur.addColorStop(0, 'hsla(' + hue + ',78%,99%,' + (.44 * glow) + ')');
    aur.addColorStop(.08, 'hsla(' + hue + ',94%,78%,' + (.31 * glow) + ')');
    aur.addColorStop(.28, 'hsla(' + hue + ',94%,55%,' + (.08 * cfg.intensity) + ')');
    aur.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = aur; ctx.fillRect(0, 0, w, h);

    var s, i, pts, u, rr;
    for (s = 0; s < 5; s++) {
      pts = [];
      for (i = 0; i <= 180; i++) { u = i / 180 * Math.PI * 2; rr = .43 + s * .085 + Math.sin(u * 3 + s + t) * .012; pts.push([Math.cos(u) * rr, Math.sin(u) * rr, Math.sin(u * 2 + s * .9) * (.18 + s * .018)]); }
      path3(ctx, pts, ax + s * .14, ay + s * .21, az + s * .38, cx, cy, md * .64, hue, .064 * cfg.intensity * cfg.wire, 1);
    }
    for (var k = 0; k < 3; k++) {
      pts = [];
      for (i = 0; i <= 210; i++) { u = i / 210 * Math.PI * 2; pts.push([Math.sin((3 + k) * u + k * .7) * .39, Math.sin((4 + k) * u) * .35, Math.sin((5 + k) * u + k) * .31]); }
      path3(ctx, pts, ax * .75 + k * .48, ay * .7 + k * .33, az + k * .25, cx, cy, md * .58, hue, .092 * cfg.intensity * cfg.wire, .9);
    }
    var screen = [];
    for (i = 0; i < parts.length; i++) {
      var p = parts[i], th = p.theta + t * p.speed, ph = p.phi + Math.sin(t * .3 + p.phase) * .04;
      var pos = [Math.sin(ph) * Math.cos(th) * p.r, Math.cos(ph) * p.r, Math.sin(ph) * Math.sin(th) * p.r];
      var q = project(rotate3(pos, ax, ay, az), cx, cy, md * .61); screen.push(q);
      var sz = p.size * (1.1 + q[3] * .7), g = ctx.createRadialGradient(q[0], q[1], 0, q[0], q[1], sz * 4.8);
      g.addColorStop(0, 'hsla(' + hue + ',85%,99%,' + (.72 * cfg.intensity) + ')');
      g.addColorStop(.35, 'hsla(' + hue + ',94%,72%,' + (.28 * cfg.intensity) + ')');
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(q[0], q[1], sz * 4.8, 0, Math.PI * 2); ctx.fill();
    }
    for (i = 0; i < screen.length; i += 7) {
      var a = screen[i], b = screen[(i * 5 + 13) % screen.length], dx = a[0] - b[0], dy = a[1] - b[1], dist = Math.hypot(dx, dy);
      if (dist < md * .34) {
        ctx.beginPath(); ctx.moveTo(a[0], a[1]);
        ctx.quadraticCurveTo((a[0] + b[0]) / 2 + Math.sin(t + i) * 8, (a[1] + b[1]) / 2 + Math.cos(t + i) * 8, b[0], b[1]);
        ctx.strokeStyle = 'hsla(' + hue + ',90%,80%,' + ((1 - dist / (md * .34)) * .075 * cfg.intensity) + ')'; ctx.lineWidth = .7; ctx.stroke();
      }
    }
    if (cfg.ripple && motion) {
      for (i = 0; i < 3; i++) { var pr = (t * .26 + i / 3) % 1; ctx.beginPath(); ctx.arc(cx, cy, pr * md * .56, 0, Math.PI * 2); ctx.strokeStyle = 'hsla(' + hue + ',90%,82%,' + ((1 - pr) * .16 * cfg.intensity) + ')'; ctx.lineWidth = 1; ctx.stroke(); }
    }
    if (cfg.branch) {
      ctx.strokeStyle = 'hsla(' + hue + ',90%,78%,.14)'; ctx.lineWidth = .8;
      for (i = 0; i < 6; i++) { ctx.beginPath(); ctx.moveTo(cx, cy); ctx.quadraticCurveTo(cx + (i - 2.5) * 34, cy - 60, cx + (i - 2.5) * 58, cy - 118); ctx.stroke(); }
    }
    if (cfg.beam) {
      ctx.strokeStyle = 'hsla(' + hue + ',90%,82%,.13)'; ctx.lineWidth = 1.1;
      for (i = 0; i < 4; i++) { var an = t * .7 + i * Math.PI / 2; ctx.beginPath(); ctx.moveTo(cx + Math.cos(an) * 32, cy + Math.sin(an) * 32); ctx.lineTo(cx + Math.cos(an) * md * .43, cy + Math.sin(an) * md * .43); ctx.stroke(); }
    }
    var core = ctx.createRadialGradient(cx, cy, 0, cx, cy, md * .075 * (1 + (life - 1) * 1.4));
    core.addColorStop(0, 'rgba(255,255,255,' + Math.min(1, .98 * glow) + ')');
    core.addColorStop(.25, 'hsla(' + hue + ',65%,96%,' + (.74 * glow) + ')');
    core.addColorStop(.52, 'hsla(' + hue + ',95%,68%,' + (.24 * glow) + ')');
    core.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(cx, cy, md * .075, 0, Math.PI * 2); ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
  }

  // ---- Pointer parallax + Nero's cursor light -----------------------------
  function stageMove(e) {
    if (!stage || !aura) return;
    var r = stage.getBoundingClientRect(), s = scale || 1;
    var x = (e.clientX - r.left) / s, y = (e.clientY - r.top) / s;
    aura.style.transform = 'translate(' + (x - 270) + 'px,' + (y - 270) + 'px)';
    px = (x / 1820 - .5) * 2; py = (y / 780 - .5) * 2;
  }

  // ========================================================================
  //  Renderers
  // ========================================================================
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function renderOrchestration() {
    orchList.innerHTML = '';
    ORCH.forEach(function (o) {
      var row = el('div', 'orch-row' + (o.id === app.selected ? ' selected' : ''));
      row.style.setProperty('--rowColor', GREY);
      var top = el('div', 'orch-top');
      top.appendChild(el('span', 'orch-role', o.role));
      top.appendChild(el('span', 'orch-model mono', o.model));
      row.appendChild(top);
      row.appendChild(el('div', 'orch-action mono', o.st.toUpperCase() + ' · ' + o.action));
      var trace = el('div', 'orch-trace'); trace.appendChild(el('span')); row.appendChild(trace);
      row.addEventListener('click', function () { select(o.id); });
      orchList.appendChild(row);
    });
  }

  function renderCouncil() {
    councilLayer.innerHTML = '';
    COUNCIL_NODES.forEach(function (c) {
      var cs = COUNCIL[c.st] || COUNCIL.idle;
      var node = el('button', 'council-node glass' + (c.id === app.selected ? ' selected' : ''));
      node.style.left = c.sx + '%'; node.style.top = c.sy + '%'; node.style.setProperty('--node', cs.c);
      node.appendChild(el('div', 'council-role', c.role));
      node.appendChild(el('div', 'council-model mono', c.model));
      node.appendChild(el('div', 'council-status mono', cs.l));
      node.addEventListener('click', function () { select(c.id); });
      councilLayer.appendChild(node);
    });
    renderFilaments();
  }

  function renderFilaments() {
    var svgns = 'http://www.w3.org/2000/svg';
    filaments.innerHTML = '';
    COUNCIL_NODES.forEach(function (c) {
      var mx = (50 + c.sx) / 2, my = (48 + c.sy) / 2, dx = c.sx - 50, dy = c.sy - 48, len = Math.hypot(dx, dy) || 1, off = 6;
      var sel = c.id === app.selected;
      var path = document.createElementNS(svgns, 'path');
      path.setAttribute('d', 'M50,48 Q' + (mx - dy / len * off).toFixed(1) + ',' + (my + dx / len * off).toFixed(1) + ' ' + c.sx + ',' + c.sy);
      path.setAttribute('class', 'filament' + (sel ? '' : ' idle'));
      path.setAttribute('style', 'stroke:' + (sel ? 'rgba(120,232,255,.55)' : 'rgba(88,210,255,.18)'));
      filaments.appendChild(path);
    });
    // The one non-Nero filament: an ownership collision — operator authority.
    var warn = document.createElementNS(svgns, 'path');
    warn.setAttribute('d', 'M79,25 Q88,39 86,61');
    warn.setAttribute('class', 'filament warning');
    warn.setAttribute('style', 'stroke:rgba(240,163,74,.52)');
    filaments.appendChild(warn);
  }

  function select(id) { app.selected = id; renderOrchestration(); renderCouncil(); }

  function setNero(k) {
    if (!CFG[k]) return;
    app.nero = k;
    fieldState.textContent = CFG[k].label;
    fieldDesc.textContent = CFG[k].desc;
    fieldScan.style.opacity = CFG[k].scan ? 1 : .12;
    Array.prototype.forEach.call(stateControl.querySelectorAll('.state-btn'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-state') === k);
      if (b.getAttribute('data-state') === k) b.setAttribute('aria-selected', 'true'); else b.removeAttribute('aria-selected');
    });
  }

  // ---- Files --------------------------------------------------------------
  function formatBytes(n) { return n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB'; }
  function addFiles(list) {
    var next = Array.prototype.slice.call(list || []).map(function (f) {
      return { file: f, name: f.name, size: f.size, id: f.name + '-' + f.size + '-' + f.lastModified };
    });
    var merged = app.files.slice();
    next.forEach(function (n) { if (!merged.some(function (x) { return x.id === n.id; })) merged.push(n); });
    app.files = merged.slice(0, 12);
    setDispatch('idle', 'Files staged locally for Claude · Architect.');
    renderFiles();
  }
  function removeFile(id) { app.files = app.files.filter(function (f) { return f.id !== id; }); renderFiles(); }
  function renderFiles() {
    fileChips.innerHTML = '';
    app.files.forEach(function (f) {
      var chip = el('span', 'file-chip mono'); chip.title = f.name;
      chip.appendChild(document.createTextNode(f.name + ' · ' + formatBytes(f.size)));
      var x = el('button', null, '×'); x.setAttribute('aria-label', 'Remove ' + f.name);
      x.addEventListener('click', function () { removeFile(f.id); });
      chip.appendChild(x); fileChips.appendChild(chip);
    });
    updateSend();
  }
  function updateSend() { sendBtn.disabled = !promptEl.value.trim() && !app.files.length; }

  // ---- Dispatch note ------------------------------------------------------
  function setDispatch(kind, message) {
    dispatchNote.textContent = message;
    dispatchNote.className = 'dispatch-note mono' + (kind && kind !== 'idle' ? ' ' + kind : '');
  }

  // ========================================================================
  //  Honest host telemetry — gauges render ONLY on attested simulated:false
  // ========================================================================
  function fetchTelemetry() {
    fetch('/api/host', { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('Host adapter returned HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      if (d.simulated !== false) throw new Error('Host adapter did not attest "simulated": false');
      var n = function (v) { return typeof v === 'number' && isFinite(v) ? v : null; };
      app.telemetry = {
        status: 'live', reason: '',
        cpu: n(d.cpu), ram: n(d.ram), ramTotal: n(d.ram_total_gb != null ? d.ram_total_gb : d.ramTotalGb),
        disk: n(d.disk), diskTotal: n(d.disk_total_gb != null ? d.disk_total_gb : d.diskTotalGb),
        gpu: n(d.gpu), gpuReason: d.gpu_reason || d.gpuReason || 'No vendor-neutral GPU source is connected on this host.',
        runtime: d.local_runtime || d.runtime || 'Active'
      };
      renderTelemetry();
    }).catch(function (e) {
      app.telemetry = {
        status: 'unavailable', reason: (e && e.message) ? e.message : 'No real input is connected.',
        cpu: null, ram: null, ramTotal: null, disk: null, diskTotal: null, gpu: null,
        gpuReason: 'No vendor-neutral GPU source is connected on this host.', runtime: 'Unavailable'
      };
      renderTelemetry();
    });
  }
  function metricRow(name, valueText, sub, percent) {
    var m = el('div', 'metric');
    var head = el('div', 'metric-head'); head.appendChild(el('span', 'metric-name', name));
    var val = el('span', 'metric-value mono'); val.appendChild(document.createTextNode(valueText));
    if (sub) val.appendChild(el('span', 'metric-sub', sub));
    head.appendChild(val); m.appendChild(head);
    var track = el('div', 'metric-track'); var span = el('span'); track.appendChild(span); m.appendChild(track);
    // liquid fill on next frame so the width transition plays
    requestAnimationFrame(function () { span.style.setProperty('--metric', Math.max(0, Math.min(100, percent)) + '%'); });
    return m;
  }
  function renderTelemetry() {
    var t = app.telemetry, live = t.status === 'live';
    telemetryBadge.textContent = live ? 'Live' : 'Disconnected';
    telemetryBadge.className = 'data-badge ' + (live ? 'live' : 'warn');
    telemetryBody.innerHTML = '';
    if (live) {
      if (t.cpu != null) telemetryBody.appendChild(metricRow('CPU', Math.round(t.cpu) + '%', 'measured', t.cpu));
      if (t.ram != null) telemetryBody.appendChild(metricRow('Memory', Math.round(t.ram) + '%', t.ramTotal ? 'of ' + t.ramTotal + ' GB' : 'measured', t.ram));
      if (t.disk != null) telemetryBody.appendChild(metricRow('Disk', Math.round(t.disk) + '%', t.diskTotal ? 'of ' + t.diskTotal + ' GB' : 'measured', t.disk));
      if (t.gpu != null) telemetryBody.appendChild(metricRow('GPU', Math.round(t.gpu) + '%', 'measured', t.gpu));
      if (t.gpu == null) {
        var g = el('div', 'gpu-null'); g.appendChild(el('strong', null, 'GPU · Unavailable')); g.appendChild(el('div', null, t.gpuReason)); telemetryBody.appendChild(g);
      }
      var health = el('div', 'health');
      [['Core kernel', 'Sealed'], ['Companion', 'Active'], ['Local runtime', t.runtime]].forEach(function (row) {
        var hr = el('div', 'health-row'); hr.appendChild(el('span', null, row[0])); hr.appendChild(el('span', 'health-state mono', row[1])); health.appendChild(hr);
      });
      telemetryBody.appendChild(health);
    } else {
      var ph = el('div', 'telemetry-placeholder');
      ph.appendChild(el('div', 'placeholder-title', 'No real input'));
      var copy = el('div', 'placeholder-copy');
      copy.appendChild(document.createTextNode('Gauges appear only when '));
      copy.appendChild(el('span', 'mono', '/api/host')); copy.appendChild(document.createTextNode(' attests '));
      copy.appendChild(el('span', 'mono', 'simulated: false')); copy.appendChild(document.createTextNode('.'));
      ph.appendChild(copy);
      var g2 = el('div', 'gpu-null'); g2.appendChild(el('strong', null, 'GPU · No reading')); g2.appendChild(el('div', null, t.gpuReason)); ph.appendChild(g2);
      telemetryBody.appendChild(ph);
    }
  }

  // ---- Approvals ----------------------------------------------------------
  function renderApprovals() {
    approvalsEl.innerHTML = '';
    if (!app.approvals.length) {
      approvalCount.textContent = 'Clear'; approvalCount.className = 'data-badge';
      var e = el('div', 'telemetry-placeholder'); e.appendChild(el('div', 'placeholder-copy mono', 'QUEUE CLEAR')); approvalsEl.appendChild(e);
      return;
    }
    approvalCount.textContent = app.approvals.length + ' pending'; approvalCount.className = 'data-badge warn';
    app.approvals.forEach(function (a) {
      var card = el('div', 'approval');
      card.appendChild(el('div', 'approval-title', a.title));
      var meta = el('div', 'approval-meta mono'); meta.appendChild(document.createTextNode(a.by + ' · '));
      var risk = el('span', null, a.risk); risk.style.color = a.riskColor; meta.appendChild(risk); card.appendChild(meta);
      var actions = el('div', 'approval-actions');
      var mk = function (cls, label, fn) { var b = el('button', 'small-btn ' + cls, label); b.addEventListener('click', fn); return b; };
      actions.appendChild(mk('inspect', 'Inspect', function () { setDispatch('idle', 'Approval evidence opened in Context Surface.'); }));
      actions.appendChild(mk('approve', 'Approve', function () { resolveApproval(a.id, 'approved'); }));
      actions.appendChild(mk('reject', 'Reject', function () { resolveApproval(a.id, 'rejected'); }));
      card.appendChild(actions); approvalsEl.appendChild(card);
    });
  }
  function resolveApproval(id, kind) {
    app.approvals = app.approvals.filter(function (a) { return a.id !== id; });
    setDispatch('success', 'Approval ' + kind + '.');
    renderApprovals();
  }

  // ---- Count-up numerals (polish) ----------------------------------------
  function countUp() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-count]'), function (node) {
      var target = parseInt(node.getAttribute('data-count'), 10) || 0;
      var prefix = node.getAttribute('data-prefix') || '';
      if (reduceMotion) { node.textContent = prefix + target; return; }
      var start = performance.now(), dur = 900;
      var step = function (now) {
        var p = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - p, 3);
        node.textContent = prefix + Math.round(target * eased);
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  // ---- Dispatch to Claude · Architect ------------------------------------
  function dispatch() {
    if (!promptEl.value.trim() && !app.files.length) return;
    setNero('executing');
    setDispatch('idle', 'Contacting Claude adapter…');
    var fd = new FormData();
    fd.append('prompt', promptEl.value);
    fd.append('target', 'claude');
    fd.append('role', 'architect');
    app.files.forEach(function (f) { fd.append('files', f.file, f.name); });
    fetch('/api/council/dispatch', { method: 'POST', body: fd }).then(function (r) {
      if (!r.ok) throw new Error('Claude adapter returned HTTP ' + r.status);
      return r.json().catch(function () { return {}; });
    }).then(function (d) {
      promptEl.value = ''; app.files = []; renderFiles();
      setDispatch('success', (d && d.message) || 'Files and instruction accepted by Claude · Architect.');
    }).catch(function (e) {
      setDispatch('error', 'Not sent: ' + ((e && e.message) ? e.message : 'Claude adapter is not connected') + '. Files remain local.');
      setNero('waiting');
    });
  }

  // ========================================================================
  //  Wiring
  // ========================================================================
  function init() {
    computeScale();
    tick(); setInterval(tick, 1000);
    renderOrchestration(); renderCouncil(); renderApprovals(); renderTelemetry();
    setNero('idle');
    countUp();
    initCanvas();
    fetchTelemetry(); setInterval(fetchTelemetry, 5000);

    stage.addEventListener('mousemove', stageMove);
    window.addEventListener('resize', function () { computeScale(); sizeCanvas(); });

    // State selector
    Array.prototype.forEach.call(stateControl.querySelectorAll('.state-btn'), function (b) {
      b.addEventListener('click', function () { setNero(b.getAttribute('data-state')); });
    });

    // Command surface
    $('#attach').addEventListener('click', function () { fileInput.click(); });
    fileInput.addEventListener('change', function (e) { addFiles(e.target.files); fileInput.value = ''; });
    promptEl.addEventListener('input', function () { updateSend(); setDispatch('idle', 'Files remain local until a Claude adapter is connected.'); });
    promptEl.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); dispatch(); } });
    sendBtn.addEventListener('click', dispatch);
    $('#voice').addEventListener('click', function () { setNero('listening'); });
    overlap.addEventListener('click', function () { setDispatch('error', 'Ownership collision: Architect and Reviewer overlap on auth module. Operator decision required.'); });

    // Drag & drop
    command.addEventListener('dragover', function (e) { e.preventDefault(); if (!app.dragging) { app.dragging = true; command.classList.add('dragging'); dropOverlay.style.opacity = 1; } });
    command.addEventListener('dragleave', function (e) { e.preventDefault(); app.dragging = false; command.classList.remove('dragging'); dropOverlay.style.opacity = 0; });
    command.addEventListener('drop', function (e) { e.preventDefault(); app.dragging = false; command.classList.remove('dragging'); dropOverlay.style.opacity = 0; addFiles(e.dataTransfer.files); });

    // Brand → back to the Companion chat
    var brand = $('#brand'); if (brand) brand.addEventListener('click', function () { window.location.href = '/'; });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
