# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 13: Structured Output — every part runs against a real LLM

This tutorial demonstrates structured output capabilities of the Locus
SDK. Every Part fires a real OCI gpt-5 call and prints
``[model call: X.XXs · prompt→completion tokens]`` so you can see the
network round-trip happen. The structured-output APIs being shown are
all real SDK features:

- ``locus.core.structured.extract_json``
- ``locus.core.structured.parse_structured`` / ``StructuredOutputError``
- ``locus.core.structured.create_schema_prompt`` /
  ``create_output_instructions``
- ``Agent(output_schema=YourPydanticModel)`` (constrained decoding +
  prompted-JSON fallback inside the agent loop)

Run with:
    python examples/tutorial_13_structured_output.py
"""

import time

from config import get_model
from pydantic import BaseModel, Field

from locus.agent import Agent
from locus.core.structured import (
    StructuredOutputError,
    create_output_instructions,
    create_schema_prompt,
    extract_json,
    parse_structured,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _banner(result, label: str = "") -> None:
    m = result.metrics
    tag = f" {label}" if label else ""
    print(
        f"  [model call{tag}: {m.duration_ms / 1000.0:.2f}s · "
        f"{m.prompt_tokens}→{m.completion_tokens} tokens]"
    )


def _llm_call(prompt: str, *, system: str = "Reply in one sentence.", max_tokens: int = 100) -> str:
    agent = Agent(model=get_model(max_tokens=max_tokens), system_prompt=system)
    t0 = time.perf_counter()
    res = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · "
        f"{res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    return res.message.strip()


# ---------------------------------------------------------------------------
# Pydantic shapes
# ---------------------------------------------------------------------------


class Person(BaseModel):
    name: str
    age: int
    email: str | None = None


class TaskResult(BaseModel):
    success: bool = Field(..., description="Whether the task succeeded")
    message: str = Field(..., description="Result message")
    score: float = Field(default=0.0, description="Confidence score 0-1")
    tags: list[str] = Field(default_factory=list, description="Related tags")


class Address(BaseModel):
    street: str
    city: str
    country: str = "USA"


class Company(BaseModel):
    name: str
    founded: int
    address: Address
    employees: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    summary: str = Field(..., description="Brief summary of findings")
    root_cause: str | None = Field(None, description="Root cause if identified")
    confidence: float = Field(..., description="Confidence level 0-1")
    recommendations: list[str] = Field(default_factory=list)
    requires_action: bool = Field(default=False)


class ToolSelection(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to use")
    arguments: dict = Field(default_factory=dict, description="Tool arguments")
    reasoning: str = Field(..., description="Why this tool was selected")


class Vendor(BaseModel):
    name: str = Field(..., description="Vendor brand name")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence 0-1")
    region: str = Field(..., description="Primary geographic region")


class VendorList(BaseModel):
    vendors: list[Vendor] = Field(..., description="Three picks")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main() -> None:
    from config import check_structured_output_capable

    check_structured_output_capable()
    print("=" * 60)
    print("Tutorial 13: Structured Output (every part calls gpt-5)")
    print("=" * 60)

    # =========================================================================
    # Part 1: Basic JSON extraction — model writes the JSON we then parse
    # =========================================================================
    print("\n=== Part 1: Basic JSON Extraction ===\n")
    raw = _llm_call(
        "Output a single JSON object with name=Alice and age=30 inside a "
        "```json fenced block. Nothing outside the fence.",
        system="Output only a fenced JSON block.",
        max_tokens=80,
    )
    extracted = extract_json(raw)
    print(f"  extract_json -> {extracted}")

    # =========================================================================
    # Part 2: Parsing into Pydantic models — agent provides the JSON
    # =========================================================================
    print("\n=== Part 2: Parsing into Pydantic Models ===\n")
    raw = _llm_call(
        "Output a single JSON object {name, age, email} for the person "
        "Diana, 28, diana@example.com. Inside a ```json block.",
        system="Output only the fenced JSON block. Nothing else.",
        max_tokens=120,
    )
    parsed = parse_structured(raw, Person, strict=False)
    print(f"  Success: {parsed.success}  Parsed: {parsed.parsed}")

    # =========================================================================
    # Part 3: Error handling — ask the model to deliberately produce broken
    #          input, then watch parse_structured handle it
    # =========================================================================
    print("\n=== Part 3: Error Handling ===\n")
    bad = _llm_call(
        "Reply with the literal string: This is not JSON.",
        system="Reply only with the requested string.",
        max_tokens=40,
    )
    bad_result = parse_structured(bad, Person, strict=False)
    print(f"  Invalid JSON - Success: {bad_result.success}  Error: {bad_result.error}")

    missing_age = _llm_call(
        "Output a JSON object with only the field name=Frank, NO age field. Inside ```json.",
        system="Output only the fenced JSON block.",
        max_tokens=80,
    )
    missing_result = parse_structured(missing_age, Person, strict=False)
    print(f"  Missing-field - Success: {missing_result.success}  Error: {missing_result.error}")
    try:
        parse_structured("invalid", Person, strict=True)
    except StructuredOutputError as e:
        print(f"  Strict mode raised {type(e).__name__}")

    # =========================================================================
    # Part 4: Schema prompts — give the model the schema, ask it to comply
    # =========================================================================
    print("\n=== Part 4: Creating Schema Prompts ===\n")
    schema_prompt = create_schema_prompt(TaskResult)
    print(f"  schema_prompt (head): {schema_prompt[:160]}...")
    instructions = create_output_instructions(TaskResult)
    raw = _llm_call(
        "Following these instructions, return a JSON for a successful "
        "deploy of service `orders-api`:\n" + instructions,
        system="Output only a fenced JSON block matching the schema.",
        max_tokens=200,
    )
    out = parse_structured(raw, TaskResult, strict=False)
    if out.success:
        print(
            f"  Parsed: success={out.parsed.success} message='{out.parsed.message}' "
            f"tags={out.parsed.tags}"
        )
    else:
        print(f"  Parse error: {out.error}")

    # =========================================================================
    # Part 5: Complex nested structures — model produces a Company
    # =========================================================================
    print("\n=== Part 5: Complex Nested Structures ===\n")
    nested = _llm_call(
        "Output a JSON for a company TechCorp, founded 2020, address "
        "(street '123 Main St', city 'San Francisco', country 'USA'), "
        "employees [Alice, Bob, Charlie]. Inside ```json.",
        system="Output only the fenced JSON block.",
        max_tokens=240,
    )
    company_res = parse_structured(nested, Company, strict=False)
    if company_res.success:
        c = company_res.parsed
        print(f"  Company: {c.name} (founded {c.founded}, {c.address.city})")
        print(f"  Employees: {', '.join(c.employees)}")
    else:
        print(f"  Parse error: {company_res.error}")

    # =========================================================================
    # Part 6: Real-world pattern — agent diagnoses an incident in JSON
    # =========================================================================
    print("\n=== Part 6: Real-world AnalysisResult ===\n")
    raw = _llm_call(
        "Diagnose an incident: 'connection pool saturated, P99=2500ms'. "
        "Return an AnalysisResult JSON inside ```json with fields summary, "
        "root_cause, confidence, recommendations, requires_action.",
        system="Output only the fenced JSON block.",
        max_tokens=300,
    )
    analysis_res = parse_structured(raw, AnalysisResult, strict=False)
    if analysis_res.success:
        a = analysis_res.parsed
        print(f"  Summary: {a.summary}")
        print(f"  Root cause: {a.root_cause}")
        print(f"  Confidence: {a.confidence:.0%}")
        print(f"  Requires action: {a.requires_action}")
        for rec in a.recommendations:
            print(f"    - {rec}")
    else:
        print(f"  Parse error: {analysis_res.error}")

    # =========================================================================
    # Part 7: Agent system-prompt pattern with ToolSelection
    # =========================================================================
    print("\n=== Part 7: Agent ToolSelection prompt ===\n")
    sys_prompt = (
        "You are an AI assistant with access to tools.\n\n"
        + create_output_instructions(ToolSelection)
        + "\nThink before selecting."
    )
    pick = _llm_call(
        "We need to look up a customer email. Pick the right tool and reply with the JSON.",
        system=sys_prompt,
        max_tokens=200,
    )
    pick_res = parse_structured(pick, ToolSelection, strict=False)
    if pick_res.success:
        ts = pick_res.parsed
        print(f"  tool={ts.tool_name}  args={ts.arguments}")
        print(f"  reasoning={ts.reasoning}")
    else:
        print(f"  Parse error: {pick_res.error}")

    # =========================================================================
    # Part 8: Agent(output_schema=…) — typed result via the SDK directly
    # =========================================================================
    print("\n=== Part 8: Agent(output_schema=VendorList) ===\n")
    live_agent = Agent(
        model=get_model(max_tokens=300),
        output_schema=VendorList,
        system_prompt=(
            "You are a cloud-procurement analyst. Recommend exactly three "
            "cloud vendors as a structured list."
        ),
    )
    t0 = time.perf_counter()
    live = live_agent.run_sync("Top three cloud vendors for a $2M enterprise compute spend.")
    dt = time.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · "
        f"{live.metrics.prompt_tokens}→{live.metrics.completion_tokens} tokens]"
    )
    picks: VendorList | None = live.parsed
    if not isinstance(picks, VendorList):
        raise TypeError(
            "Vendor agent returned no parsed VendorList. The configured model "
            "could not honor the JSON schema. Use a stronger model "
            "(e.g. openai.gpt-4o, openai.gpt-5, anthropic.claude-3-5-sonnet) "
            f"for tutorial 13 (Part 8). Raw output: {live.message!r}"
        )
    for v in picks.vendors:
        print(f"  {v.name:<14}  score={v.score:.2f}  region={v.region}")

    print("\n" + "=" * 60)
    print("Next: Tutorial 14 - Reasoning Patterns")
    print("=" * 60)


if __name__ == "__main__":
    main()
