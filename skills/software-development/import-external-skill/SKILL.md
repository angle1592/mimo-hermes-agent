---
name: import-external-skill
description: Import external resources (GitHub repos, guides, articles) as Hermes Agent skills — read source, extract principles, adapt to Hermes tools, create with skill_manage.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, import, external, guidelines, conversion]
    related_skills: [hermes-agent-skill-authoring, karpathy-guidelines]
---

# Import External Resource as Hermes Skill

## Overview

Convert external resources (GitHub repos, blog posts, guideline docs, CLAUDE.md files, etc.) into properly formatted Hermes Agent skills. This handles the full pipeline: reading the source material, extracting actionable content, adapting it for Hermes tools (patch, todo, terminal), adding proper triggers, and creating the skill via `skill_manage`.

## When to Use

**Load this skill when:**
- User shares a link to a GitHub repo containing guidelines, rules, or workflows
- User shares an article/post with a methodology they want to preserve as a skill
- User asks "can you make this into a Hermes skill?"
- You find an external reference that could be reused as a Hermes skill

**Don't use for:**
- Skills already covered by an existing skill (prefer patching the existing one)
- Simple one-off instructions that don't need reuse
- In-repo skills (use `hermes-agent-skill-authoring` instead)

## Import Pipeline

### Step 1: Read and Understand the Source

```python
# For GitHub repos — clone and explore
terminal("git clone --depth 1 https://github.com/user/repo.git /tmp/source-skill 2>&1")
terminal("ls -la /tmp/source-skill/")
read_file("/tmp/source-skill/README.md")  # Main docs
read_file("/tmp/source-skill/CLAUDE.md")  # Or CLAUDE.md if it exists
read_file("/tmp/source-skill/EXAMPLES.md")  # Examples if available
```

Identify:
- **Core principles** — what are the 1-5 main ideas?
- **Structure** — how is the content organized?
- **Tone** — formal, conversational, technical?
- **Existing tooling** — does it reference tools or workflows found in Hermes?

### Step 2: Extract Actionable Content

Not everything in the source belongs in a Hermes skill. Distill:

| Keep | Discard |
|------|---------|
| Actionable principles and rules | Platform-specific install instructions (Claude Code plugins) |
| Specific examples and before/after | Vague meta-commentary |
| Anti-patterns and pitfalls | Redundant explanations |
| Decision-making heuristics | Self-promotion sections |
| Concrete code snippets | Knowledge-cutoff disclaimers |

### Step 3: Translate to Hermes Context

For each principle, ask: **"How does this look in Hermes tools?"**

**Common mappings:**

| External Concept | Hermes Equivalent |
|------------------|-------------------|
| "Don't reformat entire file" | Use `patch(old_string=..., new_string=...)` for surgical edits |
| "Plan before implementing" | Use `todo(todos=[...])` for step tracking |
| "Test-driven approach" | Run tests via `terminal("pytest ...")` |
| "Ask before assuming" | Surface assumptions in response before using tools |
| "Clean up only your mess" | After changes, check: `terminal("git diff --stat")` for scope |

**Key pattern:** External guidelines are often abstract ("keep it simple"). Hermetize them by showing **which tool invocation** embodies the principle.

### Step 4: Design Proper Triggers

The `## When to Use` section must describe the **class** of situations, not the one conversation:

```markdown
## When to Use

**Load this skill when:**
- [Trigger scenario A] — description
- [Trigger scenario B] — description

**Don't use for:**
- [Counter-indication A]
- [Counter-indication B]
```

Bad: "Use when the user asks about Karpathy's guidelines"
Good: "Use when writing, reviewing, or refactoring code to avoid overcomplication"

### Step 5: Create the Skill

```python
skill_manage(
    action='create',
    name='skill-name',  # lowercase, hyphens, ≤64 chars
    category='appropriate-category',  # e.g. 'coding', 'devops', 'research'
    content="""
---
name: skill-name
description: One-line description starting with action verb — "Use when <trigger>. <what it does>."
version: 1.0.0
author: Hermes Agent (adapted from [source], see Attribution)
license: MIT
metadata:
  hermes:
    tags: [relevant, tags]
    related_skills: [related-skill-1, related-skill-2]
---

# Title

... (full markdown body)

---

## Attribution

Adapted from [source](original-url) ([license]).
"""
)
```

### Step 6: Add Hermes Tool Examples

In each principle section, show **concrete Hermes tool invocations**:

```markdown
## Principle: [Name]

**Core idea:** One sentence.

### ❌ Before (external-format)
> Abstract advice without tool mapping

### ✅ After (Hermetized)
```python
# ✅ In Hermes, this means:
terminal("pytest tests/ -v")  # Verify before starting
patch(
    path="src/file.py",
    old_string="old code",
    new_string="new code"  # Only what's needed
)
```
```

### Step 7: Verification

After creating, verify:

- [ ] `skill_manage` returned success
- [ ] `skill_view(name='new-skill')` loads correctly
- [ ] Description ≤ 1024 chars
- [ ] Frontmatter has `name`, `description`, `version`, `author`, `license`, `metadata.hermes.{tags, related_skills}`
- [ ] "When to Use" describes a class, not one session
- [ ] Each principle has Hermes-specific tool guidance
- [ ] Attribution to original source included

## Common Pitfalls

1. **Copying verbatim.** External content references external tools (Claude Code, Cursor). Replace with Hermes equivalents.
2. **Missing triggers.** A skill without "When to Use" won't be loaded at the right time.
3. **Too narrow.** "When user mentions Karpathy" vs "When writing/refactoring code" — the latter is correct.
4. **No tool mapping.** Abstract guidelines without `patch`/`todo`/`terminal` examples leave the user wondering how to apply them.
5. **Platform-specific instructions.** Don't include install instructions for other platforms (Claude Code plugins, Cursor rules, VS Code extensions). Focus on what's relevant in Hermes.
6. **Overwriting existing skills.** Before creating, `skills_list()` and check for overlap. Prefer patching an existing skill.

## Verification Checklist

- [ ] Skill created with `skill_manage(action='create')` — success
- [ ] Content adapted to Hermes tools and workflow
- [ ] Triggers describe a class, not a single case
- [ ] Attribution to original source included
- [ ] Source repo cleaned up: `terminal("rm -rf /tmp/source-skill")`

## Attribution

This skill generalizes the workflow used when importing `forrestchang/andrej-karpathy-skills` (MIT) into Hermes as the `karpathy-guidelines` skill.
