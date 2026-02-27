---
name: update-project
description: Updates an existing project with the latest CTO Agent standards. Checks for and adds missing Core Rules (like comprehensive-tool-use.mdc), Agents, and Skills.
---

# Update Project (Standard Sync)

This skill brings an existing project up to date with the latest CTO Agent standards.
It is idempotent: it checks for missing files and adds them, but respects existing configurations where possible.

## Workflow

### 1. Root Rule Check (The Sticky Note)
Ensure **`.cursor/rules/000-root-rule.mdc`** exists.
*   **Location:** MUST be in `.cursor/rules/`, NOT in the root.
*   **Frontmatter:** MUST include `alwaysApply: true` and `globs: "**/*"`.
*   **Content:** Explicitly instruct the agent to scan `.cursor/rules/` and `.cursor/skills/` before acting, and enforce the "No Shortcuts" pledge.
*   **OS Protocol:** Must include the "ENVIRONMENT & OS PROTOCOL" section (Windows 10/PowerShell).
*   **Safety Protocol:** Must include "Read Before Write", "Absolute Paths", and "No Secrets" rules.
*   **Escalation Protocol:** Must include the "Class A (Solo) vs Class B (Delegated)" decision tree.

### 2. Core Rules Check
Ensure the following exist in `.cursor/rules/`. If missing, create them with standard content:

*   **`comprehensive-tool-use.mdc`**: (CRITICAL) Enforces tool audits and bans shortcuts.
*   **`skill-first.mdc`**: Enforces checking skills before scripting.
*   **`cost-effective-coding.mdc`**: Enforces subagent delegation for large tasks.
*   **`subagent-delegation.mdc`**: Enforces structured subagent workflows.
*   **`ssh-pi-operations.mdc`**: (If project involves IoT/Pi) Enforces safe SSH protocols.

### 3. Core Skills Check
Ensure the "Superpowers" skills exist in `.cursor/skills/`:

*   `setup-project`
*   `update-project` (Self-replication)
*   `subagent-driven-development`
*   `dispatching-parallel-agents`
*   `systematic-debugging`
*   `brainstorming`

### 4. Core Agents Check
Ensure the standard agent team exists in `.cursor/agents/`:

*   `agent-1.md` (Architect)
*   `agent-2.md` (Manager)
*   `code-reviewer.md` (QA)
*   `deep-researcher.md` (Researcher)

### 5. Reporting
*   List all files that were added or updated.
*   If `ssh-pi-operations.mdc` was added, remind the user to verify if this is an IoT project.

## Example Usage
**User:** "Update this project to the latest standards."
**Agent:** *Checks for comprehensive-tool-use.mdc, sees it's missing, creates it. Checks others... Done.*
