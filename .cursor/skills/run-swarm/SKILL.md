---
name: run-swarm
description: Orchestrates parallel swarms of specialized agents (Kimi/Flash) for bulk tasks.
---

# Run Swarm

**Role:** Orchestrate parallel swarms of specialized agents to handle bulk tasks efficiently.

## 1. When to Use This Skill
Use this skill when the user asks to:
- "Send out the swarm"
- "Scan the whole codebase"
- "Research these 5 topics"
- "Fix all these files"
- "Map dependencies for X"

## 2. Swarm Selection Strategy

You MUST select the correct agent type based on the task:

| Task Type | Agent | Model | Cost |
|-----------|-------|-------|------|
| **Dependency Mapping** | `swarm-kimi` | `kimi-k2.5` | Low |
| **Bulk Refactoring** | `swarm-kimi` | `kimi-k2.5` | Low |
| **Quick Sanity Checks** | `swarm-kimi` | `kimi-k2.5` | Low |
| **Documentation Consolidation** | `swarm-flash` | `gemini-3-flash-preview` | Low-Mid |
| **Large Context Analysis** | `swarm-flash` | `gemini-3-flash-preview` | Low-Mid |
| **Deep Research (Complex)** | `deep-research` | `claude-3-5-sonnet` | High |

## 3. Execution Pattern

### Step 1: Break Down the Task
Split the user's request into independent, parallelizable chunks.
- **Good:** "Agent 1 check src/auth", "Agent 2 check src/api", "Agent 3 check src/ui"
- **Bad:** "Agent 1 check everything" (Too slow, hits context limits)

### Step 2: Dispatch in Parallel
Use the `Task` tool to launch multiple agents at once.

**CRITICAL:** You must specify `subagent_type` and `model` explicitly.

```typescript
// Example: Dispatching a Kimi Swarm for dependency mapping
[
  {
    "tool": "Task",
    "args": {
      "subagent_type": "swarm-kimi",
      "model": "fast", // "fast" maps to Kimi/Flash in this context or use specific model if supported
      "description": "Scan src/frontend for User dependencies",
      "prompt": "Find all imports of 'User' in src/frontend. Return list of files."
    }
  },
  {
    "tool": "Task",
    "args": {
      "subagent_type": "swarm-kimi",
      "model": "fast",
      "description": "Scan src/backend for User dependencies",
      "prompt": "Find all imports of 'User' in src/backend. Return list of files."
    }
  }
]
```

### Step 3: Aggregate Results
When the agents return:
1.  Read their summaries.
2.  Consolidate findings into a single report.
3.  Present the final answer to the user.

## 4. Example Scenarios

### Scenario A: "Find all places we use the old Button component"
**Action:**
1.  Identify target directories: `src/components`, `src/pages`, `src/features`.
2.  Launch 3 `swarm-kimi` agents, one for each directory.
3.  Prompt: "Grep for '<Button' in [directory]. List file paths."

### Scenario B: "Read these 5 API docs and write a summary"
**Action:**
1.  Launch 1 `swarm-flash` agent (since it has a huge context window, one agent might be enough, or split if >1M tokens).
2.  Prompt: "Read [file1, file2...] and write a summary."

## 5. Safety & Cost
- **Limit:** Do not launch more than 5 parallel agents without user confirmation.
- **Cost:** Remind the user if a swarm operation might be expensive (though Kimi/Flash are cheap).
