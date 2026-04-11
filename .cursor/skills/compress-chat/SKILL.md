---
name: compress-chat
description: Compresses the current chat context into a dense markdown summary to prevent token bloat and session amnesia. Use when the user types /compress, asks to compress the chat, or wants to save the current train of thought before starting a new session.
---

# Chat Compression (/compress)

When the user types `/compress` or asks to compress the chat, the context window has become too bloated and needs to be reset. You must immediately execute the following steps without asking for confirmation.

## 1. Analyze the Current Train of Thought
Review the recent messages to understand exactly what you are currently in the middle of doing (e.g., debugging a specific error, writing a specific function, planning a feature).

## 2. Write the Compressed Summary
Create or overwrite the file `.cursor/memory/sessions/latest-compressed-chat.md` with a dense, highly compressed markdown summary.

Use this exact template structure:

```markdown
# Compressed Chat Checkpoint
**Date:** [Current Date and Time]

## 🎯 Current Goal
[What were we specifically trying to achieve right now?]

## 🧠 What We Just Tried / Decisions Made
[What code did we just write, what commands did we just run, or what architectural choices did we make?]

## 🛑 The Error / Blocker
[If we are stuck, what is the exact error message or unexpected behavior?]

## ⏳ The Immediate Next Step
[What exact file and line of code were we about to change next? What is the very next action?]
```

## 3. Respond to the User
Once the file is written, respond EXACTLY with:

> ✅ Chat compressed and saved to `latest-compressed-chat.md`. Please hit **Ctrl+L** to start a fresh chat, and say 'hi' so I can run the pulse script and resume our train of thought!

## Important Notes
- Do not ask the user what to put in the summary. You have the context; extract it yourself.
- Keep the summary dense. Do not include massive code blocks unless absolutely necessary for the immediate next step.
- This skill works in tandem with the workspace `pulse.ps1` script, which automatically detects this file on startup.