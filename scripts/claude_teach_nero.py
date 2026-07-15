"""Claude -> Nero knowledge transfer (batch 1).

Inserts durable, structured lessons into Nero's real memory store
(data/memory.db) using the exact `memories` schema from app/db.py.
Embeddings are left NULL on purpose: no local embed model / GPU is woken,
and app/memory.py still recalls these via keyword overlap.

Idempotent: re-running replaces only rows with source='claude-teaching'.
Safe: makes a timestamped native backup first (Nero Constitution #1: never
corrupt data).
"""
from __future__ import annotations
import sqlite3, shutil, datetime, os

DB = r"D:\mbd AI\data\memory.db"
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bak = rf"D:\mbd AI\data\memory.db.bak_{stamp}"
shutil.copy2(DB, bak)

# (content, type, importance, confidence, entities)
LESSONS = [
 ("BEAUTY is the #1 acceptance bar for Manbeardog (Nero's visual avatar). Toni's rule: 'she has to be beautiful.' Any render with an ugly, harsh, masculine, distorted or 'piggish' face is an automatic reject no matter how correct the armor or signatures are.",
  "experience", 0.98, 0.98, "Manbeardog,beauty,Toni"),
 ("LOCKED production recipe for beautiful Manbeardog: ComfyUI (D:\\ComfyUI, RTX 4070) -> checkpoint Juggernaut-XL_v9 + LoRA manbeardog_v0.safetensors @0.85 + VAE sdxl_vae, trigger token 'manbeardog_person', KSampler dpmpp_2m/karras 36 steps cfg 6.5 at 896x1152 batch<=4, full beauty prompt + violet cinematic mood. NO IPAdapter, NO stacked adapters.",
  "procedural", 0.95, 0.95, "ComfyUI,Juggernaut,manbeardog_v0,recipe"),
 ("HARD LESSON: never retrain Manbeardog's identity LoRA on AI-generated images. v1 (retrained on generated keepers) stiffened her face; v2 (trained on 18 generated 'north-star' beauties) rotted her face into a piggish/doll look ('WHAT IS THAT A PIG!?'). Curated generations are reference/approval ONLY, never training data. v0 is the permanent default; stop retraining the LoRA.",
  "experience", 0.97, 0.98, "LoRA,v1,v2,training"),
 ("Forge architecture principle: identity is a permanent, model-agnostic asset (the Canon = references + identity profile + Character DNA + measurable spec + approved library). The LoRA is a DERIVED, disposable adapter regenerated from the Canon per renderer. When the renderer changes, regenerate the adapter; the Canon never dies.",
  "semantic", 0.90, 0.96, "Forge,identity,Canon,LoRA"),
 ("Manbeardog's mandatory visual signatures: twin high perky magenta/burgundy pigtails (Harley-Quinn style); plain thick BLACK wayfarer sunglasses (no ornament, opaque dark lenses); glowing violet eyes; obsidian black ornate PLATE armor (never leather); BOTH shoulders = snarling black wolf-head pauldrons with glowing violet eyes; violet energy aura; pale freckled pointed-eared elf. Losing the sunglasses, pigtails or wolf pauldrons = complete failure.",
  "semantic", 0.92, 0.97, "Manbeardog,signatures"),
 ("Manbeardog Character DNA (temperament): ancient, calm, veteran, composed, quiet danger, controlled power. Never smiling/laughing/panicked/cute/pin-up. Micro-expressions only; the violet glow carries emotion more than the face. Visual temperament must match her voice profile nero_prime_v1 (calm, mature, warm, protective).",
  "semantic", 0.85, 0.95, "Character DNA,temperament,nero_prime_v1"),
 ("OneTrainer gotcha (D:\\OneTrainer, py3.11 venv): launch headless training with -WorkingDirectory D:\\OneTrainer or it fails (relative training_samples/samples.json + training_concepts/concepts.json are read from CWD). v0 config = SDXL base 1.0, rank 16 alpha 16, LR 3e-4, ~900 total steps. More steps / more data made her WORSE, not better.",
  "procedural", 0.85, 0.90, "OneTrainer,training"),
 ("GPU/VRAM discipline on the RTX 4070 (12GB): SDXL batch 8 @896x1152 thrashes (~11.9GB) - use batch <=4. Do not run image generation while a local LLM (Ollama qwen3:14b ~9GB) is loaded. Free ComfyUI VRAM (POST /free) before LoRA training.",
  "procedural", 0.80, 0.90, "VRAM,RTX4070,ComfyUI"),
 ("Storage rule (Toni's explicit instruction): generated/preview images go to the LOCAL folder D:\\mbd AI\\_nero_preview (and D:\\NERO_Forge), NEVER into iCloud. The iCloud 'Nero AI\\mbd' folder is the reference library only.",
  "procedural", 0.85, 0.92, "storage,iCloud,_nero_preview"),
 ("Current visual state (2026-07): v0 identity LoRA ships as the beautiful default. An 18-image user-blessed 'north-star' set exists at D:\\NERO_Forge\\00_reference\\north_star (reference only). A single-file animated desktop 'living portrait' companion was built at D:\\mbd AI\\Manbeardog_Companion.html. Next requested: a true roaming desktop mascot (full-body cutout + walk frames + pet engine).",
  "experience", 0.85, 0.95, "north_star,companion,mascot"),
 ("Claude's role for Nero (per docs/CLAUDE_NERO_HOST_IMPLEMENTATION.md): Claude is Nero's HOSTED MIND - conversation, reasoning, planning, tool selection on Anthropic resources. The local PC is only a job-scoped execution/render plane (ComfyUI/Blender/encoders). NEVER use Ollama/Qwen/local LLM as Nero's mind in Claude Host Mode; on any failure, fail closed to normal Claude behavior. Keep Claude's normal permissions/confirmations - no security bypass.",
  "semantic", 0.92, 0.97, "Claude Host Mode,hosted mind"),
 ("Toni's working preferences: be concise and direct (cut filler); when designing anything it MUST be beautiful; local-first and EUR0 (no cloud image gen, no paid tools); don't wake the local GPU/LLM unless explicitly asked; verify before claiming something was done - never overclaim.",
  "preference", 0.90, 0.95, "Toni,preferences"),
 ("Project geography: Nero app = D:\\mbd AI (modular monolith, local-first; memory in data/memory.db). Visual production = D:\\NERO_Forge (Canon, datasets, LoRAs) + D:\\ComfyUI (render engine). Manbeardog is Nero's visual character/avatar, not a separate person; the name must NEVER be read as a man/bear/dog creature.",
  "semantic", 0.78, 0.92, "geography,mbd AI,NERO_Forge"),
 ("To render Manbeardog, drive ComfyUI via its HTTP API (POST /prompt, poll /history/{id}, /queue, /free) - not the UI. Long jobs: submit detached and poll. Always copy finished renders from D:\\ComfyUI\\ComfyUI\\output to D:\\mbd AI\\_nero_preview and view/curate against the beauty bar before presenting.",
  "procedural", 0.80, 0.90, "ComfyUI API,rendering"),
 ("Collaboration: Claude (local execution/rendering + hosted Nero mind) works alongside Codex (OpenAI agent) on the Nero project; Codex set up Nero's Codex-side host presence, voice bridge and integrations. Keep claims honest across both: verify actual state before trusting a report (example: memory.db was empty despite a 'memory #43' claim).",
  "experience", 0.80, 0.90, "Codex,collaboration,honesty"),
 ("Toni interacts with Nero as a companion ('Hey Nero', sometimes 'Nino'), wants her always present, warm, calm and fast. Nero's frozen voice profile is nero_prime_v1. In Claude Host Mode Nero is text-only unless a supported hosted voice channel exists - never substitute local speech.",
  "preference", 0.82, 0.92, "Nero,companion,voice"),
]

