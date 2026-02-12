---
description: Temporarily installs a skill, agent, or PACK from the CTO Library into the current project. Use when the user needs a capability (like "deep research") or a bundle (like "supabase pack").
---

# Temporary Skill Loader

## Purpose
To give a project "Superpowers" on demand without permanently bloating its configuration.

## Workflow

1.  **Consult Playstore**
    -   If the user asks for a skill you don't have, read the Playstore at:
        `C:\Users\jthompson\Desktop\CTO Agent\PLAYSTORE.md`
    -   Identify the path of the requested Skill or Pack.

2.  **Install (Temp)**
    -   **For a Single Skill:**
        -   Copy `[SourcePath]` to `.cursor/skills/[SkillName]`.
    -   **For a Pack:**
        -   Copy `[SourcePath]/skills/*` to `.cursor/skills/`.
        -   Copy `[SourcePath]/rules/*` to `.cursor/rules/`.
        -   Copy `[SourcePath]/agents/*` to `.cursor/agents/`.
        -   (Packs unpack their contents directly into the respective folders).

3.  **Execute**
    -   Tell the user: "I have loaded the [Name]. You can now use it."
    -   (The user or AI performs the task).

4.  **Cleanup (The "Wrap Up")**
    -   When the user says "Wrap up", delete the temporary files.
    -   Log usage in `DAILY_LOG.md`.

## Tools
-   `Desktop Commander` (or Shell) to copy files.
