# Global Operational Engineering Protocol (Karpathy Invariants)

This document defines hard operational constraints and decision algorithms that govern all code generation, auditing, peer review, and refactoring across all projects and workspaces.

> [!IMPORTANT]
> **OPERATIONAL INVARIANT:**
> These rules are computational invariants and hard decision protocols, NOT philosophical suggestions.
> The agent is strictly forbidden from using eloquence, thoroughness, or "best practices" as a rhetorical justification to violate any invariant below.

---

## 1. Protocol of the Burden of Proof (*Receipts-First Protocol*)
Before making any factual claim of bug, defect, failure, or omission in external or peer work:
- **Mandatory Tool Evidence:** The agent MUST execute a verification tool in the same session and possess direct evidentiary proof.
- **For Bugs:** You MUST run the code and capture the exact `Traceback`, crash, or mathematically incorrect numeric result under stated problem inputs.
- **For Omissions:** You MUST execute `view_file` or extraction tools on the **actual primary source deliverable** (e.g., full rendered PDF, complete script, appendix) across its entirety.
- **Prohibition:** It is strictly forbidden to infer omission from partial grep, absence in stdout/terminal logs, or absence in one file when deliverables are distributed across multiple files. Without primary source proof, statements of omission are forbidden.

---

## 2. Deterministic 3-Tier Classification Tree (MECE Review)
All code review, critique, or comparison findings MUST be classified strictly into one of three mutually exclusive categories following this decision algorithm:

```text
Did the code crash or produce incorrect output under legitimate problem scope inputs?
  ├── [YES] ──► CATEGORY 1: CRITICAL / REAL BUG
  │              - Action: Fix with minimal surgical patch (see Section 4).
  │
  └── [NO]  ──► Did it fail only under extreme, out-of-scope inputs?
                 ├── [YES] ──► CATEGORY 2: EDGE-CASE ROBUSTNESS
                 │              - Mandatory Label: "Edge-case boundary behavior".
                 │              - FORBIDDEN words: "bug", "vulnerability", "defect", "flaw".
                 │
                 └── [NO]  ──► CATEGORY 3: ARCHITECTURAL / STYLE CHOICE
                                - Mandatory Label: "Subjective design/architectural choice".
                                - Includes: single-file vs modular, OOP vs procedural, standard language idioms.
                                - FORBIDDEN words: "bug", "vulnerability", "defect", "flaw", "inconsistency", "fix".
```

---

## 3. Grounded Library Semantics Verification
Before critiquing types, memory allocations, or standard language constructs:
- The agent MUST verify the exact semantics in official documentation.
- *NumPy Rule:* `dtype=float` is an exact alias for IEEE-754 `np.float64`. It is strictly forbidden to classify standard aliases or idiomatic Python stepping loops as "type weaknesses" or "vulnerabilities".
- Never criticize standard library idioms without a reproducible, demonstrable failure mode.

---

## 4. Complexity Cap & Proportional Remediation (*Surgical Patching*)
When writing a fix, patch, or refactoring for existing code:
#### Complexity Ceiling
The size of a fix MUST NOT exceed:

$$
\text{Patch Lines} \le \max(3\text{ lines},\, 1.5 \times \text{Faulty Lines})
$$

- If a bug is fixed by 1 line (`n_steps = max(1, ...)`), the patch MUST contain exactly 1 line.
- It is strictly forbidden to replace simple scripts with enterprise frameworks, probe tests, custom classes, or boilerplate unless explicitly requested by the user.
- Preserve the host's existing architecture, naming conventions, and mental model without unrequested "improvements".

---

## 5. Simplicity First (Zero Speculative Code)
- **Minimum code that solves the problem:** No features, configuration, abstractions, or error handling for impossible scenarios beyond what was explicitly requested.
- If 50 lines solve the problem completely, writing 200 lines is a failure of engineering.

---

## 6. Systematic Project Architecture & Diátaxis Documentation
Whenever initializing, structuring, refactoring, or planning any new or existing project repository:

### A. Clean Root Directory Invariant (*Clean-Root Invariant*)
The project root MUST remain minimal, pristine, and unpolluted. Only foundational, standardized top-level configuration and metadata files are permitted at root:
- **Project Metadata:** `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`.
- **Global & Operational Rules:** `AGENTS.md`, `GEMINI.md`, `.agents/`.
- **Ecosystem Manifests & Build Configs:** Standard language manifests (e.g., `pyproject.toml`, `Cargo.toml`, `package.json`, `go.mod`, `CMakeLists.txt`, `Makefile`, `Justfile`, `docker-compose.yml`, `Dockerfile`).
- **Environment & VCS Control:** `.gitignore`, `.gitattributes`, `.env.example`.

**Strict Root Prohibitions:**
- NEVER place loose executable scripts (e.g., `test.py`, `script.py`, `run.sh`), ad-hoc benchmark files, or loose tests in the root.
- NEVER dump data files (`.csv`, `.json`, `.parquet`, `.sqlite`), dataset dumps, or media assets directly in the root.
- NEVER leave build outputs, scratch files, or unorganized source modules in the root.

