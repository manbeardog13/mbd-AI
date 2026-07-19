"""Controlled embedding pass (authorized by Toni: 'teach her, then embed').

Embeds every memory with Nero's configured embedder (nomic-embed-text) via the
SAME call her app uses (POST /api/embeddings {model, prompt}), so stored vectors
match query-time recall. Model stays loaded during the batch, then a final
keep_alive:0 request unloads it (job-scoped teardown, no lingering GPU use).

Writes a result log to data/embed_result.txt and prints it.
"""
from __future__ import annotations
import sqlite3, json, urllib.request, datetime, shutil, math

DB = r"D:\mbd AI\data\memory.db"
LOG = r"D:\mbd AI\data\embed_result.txt"
HOST = "http://127.0.0.1:11434"
MODEL = "nomic-embed-text"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg)

def embed(text, keep_alive=None):
    body = {"model": MODEL, "prompt": text}
    if keep_alive is not None:
        body["keep_alive"] = keep_alive
    req = urllib.request.Request(HOST + "/api/embeddings",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("embedding")

def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na and nb else 0.0

open(LOG, "w", encoding="utf-8").close()
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(DB, rf"D:\mbd AI\data\memory.db.bak_embed_{stamp}")

con = sqlite3.connect(DB, timeout=30)
cur = con.cursor()
rows = cur.execute("select id, content from memories order by id").fetchall()
log(f"embedding {len(rows)} memories with {MODEL} ...")
dim = None
done = 0
for mid, content in rows:
    try:
        emb = embed(content)
        if emb:
            dim = len(emb)
            cur.execute("update memories set embedding=? where id=?", (json.dumps(emb), mid))
            done += 1
    except Exception as e:
        log(f"  id {mid} FAILED: {e}")
con.commit()
log(f"embedded {done}/{len(rows)} (dim={dim})")

# ---- recall proof WITH embeddings (the queries that keyword-only got wrong) ----
stored = [(r[0], r[1], json.loads(r[2]) if r[2] else None)
          for r in cur.execute("select id, content, embedding from memories")]
log("\n--- semantic recall test ---")
for q in ["how do I render Manbeardog so she looks beautiful",
          "where do generated images get saved",
          "can Nero use the local qwen model as her mind in Claude host mode",
          "what are Nero's top priorities",
          "is Nero allowed to run dangerous actions without asking"]:
    qe = embed(q)
    best = max(stored, key=lambda t: cosine(qe, t[2]) if t[2] else -1)
    log(f"Q: {q}")
    log(f"  -> {best[1][:150]} ...")

# teardown: unload the embedder from VRAM
try:
    embed("unload", keep_alive="0")
    log("\nembedder unload requested (keep_alive=0)")
except Exception as e:
    log(f"unload note: {e}")
con.close()
log("DONE")
