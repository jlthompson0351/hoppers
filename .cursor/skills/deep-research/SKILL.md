---
name: deep-research
description: Autonomous deep research using Exa, Context7, browser, GitHub, Reddit, and Stack Overflow. Use when adding new features, choosing technologies, researching best practices, or when the user asks to "research" something. Automatically runs parallel searches and synthesizes findings without manual guidance.
---

# Deep Research

Automated research agent that uses multiple tools in parallel to find comprehensive, up-to-date information about technologies, implementations, and best practices.

## When to Use This Skill

**ALWAYS use this skill when:**
- Adding new features ("add authentication")
- Updating existing functionality ("improve performance")
- Choosing between technologies ("React vs Vue")
- Finding best practices ("API security patterns")
- User explicitly asks to "research", "find out", or "investigate"
- Implementing something unfamiliar

**DON'T use for:**
- Simple, obvious changes
- Quick fixes you already understand
- Internal refactoring with no external dependencies

## Research Workflow

### Phase 1: Parallel Initial Searches (Run ALL simultaneously)

```
1. Exa Web Search → Recent articles, tutorials, comparisons
2. Exa Code Context → Real implementation examples from GitHub
3. Context7 → Official documentation
4. Browser (if needed) → Live verification, changelogs
```

**Example parallel execution:**
```
For "Next.js authentication best practices":
├─ user-exa-web_search_exa: "Next.js authentication 2026 best practices"
├─ user-exa-get_code_context_exa: "Next.js authentication implementation examples"
├─ user-Context7-resolve-library-id: libraryName="Next.js", query="authentication"
└─ (Then) user-Context7-query-docs: with resolved ID
```

### Phase 2: Deep Dive on Findings

Based on Phase 1 results, automatically:

**Follow interesting leads:**
- If a specific library is mentioned → Search Context7 for it
- If a pattern emerges → Find more code examples with Exa
- If there's debate → Search Reddit/Stack Overflow sentiment

**Community validation:**
- Check Reddit discussions (via Exa web search): "site:reddit.com [technology] experiences"
- Check Stack Overflow (via Exa): "site:stackoverflow.com [technology] problems"
- Check GitHub issues: Use Exa to find "site:github.com [repo] issues [topic]"

**Example deep dive:**
```
Initial finding: "NextAuth.js is popular"
→ user-Context7-query-docs for NextAuth.js documentation
→ user-exa-get_code_context_exa for production NextAuth examples
→ user-exa-web_search_exa: "site:reddit.com NextAuth.js production experience"
→ user-exa-web_search_exa: "site:github.com nextauthjs issues security"
```

### Phase 3: Verification & Current State

**Check for:**
- Latest version/release notes (browser_navigate to docs)
- Recent security issues (GitHub/Exa search)
- Active maintenance (GitHub activity via Exa)
- Breaking changes (changelog via browser or Exa)

### Phase 4: Synthesis

Create structured report:


```markdown
## [Technology Name]

### Summary
One-paragraph overview of findings.

### Recommendation
Clear recommendation: Use it / Don't use it / Use with caution

### Key Findings
- **Pros:** List of advantages with sources
- **Cons:** List of disadvantages with sources
- **Community Sentiment:** What developers are saying
- **Maintenance Status:** Active/Stale, last update, GitHub stars

### Implementation Approach
Step-by-step recommended implementation based on research.

### Code Examples
Paste best code examples found from research.

### Security Considerations
Any security issues, CVEs, or concerns discovered.

### Alternative Options
Other technologies considered and why chosen/rejected.

### Sources
- Link 1 (Exa web search result)
- Link 2 (Context7 docs)
- Link 3 (GitHub repo/issues)
- Link 4 (Reddit discussion)
```

## Tool Reference

### Exa Tools

**user-exa-web_search_exa**
- Purpose: Find recent articles, blog posts, comparisons, tutorials
- Best for: Latest trends, opinions, "what's new in 2026"
- Query tips: Include year for recency, be specific

```
Examples:
- "Next.js authentication best practices 2026"
- "React vs Vue performance comparison 2026"
- "site:reddit.com NextAuth production experience"
- "site:stackoverflow.com prisma query optimization"
```

**user-exa-get_code_context_exa**
- Purpose: Find real implementation examples from GitHub/docs
- Best for: "How do people actually implement this?"
- Returns: Code snippets with context

```
Examples:
- "Next.js authentication with NextAuth implementation"
- "Express middleware error handling production code"
- "Prisma schema design patterns real examples"
```

**user-exa-company_research_exa**
- Purpose: Research companies, their tech stack, reputation
- Best for: Understanding who uses/maintains technology
- Use when: Evaluating library maintainers or adoption

### Context7 Tools

**user-Context7-resolve-library-id**
- Purpose: Find the correct library ID for documentation
- Required: ALWAYS call this before query-docs
- Returns: Library ID like "/vercel/next.js"

```
Example:
user-Context7-resolve-library-id(
  libraryName: "Next.js",
  query: "Next.js authentication and routing documentation"
)
```