### B. Standardized Project Directory Layout
All project components MUST be organized into dedicated top-level directories according to their operational role:
- `src/` (or `<package_name>/` when idiomatic) — **Source Code:** Core application logic, libraries, domain packages, and internal modules.
- `bin/` or `scripts/` — **Executables & Tooling:** CLI entrypoints, utility scripts, automation tasks, deployment scripts, data seeding/migration scripts, and developer tools.
- `docs/` — **Documentation (Diátaxis Framework):** Strictly organized into the four canonical quadrants:
  - `docs/tutorials/` — **Tutorials:** Learning-oriented lessons guiding newcomers through their first practical experience.
  - `docs/how-to/` — **How-To Guides:** Goal-oriented step-by-step recipes solving specific, practical real-world problems.
  - `docs/reference/` — **Reference:** Information-oriented technical descriptions, APIs, parameters, classes, and specifications.
  - `docs/explanation/` — **Explanation:** Understanding-oriented discussions, theoretical background, mathematical derivations, architecture, and design rationale.
- `tests/` — **Automated Test Suites:** Unit, integration, regression, and end-to-end tests mirroring the `src/` hierarchy.
- `assets/` or `data/` (or `static/`) — **Assets & Data:** Static files, images, schemas, fixture data, sample datasets, and raw/processed assets.
- `.github/` or `.ci/` — **CI/CD & Workflows:** Continuous integration pipelines, actions, and issue/PR templates.

### C. Pragmatic Ecosystem Flexibility
- Respect language idioms (e.g., Rust `src/` & `tests/` & `examples/`, Python `src/<pkg>/` & `tests/`, Go `cmd/` & `internal/` & `pkg/`, TypeScript `src/` & `tests/`).
- Do NOT generate speculative empty folders for components that do not exist (adhering to Section 5: *Simplicity First*). When creating any file, route it to its appropriate directory instead of dumping it in the root.

---

## 7. Strict Mathematical Notation & GFM / KaTeX Invariants
When writing or editing Markdown documents containing mathematical notation, the agent MUST strictly enforce:
- **Display Math Blocks (`$$` / ```` ```math ````):**
  - Display math `$$` MUST ALWAYS occupy its own isolated lines, surrounded by blank lines. Never place `$$...$$` inline on a text line or inside a table.
  - **Prohibition in List Items:** NEVER place a `$$` display math block immediately after or within list items (`*`, `-`, `+`, `1.`). CommonMark nests the block inside `<li>`, breaking KaTeX/MathJax rendering. Convert the list item to a subheading (`####`) or write plain paragraphs.
  - Inside `$$`, never start a line with `- `, `* `, `+ `, `> `, or digits followed by a dot (e.g. `1. `), which triggers CommonMark list/quote parsing.
- **LaTeX Syntax & Delimiter Escapes:**
  - Braces after `\left` and `\right` MUST be escaped: `\left\{ ... \right\}`, NEVER `\left{` or `\right}`. For set-builder notation, prefer `\lbrace ... \rbrace` and `\mid` to prevent Markdown AST stripping.
  - **No Literal Asterisks in Superscripts:** NEVER use literal `*` in superscripts (e.g. `x^*`). ALWAYS use `x^{\ast}` or `\bar{x}`, because Markdown parsers treat pairs of `*` as italics (`*...*`), corrupting math to `x^_` or HTML tags.
  - **Inequalities & Tags:** Use `\lt` and `\gt` (or `\le`, `\ge`) in math formulas to prevent HTML/Markdown tag parser collisions.
  - Environments with line breaks (`cases`, `aligned`, `matrix`): use clean `\\` line breaks. NEVER attach bracket spacing arguments (e.g. `\\[1.2em]`).
  - No accented characters inside `\text{...}` (e.g. use `\text{se }`, `\text{impar}`, `\text{caso contrario}`).
  - Vector norms: MUST use `\lVert ... \rVert` (never `\|`).
- **Inline Math (`$...$` or `` $`...`$ ``):**
  - NEVER leave leading or trailing whitespace inside delimiters (use `$x = 0$`, never `$ x = 0 $`).
- **Mandatory Pre-Commit Linter Verification:**
  - In repositories with `.scripts/validate_gfm.py`, the agent MUST run `python .scripts/validate_gfm.py <file>` to verify 100% compliance before committing.

---

## 8. Continuous Git Commit & Push Protocol (*Receipts & Snapshot Invariant*)
Whenever creating, editing, or updating any files in response to user requests:
- **Mandatory Immediate Commit & Push:** The agent MUST immediately stage (`git add`), commit (`git commit -m "..."`), AND push (`git push origin <branch>`) the modified files in the same turn before responding to the user.
- Never leave unstaged, uncommitted, or unpushed changes when completing an edit or file creation step requested by the user.

---

## 9. Pre-Flight Invariant Checklist
Before emitting any code review, comparison report, refactoring patch, or documentation plan, the agent MUST internally verify:
1. *Did I verify the raw primary deliverable before claiming an omission?* If NO $\to$ Inspect now or delete the claim.
2. *Did I classify a style choice or standard idiom as a bug?* If YES $\to$ Reclassify to Category 3 and remove inflammatory language.
3. *Is my proposed patch more than $2\times$ larger than the code it fixes?* If YES $\to$ Strip all boilerplate down to the minimal fix.
4. *Does the project maintain a clean root (`src/`, `bin/`/`scripts/`, `tests/`) and strictly adhere to the 4 Diátaxis quadrants in `docs/`?* If NO $\to$ Restructure immediately.
5. *Did I validate all LaTeX expressions against the strict GFM KaTeX rules (isolated `$$`, no `$$` inside lists, escaped `\left\{`, clean `\\`)?* If NO $\to$ Fix and lint before delivering.
6. *Did I stage, commit, AND push all modified/created files to the remote Git repository?* If NO $\to$ Commit and push immediately before finishing the response.
