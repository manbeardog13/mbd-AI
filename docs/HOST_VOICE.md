# Nero Host Voice status

## Current policy

Automatic Host Voice is disabled. Codex Host Mode is text-only until Codex
provides a supported hosted voice-output channel.

The hardcoded switches in `.codex/nero-host.json` disable voice, automatic
speech, desktop warmup, background workers, project-server startup, and local
fallback. `.codex/hooks.json` is empty, so normal Codex tasks cannot invoke the
legacy voice startup or stop workers.

## Resource boundary

Host Presence must never call the loopback `/api/speak` route, Kokoro, Windows
speaker playback, or another local synthesis path. Those paths consume local
CPU/RAM and conflict with the global hosted-only rule.

Existing voice code and historical ADRs may remain in the repository for
forensic history or a separately authorized future migration. Their presence on
disk does not make them active and they must not be wired into Codex task hooks.

## Future hosted voice

Voice may be reconsidered only when Codex exposes a documented hosted audio
output channel. A future design must:

- keep intelligence and synthesis on hosted resources;
- require no local model, server, daemon, warmup, or project hook;
- fail closed to text without a local fallback;
- preserve Nero's frozen voice identity only through a supported hosted path;
- add a new ADR, tests, and an updated resource audit before activation.

Until those conditions are met, a Nero reply in Codex is intentionally text
only.
