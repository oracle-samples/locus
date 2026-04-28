"""
Tutorial 32: Skills — AgentSkills.io Progressive Disclosure

This tutorial covers:
- Skill: packaged instruction bundles (SKILL.md)
- SkillsPlugin: progressive disclosure (catalog → instructions → resources)
- Loading skills from filesystem
- Creating skills programmatically

Prerequisites:
- Configure model via environment variables

Difficulty: Intermediate
"""

from pathlib import Path

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.skills import Skill


# =============================================================================
# Part 1: Programmatic Skills
# =============================================================================


def example_programmatic():
    """Create skills in code without SKILL.md files."""
    print("=== Part 1: Programmatic Skills ===\n")

    model = get_model()

    code_review = Skill(
        name="code-review",
        description="Use when reviewing code for bugs and security issues.",
        instructions=(
            "# Code Review Checklist\n"
            "1. Check for SQL injection\n"
            "2. Check for hardcoded credentials\n"
            "3. Check error handling\n"
            "4. Report findings as: FINDING: <description>"
        ),
    )

    agent = Agent(config=AgentConfig(
        system_prompt="You are a security reviewer. Use available skills.",
        max_iterations=5, model=model,
        skills=[code_review],
    ))

    result = agent.run_sync(
        "Review: def login(u,p): return db.query(f'SELECT * FROM users WHERE name={u}')"
    )
    print(f"Response: {result.message[:200]}...")

    # Check if skill was activated
    skills_used = [te for te in result.tool_executions if te.tool_name == "skills"]
    print(f"Skills activated: {len(skills_used)}")


# =============================================================================
# Part 2: Load Skills from Filesystem
# =============================================================================


def example_filesystem():
    """Load skills from SKILL.md files."""
    print("\n=== Part 2: Filesystem Skills ===\n")

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.exists():
        skills = Skill.from_directory(skills_dir)
        print(f"Loaded {len(skills)} skills:")
        for s in skills:
            print(f"  - {s.name}: {s.description[:60]}...")
    else:
        print("No skills directory found. Create examples/skills/my-skill/SKILL.md")


# =============================================================================
# Part 3: SKILL.md Format
# =============================================================================


def example_format():
    """Show the SKILL.md file format."""
    print("\n=== Part 3: SKILL.md Format ===\n")

    print("""
---
name: my-skill
description: Use when the user asks about X.
allowed-tools: search analyze
metadata:
  author: your-name
  version: "1.0"
---

# Instructions for the Agent

1. First, do this
2. Then, do that
3. Finally, summarize

## Resource Files
Place additional files in:
- scripts/   — executable code
- references/ — documentation
- assets/    — templates, data
    """)


if __name__ == "__main__":
    example_programmatic()
    example_filesystem()
    example_format()
