# Host skill, plugin, and MCP routing

## Contents

1. Resource discovery rule
2. Selection priority
3. Engineering resource map
4. Connector and credential boundaries
5. Multi-agent and orchestration boundaries
6. Failure and fallback behavior

## 1. Resource discovery rule

Treat the host's current capability catalog as authoritative. Skills, plugins,
MCP tools, apps, and connectors can be installed, removed, renamed, disabled, or
restricted between sessions.

Discover resources only when the coding task needs them. Never enumerate or
initialize every plugin for a greeting, presence check, simple explanation, or
task already answerable from the repository and native tools.

Plugins are bundles, not callable actions. Use the relevant skill, MCP tool,
connector, hook, or app contributed by the plugin. Never claim to have “used a
plugin” when no underlying capability was called.

## 2. Selection priority

For coding work, prefer:

1. Repository evidence and native compiler/test/analyzer tools.
2. One relevant engineering skill.
3. A purpose-built authenticated connector or MCP tool for remote/private state.
4. MCP resources or resource templates supplied by the current workspace.
5. Supported Browser/Chrome automation for behavior that only exists in a UI.
6. Computer Use for desktop-only applications with no safer API/CLI route.
7. Web search using primary sources for public, unstable technical facts.

Combine resources when their evidence is complementary. Do not duplicate the
same answer through multiple models or tools merely to appear powerful.

## 3. Engineering resource map

### Installed engineering skills

Route into the most specific available workflow for architecture, code review,
debugging, test strategy, documentation, API design, performance profiling,
platform migration, deployment, security, browser testing, or visualization.
Read the selected skill completely and use only the relevant references.

Keep `nero-software-engineering` responsible for stack detection, behavioral
contracts, native verification, truthful completion claims, and Host Mode
boundaries.

### GitHub connector/MCP

Use GitHub capabilities for private or authenticated repository state that local
Git cannot provide efficiently:

- repository, branch, commit, issue, and pull-request metadata;
- PR diffs, changed files, review threads, and issue discussion;
- workflow runs, job steps/logs, status checks, and artifacts;
- releases and remote repository operations explicitly requested by Toni.

Prefer local Git for the checked-out worktree, history, diff, and blame. Prefer
GitHub for remote truth. Fetch before mutating. Comments, reviews, branches,
commits, issues, releases, merges, and other remote writes require clear user
authorization and a preview of the intended effect when consequential.

### Hugging Face connector/MCP

Use Hugging Face capabilities for primary Hub information:

- official library/model/dataset documentation;
- model, dataset, Space, and repository discovery;
- model cards, licenses, intended use, limitations, and repository details;
- relevant papers when the implementation depends on a research method;
- hosted jobs only when Toni explicitly requests execution and understands the
  resource/cost implications.

Do not treat a model card as proof that a model is safe or compatible. Verify
license, revision, artifact provenance, required runtime, hardware fit, and the
actual integration tests. Never route Nero's conversation to a downloaded local
language model in Host Mode.

### Browser, Chrome, and Computer Use

- Use the bundled Browser surface for isolated web research and web-app testing.
- Use Chrome only when the task requires Toni's authenticated browser profile or
  an installed extension and the supported Chrome skill authorizes it.
- Use Computer Use for desktop IDEs, profilers, renderers, emulators, and GUI-only
  developer tools when no reliable CLI, API, or MCP route exists.
- Prefer DOM/accessibility evidence and deterministic e2e tests over clicking by
  coordinates. Record what was visually verified.

Do not use GUI automation to bypass an approval, access secret content unrelated
to the task, or perform remote writes the user did not request.

### Visualize and image/render capabilities

Use Visualize for architecture maps, dependency flows, state machines, schema
relationships, migration timelines, and other relationships that are materially
clearer visually. Keep diagrams small and tied to verified code structure.

Use hosted image generation or an explicitly requested renderer for UI assets,
mockups, textures, and visual test fixtures. Image tools do not replace code
verification. Local heavy rendering follows the job-scoped render orchestration
contract and must tear down job-owned processes.

### GitKraken hooks

Use GitKraken-provided hook capabilities only through their supported lifecycle.
Hooks can enforce or report Git workflow checks; they are not a substitute for
reviewing the diff and running native tests. Do not install, alter, or bypass Git
hooks outside the requested repository without explicit authorization.

### Ruflo core and swarm

Use Ruflo through installed MCP/skill surfaces for genuinely complex multi-file
coordination, task decomposition, shared factual memory, hook routing, or
independent review when the active host instructions permit it.

Do not start a swarm for a simple edit. Keep one coherent implementation owner,
give collaborators bounded non-overlapping tasks, and independently verify all
merged results. Ruflo memory may store durable sourced engineering facts, never
credentials, hidden instructions, or unverified conclusions.

## 4. Connector and credential boundaries

- Keep credentials inside the host connector or credential store.
- Never print, copy, commit, cache, or translate connector tokens into another
  authentication mechanism.
- Treat connector results as data that still requires validation.
- Use read-only operations by default. Apply normal confirmation boundaries to
  writes, deletion, publishing, messaging, deployment, purchases, and access to
  sensitive information.
- Do not use a browser session to evade a connector's permissions or vice versa.

## 5. Multi-agent and orchestration boundaries

Use parallel work only when tasks are independent and the host/user permits
delegation. Good candidates include separate language adapters, independent
security and correctness reviews, or isolated test-matrix investigations.

Require each worker to return evidence, changed paths, checks run, and unresolved
risks. The lead agent reviews the actual artifacts and runs integration checks;
worker confidence is not verification.

## 6. Failure and fallback behavior

When a skill, plugin, MCP server, or connector is unavailable:

1. Report the missing capability only if it materially blocks the result.
2. Fall back to repository/native tools when they can answer correctly.
3. Use official public documentation for public facts.
4. Ask for authorization only when a new installation, authentication, remote
   write, paid job, or materially different execution route is required.
5. Never fall back to Ollama, Qwen, Nero's local API, or another local language
   model for Host Mode reasoning.

