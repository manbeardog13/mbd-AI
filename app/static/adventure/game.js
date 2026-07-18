(() => {
  "use strict";

  const VERSION = "1.1.2";
  const STORAGE_KEY = "nero.voidbound.v1";
  const W = 960;
  const H = 540;
  const WORLD = 3200;
  const TILE = 32;
  const TAU = Math.PI * 2;

  const BIOMES = [
    { name: "Mossglint Wilds", short: "MOSSGLINT", ground: "#1b3540", alt: "#214d49", detail: "#63b67e", fog: "#78dfb4", enemy: "Briarling", boss: "The Rootbound Hart" },
    { name: "Cinderwake Forge", short: "CINDERWAKE", ground: "#45262b", alt: "#63322b", detail: "#ee7a4b", fog: "#ffb065", enemy: "Cinder Imp", boss: "Vulkran, Kiln Heart" },
    { name: "Glasswater Reach", short: "GLASSWATER", ground: "#17334d", alt: "#1d4f67", detail: "#59c7d9", fog: "#8ff5ff", enemy: "Tide Wraith", boss: "Morrowfin the Deep" },
    { name: "Gloamveil Archive", short: "GLOAMVEIL", ground: "#30264f", alt: "#45356a", detail: "#a87cff", fog: "#d2b7ff", enemy: "Inkbound", boss: "The Unwritten" },
    { name: "Starfall Expanse", short: "STARFALL", ground: "#172a44", alt: "#263e62", detail: "#87b9ff", fog: "#d0e8ff", enemy: "Astral Fang", boss: "Orryx, Fallen Orbit" },
    { name: "Ashen Crown", short: "ASHEN CROWN", ground: "#39343b", alt: "#504752", detail: "#d4a49c", fog: "#f1c7b9", enemy: "Crownless", boss: "The Pale Regent" },
    { name: "Lumenrest Ruins", short: "LUMENREST", ground: "#233d3e", alt: "#315a50", detail: "#edcf7b", fog: "#fff0ac", enemy: "Hollow Pilgrim", boss: "Bellkeeper Eidos" },
    { name: "The Violet Terminus", short: "TERMINUS", ground: "#211333", alt: "#392050", detail: "#bd74ff", fog: "#edc7ff", enemy: "Void Revenant", boss: "Nihra, Last Silence" },
  ];

  const CLASSES = {
    vanguard: {
      name: "Void Vanguard", title: "IRON OATH", glyph: "◆", weapon: "Nightglass Blade",
      description: "Close-range bulwark. Heavy arcs, high health, and a poise-breaking shockwave.",
      color: "#a77bff", hp: 132, speed: 205, damage: 24, rate: .34, reach: 74, staminaCost: 14,
      art: "Gravitic Break", artDescription: "A circular rupture that damages, staggers, and pulls nearby foes.",
    },
    lancer: {
      name: "Dawn Lancer", title: "SPEAR OATH", glyph: "✦", weapon: "Solaris Pike",
      description: "Precise reach fighter. Fast thrusts, critical momentum, and a piercing charge.",
      color: "#ffc86b", hp: 108, speed: 225, damage: 20, rate: .25, reach: 118, staminaCost: 11,
      art: "Comet Passage", artDescription: "Dash through enemies in a line and guarantee a critical strike.",
    },
    arcanist: {
      name: "Gloam Arcanist", title: "WAND OATH", glyph: "◇", weapon: "Witchlight Scepter",
      description: "Mobile spellcaster. Ranged bolts, rapid stamina recovery, and a chained void nova.",
      color: "#7ce9ff", hp: 92, speed: 215, damage: 17, rate: .28, reach: 360, staminaCost: 9,
      art: "Nero's Chorus", artDescription: "Release seeking motes that chain between marked enemies.",
    },
  };

  const COMPANIONS = {
    iskra: {
      name: "Iskra", title: "EMBER HUNTRESS", asset: "./assets/iskra-v2.webp", color: "#ff9b52",
      description: "Marks a nearby enemy, then pounces for focused damage. Bond increases mark strength.",
      art: "Copper Pounce", provenance: "validated Codex Pet v2",
    },
    nero: {
      name: "Nero", title: "VOID GUARDIAN", asset: "./assets/nero-void-guardian-v2.webp", color: "#c477ff",
      description: "Reduces incoming harm and periodically ruptures the poise of surrounding enemies.",
      art: "Guardian Rupture", provenance: "validated Nero Void Guardian v2",
    },
    mia: {
      name: "Mia", title: "KEEPER OF LIGHT", asset: "./assets/mia-v2-provisional.webp", color: "#ffd27d",
      description: "Raises a warm beacon that heals when wounded, or burns the nearest threat when steady.",
      art: "Nineteenth Light", provenance: "provisional Mia v2 build copy",
    },
  };

  const companionImages = Object.fromEntries(Object.entries(COMPANIONS).map(([id, companion]) => {
    const image = new Image(); image.decoding = "async"; image.src = companion.asset; return [id, image];
  }));

  const UPGRADE_POOL = [
    { id: "might", glyph: "⚔", name: "Blackstar Edge", text: "+18% weapon damage.", apply: p => { p.damage *= 1.18; } },
    { id: "vitality", glyph: "♥", name: "Vessel Unbroken", text: "+24 maximum HP and heal 24.", apply: p => { p.maxHp += 24; p.hp = Math.min(p.maxHp, p.hp + 24); } },
    { id: "haste", glyph: "↯", name: "Quickened Oath", text: "+10% attack speed and movement.", apply: p => { p.attackRate *= .9; p.speed *= 1.1; } },
    { id: "reach", glyph: "⌁", name: "Long Memory", text: "+18% reach and projectile speed.", apply: p => { p.reach *= 1.18; p.projectileSpeed *= 1.15; } },
    { id: "stamina", glyph: "◈", name: "Second Breath", text: "+28 stamina and faster recovery.", apply: p => { p.maxStamina += 28; p.stamina = p.maxStamina; p.staminaRegen += 6; } },
    { id: "crit", glyph: "✧", name: "Certain Ending", text: "+9% critical chance; criticals deal more damage.", apply: p => { p.crit += .09; p.critDamage += .2; } },
    { id: "leech", glyph: "☾", name: "Kindred Hunger", text: "Recover 3% of damage dealt as HP.", apply: p => { p.leech += .03; } },
    { id: "guard", glyph: "⬡", name: "Violet Aegis", text: "Take 12% less damage.", apply: p => { p.armor = Math.min(.6, p.armor + .12); } },
    { id: "art", glyph: "✦", name: "Resonant Art", text: "Oath art cooldown reduced by 22%.", apply: p => { p.artRate *= .78; } },
  ];

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d", { alpha: false });
  ctx.imageSmoothingEnabled = false;

  const $ = id => document.getElementById(id);
  const ui = {
    start: $("start-screen"), level: $("level-screen"), codex: $("codex-screen"), ranks: $("rank-screen"), end: $("end-screen"),
    classGrid: $("class-grid"), companionGrid: $("companion-grid"), startButton: $("start-button"), continueButton: $("continue-button"), upgradeGrid: $("upgrade-grid"),
    hpFill: $("hp-fill"), hpLabel: $("hp-label"), staminaFill: $("stamina-fill"), staminaLabel: $("stamina-label"),
    xpFill: $("xp-fill"), xpLabel: $("xp-label"), levelLabel: $("level-label"), scoreLabel: $("score-label"), shardLabel: $("shard-label"),
    runLabel: $("run-label"), objective: $("objective"), announcement: $("announcement"), classIcon: $("class-icon"), classLabel: $("class-label"),
    weaponLabel: $("weapon-label"), masteryLabel: $("mastery-label"), tonicLabel: $("tonic-label"), audioLabel: $("audio-label"),
    companionAvatar: $("companion-avatar"), companionLabel: $("companion-label"), bondLabel: $("bond-label"),
    codexContent: $("codex-content"), rankContent: $("rank-content"), endTitle: $("end-title"), endKicker: $("end-kicker"), endStats: $("end-stats"),
  };

  const input = { keys: new Set(), pressed: new Set(), x: 0, y: 0, attack: false, dash: false, ability: false };
  let selectedClass = "vanguard";
  let selectedMode = "journey";
  let selectedCompanion = "iskra";
  let meta = loadMeta();
  let game = blankGame();
  let last = performance.now();
  let frameRequest = 0;
  let announceTimer = 0;
  let saveTimer = 0;
  let audio = null;

  function blankGame() {
    return {
      state: "menu", mode: "journey", seed: 1, rng: mulberry32(1), time: 0, biome: 0, threat: 1,
      player: null, companion: null, enemies: [], projectiles: [], effects: [], pickups: [], scenery: [],
      kills: 0, biomeKills: 0, goal: 12, bossSpawned: false, portal: null, score: 0, shards: 0,
      camera: { x: WORLD / 2, y: WORLD / 2, shake: 0 }, spawnClock: 3.2, runStarted: 0, runId: "", gamepadAttack: false,
    };
  }

  function safeNumber(value, fallback, min = -Infinity, max = Infinity) {
    return Number.isFinite(Number(value)) ? clamp(Number(value), min, max) : fallback;
  }

  function defaultMeta() {
    return { version: VERSION, audio: true, preferredCompanion: "iskra", ranks: [], runs: 0, bestJourney: 0, bestSurvival: 0, lifetimeShards: 0, lastRun: null };
  }

  function loadMeta() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!value || typeof value !== "object" || Array.isArray(value)) return defaultMeta();
      return {
        ...defaultMeta(),
        audio: value.audio !== false,
        preferredCompanion: COMPANIONS[value.preferredCompanion] ? value.preferredCompanion : "iskra",
        ranks: Array.isArray(value.ranks) ? value.ranks.filter(validRank).slice(0, 10) : [],
        runs: safeNumber(value.runs, 0, 0, 1e7),
        bestJourney: safeNumber(value.bestJourney, 0, 0, 1e9),
        bestSurvival: safeNumber(value.bestSurvival, 0, 0, 1e9),
        lifetimeShards: safeNumber(value.lifetimeShards, 0, 0, 1e9),
        lastRun: validSavedRun(value.lastRun) ? value.lastRun : null,
      };
    } catch (_) {
      return defaultMeta();
    }
  }

  function validRank(rank) {
    return rank && typeof rank === "object" && ["journey", "survival"].includes(rank.mode) && CLASSES[rank.classId]
      && (!rank.companionId || COMPANIONS[rank.companionId])
      && Number.isFinite(rank.score) && rank.score >= 0 && Number.isFinite(rank.level) && rank.level >= 1
      && typeof rank.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(rank.date);
  }

  function validSavedRun(run) {
    return run && typeof run === "object" && ["journey", "survival"].includes(run.mode) && CLASSES[run.classId]
      && (!run.companionId || COMPANIONS[run.companionId])
      && Number.isFinite(run.seed) && run.player && typeof run.player === "object" && Number.isFinite(run.player.level);
  }

  function persistMeta() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(meta)); } catch (_) { /* private mode may deny storage */ }
  }

  function saveRun() {
    if (game.state !== "playing" || !game.player) return;
    const p = game.player;
    meta.lastRun = {
      version: VERSION, mode: game.mode, classId: p.classId, companionId: game.companion?.id || selectedCompanion, seed: game.seed, time: game.time, biome: game.biome,
      threat: game.threat, kills: game.kills, biomeKills: game.biomeKills, goal: game.goal, score: game.score, shards: game.shards,
      bossSpawned: false, player: {
        level: p.level, xp: p.xp, xpNext: p.xpNext, hp: p.hp, maxHp: p.maxHp, maxStamina: p.maxStamina,
        damage: p.damage, attackRate: p.attackRate, speed: p.speed, reach: p.reach, projectileSpeed: p.projectileSpeed,
        staminaRegen: p.staminaRegen, crit: p.crit, critDamage: p.critDamage, leech: p.leech, armor: p.armor,
        artRate: p.artRate, tonics: p.tonics, upgrades: [...p.upgrades], mastery: p.mastery,
      },
      companion: game.companion ? { bond: game.companion.bond, bondXp: game.companion.bondXp } : null,
    };
    persistMeta();
  }

  function mulberry32(seed) {
    let a = seed >>> 0;
    return () => {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function distance(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
  function normalize(x, y) { const d = Math.hypot(x, y) || 1; return { x: x / d, y: y / d }; }
  function hash2(x, y, seed = game.seed) {
    let h = Math.imul(x ^ seed, 374761393) + Math.imul(y ^ (seed >>> 8), 668265263);
    h = (h ^ (h >>> 13)) * 1274126177;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
  }
  function pick(array) { return array[Math.floor(game.rng() * array.length)]; }

  function buildClassCards() {
    ui.classGrid.innerHTML = "";
    Object.entries(CLASSES).forEach(([id, klass]) => {
      const button = document.createElement("button");
      button.className = `class-card${id === selectedClass ? " selected" : ""}`;
      button.dataset.classId = id;
      button.innerHTML = `<span class="class-glyph">${klass.glyph}</span><strong>${klass.name}</strong><em>${klass.title}</em><p>${klass.description}</p>`;
      button.addEventListener("click", () => selectClass(id));
      ui.classGrid.append(button);
    });
  }

  function buildCompanionCards() {
    ui.companionGrid.innerHTML = "";
    Object.entries(COMPANIONS).forEach(([id, companion]) => {
      const button = document.createElement("button");
      button.className = `companion-card${id === selectedCompanion ? " selected" : ""}`;
      button.dataset.companionId = id;
      button.innerHTML = `<span class="companion-portrait"></span><span><strong>${companion.name}</strong><em>${companion.title}</em><p>${companion.description}</p></span>`;
      button.addEventListener("click", () => selectCompanion(id));
      ui.companionGrid.append(button);
    });
  }

  function selectClass(id) {
    if (!CLASSES[id]) return;
    selectedClass = id;
    document.querySelectorAll(".class-card").forEach(el => el.classList.toggle("selected", el.dataset.classId === id));
  }

  function selectCompanion(id) {
    if (!COMPANIONS[id]) return;
    selectedCompanion = id; meta.preferredCompanion = id; persistMeta();
    document.querySelectorAll(".companion-card").forEach(el => el.classList.toggle("selected", el.dataset.companionId === id));
  }

  function createPlayer(classId) {
    const c = CLASSES[classId];
    return {
      classId, x: WORLD / 2, y: WORLD / 2, vx: 0, vy: 0, facing: { x: 1, y: 0 }, radius: 15,
      hp: c.hp, maxHp: c.hp, stamina: 100, maxStamina: 100, staminaRegen: classId === "arcanist" ? 31 : 25,
      speed: c.speed, damage: c.damage, attackRate: c.rate, attackTimer: 0, reach: c.reach,
      projectileSpeed: 580, crit: .07, critDamage: 1.75, leech: 0, armor: classId === "vanguard" ? .08 : 0,
      level: 1, xp: 0, xpNext: 80, tonics: 3, invuln: 0, dashTimer: 0, artTimer: 0, artRate: 8,
      upgrades: [], mastery: 1, combo: 0, comboTimer: 0, step: 0,
    };
  }

  function createCompanion(id) {
    const companion = COMPANIONS[id] || COMPANIONS.iskra;
    return {
      id: COMPANIONS[id] ? id : "iskra", x: WORLD / 2 - 46, y: WORLD / 2 + 36, vx: 0, vy: 0,
      facing: 1, row: 0, frame: 0, animationClock: 0, abilityTimer: 2.5, pulse: 0,
      bond: 1, bondXp: 0, bondNext: 12, target: null, color: companion.color,
    };
  }

  function beginRun(classId = selectedClass, mode = selectedMode, saved = null) {
    selectedClass = classId;
    selectedMode = mode;
    selectedCompanion = saved?.companionId && COMPANIONS[saved.companionId] ? saved.companionId : selectedCompanion;
    meta.preferredCompanion = selectedCompanion;
    game = blankGame();
    game.state = "playing";
    game.mode = mode;
    game.seed = saved?.seed || Math.floor(Date.now() % 2147483647);
    game.rng = mulberry32(game.seed);
    game.runId = `${Date.now().toString(36)}-${game.seed.toString(36)}`;
    game.player = createPlayer(classId);
    game.companion = createCompanion(selectedCompanion);
    if (saved) restoreRun(saved);
    game.runStarted = Date.now();
    generateScenery();
    ui.start.hidden = true;
    ui.end.hidden = true;
    if (!saved) meta.runs += 1;
    meta.lastRun = null;
    persistMeta();
    updateHud(true);
    announce(BIOMES[game.biome].name, mode === "journey" ? `DOMAIN ${game.biome + 1} OF ${BIOMES.length}` : "ENDLESS SURVIVAL");
    sound("start");
    canvas.focus();
  }

  function restoreRun(saved) {
    const p = game.player;
    game.time = safeNumber(saved.time, 0, 0, 1e8); game.biome = Math.floor(safeNumber(saved.biome, 0, 0, BIOMES.length - 1));
    game.threat = Math.floor(safeNumber(saved.threat, 1, 1, 999)); game.kills = Math.floor(safeNumber(saved.kills, 0, 0, 1e7));
    game.biomeKills = Math.floor(safeNumber(saved.biomeKills, 0, 0, 1e6)); game.goal = Math.floor(safeNumber(saved.goal, 12, 1, 1e6));
    game.score = Math.floor(safeNumber(saved.score, 0, 0, 1e12)); game.shards = Math.floor(safeNumber(saved.shards, 0, 0, 1e8));
    const s = saved.player;
    const limits = {
      level: [1, 1000], xp: [0, 1e9], xpNext: [1, 1e9], maxHp: [1, 1e6], maxStamina: [1, 1e6],
      damage: [1, 1e6], attackRate: [.05, 5], speed: [20, 1000], reach: [10, 2000], projectileSpeed: [50, 3000],
      staminaRegen: [0, 1000], crit: [0, 1], critDamage: [1, 10], leech: [0, 1], armor: [0, .8],
      artRate: [.1, 120], tonics: [0, 5], mastery: [1, 1000],
    };
    Object.entries(limits).forEach(([key, [min, max]]) => { p[key] = safeNumber(s[key], p[key], min, max); });
    p.level = Math.floor(p.level); p.tonics = Math.floor(p.tonics); p.mastery = Math.floor(p.mastery);
    p.hp = clamp(safeNumber(s.hp, p.maxHp), 1, p.maxHp); p.stamina = p.maxStamina;
    p.upgrades = Array.isArray(s.upgrades) ? s.upgrades.filter(id => UPGRADE_POOL.some(u => u.id === id)).slice(0, 40) : [];
    if (game.companion && saved.companion && typeof saved.companion === "object") {
      game.companion.bond = Math.floor(safeNumber(saved.companion.bond, 1, 1, 100));
      game.companion.bondXp = Math.floor(safeNumber(saved.companion.bondXp, 0, 0, 1e7));
      game.companion.bondNext = 8 + game.companion.bond * 6;
    }
  }

  function generateScenery() {
    game.scenery = [];
    const rng = mulberry32(game.seed + game.biome * 911);
    for (let i = 0; i < 230; i++) {
      const x = 70 + rng() * (WORLD - 140); const y = 70 + rng() * (WORLD - 140);
      if (Math.hypot(x - WORLD / 2, y - WORLD / 2) < 170) continue;
      game.scenery.push({ x, y, type: rng() < .68 ? "plant" : rng() < .82 ? "stone" : "rune", size: 8 + rng() * 20, phase: rng() * TAU });
    }
  }

  function spawnEnemy(options = {}) {
    if (!game.player) return;
    const angle = game.rng() * TAU;
    const dist = options.boss ? 300 : 380 + game.rng() * 250;
    const level = 1 + game.biome * 2 + (game.mode === "survival" ? game.threat : 0);
    const passive = !options.boss && game.rng() < .42;
    const elite = !options.boss && game.rng() < Math.min(.24, .04 + level * .008);
    const scale = options.boss ? 7 + game.biome * 1.4 : elite ? 2.2 : 1;
    const maxHp = (28 + level * 8) * scale;
    game.enemies.push({
      id: `${game.time}-${game.rng()}`, x: clamp(game.player.x + Math.cos(angle) * dist, 40, WORLD - 40),
      y: clamp(game.player.y + Math.sin(angle) * dist, 40, WORLD - 40), vx: 0, vy: 0,
      radius: options.boss ? 37 : elite ? 21 : 15, hp: maxHp, maxHp, speed: (options.boss ? 72 : 68 + game.rng() * 32) * (1 + level * .008),
      damage: (options.boss ? 18 : 3 + level * .4) * (elite ? 1.35 : 1), xp: Math.round((12 + level * 4) * scale),
      aggressive: !passive || options.boss, alerted: !passive || options.boss, elite, boss: !!options.boss,
      name: options.boss ? BIOMES[game.biome].boss : elite ? `Ascendant ${BIOMES[game.biome].enemy}` : BIOMES[game.biome].enemy,
      attackTimer: 0, hitFlash: 0, stagger: 0, phase: game.rng() * TAU, dead: false,
    });
  }

  function update(dt) {
    pollGamepad();
    if (game.state !== "playing" || !game.player) { clearTransientInput(); return; }
    game.time += dt;
    saveTimer += dt;
    if (saveTimer > 8) { saveTimer = 0; saveRun(); }
    updatePlayer(dt);
    updateCompanion(dt);
    updateEnemies(dt);
    updateProjectiles(dt);
    updateEffects(dt);
    updatePickups(dt);
    updateSpawning(dt);
    updateJourney(dt);
    game.camera.x = lerp(game.camera.x, game.player.x, 1 - Math.pow(.0005, dt));
    game.camera.y = lerp(game.camera.y, game.player.y, 1 - Math.pow(.0005, dt));
    game.camera.shake = Math.max(0, game.camera.shake - dt * 24);
    updateHud();
    clearTransientInput();
  }

  function updatePlayer(dt) {
    const p = game.player;
    let mx = input.x + ((input.keys.has("KeyD") || input.keys.has("ArrowRight")) ? 1 : 0) - ((input.keys.has("KeyA") || input.keys.has("ArrowLeft")) ? 1 : 0);
    let my = input.y + ((input.keys.has("KeyS") || input.keys.has("ArrowDown")) ? 1 : 0) - ((input.keys.has("KeyW") || input.keys.has("ArrowUp")) ? 1 : 0);
    if (mx || my) { const n = normalize(mx, my); mx = n.x; my = n.y; p.facing = n; p.step += dt * 10; }
    p.invuln = Math.max(0, p.invuln - dt); p.attackTimer = Math.max(0, p.attackTimer - dt); p.artTimer = Math.max(0, p.artTimer - dt); p.comboTimer -= dt;
    if (p.comboTimer <= 0) p.combo = 0;
    p.stamina = Math.min(p.maxStamina, p.stamina + p.staminaRegen * dt);
    const dashRequested = input.dash || input.pressed.has("ShiftLeft") || input.pressed.has("ShiftRight");
    if (dashRequested && p.dashTimer <= 0 && p.stamina >= 28) {
      p.stamina -= 28; p.dashTimer = .18; p.invuln = .28; sound("dash");
      for (let i = 0; i < 8; i++) particle(p.x, p.y, CLASSES[p.classId].color, 110, .32);
    }
    if (p.dashTimer > 0) { p.dashTimer -= dt; p.vx = p.facing.x * 640; p.vy = p.facing.y * 640; }
    else { p.vx = mx * p.speed; p.vy = my * p.speed; }
    p.x = clamp(p.x + p.vx * dt, 24, WORLD - 24); p.y = clamp(p.y + p.vy * dt, 24, WORLD - 24);

    const attackRequested = input.attack || input.keys.has("Space") || input.keys.has("KeyJ");
    if (attackRequested && p.attackTimer <= 0 && p.stamina >= CLASSES[p.classId].staminaCost) attack();
    if (input.ability || input.pressed.has("KeyF")) useArt();
    if (input.pressed.has("KeyQ")) useTonic();
    if (input.pressed.has("KeyC")) openCodex();
    if (input.pressed.has("KeyL")) openRanks();
    if (input.pressed.has("KeyM")) toggleAudio();
    if (game.portal && distance(p, game.portal) < 45) enterPortal();
  }

  function attack() {
    const p = game.player; const c = CLASSES[p.classId];
    p.attackTimer = p.attackRate; p.stamina -= c.staminaCost; p.combo = (p.combo % 3) + 1; p.comboTimer = .75;
    if (p.classId === "arcanist") {
      game.projectiles.push({ x: p.x + p.facing.x * 18, y: p.y + p.facing.y * 18, vx: p.facing.x * p.projectileSpeed, vy: p.facing.y * p.projectileSpeed, radius: 7, life: p.reach / p.projectileSpeed, damage: p.damage * (p.combo === 3 ? 1.35 : 1), friendly: true, color: c.color, pierce: p.combo === 3 ? 2 : 0 });
    } else {
      const arc = p.classId === "vanguard" ? .86 : .36; let hits = 0;
      game.enemies.forEach(e => {
        if (e.dead || distance(p, e) > p.reach + e.radius) return;
        const n = normalize(e.x - p.x, e.y - p.y); const dot = n.x * p.facing.x + n.y * p.facing.y;
        if (dot > 1 - arc) { damageEnemy(e, p.damage * (p.combo === 3 ? 1.45 : 1)); hits++; }
      });
      game.effects.push({ type: "slash", x: p.x, y: p.y, angle: Math.atan2(p.facing.y, p.facing.x), radius: p.reach, color: c.color, life: .14, maxLife: .14 });
      if (hits) game.camera.shake = 5;
    }
    sound("attack");
  }

  function useArt() {
    const p = game.player; if (p.artTimer > 0 || p.stamina < 42) return;
    p.artTimer = p.artRate; p.stamina -= 42; const color = CLASSES[p.classId].color;
    if (p.classId === "vanguard") {
      game.enemies.forEach(e => { if (!e.dead && distance(p, e) < 190) { damageEnemy(e, p.damage * 1.75); e.stagger = 1.1; const n = normalize(p.x - e.x, p.y - e.y); e.x += n.x * 36; e.y += n.y * 36; } });
      game.effects.push({ type: "nova", x: p.x, y: p.y, radius: 20, maxRadius: 200, color, life: .55, maxLife: .55 });
    } else if (p.classId === "lancer") {
      for (let i = 0; i < 5; i++) game.projectiles.push({ x: p.x + p.facing.x * i * 40, y: p.y + p.facing.y * i * 40, vx: p.facing.x * 740, vy: p.facing.y * 740, radius: 16, life: .42, damage: p.damage * 1.25, friendly: true, color, pierce: 99 });
      p.dashTimer = .42; p.invuln = .5;
    } else {
      const targets = [...game.enemies].filter(e => !e.dead).sort((a, b) => distance(p, a) - distance(p, b)).slice(0, 7);
      targets.forEach((e, i) => setTimeout(() => {
        if (game.state === "playing" && !e.dead) {
          game.projectiles.push({ x: p.x, y: p.y, target: e, vx: 0, vy: 0, radius: 9, life: 1.4, damage: p.damage * 1.45, friendly: true, color, pierce: 0, seeking: true });
        }
      }, i * 65));
    }
    announce(CLASSES[p.classId].art, "OATH ART"); sound("art");
  }

  function useTonic() {
    const p = game.player; if (p.tonics <= 0 || p.hp >= p.maxHp) return;
    p.tonics--; p.hp = Math.min(p.maxHp, p.hp + p.maxHp * .36); p.stamina = Math.min(p.maxStamina, p.stamina + 45);
    for (let i = 0; i < 16; i++) particle(p.x, p.y, "#7cffb1", 130, .7); sound("heal"); updateHud(true);
  }

  function updateCompanion(dt) {
    const companion = game.companion; const p = game.player; if (!companion || !p) return;
    companion.abilityTimer -= dt; companion.pulse = Math.max(0, companion.pulse - dt); companion.animationClock += dt;
    const side = { x: -p.facing.y, y: p.facing.x };
    const desired = { x: p.x - p.facing.x * 54 + side.x * 38, y: p.y - p.facing.y * 54 + side.y * 38 };
    let d = Math.hypot(desired.x - companion.x, desired.y - companion.y);
    if (d > 440) { companion.x = desired.x; companion.y = desired.y; d = 0; for (let i=0;i<10;i++) particle(companion.x, companion.y, companion.color, 90, .45); }
    if (d > 26) {
      const n = normalize(desired.x - companion.x, desired.y - companion.y); const speed = Math.min(360, 185 + d * .72);
      companion.vx = n.x * speed; companion.vy = n.y * speed; companion.x += companion.vx * dt; companion.y += companion.vy * dt;
      companion.facing = companion.vx >= 0 ? 1 : -1; companion.row = companion.facing > 0 ? 1 : 2; companion.frame = Math.floor(companion.animationClock * 10) % 8;
    } else { companion.vx *= .7; companion.vy *= .7; companion.row = 0; companion.frame = Math.floor(companion.animationClock * 4) % 6; }

    const targets = game.enemies.filter(e => !e.dead).sort((a, b) => distance(companion, a) - distance(companion, b));
    const target = targets[0]; companion.target = target || null;
    if (companion.abilityTimer > 0) return;
    if (companion.id === "iskra" && target && distance(companion, target) < 380) {
      companion.abilityTimer = Math.max(.8, 2.25 - companion.bond * .045); companion.pulse = .42;
      target.marked = Math.max(target.marked || 0, 3.5 + companion.bond * .08);
      damageEnemy(target, p.damage * (.34 + companion.bond * .025), true);
      game.effects.push({ type: "beam", x: companion.x, y: companion.y, x2: target.x, y2: target.y, color: companion.color, life: .18, maxLife: .18 });
      sound("companion");
    } else if (companion.id === "nero") {
      const nearby = targets.filter(e => distance(companion, e) < 185);
      if (nearby.length) {
        companion.abilityTimer = Math.max(3.2, 6.4 - companion.bond * .09); companion.pulse = .6;
        nearby.forEach(e => { damageEnemy(e, p.damage * (.3 + companion.bond * .018), true); e.stagger = Math.max(e.stagger, .8); });
        game.effects.push({ type: "nova", x: companion.x, y: companion.y, radius: 15, maxRadius: 190, color: companion.color, life: .6, maxLife: .6 }); sound("art");
      }
    } else if (companion.id === "mia") {
      companion.abilityTimer = Math.max(3.8, 7.2 - companion.bond * .1); companion.pulse = .8;
      if (p.hp < p.maxHp * .78) {
        const heal = p.maxHp * Math.min(.2, .075 + companion.bond * .004); p.hp = Math.min(p.maxHp, p.hp + heal);
        floatText(p.x, p.y - 28, `+${Math.round(heal)}`, "#ffd27d", 1.1);
        game.effects.push({ type: "nova", x: companion.x, y: companion.y, radius: 12, maxRadius: 150, color: companion.color, life: .85, maxLife: .85 }); sound("heal");
      } else if (target && distance(companion, target) < 430) {
        damageEnemy(target, p.damage * (.42 + companion.bond * .02), true);
        game.effects.push({ type: "beam", x: companion.x, y: companion.y, x2: target.x, y2: target.y, color: companion.color, life: .4, maxLife: .4 }); sound("pickup");
      }
    }
  }

  function grantCompanionBond(amount) {
    const companion = game.companion; if (!companion) return;
    companion.bondXp += amount;
    while (companion.bondXp >= companion.bondNext && companion.bond < 100) {
      companion.bondXp -= companion.bondNext; companion.bond++; companion.bondNext = 8 + companion.bond * 6;
      announce(`${COMPANIONS[companion.id].name} · Bond ${companion.bond}`, COMPANIONS[companion.id].art.toUpperCase()); sound("level");
    }
  }

  function damageEnemy(enemy, baseDamage, fromCompanion = false) {
    if (enemy.dead) return;
    const p = game.player; const critical = game.rng() < p.crit;
    const markBonus = !fromCompanion && enemy.marked > 0 && game.companion?.id === "iskra" ? 1.18 + game.companion.bond * .003 : 1;
    const damage = Math.max(1, Math.round(baseDamage * markBonus * (critical ? p.critDamage : 1) * (.92 + game.rng() * .16)));
    enemy.hp -= damage; enemy.alerted = true; enemy.hitFlash = .1; enemy.stagger = Math.max(enemy.stagger, .08);
    if (p.leech) p.hp = Math.min(p.maxHp, p.hp + damage * p.leech);
    floatText(enemy.x, enemy.y - enemy.radius, `${critical ? "✦ " : ""}${damage}`, critical ? "#ffc86b" : "#ffffff", critical ? 1.25 : 1);
    for (let i = 0; i < (critical ? 9 : 4); i++) particle(enemy.x, enemy.y, critical ? "#ffc86b" : CLASSES[p.classId].color, 130, .34);
    if (enemy.hp <= 0) killEnemy(enemy);
  }

  function killEnemy(enemy) {
    enemy.dead = true; game.kills++; game.biomeKills++; game.score += Math.round(enemy.xp * (enemy.elite ? 6 : enemy.boss ? 18 : 3));
    grantXp(enemy.xp); grantCompanionBond(enemy.boss ? 6 : enemy.elite ? 2 : 1); sound(enemy.boss ? "boss" : "kill");
    const dropCount = enemy.boss ? 8 : enemy.elite ? 3 : game.rng() < .35 ? 1 : 0;
    for (let i = 0; i < dropCount; i++) game.pickups.push({ x: enemy.x + (game.rng() - .5) * 24, y: enemy.y + (game.rng() - .5) * 24, type: "shard", value: enemy.boss ? 3 : 1, life: 18, phase: game.rng() * TAU });
    if (!enemy.boss && game.rng() < .045) game.pickups.push({ x: enemy.x, y: enemy.y, type: "tonic", value: 1, life: 18, phase: 0 });
    if (enemy.boss) {
      game.portal = { x: enemy.x, y: enemy.y, radius: 22, phase: 0 };
      announce("Keeper Bound", "ENTER THE VIOLET GATE");
    }
  }

  function grantXp(amount) {
    const p = game.player; p.xp += amount;
    if (p.xp >= p.xpNext) {
      p.xp -= p.xpNext; p.level++; p.mastery = 1 + Math.floor(p.level / 3); p.xpNext = Math.round(p.xpNext * 1.28 + 18);
      p.hp = Math.min(p.maxHp, p.hp + p.maxHp * .25); p.stamina = p.maxStamina;
      showLevelUp();
    }
  }

  function showLevelUp() {
    game.state = "levelup"; ui.upgradeGrid.innerHTML = "";
    const choices = [...UPGRADE_POOL].sort(() => game.rng() - .5).slice(0, 3);
    choices.forEach(upgrade => {
      const button = document.createElement("button"); button.className = "upgrade-card";
      button.innerHTML = `<i>${upgrade.glyph}</i><strong>${upgrade.name}</strong><span>${upgrade.text}</span>`;
      button.addEventListener("click", () => {
        upgrade.apply(game.player); game.player.upgrades.push(upgrade.id); ui.level.hidden = true; game.state = "playing";
        announce(`Level ${game.player.level}`, upgrade.name.toUpperCase()); sound("level"); canvas.focus(); saveRun();
      });
      ui.upgradeGrid.append(button);
    });
    ui.level.hidden = false;
  }

  function updateEnemies(dt) {
    const p = game.player;
    for (const e of game.enemies) {
      if (e.dead) continue;
      e.hitFlash = Math.max(0, e.hitFlash - dt); e.attackTimer -= dt; e.stagger -= dt; e.marked = Math.max(0, (e.marked || 0) - dt); e.phase += dt * 3;
      const d = distance(e, p); if (!e.alerted && d < 105) e.alerted = true;
      if (e.alerted && e.stagger <= 0) {
        const n = normalize(p.x - e.x, p.y - e.y); const orbit = e.boss ? Math.sin(game.time * .8 + e.phase) * .34 : 0;
        e.vx = (n.x - n.y * orbit) * e.speed; e.vy = (n.y + n.x * orbit) * e.speed;
        if (d > e.radius + p.radius + 12) { e.x += e.vx * dt; e.y += e.vy * dt; }
        else if (e.attackTimer <= 0) { damagePlayer(e.damage, e); e.attackTimer = e.boss ? 1.15 : 1.35; }
        if (e.boss && e.attackTimer > .78 && e.attackTimer - dt <= .78) bossVolley(e);
      }
    }
    game.enemies = game.enemies.filter(e => !e.dead && distance(e, p) < 1300);
  }

  function bossVolley(enemy) {
    const count = 8 + game.biome;
    for (let i = 0; i < count; i++) {
      const a = i / count * TAU + game.time * .2;
      game.projectiles.push({ x: enemy.x, y: enemy.y, vx: Math.cos(a) * 180, vy: Math.sin(a) * 180, radius: 8, life: 3.2, damage: enemy.damage * .55, friendly: false, color: BIOMES[game.biome].fog });
    }
  }

  function damagePlayer(amount, source) {
    const p = game.player; if (p.invuln > 0 || game.state !== "playing") return;
    const guardian = game.companion?.id === "nero" ? Math.min(.3, .14 + game.companion.bond * .008) : 0;
    const damage = Math.max(1, Math.round(amount * (1 - p.armor) * (1 - guardian)));
    p.hp = Math.max(0, p.hp - damage); p.invuln = .65; game.camera.shake = 12;
    floatText(p.x, p.y - 24, `-${damage}`, "#ff6688", 1.15); sound("hurt");
    const n = normalize(p.x - source.x, p.y - source.y); p.x += n.x * 24; p.y += n.y * 24;
    if (p.hp <= 0) endRun(false);
  }

  function updateProjectiles(dt) {
    const p = game.player;
    for (const shot of game.projectiles) {
      if (shot.seeking && shot.target && !shot.target.dead) {
        const n = normalize(shot.target.x - shot.x, shot.target.y - shot.y); shot.vx = lerp(shot.vx, n.x * 520, .14); shot.vy = lerp(shot.vy, n.y * 520, .14);
      }
      shot.x += shot.vx * dt; shot.y += shot.vy * dt; shot.life -= dt;
      if (shot.friendly) {
        for (const e of game.enemies) {
          if (e.dead || shot.hits?.has(e.id) || distance(shot, e) > shot.radius + e.radius) continue;
          damageEnemy(e, shot.damage); (shot.hits ||= new Set()).add(e.id);
          if (shot.pierce > 0) shot.pierce--; else { shot.life = 0; break; }
        }
      } else if (distance(shot, p) < shot.radius + p.radius) { damagePlayer(shot.damage, shot); shot.life = 0; }
    }
    game.projectiles = game.projectiles.filter(s => s.life > 0 && s.x > 0 && s.x < WORLD && s.y > 0 && s.y < WORLD);
  }

  function particle(x, y, color, speed = 100, life = .5) {
    const a = game.rng() * TAU; const s = speed * (.3 + game.rng() * .7);
    game.effects.push({ type: "particle", x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, color, life, maxLife: life, size: 2 + game.rng() * 3 });
  }

  function floatText(x, y, text, color, scale = 1) {
    game.effects.push({ type: "text", x, y, text, color, life: .75, maxLife: .75, scale });
  }

  function updateEffects(dt) {
    for (const e of game.effects) {
      e.life -= dt;
      if (e.type === "particle") { e.x += e.vx * dt; e.y += e.vy * dt; e.vx *= .96; e.vy *= .96; }
      if (e.type === "text") e.y -= 42 * dt;
    }
    game.effects = game.effects.filter(e => e.life > 0);
  }

  function updatePickups(dt) {
    const p = game.player;
    for (const item of game.pickups) {
      item.life -= dt; item.phase += dt * 4;
      const d = distance(item, p);
      if (d < 110) { const n = normalize(p.x - item.x, p.y - item.y); item.x += n.x * dt * (280 - d); item.y += n.y * dt * (280 - d); }
      if (d < p.radius + 12) {
        if (item.type === "shard") { game.shards += item.value; game.score += item.value * 25; }
        else p.tonics = Math.min(5, p.tonics + 1);
        item.life = 0; sound("pickup");
      }
    }
    game.pickups = game.pickups.filter(i => i.life > 0);
  }

  function updateSpawning(dt) {
    game.spawnClock -= dt;
    const cap = game.mode === "survival" ? Math.min(34, 7 + game.threat * 2) : 5 + game.biome * 2;
    if (game.spawnClock <= 0 && game.enemies.filter(e => !e.dead).length < cap && !game.portal) {
      spawnEnemy(); game.spawnClock = Math.max(.22, 1.35 - (game.biome + game.threat) * .055);
    }
    if (game.mode === "survival") {
      const newThreat = 1 + Math.floor(game.time / 42);
      if (newThreat > game.threat) { game.threat = newThreat; announce(`Threat ${String(newThreat).padStart(2, "0")}`, "THE VOID DEEPENS"); }
      if (game.time > 0 && Math.floor(game.time / 75) > Math.floor((game.time - dt) / 75)) spawnEnemy({ boss: true });
      game.biome = Math.floor(game.time / 55) % BIOMES.length;
    }
  }

  function updateJourney() {
    if (game.mode !== "journey" || game.portal) return;
    if (game.biomeKills >= game.goal && !game.bossSpawned) {
      game.bossSpawned = true; spawnEnemy({ boss: true }); announce(BIOMES[game.biome].boss, "DOMAIN KEEPER"); sound("warning");
    }
  }

  function enterPortal() {
    if (game.mode !== "journey") return;
    if (game.biome >= BIOMES.length - 1) { endRun(true); return; }
    game.biome++; game.biomeKills = 0; game.goal = 12 + game.biome * 4; game.bossSpawned = false; game.portal = null;
    game.enemies.length = 0; game.projectiles.length = 0; game.scenery.length = 0; game.player.x = WORLD / 2; game.player.y = WORLD / 2;
    if (game.companion) { game.companion.x = WORLD / 2 - 46; game.companion.y = WORLD / 2 + 36; }
    game.player.hp = Math.min(game.player.maxHp, game.player.hp + game.player.maxHp * .35); game.player.tonics = Math.min(5, game.player.tonics + 1);
    generateScenery(); announce(BIOMES[game.biome].name, `DOMAIN ${game.biome + 1} OF ${BIOMES.length}`); sound("portal"); saveRun();
  }

  function endRun(victory) {
    if (!game.player || game.state === "end") return;
    game.state = "end"; meta.lastRun = null; meta.lifetimeShards += game.shards;
    if (game.mode === "journey") meta.bestJourney = Math.max(meta.bestJourney, game.score); else meta.bestSurvival = Math.max(meta.bestSurvival, game.score);
    meta.ranks.push({ mode: game.mode, classId: game.player.classId, companionId: game.companion?.id, score: game.score, level: game.player.level, domain: game.biome + 1, time: Math.round(game.time), victory, date: new Date().toISOString().slice(0, 10) });
    meta.ranks.sort((a, b) => b.score - a.score); meta.ranks = meta.ranks.slice(0, 10); persistMeta();
    ui.endKicker.textContent = victory ? "THE LIGHT RETURNS" : "THE VOID REMEMBERS";
    ui.endTitle.textContent = victory ? "Chronicle complete" : "Your oath is broken";
    ui.endStats.innerHTML = statGrid({ Score: game.score.toLocaleString(), Level: game.player.level, Defeated: game.kills, Time: formatTime(game.time) });
    ui.end.hidden = false; sound(victory ? "victory" : "defeat");
  }

  function updateHud(force = false) {
    const p = game.player; if (!p) return;
    const setWidth = (el, n) => { const value = `${clamp(n, 0, 1) * 100}%`; if (force || el.style.width !== value) el.style.width = value; };
    setWidth(ui.hpFill, p.hp / p.maxHp); setWidth(ui.staminaFill, p.stamina / p.maxStamina); setWidth(ui.xpFill, p.xp / p.xpNext);
    ui.hpLabel.textContent = `${Math.ceil(p.hp)}/${Math.round(p.maxHp)}`; ui.staminaLabel.textContent = `${Math.round(p.stamina)}/${Math.round(p.maxStamina)}`;
    ui.xpLabel.textContent = `${Math.round(p.xp)}/${p.xpNext}`; ui.levelLabel.textContent = p.level; ui.scoreLabel.textContent = String(game.score).padStart(6, "0"); ui.shardLabel.textContent = game.shards;
    const biome = BIOMES[game.biome]; ui.runLabel.textContent = `${game.mode === "journey" ? `${game.biome + 1}/${BIOMES.length}` : "SURVIVAL"} ${biome.short} · ${formatTime(game.time)}`;
    ui.classIcon.textContent = CLASSES[p.classId].glyph; ui.classLabel.textContent = CLASSES[p.classId].title; ui.weaponLabel.textContent = CLASSES[p.classId].weapon;
    ui.masteryLabel.textContent = `M${p.mastery}`; ui.tonicLabel.textContent = p.tonics;
    if (game.companion) {
      const companion = COMPANIONS[game.companion.id]; ui.companionLabel.textContent = companion.name; ui.bondLabel.textContent = `B${game.companion.bond}`;
      ui.companionAvatar.parentElement.classList.remove("companion-iskra", "companion-nero", "companion-mia");
      ui.companionAvatar.parentElement.classList.add(`companion-${game.companion.id}`);
    }
    if (game.mode === "journey") ui.objective.innerHTML = game.portal ? `<b>Violet gate open</b><br>Enter the keeper's seal` : game.bossSpawned ? `<b>${biome.boss}</b><br>Bind the domain keeper` : `<b>Domain resonance</b><br>${Math.min(game.biomeKills, game.goal)} / ${game.goal} echoes bound`;
    else ui.objective.innerHTML = `<b>Threat ${String(game.threat).padStart(2, "0")}</b><br>${game.kills} echoes · survive`;
  }

  function formatTime(seconds) { const s = Math.floor(seconds); return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; }
  function statGrid(stats) { return `<div class="stat-grid">${Object.entries(stats).map(([k, v]) => `<div><small>${k.toUpperCase()}</small><b>${v}</b></div>`).join("")}</div>`; }

  function announce(title, subtitle = "") {
    clearTimeout(announceTimer); ui.announcement.innerHTML = `${title}<small>${subtitle}</small>`; ui.announcement.classList.add("show");
    announceTimer = setTimeout(() => ui.announcement.classList.remove("show"), 2100);
  }

  function openCodex() {
    if (!game.player || game.state !== "playing") return;
    const p = game.player; game.state = "paused";
    const counts = p.upgrades.reduce((out, id) => { out[id] = (out[id] || 0) + 1; return out; }, {});
    const companion = game.companion ? COMPANIONS[game.companion.id] : null;
    ui.codexContent.innerHTML = `${statGrid({ Might: Math.round(p.damage), Rate: `${(1 / p.attackRate).toFixed(1)}/s`, Reach: Math.round(p.reach), Guard: `${Math.round(p.armor * 100)}%` })}<p class="eyebrow">OATH ART</p><h3>${CLASSES[p.classId].art}</h3><p>${CLASSES[p.classId].artDescription}</p>${companion ? `<p class="eyebrow">BOUND COMPANION · BOND ${game.companion.bond}</p><h3>${companion.name} · ${companion.art}</h3><p>${companion.description}</p><p class="privacy-note">Asset provenance: ${companion.provenance}.</p>` : ""}<p class="eyebrow">RESONANCES</p><ul class="relic-list">${Object.entries(counts).map(([id, n]) => { const u = UPGRADE_POOL.find(x => x.id === id); return `<li><span>${u?.glyph || "·"} ${u?.name || id}</span><b>×${n}</b></li>`; }).join("") || "<li><span>No resonances bound yet.</span></li>"}</ul>`;
    ui.codex.hidden = false;
  }

  function openRanks() {
    if (game.state === "levelup" || game.state === "end") return;
    const resume = game.state === "playing"; if (resume) game.state = "paused";
    ui.ranks.dataset.resume = resume ? "true" : "false";
    ui.rankContent.innerHTML = meta.ranks.length ? `<ol class="rank-list">${meta.ranks.map((r, i) => `<li><span>${i + 1}. ${CLASSES[r.classId].name}${r.companionId ? ` + ${COMPANIONS[r.companionId].name}` : ""} · ${r.mode.toUpperCase()} · LV ${r.level}</span><b>${r.score.toLocaleString()}</b></li>`).join("")}</ol>` : `<p class="privacy-note">No completed chronicles yet.</p>`;
    ui.ranks.hidden = false;
  }

  function closeDialog(id) {
    const el = $(id); if (!el) return; el.hidden = true;
    if (game.player && game.state === "paused" && (id !== "rank-screen" || el.dataset.resume === "true")) { game.state = "playing"; canvas.focus(); }
  }

  function toggleAudio() { meta.audio = !meta.audio; ui.audioLabel.textContent = meta.audio ? "Audio" : "Muted"; persistMeta(); if (meta.audio) sound("pickup"); }

  function getAudio() {
    if (!meta.audio) return null;
    if (!audio) { const AudioCtx = window.AudioContext || window.webkitAudioContext; if (!AudioCtx) return null; audio = new AudioCtx(); }
    if (audio.state === "suspended") audio.resume().catch(() => {});
    return audio;
  }

  function sound(type) {
    const ac = getAudio(); if (!ac) return;
    const table = { attack: [180, .035, "square"], dash: [90, .08, "sawtooth"], hurt: [75, .14, "sawtooth"], kill: [320, .06, "triangle"], pickup: [680, .05, "sine"], companion: [760, .08, "triangle"], heal: [420, .18, "sine"], art: [130, .36, "sawtooth"], warning: [82, .42, "square"], level: [520, .32, "triangle"], portal: [240, .5, "sine"], boss: [55, .5, "sawtooth"], start: [260, .22, "triangle"], victory: [660, .75, "triangle"], defeat: [65, .8, "sawtooth"] };
    const spec = table[type] || table.pickup; const osc = ac.createOscillator(); const gain = ac.createGain(); const now = ac.currentTime;
    osc.type = spec[2]; osc.frequency.setValueAtTime(spec[0], now); osc.frequency.exponentialRampToValueAtTime(Math.max(30, spec[0] * (type === "hurt" || type === "defeat" ? .55 : 1.8)), now + spec[1]);
    gain.gain.setValueAtTime(.035, now); gain.gain.exponentialRampToValueAtTime(.0001, now + spec[1]); osc.connect(gain).connect(ac.destination); osc.start(now); osc.stop(now + spec[1]);
  }

  function draw() {
    const shakeX = game.camera.shake ? (Math.random() - .5) * game.camera.shake : 0;
    const shakeY = game.camera.shake ? (Math.random() - .5) * game.camera.shake : 0;
    const cam = { x: game.camera.x - W / 2 - shakeX, y: game.camera.y - H / 2 - shakeY };
    drawGround(cam);
    if (!game.player) { drawMenuBackdrop(); return; }
    drawScenery(cam); drawPortal(cam); drawPickups(cam); drawEnemies(cam); drawProjectiles(cam); drawCompanion(cam); drawPlayer(cam); drawEffects(cam); drawVignette();
  }

  function drawGround(cam) {
    const b = BIOMES[game.biome] || BIOMES[0]; ctx.fillStyle = b.ground; ctx.fillRect(0, 0, W, H);
    const startX = Math.floor(cam.x / TILE) * TILE; const startY = Math.floor(cam.y / TILE) * TILE;
    for (let y = startY; y < cam.y + H + TILE; y += TILE) for (let x = startX; x < cam.x + W + TILE; x += TILE) {
      const h = hash2(x / TILE, y / TILE, game.seed + game.biome * 101); const sx = Math.floor(x - cam.x); const sy = Math.floor(y - cam.y);
      if (h > .54) { ctx.fillStyle = b.alt; ctx.globalAlpha = .18 + h * .14; ctx.fillRect(sx, sy, TILE, TILE); }
      if (h > .82) { ctx.fillStyle = b.detail; ctx.globalAlpha = .24; ctx.fillRect(sx + 5, sy + 7, 2, 2); ctx.fillRect(sx + 21, sy + 23, 3, 2); }
    }
    ctx.globalAlpha = 1;
    const glow = ctx.createRadialGradient(W * .5, H * .48, 20, W * .5, H * .48, H * .76);
    glow.addColorStop(0, `${b.fog}12`); glow.addColorStop(.55, `${b.detail}08`); glow.addColorStop(1, "#02010836"); ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "#ffffff08"; ctx.lineWidth = 2; ctx.strokeRect(-cam.x + 16, -cam.y + 16, WORLD - 32, WORLD - 32);
  }

  function drawMenuBackdrop() {
    ctx.fillStyle = "#0c0915"; ctx.fillRect(0, 0, W, H);
    for (let i = 0; i < 60; i++) { const x = (i * 173) % W, y = (i * 97) % H; ctx.fillStyle = i % 3 ? "#a77bff18" : "#7ce9ff18"; ctx.fillRect(x, y, 2, 2); }
  }

  function screen(entity, cam) { return { x: Math.round(entity.x - cam.x), y: Math.round(entity.y - cam.y) }; }
  function visible(entity, cam, pad = 80) { const s = screen(entity, cam); return s.x > -pad && s.x < W + pad && s.y > -pad && s.y < H + pad; }

  function drawScenery(cam) {
    const b = BIOMES[game.biome];
    for (const s of game.scenery) {
      if (!visible(s, cam)) continue; const p = screen(s, cam); ctx.save(); ctx.translate(p.x, p.y);
      if (s.type === "plant") { ctx.fillStyle = "#07120f88"; ctx.fillRect(-2, 2, 4, s.size); ctx.fillStyle = b.detail; ctx.globalAlpha = .6; ctx.fillRect(-s.size * .35, -s.size * .25, s.size * .3, s.size * .6); ctx.fillRect(1, -s.size * .45, s.size * .35, s.size * .7); }
      else if (s.type === "stone") { ctx.fillStyle = "#09070db8"; ctx.beginPath(); ctx.ellipse(4, s.size * .45, s.size * .7, s.size * .3, 0, 0, TAU); ctx.fill(); ctx.fillStyle = b.alt; ctx.beginPath(); ctx.moveTo(-s.size*.45, s.size*.3); ctx.lineTo(-s.size*.2,-s.size*.45); ctx.lineTo(s.size*.35,-s.size*.3); ctx.lineTo(s.size*.55,s.size*.35); ctx.closePath(); ctx.fill(); }
      else { const pulse = .45 + Math.sin(game.time * 2 + s.phase) * .18; ctx.strokeStyle = b.fog; ctx.globalAlpha = pulse; ctx.lineWidth = 2; ctx.rotate(Math.PI / 4); ctx.strokeRect(-s.size*.35, -s.size*.35, s.size*.7, s.size*.7); }
      ctx.restore();
    }
  }

  function drawPlayer(cam) {
    const p = game.player; const s = screen(p, cam); const c = CLASSES[p.classId]; const bob = Math.sin(p.step) * 2;
    ctx.save(); ctx.translate(s.x, s.y + bob); ctx.globalAlpha = p.invuln > 0 && Math.floor(p.invuln * 14) % 2 ? .35 : 1;
    ctx.fillStyle = "#05040a66"; ctx.beginPath(); ctx.ellipse(0, 15, 18, 7, 0, 0, TAU); ctx.fill();
    ctx.strokeStyle = "#05030a"; ctx.lineWidth = 3; ctx.strokeRect(-11, -10, 22, 24); ctx.fillStyle = c.color; ctx.fillRect(-10, -9, 20, 22); ctx.fillStyle = "#1a1226"; ctx.fillRect(-7, -5, 14, 18);
    ctx.fillStyle = `${c.color}aa`; ctx.fillRect(-13, -7, 5, 12); ctx.fillRect(8, -7, 5, 12); ctx.fillStyle = "#08050f"; ctx.fillRect(-7, 9, 5, 8); ctx.fillRect(2, 9, 5, 8);
    ctx.fillStyle = "#d8b7a0"; ctx.fillRect(-7, -19, 14, 11); ctx.fillStyle = "#100c18"; ctx.fillRect(-9, -22, 18, 7);
    ctx.fillStyle = c.color; ctx.fillRect(p.facing.x * 11 - 2, p.facing.y * 8 - 4, 5, 15);
    ctx.fillStyle = "#fff"; ctx.fillRect(p.facing.x * 5 - 1, -17 + p.facing.y * 2, 2, 2);
    ctx.restore();
  }

  function drawCompanion(cam) {
    const companion = game.companion; if (!companion || !visible(companion, cam)) return;
    const s = screen(companion, cam); const spec = COMPANIONS[companion.id]; const image = companionImages[companion.id];
    const sizes = { iskra: [70, 76], nero: [74, 88], mia: [58, 74] }; const [width, height] = sizes[companion.id] || [64, 72];
    ctx.save(); ctx.translate(s.x, s.y); ctx.fillStyle = "#0302087a"; ctx.beginPath(); ctx.ellipse(0, 9, width * .34, 8, 0, 0, TAU); ctx.fill();
    if (companion.pulse > 0) { ctx.strokeStyle = spec.color; ctx.globalAlpha = companion.pulse; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(0, 0, 26 + (1 - companion.pulse) * 30, 0, TAU); ctx.stroke(); ctx.globalAlpha = 1; }
    if (image?.complete && image.naturalWidth) {
      const frame = clamp(companion.frame, 0, 7); const row = clamp(companion.row, 0, 10);
      ctx.drawImage(image, frame * 192, row * 208, 192, 208, -width / 2, -height + 15, width, height);
    } else {
      ctx.fillStyle = spec.color; ctx.font = "28px Georgia"; ctx.textAlign = "center"; ctx.fillText(companion.id === "iskra" ? "◆" : companion.id === "nero" ? "✦" : "☼", 0, -4); ctx.textAlign = "left";
    }
    ctx.restore();
  }

  function drawEnemies(cam) {
    const b = BIOMES[game.biome];
    for (const e of game.enemies) {
      if (e.dead || !visible(e, cam)) continue; const s = screen(e, cam); const size = e.radius * 2;
      ctx.save(); ctx.translate(s.x, s.y + Math.sin(game.time * 3 + e.phase) * 2);
      ctx.fillStyle = "#05040a66"; ctx.beginPath(); ctx.ellipse(0, e.radius*.78, e.radius, e.radius*.35, 0, 0, TAU); ctx.fill();
      ctx.fillStyle = e.hitFlash ? "#ffffff" : e.boss ? "#2a0c35" : e.elite ? b.fog : b.detail;
      if (e.boss) { ctx.beginPath(); for (let i=0;i<12;i++){ const a=i/12*TAU; const r=i%2?e.radius*.7:e.radius*1.25; const x=Math.cos(a)*r,y=Math.sin(a)*r; i?ctx.lineTo(x,y):ctx.moveTo(x,y);} ctx.closePath(); ctx.fill(); ctx.fillStyle=b.fog; ctx.fillRect(-e.radius*.4,-e.radius*.35,e.radius*.8,e.radius*.7); }
      else { ctx.fillRect(-e.radius*.7, -e.radius*.65, e.radius*1.4, e.radius*1.45); ctx.fillStyle="#0a0710"; ctx.fillRect(-e.radius*.35,-e.radius*.25,3,3); ctx.fillRect(e.radius*.2,-e.radius*.25,3,3); }
      if (e.marked > 0) { ctx.strokeStyle = "#ff9b52"; ctx.globalAlpha = .55 + Math.sin(game.time * 9) * .25; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(0, 0, e.radius + 7, 0, TAU); ctx.stroke(); ctx.globalAlpha = 1; }
      if (!e.boss && !e.aggressive && !e.alerted) { ctx.fillStyle="#ffffffb0"; ctx.font="12px sans-serif"; ctx.fillText("·", -2, -e.radius-7); }
      ctx.restore();
      if (e.boss || e.elite || e.hp < e.maxHp) {
        const width = e.boss ? 110 : size; ctx.fillStyle="#08060e"; ctx.fillRect(s.x-width/2,s.y-e.radius-15,width,5); ctx.fillStyle=e.boss?"#ff6688":b.fog; ctx.fillRect(s.x-width/2,s.y-e.radius-15,width*(e.hp/e.maxHp),5);
        if (e.boss) { ctx.fillStyle="#f4eaff"; ctx.font="9px Courier New"; ctx.textAlign="center"; ctx.fillText(e.name.toUpperCase(),s.x,s.y-e.radius-22); ctx.textAlign="left"; }
      }
    }
  }

  function drawProjectiles(cam) {
    for (const p of game.projectiles) { if (!visible(p,cam)) continue; const s=screen(p,cam); ctx.fillStyle=p.color; ctx.globalAlpha=.3; ctx.beginPath(); ctx.arc(s.x,s.y,p.radius*2.2,0,TAU);ctx.fill();ctx.globalAlpha=1;ctx.fillRect(s.x-p.radius/2,s.y-p.radius/2,p.radius,p.radius); }
  }

  function drawPickups(cam) {
    for (const p of game.pickups) { if (!visible(p,cam)) continue; const s=screen(p,cam); const bob=Math.sin(p.phase)*4; ctx.save();ctx.translate(s.x,s.y+bob);ctx.rotate(p.phase*.2);ctx.fillStyle=p.type==="shard"?"#c18cff":"#7cffb1";ctx.globalAlpha=.25;ctx.fillRect(-10,-10,20,20);ctx.globalAlpha=1;ctx.fillRect(-4,-7,8,14);ctx.restore(); }
  }

  function drawPortal(cam) {
    if (!game.portal) return; const p=game.portal; p.phase += .035; const s=screen(p,cam); ctx.save();ctx.translate(s.x,s.y);ctx.rotate(p.phase);for(let i=0;i<4;i++){ctx.strokeStyle=i%2?"#7ce9ff":"#bd7cff";ctx.globalAlpha=.8-i*.14;ctx.lineWidth=2;ctx.rotate(Math.PI/4);ctx.strokeRect(-22-i*7,-22-i*7,44+i*14,44+i*14);}ctx.restore();
  }

  function drawEffects(cam) {
    for (const e of game.effects) { if (!visible(e,cam)) continue; const s=screen(e,cam); const alpha=clamp(e.life/e.maxLife,0,1);ctx.save();ctx.globalAlpha=alpha;
      if(e.type==="particle"){ctx.fillStyle=e.color;ctx.fillRect(s.x-e.size/2,s.y-e.size/2,e.size,e.size);}
      else if(e.type==="text"){ctx.fillStyle=e.color;ctx.font=`bold ${Math.round(12*e.scale)}px Courier New`;ctx.textAlign="center";ctx.fillText(e.text,s.x,s.y);}
      else if(e.type==="slash"){ctx.strokeStyle=e.color;ctx.lineWidth=8*alpha;ctx.beginPath();ctx.arc(s.x,s.y,e.radius,-.7+e.angle,.7+e.angle);ctx.stroke();}
      else if(e.type==="nova"){const progress=1-alpha;ctx.strokeStyle=e.color;ctx.lineWidth=6*alpha;ctx.beginPath();ctx.arc(s.x,s.y,lerp(e.radius,e.maxRadius,progress),0,TAU);ctx.stroke();}
      else if(e.type==="beam"){const end=screen({x:e.x2,y:e.y2},cam);ctx.strokeStyle=e.color;ctx.lineWidth=5*alpha;ctx.beginPath();ctx.moveTo(s.x,s.y);ctx.lineTo(end.x,end.y);ctx.stroke();ctx.fillStyle="#fff";ctx.fillRect(end.x-2,end.y-2,4,4);}
      ctx.restore();
    }
  }

  function drawVignette() {
    const grad=ctx.createRadialGradient(W/2,H/2,H*.15,W/2,H/2,H*.75);grad.addColorStop(0,"#00000000");grad.addColorStop(1,"#040208b8");ctx.fillStyle=grad;ctx.fillRect(0,0,W,H);
    ctx.fillStyle="#ffffff05";for(let y=0;y<H;y+=4)ctx.fillRect(0,y,W,1);
  }

  function pollGamepad() {
    const pads = navigator.getGamepads?.(); const pad = pads && [...pads].find(Boolean); if (!pad) return;
    const dead = v => Math.abs(v) > .18 ? v : 0; input.x = dead(pad.axes[0] || 0); input.y = dead(pad.axes[1] || 0);
    input.attack = !!pad.buttons[0]?.pressed; input.dash = !!pad.buttons[1]?.pressed; input.ability = !!pad.buttons[2]?.pressed;
    if (pad.buttons[3]?.pressed && !game.gamepadCodex) { input.pressed.add("KeyC"); game.gamepadCodex = true; } else if (!pad.buttons[3]?.pressed) game.gamepadCodex = false;
  }

  function clearTransientInput() { input.pressed.clear(); input.attack = false; input.dash = false; input.ability = false; }

  function setupTouch() {
    const stick = $("touch-stick"); const knob = stick.querySelector("span"); let active = null;
    const move = event => { if (active === null) return; const touch=[...event.touches].find(t=>t.identifier===active); if(!touch)return; const r=stick.getBoundingClientRect();let dx=touch.clientX-(r.left+r.width/2),dy=touch.clientY-(r.top+r.height/2);const n=Math.hypot(dx,dy);if(n>42){dx=dx/n*42;dy=dy/n*42;}input.x=dx/42;input.y=dy/42;knob.style.transform=`translate(${dx}px,${dy}px)`;event.preventDefault(); };
    stick.addEventListener("touchstart",e=>{const t=e.changedTouches[0];active=t.identifier;move(e);},{passive:false});stick.addEventListener("touchmove",move,{passive:false});
    const end=e=>{if([...e.changedTouches].some(t=>t.identifier===active)){active=null;input.x=0;input.y=0;knob.style.transform="";}};stick.addEventListener("touchend",end);stick.addEventListener("touchcancel",end);
    document.querySelectorAll("[data-touch]").forEach(button=>{const key=button.dataset.touch;button.addEventListener("pointerdown",e=>{e.preventDefault();input[key]=true;});button.addEventListener("pointerup",()=>{input[key]=false;});button.addEventListener("pointercancel",()=>{input[key]=false;});});
  }

  function bindEvents() {
    window.addEventListener("keydown", e => {
      if (["Space","ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault();
      if (!input.keys.has(e.code)) input.pressed.add(e.code); input.keys.add(e.code);
      if (e.code === "Escape") { ["codex-screen","rank-screen"].forEach(id => { if (!$(id).hidden) closeDialog(id); }); }
    });
    window.addEventListener("keyup", e => input.keys.delete(e.code));
    window.addEventListener("blur", () => { input.keys.clear(); input.x = input.y = 0; });
    document.querySelectorAll(".mode-tab").forEach(button => button.addEventListener("click", () => {
      selectedMode = button.dataset.mode; document.querySelectorAll(".mode-tab").forEach(el => { const on=el===button;el.classList.toggle("selected",on);el.setAttribute("aria-selected",String(on)); });
    }));
    ui.startButton.addEventListener("click", () => beginRun());
    ui.continueButton.addEventListener("click", () => { const saved=meta.lastRun;if(saved)beginRun(saved.classId,saved.mode,saved); });
    $("retry-button").addEventListener("click", () => beginRun(selectedClass, game.mode));
    $("menu-button").addEventListener("click", showMenu);
    $("return-nero").addEventListener("click", () => {
      saveRun();
      if (history.length > 1) history.back(); else window.close();
    });
    document.querySelectorAll("[data-close]").forEach(button => button.addEventListener("click", () => closeDialog(button.dataset.close)));
    document.querySelectorAll("[data-command]").forEach(button => button.addEventListener("click", () => {
      const command=button.dataset.command;if(command==="codex")openCodex();else if(command==="ranks")openRanks();else if(command==="audio")toggleAudio();else if(command==="tonic")useTonic();
    }));
    document.addEventListener("visibilitychange", () => { if (document.hidden) saveRun(); });
    window.addEventListener("beforeunload", saveRun);
    setupTouch();
  }

  function showMenu() {
    game.state = "menu"; game.player = null; game.companion = null; ui.end.hidden = true; ui.start.hidden = false; ui.continueButton.hidden = !meta.lastRun; buildClassCards(); buildCompanionCards();
  }

  function loop(now) {
    const dt = Math.min(.05, (now - last) / 1000 || 0); last = now; update(dt); draw(); frameRequest = requestAnimationFrame(loop);
  }

  function init() {
    selectedCompanion = meta.preferredCompanion; buildClassCards(); buildCompanionCards(); bindEvents(); ui.continueButton.hidden = !meta.lastRun; ui.audioLabel.textContent = meta.audio ? "Audio" : "Muted";
    draw(); frameRequest = requestAnimationFrame(loop);
  }

  window.__VOIDBOUND__ = Object.freeze({ version: VERSION, BIOMES, CLASSES, COMPANIONS, UPGRADE_POOL, validSavedRun, validRank, formatTime, start: beginRun, getState: () => game, stop: () => cancelAnimationFrame(frameRequest) });
  init();
})();
