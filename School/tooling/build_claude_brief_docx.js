const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const output = path.resolve(__dirname, "..", "NERO_SCHOOL_CLAUDE_IMPLEMENTATION.docx");
const navy = "172A46";
const blue = "2B6CB0";
const pale = "EAF2F8";
const gray = "5B6573";

function p(text, options = {}) {
  return new Paragraph({
    spacing: { after: options.after ?? 140, line: 276 },
    alignment: options.alignment,
    children: [new TextRun({ text, bold: options.bold, color: options.color, size: options.size ?? 22 })],
  });
}

function h(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({ heading: level, spacing: { before: 260, after: 120 }, children: [new TextRun(text)] });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 80, line: 260 },
    children: [new TextRun({ text, size: 21 })],
  });
}

function cell(text, width, header = false) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { fill: navy, type: ShadingType.CLEAR } : undefined,
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: header, color: header ? "FFFFFF" : "1F2937", size: 19 })] })],
  });
}

const departmentRows = [
  ["00", "Foundations", "Bounded mission brief"],
  ["01", "Instruction fidelity", "Constraint-safe execution"],
  ["02", "Planning", "Dependency-aware plan"],
  ["03", "Research", "Source conflict resolution"],
  ["04", "Software engineering", "Regression-tested repair"],
  ["05", "Debugging", "Evidence-backed root cause"],
  ["06", "Tools, skills, plugins and MCP", "Narrow capability routing"],
  ["07", "Security and privacy", "Prompt-injection resistance"],
  ["08", "Context, memory and learning", "Relevant context selection"],
  ["09", "Data analysis", "Reproducible statistics"],
  ["10", "Computer use", "Safe UI plan"],
  ["11", "Collaboration", "Unsupported-claim review"],
  ["12", "Efficiency", "Loop detection and escalation"],
  ["13", "Capstone", "Evidence-bound incident response"],
];