**user-Context7-query-docs**
- Purpose: Get official, up-to-date documentation
- Best for: API references, official guides, accurate specs
- Returns: Structured documentation snippets

```
Example:
user-Context7-query-docs(
  libraryId: "/vercel/next.js",
  query: "Next.js 14 app router authentication patterns"
)
```

### Browser Tools (if available)

Use browser tools for:
- Checking changelogs on official sites
- Verifying current version numbers
- Reading blog posts with rich formatting
- Checking GitHub issue counts/activity

### Community Research Patterns

**Reddit Research (via Exa):**
```
"site:reddit.com r/nextjs authentication issues"
"site:reddit.com r/webdev [technology] production"
```

**Stack Overflow (via Exa):**
```
"site:stackoverflow.com [technology] common problems"
"site:stackoverflow.com tagged/nextjs authentication"
```

**GitHub Research (via Exa):**
```
"site:github.com [org]/[repo] issues [topic]"
"site:github.com [technology] stars:>1000 topic:authentication"
```


## Research Decision Tree

### For "Add [Feature]" Requests

```
1. Is this a well-known pattern?
   YES → Search Context7 for official docs first
   NO → Start with Exa web search for recent articles

2. Are there multiple approaches?
   YES → Research each approach in parallel:
         ├─ Approach A: Exa code + Context7 docs + Reddit sentiment
         ├─ Approach B: Exa code + Context7 docs + Reddit sentiment
         └─ Compare in synthesis
   NO → Deep dive on the single approach

3. Is security critical?
   YES → Extra searches:
         ├─ "site:github.com [tech] issues security"
         ├─ "site:reddit.com [tech] security concerns"
         └─ Check for recent CVEs via Exa web search
   NO → Standard security check only

4. Is this a newer technology (<2 years old)?
   YES → Focus on:
         ├─ Reddit/community sentiment
         ├─ GitHub issue activity
         ├─ Breaking change frequency
   NO → Focus on:
         ├─ Best practices evolution
         ├─ Current recommended patterns
```

### For "Technology Choice" Requests

```
Research Pattern:
├─ Option A: Full research (Exa + Context7 + Community)
├─ Option B: Full research (Exa + Context7 + Community)
└─ Direct comparisons: "A vs B 2026" via Exa

Compare:
- Learning curve
- Performance
- Community size
- Maintenance status
- Job market demand (if relevant)
- Migration difficulty
```

### For "Best Practices" Requests

```
1. Official docs (Context7) → What do maintainers say?
2. Recent articles (Exa web) → What's trending in 2026?
3. Production code (Exa code) → What do real apps do?
4. Community (Reddit/SO) → What are the gotchas?
5. Synthesize: Recommend patterns with confidence level
```

## Execution Examples

### Example 1: Add Authentication

**User request:** "Add authentication to the Next.js app"

**Automatic research sequence:**

```
[Phase 1 - Parallel]
1. user-exa-web_search_exa
   query: "Next.js authentication best practices 2026"
   numResults: 8

2. user-exa-get_code_context_exa
   query: "Next.js authentication implementation examples production"
   tokensNum: 8000

3. user-Context7-resolve-library-id
   libraryName: "Next.js"
   query: "Next.js authentication"

4. user-Context7-query-docs
   libraryId: [from step 3]
   query: "Next.js app router authentication middleware"

[Phase 2 - Deep Dive on Findings]
If NextAuth.js mentioned:
5. user-Context7-resolve-library-id
   libraryName: "NextAuth.js"

6. user-Context7-query-docs
   libraryId: [from step 5]
   query: "NextAuth.js setup and configuration"

7. user-exa-web_search_exa
   query: "site:reddit.com NextAuth production issues 2026"

8. user-exa-web_search_exa
   query: "site:github.com nextauthjs/next-auth issues"

[Phase 3 - Security Check]
9. user-exa-web_search_exa
   query: "NextAuth security vulnerabilities CVE"

[Phase 4 - Synthesize]
Generate report with findings, recommendation, and implementation plan
```

### Example 2: Choose Database

**User request:** "Should I use Postgres or MongoDB?"

**Automatic research sequence:**

```
[Parallel Research - Both Options]
Postgres:
├─ user-exa-web_search_exa: "PostgreSQL best practices 2026"
├─ user-exa-get_code_context_exa: "PostgreSQL Node.js production code"
├─ user-Context7 docs for pg/Prisma
└─ user-exa-web_search_exa: "site:reddit.com PostgreSQL production experience"

MongoDB:
├─ user-exa-web_search_exa: "MongoDB best practices 2026"
├─ user-exa-get_code_context_exa: "MongoDB Node.js production code"
├─ user-Context7 docs for mongodb/mongoose
└─ user-exa-web_search_exa: "site:reddit.com MongoDB production experience"

Comparison:
└─ user-exa-web_search_exa: "PostgreSQL vs MongoDB 2026 comparison"

[Synthesize]
Create comparison table with:
- Use cases for each
- Performance characteristics
- Scaling considerations
- Team expertise required
- Clear recommendation based on findings
```


