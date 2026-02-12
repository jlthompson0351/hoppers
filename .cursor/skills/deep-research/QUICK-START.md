# Deep Research - Quick Start Guide

## TL;DR

Just ask questions naturally. The system automatically triggers when you need research.

## Example Prompts That Work

### Adding Features
```
"Add authentication to the app"
"Add real-time chat functionality"
"Implement payment processing"
```

### Technology Choices
```
"Should I use Postgres or MongoDB?"
"What's the best state management for React?"
"Which ORM should I use?"
```

### Best Practices
```
"What's the best way to handle errors in Express?"
"How should I structure a Next.js app?"
"Find React performance optimization techniques"
```

### Research Requests
```
"Research GraphQL vs REST for this project"
"Find the latest authentication patterns"
"What are the security best practices for APIs?"
```

## What You'll Get

Every research returns:
- 📊 Executive summary (2-3 sentences)
- ✅ Clear recommendation (Use it / Don't / Cautious)
- 🔍 Detailed findings (pros, cons, sources)
- 👥 Community sentiment (Reddit, Stack Overflow)
- 🔒 Security status
- 📝 Step-by-step implementation guide
- 💻 Code examples from real projects
- 🔄 Alternative options considered
- ⚠️ Common gotchas
- 📚 All sources cited

## Cost per Research

- Quick: $0.30-0.50 (5-8 searches)
- Standard: $0.70-1.20 (10-15 searches)
- Deep: $1.50-3.00 (20-30 searches)

With Ultra plan ($400/month), you can do 100+ deep researches.

## Tips

1. **Be specific**: "Add OAuth2 authentication" > "Add auth"
2. **Ask directly**: Don't say "can you research?" - just ask the question
3. **Follow up**: Research is cached, ask follow-ups freely
4. **Trust it**: The system checks multiple sources automatically

## Tools Used Automatically

- ✅ Exa (web search, code examples)
- ✅ Context7 (official docs)
- ✅ GitHub (via Exa)
- ✅ Reddit (via Exa)
- ✅ Stack Overflow (via Exa)
- ✅ Browser (when needed)

You don't need to specify which tools - it uses them all automatically.

## Quality Guarantees

Every research:
- ✅ Multiple sources (never just one)
- ✅ Official docs included
- ✅ Real code examples
- ✅ Community validated
- ✅ Security checked
- ✅ Maintenance verified

## When It Activates

Automatically triggers on:
- "research", "find out", "investigate"
- "what's the best way to..."
- "should I use X or Y?"
- "add [feature]" (when unfamiliar)
- "how do I implement..."

## When It Doesn't Activate

Skips research for:
- Simple, obvious changes
- Internal refactoring
- Quick bug fixes
- Things you just researched

## After Research

You can:
- Ask to implement the recommendation
- Request deeper dive on specific aspect
- Ask about alternatives
- Get clarification on any finding

The research stays in conversation context for follow-ups.

## Example Session

```
You: "What's the best way to add authentication to Next.js?"

[Deep researcher activates automatically]

Agent: "I've researched Next.js authentication options. Here's what I found:

# Research: Next.js Authentication

## TL;DR
Use NextAuth.js for most production apps. It's the official Next.js recommendation, 
actively maintained, and handles OAuth + credentials securely.

## Recommendation
**Use NextAuth.js** because:
- Official Next.js integration
- 20K+ GitHub stars, actively maintained
- Supports all major OAuth providers
- Built-in CSRF protection
- Strong community support

[... detailed findings, code examples, alternatives, gotchas ...]

## Implementation Guide

Step 1: Install NextAuth
```bash
npm install next-auth
```

Step 2: Create API route
```javascript
// pages/api/auth/[...nextauth].js
[... complete working code example ...]
```

[... continues with full implementation ...]"

You: "Looks good, implement it"

Agent: [Proceeds with confident implementation based on research]
```

## Need Help?

- Read full docs: `SKILL.md` in this folder
- See subagent details: `../../agents/deep-researcher.md`
- Project overview: `../../../README.md`
