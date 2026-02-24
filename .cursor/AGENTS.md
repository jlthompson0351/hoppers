# Scales Project - Agent Team Roster

This document defines the specialized AI agents available in the Scales project and their specific responsibilities.

## 1. Core Domain Team (Scales Specific)
These agents handle the unique business logic and hardware integration of the project.

| Agent | Role | When to Call |
|-------|------|--------------|
| **`hardware-specialist`** | Physical Interface | "Read the scale weight", "Calibrate the sensor", "Debug GPIO pins". |
| **`pi-ops`** | System Admin | "Update the OS", "Check CPU temp", "Manage systemd services", "Configure network". |
| **`data-analyst`** | Business Logic | "Process weight data", "Generate reports", "Analyze trends", "Database queries". |
| **`backup-specialist`** | Data Safety | "Run a backup now", "Restore from yesterday", "Check backup integrity". |

## 2. The Utility Belt (General Purpose)
These agents provide powerful capabilities for research, documentation, and history.

| Agent | Role | When to Call |
|-------|------|--------------|
| **`deep-researcher`** | Complex Research | "Research best practices for X", "Compare library A vs B", "Find security vulnerabilities". |
| **`swarm-kimi`** | The Scout (Fast/Bulk) | "Find all files importing User", "Check 50 files for pattern X", "Quick sanity check". |
| **`swarm-flash`** | The Librarian (Docs) | "Consolidate all docs into one README", "Generate JSDoc for this module", "Analyze large logs". |
| **`transcript-analyzer`** | The Historian | "Find where we discussed X last week", "Summarize project history", "Retrieve old code snippet". |

## 3. Leadership
| Agent | Role | When to Call |
|-------|------|--------------|
| **`cto`** | Strategy & Planning | High-level architectural decisions, roadmap planning, technical debt assessment. |

## workflow Integration

1.  **Orchestrator (Main Agent):** Receives user request.
2.  **Router:** Consults this roster to pick the *best* agent for the job.
3.  **Dispatch:** Uses the `Task` tool with the specific `subagent_type` or `model`.

**Example:**
- User: "Why is the scale reading weird values?"
- Router: "This is a hardware issue. Dispatch `hardware-specialist`."

- User: "Find all the places we use the old sensor library."
- Router: "This is a bulk search task. Dispatch `swarm-kimi`."
