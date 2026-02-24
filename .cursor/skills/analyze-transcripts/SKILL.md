---
name: analyze-transcripts
description: Reads past chat transcripts to identify user pain points, repetitive tasks, and agent errors. Generates new Rules, Skills, and Agents to optimize the workflow.
---

# Analyze Transcripts

**Role:** Use the `transcript-analyzer` agent to explore project history and learn from past interactions.

## 1. When to Use This Skill
Use this skill when the user asks to:
- "Look back at our history"
- "Find when we talked about [topic]"
- "Analyze what we've been working on"
- "See if you can find [info] in the transcripts"

## 2. Execution Pattern

### Step 1: Identify the Goal
Determine what the user is looking for:
- **Specific Info:** A code snippet, a decision, a specific conversation.
- **General Analysis:** Summary of work, pattern recognition, workflow improvement.

### Step 2: Dispatch the Agent
Use the `Task` tool to launch the `transcript-analyzer`.

```typescript
{
  "tool": "Task",
  "args": {
    "subagent_type": "generalPurpose", // Use generalPurpose for custom agents not in the enum list yet, or update enum if possible. For now, we use the model to select the right agent behavior.
    "model": "gemini-3-flash-preview", // CRITICAL: Use Flash for context window
    "description": "Analyze transcripts for [topic]",
    "prompt": "You are the Transcript Analyzer. Your goal is to [user goal]. The transcripts are located at C:\\Users\\jthompson\\.cursor\\projects\\c-Users-jthompson-Desktop-CTO-Agent\\agent-transcripts. 1. List the files. 2. Read relevant ones. 3. Answer: [specific question]."
  }
}
```

### Step 3: Review Findings
When the agent returns, present the found information clearly to the user, citing the session ID if possible.

## 3. Location of Transcripts
Remind the agent that transcripts are stored in:
`C:\Users\jthompson\.cursor\projects\c-Users-jthompson-Desktop-CTO-Agent\agent-transcripts` (Note: Adjust path if running in a different project)

## 4. Tips
- **Grep first:** If looking for a specific keyword, tell the agent to `grep` the directory first to find which files to read.
- **Read fully:** If doing a general analysis, Gemini Flash can read many full files.
