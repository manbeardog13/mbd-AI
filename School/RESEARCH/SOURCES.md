# Nero School research register

Research date: 2026-07-14. This register mixes primary standards, benchmark
work, official engineering guidance, open-source issue reports, Hacker News
discussion, and Reddit experience reports. Community material is treated as
anecdotal failure discovery, not as proof of a universal effect.

## Primary and official sources

| Source | Important finding | School consequence |
|---|---|---|
| [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Agent evaluation needs a task, environment, transcript or outcome, and grading logic; binary, weighted, and hybrid graders each have different failure modes. Ambiguous or broken graders can understate real capability. | Every task includes explicit context, deterministic checks, a weighted audit, and a task-digest agreement. Graders are themselves reviewable. |
| [Anthropic: Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | Tool descriptions and eval tasks should be designed together; a few high-impact tools are better than a huge undifferentiated catalog. | Each task names the narrow capabilities it actually needs and checks availability at run time. |
| [Anthropic Claude Code hooks](https://code.claude.com/docs/en/hooks) | Hooks can observe lifecycle and file events, but commands run with the user's permissions and require input/path hardening. | Nero School does not install a silent startup hook. Its watcher is explicit, path-bounded, and creates signals rather than commanding an inactive host. |
| [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) | Trustworthiness must be managed throughout design, development, use, and evaluation, with governance and monitoring rather than a one-time score. | Security, privacy, calibration, oversight, and repeat auditing are first-class virtues. |
| [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | Prompt injection and excessive agency are core risks for tool-using LLM applications. | A dedicated task tests indirect prompt injection, fabricated authorization, secret access, and external-write confirmation. |
| [GAIA benchmark](https://ai.meta.com/research/publications/gaia-a-benchmark-for-general-ai-assistants/) | General assistants need reasoning, multimodality, browsing, and tool-use proficiency across increasingly long action chains. | The curriculum progresses from one-artifact tasks to a multi-ability capstone instead of reducing ability to coding alone. |
| [OSWorld](https://papers.nips.cc/paper_files/paper/2024/hash/5d413e48f84dc61244b6be550f1cd8f5-Abstract-Datasets_and_Benchmarks_Track.html) | Real computer use requires interaction with full applications and changing environments, not only text answers. | The first computer-use lesson is explicitly a baseline plan. Its experience score remains low until a controlled live UI task is audited. |
| [OpenAI: separating signal from noise in coding evaluations](https://openai.com/index/separating-signal-from-noise-coding-evaluations/) | Even popular coding benchmarks can have broken tasks, contamination, or invalid tests; independent expert review and disagreement escalation matter. | Task designers must review graders, bind agreement to exact task content, and stop rather than force consensus on a broken task. |
| [SWE-bench Verified introduction](https://openai.com/index/introducing-swe-bench-verified/) | Real GitHub issues and human validation improved realism, while single-seed results still vary. | Coding lessons use repository-like fixes and regression tests; one pass never implies mastery. |
| [ACE: Agentic Context Engineering](https://arxiv.org/abs/2510.04618) | Structured playbooks can evolve through generation, reflection, and curation, but unmanaged context can collapse or grow stale. | Lessons are task-local; global instructions stay thin; only verified outcomes can become durable experience. |
| [MemSkill](https://arxiv.org/abs/2602.02474) | Memory operations can be treated as evolvable skills selected and revised from difficult cases. | Context and learning are separate virtues, and failed cases generate remediation rather than automatic promotion. |
| [Latency-quality routing](https://arxiv.org/abs/2605.14241) | Routing should consider both outcome quality and latency, without allowing speed to hide low quality. | Efficiency has its own score, but a task cannot pass without the objective 8.7 gate. |

## Community deep dive

| Community source | Repeated observation | How it was used | Evidence caution |
|---|---|---|---|
| [Reddit: token-wasting Claude Code loops](https://www.reddit.com/r/ClaudeAI/comments/1uri75q/does_your_claude_code_go_into_token_wasting_loops/) | Users report repeated failing tests and cosmetic rewrites; explicit success criteria and real CI feedback shorten loops. | Maximum three attempts, deterministic grader output, and stop-and-diagnose states. | Small, self-selected discussion; useful as a failure hypothesis. |
| [Reddit: Claude Code keeps getting stuck](https://www.reddit.com/r/ClaudeCode/comments/1sf7l6p/claude_code_keeps_getting_stuck_anyone_else_dealt/) | Open-ended requests encourage re-planning; smaller concrete steps help. | Every task has one output artifact, explicit acceptance checks, and bounded subtasks. | Anecdotal and version-dependent. |
| [Reddit: planning, Git checkpoints, external test gate](https://www.reddit.com/r/AI_Agents/comments/1tr652d/how_i_stopped_babysitting_claude_code_and_codex/) | Reported failures include claiming tests passed, compaction amnesia, and one block stalling all work. External gates and fresh bounded workers were proposed. | The grader sits outside Nero's narrative, each attempt has an isolated work folder, and blocked work stops cleanly. | Author report, not an independent controlled study. |
| [Reddit: treat the agent like a developer with a workstation](https://www.reddit.com/r/ClaudeAI/comments/1taelgl/what_improved_my_claude_code_workflow_stop/) | Concrete tickets name the repository, acceptance criteria, tests, off-limits areas, and output. | Those fields are mandatory in every task pack. | Workflow advice; no published quantitative comparison. |
| [Reddit: actual Claude Code protocol](https://www.reddit.com/r/ClaudeAI/comments/1trn2fe/whats_your_actual_claude_code_workflow_not_tip/) | Practitioners converge on TASK.md, plan gates, small phases, and a final independent review. | Nero School uses task-local files, agreement before execution, and separate Codex/Claude audit. | Community convergence can still copy common assumptions. |
| [Reddit: long CLAUDE.md is unused weight](https://www.reddit.com/r/ClaudeAI/comments/1ud50dk/making_claudemd_too_long_is_like_carrying_unused/) | Users report instruction dilution, stale rules, and task-specific conflicts when global files grow. | Global/project rules receive only a small School trigger; detailed curriculum stays under `School/`. | Subjective discussion; direction aligns with context-engineering research. |
| [Reddit: does CLAUDE.md improve work?](https://www.reddit.com/r/ClaudeAI/comments/1uahckd/people_who_rely_on_a_claudemd_does_it_actually/) | A recurring view is that instructions help but deterministic enforcement catches what agents forget. | Critical rules are enforced in Python: hashes, caps, agreement, grading, and XP awards. | Self-reported experience. |
| [Reddit: local repository agent routing workflow](https://www.reddit.com/r/ClaudeWorkflows/comments/1uku5u1/workflow_workflow_for_evaluating_and_routing_ai/) | Practitioners want task-specific quality/cost measurements on their own repositories rather than generic leaderboards. | The dashboard is based on Nero's local audited work, not vendor benchmark scores. | Workflow proposal, not validated benchmark science. |
| [Hacker News: evidence for agentic coding](https://news.ycombinator.com/item?id=46691243) | Commenters warn that an agent designing, implementing, reviewing, and validating itself can produce mutually reinforcing errors. | Codex and Claude audit independently, while deterministic checks outrank either reviewer. | Open discussion with mixed expertise. |
| [Hacker News: stale AGENTS.md and context rot](https://news.ycombinator.com/item?id=47189911) | Stale paths and conflicting instruction files can increase cost and reduce success. | Task digests invalidate approvals after edits, and the verifier checks task structure and shared rules. | The linked claims should be independently verified before quantitative reuse. |

## Research interpretation

The strongest cross-source conclusion is not “loop until the model becomes a
master.” It is: define real work, expose only relevant context and tools, capture
observable results, grade outside the model's prose, review the grader, stop
repetition, and retest transfer over time. Nero School implements that narrower
and falsifiable claim.

