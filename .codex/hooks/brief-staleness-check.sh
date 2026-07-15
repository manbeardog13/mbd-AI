#!/bin/bash
# Stop hook — standing rule: keep docs/PROJECT_BRIEF.md current.
#
# When Claude stops with nothing left to do, if the project's source has
# changed since PROJECT_BRIEF.md was last updated, remind Claude (via exit 2 →
# stderr feedback) to refresh the brief, commit+push it, and say so in chat.
# On turns that changed nothing, it exits 0 and stays silent.

input=$(cat)

# Recursion guard: don't re-fire on the stop caused by our own feedback.
if command -v jq >/dev/null 2>&1; then
  active=$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)
else
  active=$(printf '%s' "$input" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true' && echo true || echo false)
fi
[ "$active" = "true" ] && exit 0

# Only inside a git repo; operate from the repo root.
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

BRIEF="docs/PROJECT_BRIEF.md"
[ -f "$BRIEF" ] || exit 0

# Last commit time of the brief vs. the latest commit touching meaningful source.
brief_t=$(git log -1 --format=%ct -- "$BRIEF" 2>/dev/null); brief_t=${brief_t:-0}
src_t=$(git log -1 --format=%ct -- \
  app verify tests bootstrap.py run.py config.example.yaml \
  docs/VISION.md docs/DIRECTIVE.md 2>/dev/null); src_t=${src_t:-0}

if [ "$src_t" -gt "$brief_t" ]; then
  echo "Standing rule (keep the brief current): the project's source has changed since docs/PROJECT_BRIEF.md was last updated. Update docs/PROJECT_BRIEF.md to reflect the current state, commit and push it (merge to main), then tell Toni in chat that you've updated the brief." >&2
  exit 2
fi

exit 0