### Example 3: Performance Optimization

**User request:** "How can I make my React app faster?"

**Automatic research sequence:**

```
[Phase 1 - General Patterns]
1. user-exa-web_search_exa
   query: "React performance optimization 2026 best practices"

2. user-exa-get_code_context_exa
   query: "React performance optimization patterns production code"

3. user-Context7-query-docs
   libraryId: "/facebook/react"
   query: "React performance optimization memoization"

[Phase 2 - Specific Techniques]
Based on findings, research each technique:
├─ Memoization: Context7 docs + code examples
├─ Code splitting: Context7 docs + code examples
├─ Virtual scrolling: Exa search libraries + examples
└─ Bundle optimization: Webpack/Vite docs + practices

[Phase 3 - Tooling]
4. user-exa-web_search_exa
   query: "React performance monitoring tools 2026"

5. Research top tools found (web-vitals, Lighthouse, etc.)

[Synthesize]
Create prioritized checklist:
1. Quick wins (high impact, low effort)
2. Medium term (requires refactoring)
3. Advanced (architectural changes)
With code examples for each
```

## Cost Awareness

**Estimated costs per research:**
- Light research (5-8 tool calls): $0.30-0.50
- Standard research (10-15 calls): $0.70-1.20
- Deep research (20-30 calls): $1.50-3.00

**Optimization tips:**
- Run parallel searches simultaneously (faster, same cost)
- Use Context7 for docs (cheaper than web search)
- Cache findings in conversation for follow-up questions
- Don't re-research if you just did it 5 minutes ago

## Quality Checklist

Before presenting findings, verify:

- [ ] Checked multiple sources (not just one article)
- [ ] Included official documentation (Context7)
- [ ] Found real code examples (Exa code context)
- [ ] Checked community sentiment (Reddit/SO)
- [ ] Verified current/maintained (GitHub activity)
- [ ] Identified security concerns
- [ ] Provided clear recommendation
- [ ] Included implementation examples
- [ ] Listed alternatives considered
- [ ] Cited all sources

## Output Format

Always structure final report as:

```markdown
# Research: [Topic]

## Executive Summary
2-3 sentences: What did you find? What's the recommendation?

## Recommendation
**Use [Technology/Approach]** because [key reasons]

OR

**Don't use [Technology]** because [key concerns]

OR

**Use with caution:** [conditions where it works] vs [where it doesn't]

## Detailed Findings

### Overview
What is it? What problem does it solve?

### Pros
- ✅ Advantage 1 (source: [link])
- ✅ Advantage 2 (source: [link])

### Cons
- ❌ Disadvantage 1 (source: [link])
- ❌ Disadvantage 2 (source: [link])

### Community Sentiment
What are developers saying? Common complaints? Praise?
(sources: Reddit threads, SO discussions)

### Maintenance & Adoption
- GitHub stars: [count]
- Last updated: [date]
- Open issues: [count]
- Community size: [assessment]

### Security
Any CVEs? Known vulnerabilities? Security best practices?

## Implementation Guide

### Step 1: [First step]
```[language]
[code example]
```

### Step 2: [Second step]
```[language]
[code example]
```

[Continue with clear steps...]

## Alternatives Considered

### Option A
Why considered? Why rejected/accepted?

### Option B
Why considered? Why rejected/accepted?

## Code Examples

### Basic Implementation
```[language]
[working code example from research]
```

### Production Pattern
```[language]
[real-world production code from Exa]
```

## Gotchas & Common Mistakes

Based on community research:
- ⚠️ Watch out for: [common mistake 1]
- ⚠️ Watch out for: [common mistake 2]

## Additional Resources
- [Official docs link]
- [Best tutorial found]
- [GitHub repo]
- [Helpful Reddit thread]

## Sources
1. [Source 1] - [What it provided]
2. [Source 2] - [What it provided]
[... all sources used]
```

## Tips for Effective Research

1. **Start broad, go deep**: Web search first for landscape, then focus on specifics
2. **Verify with code**: Don't trust articles without checking real implementations
3. **Check the date**: Technology moves fast, prefer 2025-2026 content
4. **Community = reality**: Official docs are optimistic, Reddit shows real problems
5. **Security first**: Always check for known issues before recommending
6. **Provide escape hatches**: Always mention alternatives in case recommendation doesn't fit
7. **Show, don't tell**: Include actual code examples, not just descriptions
8. **Cite everything**: User needs to verify your research if needed

## When Research is Complete

After presenting findings:
- Ask if user wants to proceed with recommendation
- Offer to implement based on research
- Suggest next steps clearly
- Keep research context in conversation for follow-up questions

---

## Integration with Other Workflows

This skill works best when:
- Combined with coding agents (research → plan → implement)
- Used before making architectural decisions
- Invoked automatically when uncertain about approach
- Paired with security review for critical features

**Do NOT:**
- Over-research simple/obvious tasks
- Re-research within same conversation (use previous findings)
- Research when you already know the clear answer
- Delay implementation with unnecessary deep dives
