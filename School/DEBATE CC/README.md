# DEBATE CC

`DEBATE CC.txt` holds the compact Codex/Claude debate protocol. `LOG.txt` is the
append-only work ledger. Saving either file can be observed by the opt-in watcher
started with `START_DEBATE_WATCHER.bat`.

The watcher creates `.signals/codex.pending.json` and
`.signals/claude.pending.json` and displays a local notification. It does not and
cannot directly wake inactive hosted chats. Each host checks its pending signal
before substantive School work and logs what it starts and finishes.

