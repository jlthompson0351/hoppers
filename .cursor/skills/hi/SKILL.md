---
name: hi
description: Initializes a new chat session by running the pulse script to gather workspace context. Use when the user types /hi to wake up the agent and resume the train of thought.
---

# Session Initialization (/hi)

When the user types `/hi`, you are waking up in a new chat session. You must immediately gather your context before answering.

## 1. Run the Pulse Script
Execute the following command using the Shell tool:
`powershell.exe -ExecutionPolicy Bypass -File "C:\Users\jthompson\Desktop\Projects\scripts\pulse.ps1"`

## 2. Analyze the Output
Read the output of the pulse script carefully. Pay special attention to:
- **Master State:** What phase are we in? What is the next action?
- **Git Health:** Are there uncommitted changes?
- **Active Train of Thought:** Did the script find a `latest-compressed-chat.md` file?

## 3. Resume the Context
If the pulse script indicates there is a recent compressed chat file (e.g., `.cursor/memory/sessions/latest-compressed-chat.md`), you MUST use the Read tool to read that file immediately.

## 4. Greet the User
Once you have run the script and read any necessary files, greet the user. Summarize the current state, acknowledge the active train of thought (if any), and ask if they are ready to proceed with the "Next Action".