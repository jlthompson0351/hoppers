---
name: setup-project
description: Bootstraps a new project with the CTO Agent "Standard Setup" (Core Agents, Rules, and Skills).
---

# Setup Project (Bootstrapper)

This skill initializes the current workspace with the "Standard Setup" defined in the CTO Agent Master Template.

## Workflow

### 1. Create Directory Structure
Ensure the following folders exist:
- `.cursor/agents`
- `.cursor/rules`
- `.cursor/skills`

### 2. Deploy Root Rule (The Sticky Note)
Generate the **`.cursor/rules/000-root-rule.mdc`** file.
*   **Location:** MUST be in `.cursor/rules/`, NOT in the root.
*   **Frontmatter:** MUST include `alwaysApply: true` and `globs: "**/*"`.
*   **Content:** Explicitly instruct the agent to scan `.cursor/rules/` and `.cursor/skills/` before acting, and enforce the "No Shortcuts" pledge.
*   **OS Protocol:** Must include the "ENVIRONMENT & OS PROTOCOL" section (Windows 10/PowerShell).
*   **Safety Protocol:** Must include "Read Before Write", "Absolute Paths", and "No Secrets" rules.
*   **Escalation Protocol:** Must include the "Class A (Solo) vs Class B (Delegated)" decision tree.

### 3. Deploy Core Agents
Generate the following files in `.cursor/agents/` using the **latest models**:

*   **`agent-1.md` (Architect)** -> Model: `gpt-5.3-codex-xhigh`
*   **`agent-2.md` (Manager)** -> Model: `claude-4.6-opus-high-thinking`
*   **`code-reviewer.md` (QA)** -> Model: `claude-4.6-opus-max-thinking`
*   **`deep-researcher.md` (Researcher)** -> Model: `gemini-3-pro`

### 3. Deploy Core Rules
Generate the following files in `.cursor/rules/`:

*   **`subagent-delegation.mdc`**: Enforce `subagent-driven-development`.
*   **`cost-effective-coding.mdc`**: Enforce delegation.
*   **`skill-first.mdc`**: Enforce skill usage.
*   **`comprehensive-tool-use.mdc`**: Enforce tool audit and ban shortcuts.
*   **`anthropic-4-5-optimization.mdc`**: XML thinking protocol.

### 4. Deploy Core Skills
Generate the essential "Superpowers" skills in `.cursor/skills/`:

*   `subagent-driven-development`
*   `dispatching-parallel-agents`
*   `systematic-debugging`
*   `brainstorming`
*   `create-subagent`
*   `update-project`

### 5. Stack Selection (The Add-on Phase)
**CRITICAL:** After deploying the core, you MUST ask the user:

> "Standard Setup complete. What is the tech stack for this project?
> 1. **Web App** (React/Next.js/Tailwind)
> 2. **Backend/DB** (Supabase/Postgres)
> 3. **Python/Data** (FastAPI/Pandas)
> 4. **Custom**"

Based on the answer, generate the specific `*-specialist.md` agent.

## Example Usage
**User:** "Set up this project."
**Agent:** *Runs the workflow above, creates files, and asks for the stack.*
