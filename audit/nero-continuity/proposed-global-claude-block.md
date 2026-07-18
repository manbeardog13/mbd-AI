---
id: audit.proposed-global-claude-block
title: "PROPOSED (NOT DEPLOYED): global Claude routing block"
layer: operational
type: plan
status: proposed
owner: shared
created: 2026-07-15
updated: 2026-07-18
---

# PROPOSED (NOT DEPLOYED): global Claude routing block

This is an **optional** routing aid. The project-level skill
`.claude/skills/nero-continuity/SKILL.md` already handles on-demand discovery, so
this block is not required. It is provided for Toni's approval only. **Claude has
not deployed it.** Deploying it edits the global `C:\Users\tonij\.claude\CLAUDE.md`,
which is a stop-and-ask boundary.

## Exact managed block

Insert verbatim into `C:\Users\tonij\.claude\CLAUDE.md` (anywhere after the Ruflo
section; adjacent to the `NERO_CLAUDE_GLOBAL_CAPSULE_V1` block reads well):

```
<!-- NERO_CLAUDE_CONTINUITY_ROUTING_V1:BEGIN -->
## Nero cross-host continuity routing

When Toni deliberately routes a memory across hosts — "remember across hosts",
"share/sync this across hosts", "create a handoff", asks what he told Nero to
remember across hosts / by a challenge id, or asks to correct/forget such a
record — use the project skill `nero-continuity` (repo `D:\mbd AI`). It runs the
local continuity CLI once and returns a source receipt. Do NOT use it for
greetings or ordinary chat, on every prompt, to auto-save conclusions, or to
scrape transcripts. A save does not contact Codex; source_host_claim is claimed,
not provider-attested. On NOT_FOUND/UNAVAILABLE/INTEGRITY_FAILED say you can't
verify it — never guess; on AMBIGUOUS ask Toni to resolve. Fail closed to
ordinary Claude behavior if the ledger is unavailable.
<!-- NERO_CLAUDE_CONTINUITY_ROUTING_V1:END -->
```

## Apply (Toni, or Claude only with Toni's explicit go-ahead)

1. Back up: copy `C:\Users\tonij\.claude\CLAUDE.md` to `CLAUDE.md.bak`.
2. Append the block above (including both marker comments).
3. Save. No restart needed.

## Rollback

Delete everything between `NERO_CLAUDE_CONTINUITY_ROUTING_V1:BEGIN` and
`...:END` (inclusive), or restore `CLAUDE.md.bak`. No database or other file
change is entailed.

## Why it is safe to omit

The skill's front-matter `description` already scopes it to the deliberate
routing phrases, so Claude will reach for it on those requests without a global
block. The block only makes the routing slightly more salient across arbitrary
folders. Recommendation: **leave undeployed** unless Toni wants the extra
salience.
