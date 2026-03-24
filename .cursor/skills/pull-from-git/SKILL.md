# Pull from Git

When Justin says "pull from git", "pull latest", "sync", "what's new", or starts a new session on this project:

## Steps

### 1. Pull Latest
```bash
git pull origin main
```

### 2. Read the Handoff Docs (IN THIS ORDER)
1. **HANDOFF.md** — What the last agent/session left for you. Read this FIRST.
2. **STATUS.md** — Current state of the project, latest activity.
3. **TODO.md** — The backlog. See what's checked off and what's pending.
4. **DECISIONS.md** — If it exists, skim for recent entries so you don't redo past decisions.

### 3. Summarize for Justin
After reading, give a brief summary:
- "Last session [agent/person] worked on [X]. Current status is [Y]. Next step is [Z]. There are [N] open TODOs."

### 4. Ready to Work
You now have full context. Don't ask Justin to repeat what's already in the docs.

## Why This Matters
OpenClaw agents (Anton, Ledger, Prism, Talos) push updates to these docs from the VPS. If you don't read them, you're missing context from work done outside Cursor. Always pull and read before building.
