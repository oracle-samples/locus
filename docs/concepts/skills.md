# Skills

Skills are filesystem-first capability disclosure — the
[AgentSkills.io](https://agentskills.io) pattern. Drop a folder with a
`SKILL.md`, a few example files, and a tool definition; the agent
loads it on demand.

```text
my_skill/
├── SKILL.md         # frontmatter + body — what the skill is, when to use it
├── examples/
│   ├── one.md
│   └── two.md
└── tools/
    └── analyse.py
```

```python
from locus.skills import Skill

researcher = Skill.from_file("./my_skill/SKILL.md")
agent = Agent(model=..., skills=[researcher])
```

The agent reads the `SKILL.md` body when the skill seems relevant
(progressive disclosure — the model doesn't load everything at every
turn). Tools defined inside the skill folder become available when the
skill is loaded.

## Why filesystem-first

- Agent capabilities are version-controllable like any other code.
- Non-engineers can edit a skill (it's mostly markdown).
- Skills are sharable across projects via plain `git clone`.
- Easy to grep, easy to diff, easy to remove.

## SKILL.md shape

```markdown
---
name: vendor-research
description: Read the vendor catalogue and quote prices. Use when the task is a sourcing decision.
when_to_use: When the prompt names "vendor", "price", "RFP", or asks for sourcing options.
tools: ["./tools/lookup.py", "./tools/quote.py"]
---

# Vendor Research

Long-form context the agent reads when the skill loads. Examples,
constraints, error patterns to avoid, escalation rules.
```

Frontmatter is structured (loaded as metadata); the body is what the
agent reads.

## When to use

- A reusable capability that crosses agents (research, summarisation,
  bug-triage).
- Knowledge that's easier to write in markdown than to encode in a
  system prompt.
- Capabilities that need their own tools.

## Tutorial

[`tutorial_32_skills.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_32_skills.py).

## Source

`src/locus/skills/`.