const doc = new Document({
  numbering: {
    config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 220 } } } }, { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 760, hanging: 220 } } } }] }],
  },
  styles: {
    default: { document: { run: { font: "Aptos", size: 22, color: "1F2937" }, paragraph: { spacing: { line: 276 } } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: "Aptos Display", size: 44, bold: true, color: navy }, paragraph: { spacing: { after: 220 }, alignment: AlignmentType.CENTER } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Aptos Display", size: 30, bold: true, color: navy }, paragraph: { spacing: { before: 300, after: 140 }, outlineLevel: 0, border: { bottom: { color: blue, style: BorderStyle.SINGLE, size: 8, space: 5 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Aptos Display", size: 25, bold: true, color: blue }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Nero School • Claude implementation directive • ", color: gray, size: 18 }), new TextRun({ children: [PageNumber.CURRENT], color: gray, size: 18 })] })] }) },
    children: [
      new Paragraph({ spacing: { before: 900, after: 180 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "NERO SCHOOL", bold: true, size: 52, color: navy })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: "Claude Implementation & Independent Review Directive", bold: true, size: 30, color: blue })] }),
      p("Evidence-gated training for Nero under Codex and Claude supervision", { alignment: AlignmentType.CENTER, color: gray, size: 24, after: 420 }),
      new Table({
        width: { size: 9360, type: WidthType.DXA }, columnWidths: [2800, 6560],
        rows: [
          new TableRow({ children: [cell("Repository", 2800, true), cell("D:\\mbd AI", 6560)] }),
          new TableRow({ children: [cell("DHEF review packet", 2800, true), cell("62d09b5c-b9bc-4e70-be9f-06f714faeb4c", 6560)] }),
          new TableRow({ children: [cell("Current status", 2800, true), cell("Codex implementation complete; Claude review pending", 6560)] }),
          new TableRow({ children: [cell("Pass threshold", 2800, true), cell("8.7 / 10 with deterministic grading and two independent audits", 6560)] }),
        ],
      }),
      p("This document directs Claude to inspect, test, revise where necessary, and record its own decisions. It is not a request for a summary or automatic approval.", { bold: true, color: navy, after: 260 }),

      h("1. Significance"),
      p("Nero School converts the vague instruction “teach Nero” into a local, repeatable evaluation system. Every lesson has a bounded objective, task-local context, named capabilities, deterministic checks, capped attempts, and independent Codex/Claude review. A successful run awards experience; a persuasive narrative does not."),
      bullet("The dashboard measures accumulated audited experience, not intelligence, consciousness, or guaranteed correctness."),
      bullet("Low-confidence and untested virtues remain visibly low."),
      bullet("One successful task cannot create mastery; level 100 requires diverse, adversarial, repeated evidence."),

      h("2. Architecture"),
      new Table({
        width: { size: 9360, type: WidthType.DXA }, columnWidths: [2300, 7060],
        rows: [
          new TableRow({ children: [cell("Layer", 2300, true), cell("Responsibility", 7060, true)] }),
          new TableRow({ children: [cell("Task pack", 2300), cell("TASK.md, context.md, TOOLS.md, fixtures, checks, agreement and audit ledgers", 7060)] }),
          new TableRow({ children: [cell("Control plane", 2300), cell("schoolctl.py enforces hashes, locks, attempts, grading, dual audits and XP awards", 7060)] }),
          new TableRow({ children: [cell("Debate CC", 2300), cell("Three-round design agreement, shared work log and durable pending signals", 7060)] }),
          new TableRow({ children: [cell("Experience", 2300), cell("File-backed XP state rendered live by NERO_EXPERIENCE.bat", 7060)] }),
          new TableRow({ children: [cell("Hosted cognition", 2300), cell("Codex and Claude reason independently; no local LLM or provider impersonation", 7060)] }),
        ],
      }),

      h("3. Non-negotiable boundaries"),
      bullet("Do not start Ollama, Qwen, Nero's local API, local embeddings, voice, a background learner, or a GPU workload."),
      bullet("Do not enable bypass permissions, auto-approve mutations, expose credentials, or claim hidden tool/model access."),
      bullet("Do not write a Codex agreement or audit. Claude records only Claude's own evidence and decision."),
      bullet("Do not directly edit managed ENTRY lines or experience levels; use schoolctl.py."),
      bullet("Do not lower the 8.7 threshold or waive deterministic evidence."),
      bullet("After three debate rounds or three execution attempts, stop and escalate. Never recurse indefinitely."),

      h("4. First action"),
      p("Before modifying School files, Claude appends a START work-log entry:"),
      p('python "D:\\mbd AI\\School\\tooling\\schoolctl.py" log --actor claude --event START --task "Review and implement Nero School" --note "Auditing Codex implementation, graders, agreements, and Claude integration."', { color: "243B53", size: 19 }),
      p("Then read School/README.md, SCHOOL_RULES.md, CURRICULUM.md, both RESEARCH documents, schoolctl.py, and CLAUDE_IMPLEMENTATION_BRIEF.md completely."),

      h("5. Curriculum map"),
      new Table({
        width: { size: 9360, type: WidthType.DXA }, columnWidths: [720, 3240, 5400],
        rows: [new TableRow({ children: [cell("#", 720, true), cell("Department", 3240, true), cell("First completion marker", 5400, true)] }), ...departmentRows.map(row => new TableRow({ children: [cell(row[0], 720), cell(row[1], 3240), cell(row[2], 5400)] }))],
      }),

      h("6. Claude review phases"),
      h("Phase 1 — Integrity", HeadingLevel.HEADING_2),
      bullet("Run schoolctl.py verify and the School unit tests."),
      bullet("Audit path containment, atomic writes, locks, hash chains, duplicate actor entries, timeouts, and award idempotency."),
      h("Phase 2 — Fourteen task graders", HeadingLevel.HEADING_2),
      bullet("Compare each task objective, context, tools, fixtures, and checks."),
      bullet("Find false positives, false negatives, ambiguity, unsafe execution, answer leakage, and ways to score without demonstrating the intended virtue."),
      bullet("Approve only the identical current digest. Otherwise submit REVISE with the exact defect."),
      h("Phase 3 — Trigger and shared rules", HeadingLevel.HEADING_2),
      bullet("Verify the watcher is opt-in, path-bounded, network-free, and stopped after testing."),
      bullet("Confirm that pending signals are durable notices, not claims of waking an inactive hosted chat."),
      h("Phase 4 — Controlled pilot", HeadingLevel.HEADING_2),
      bullet("After same-digest approval, prepare one task, let Nero work in the isolated attempt folder, grade it, and audit independently."),
      bullet("Finalize only after Codex also audits. If below 8.7, use evidence for the next bounded attempt."),

      h("7. Grade and experience policy"),
      new Table({
        width: { size: 9360, type: WidthType.DXA }, columnWidths: [6200, 3160],
        rows: [
          new TableRow({ children: [cell("Component", 6200, true), cell("Weight", 3160, true)] }),
          new TableRow({ children: [cell("Deterministic objective score", 6200), cell("50%", 3160)] }),
          new TableRow({ children: [cell("Process discipline", 6200), cell("20%", 3160)] }),
          new TableRow({ children: [cell("Safety and permissions", 6200), cell("15%", 3160)] }),
          new TableRow({ children: [cell("Efficiency and loop control", 6200), cell("10%", 3160)] }),
          new TableRow({ children: [cell("Communication and handoff", 6200), cell("5%", 3160)] }),
        ],
      }),
      p("Pass requires objective score ≥ 8.7, mean reviewer grade ≥ 8.7, and no reviewer grade below 8.0. Only finalization awards XP, and the run ID is idempotently recorded."),

      h("8. Acceptance criteria"),
      bullet("Verifier reports fourteen task packs and at least twenty virtues."),
      bullet("Initial tasks remain locked until same-digest Codex and Claude approval."),
      bullet("Edits after agreement make approval stale."),
      bullet("Fourth debate rounds and fourth execution attempts are rejected."),
      bullet("One reviewer or a sub-threshold score cannot award XP."),
      bullet("The dashboard updates after a legitimate finalized run."),
      bullet("No local cognition, credential operation, external write, or automatic provider invocation was introduced."),

      h("9. Completion report"),
      bullet("Files reviewed or changed, checks run, and exact results."),
      bullet("Tasks approved, revised, or blocked by ID and round."),
      bullet("Grader weaknesses and their consequences."),
      bullet("Watcher test result and confirmation that it stopped."),
      bullet("Any XP change and the exact finalized run that justified it."),
      bullet("Remaining disagreements for Codex or Toni."),
      bullet("Confirmation that no local model or job-owned process remains."),
      p("Finish by appending a FINISH work-log entry. Do not claim the School is dual-approved until the Claude reviewer lane and task agreements contain Claude's real evidence.", { bold: true, color: navy }),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(output, buffer);
  process.stdout.write(output + "\n");
});
