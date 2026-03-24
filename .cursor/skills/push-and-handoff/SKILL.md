# Push and Handoff

When Justin says "push to git", "wrap up", "commit", "push it", or anything indicating the session is ending or work should be saved:

**DO NOT just commit and push raw code.** First, update the project docs so the next agent (OpenClaw or Cursor) knows exactly what happened.

## Steps

### 1. Update STATUS.md
Add a dated entry at the top with:
- What was just built, fixed, or changed
- Current state of the feature/fix
- Any warnings or known issues

### 2. Update HANDOFF.md  
Write a clear "next step" section:
- What was the goal of this session?
- What got done?
- What's the very next thing to do?
- Any blockers or decisions needed?

### 3. Update TODO.md
- Check off `[x]` anything that was completed
- Add `- [ ]` for any new tasks discovered during the work
- Remove anything that's no longer relevant

### 4. Update DECISIONS.md (if applicable)
If any architectural or design decisions were made, document WHY — not just what.

### 5. THEN Commit and Push
```bash
git add .
git commit -m "feat/fix/docs: [brief description of what changed]"
git push origin main
```

## Why This Matters
OpenClaw agents (Anton, Ledger, Prism, Talos) pull this repo and read these docs to continue work. If the docs are stale, they're flying blind. Clean handoffs save Justin time and money.

## Quick Reference
- `STATUS.md` = what's happening NOW
- `HANDOFF.md` = what the NEXT person needs to know
- `TODO.md` = the backlog
- `DECISIONS.md` = why we did it this way
