// v0
// AGENTS.md
# AGENTS.md — Codex Operational Rules for PMCSN ASF Project

> **Purpose:**  
> Defines how **Codex** operates in the PMCSN ASF project.  
> Codex is the **implementation agent**, executing GPT’s prompts to produce complete, fully-commented, versioned, and logged code.

---

## 1) General Compliance

- Follow all rules below unless explicitly overridden.  
- Modify **only** what GPT’s prompt defines.  
- Minimal surrounding changes to preserve build/run.  
- If breaking a rule is necessary, explain it clearly in PR body.

---

## 2) Output & Delivery

- Output = **branch + PR** containing full Git diff and descriptive commits.  
- PR body must contain:
  - **Diff Summary & Notes**
  - **Design Rationale**
- Keep changes atomic (small, focused).

---

## 3) File Completeness & Version Headers

Each file must begin with:
```go
// vN
// <filename>
```
Increment version from previous input (e.g., v2 after v1).  
Generate **full files** — copy-paste replaceable.  
Build must succeed as-is.

---

## 4) Commenting & Rationale

- Code must be **naturally commented** (no AI tone).  
- End each PR with a brief Design Rationale: why and trade-offs.

---

## 5) Logging Policy

- Log every operation to **stdout and a logfile**.  
- Prefer the project’s standard logger (`log/slog` or Python `logging`).  
- Do not add external logging libs without approval.

---

## 6) Dependencies & Libraries

- Use **standard libraries only** unless prompt allows otherwise.  
- If a non-stdlib lib is needed, pause and request approval.

---

## 7) Simulation / Data Handling

- Scripts and models must load data only from documented paths (`/data`, `/input`).  
- Log all file reads/writes and parameter loads.  
- Use configurable paths (via env vars or CLI args).

---

## 8) Definition of Done (DoD)

Complete only if:
1. Build or script runs without errors.  
2. Output matches expected scope.  
3. Code is fully commented and logged.  
4. PR documents changes and reasoning.  

---

## 9) Documentation Awareness

Before editing:
- Read `docs/project_documentation.md`.  
- Flag any contradictions as **Design Conflicts** in PR.  
- Never override docs silently.

---

## 10) Version Control Conventions

- **PR title:** `[Module] — <short action>: <goal>`  
- **Commit style:** imperative (“Add logging middleware”).  
- Always include HEAD commit hash in PR body.  

---

## 11) Behavioral Checklist

- Work on latest repo snapshot.  
- Ensure build/test passes.  
- Use standard logging and libs.  
- Fully comment every file.  
- Never edit beyond scope.  
- Always log operations.  

---

**End of AGENTS.md**