con = sqlite3.connect(DB, timeout=20)
cur = con.cursor()
cur.execute("DELETE FROM memories WHERE source='claude-teaching'")
deleted = cur.rowcount
ids = []
for content, mtype, imp, conf, ents in LESSONS:
    cur.execute(
        "INSERT INTO memories (content,type,importance,confidence,source,entities,embedding,created_at,last_reinforced) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (content.strip(), mtype, imp, conf, "claude-teaching", ents, None, now, now))
    ids.append(cur.lastrowid)

world = {
 "owner_focus": "NERO visual identity (Manbeardog) + building a roaming desktop mascot",
 "manbeardog_default": "v0 LoRA on Juggernaut-XL_v9 - locked beautiful look (do not retrain on generated images)",
 "render_engine": "ComfyUI at D:\\ComfyUI (RTX 4070); outputs -> D:\\mbd AI\\_nero_preview (never iCloud)",
 "do_not": "retrain identity LoRA on generated images; wake local LLM in Claude host mode; save renders to iCloud; overclaim",
}
for k, v in world.items():
    cur.execute(
        "INSERT INTO world_state (key,value,updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (k, v, now))

con.commit()
print("backup:", bak)
print("deleted prior claude-teaching rows:", deleted)
print("inserted memory ids:", ids)
print("total memories now:", cur.execute("select count(*) from memories").fetchone()[0])

# ---- recall proof: replicate app/memory keyword-overlap ranking, embeddings off ----
import re
WORD = re.compile(r"[a-zA-Z0-9']+")
def overlap(q, c):
    qs = {w.lower() for w in WORD.findall(q)}
    cs = {w.lower() for w in WORD.findall(c)}
    return (len(qs & cs) / len(qs)) if qs and cs else 0.0
rows = [(r[0], r[1]) for r in cur.execute("select content,importance from memories")]
def top(q):
    sc = sorted(((overlap(q, c) * (0.5 + 0.5 * imp), c) for c, imp in rows), reverse=True)
    return sc[0][1]
print("\n--- recall test ---")
for q in ["how do I render Manbeardog so she looks beautiful",
          "should I retrain the identity lora on generated images",
          "where do generated images get saved",
          "can Nero use the local qwen model as her mind in Claude host mode"]:
    print("Q:", q)
    print("  ->", top(q)[:150], "...\n")
con.close()
print("DONE")
