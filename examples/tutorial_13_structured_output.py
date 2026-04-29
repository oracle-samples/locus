"""
Tutorial 13: Structured Output

This tutorial demonstrates how to get structured, typed responses from
language models using Pydantic models.

Topics covered:
1. Parsing model output into Pydantic models
2. JSON extraction from code blocks
3. Creating schema prompts
4. Handling parse errors gracefully
5. Complex nested structures

Run with:
    python examples/tutorial_13_structured_output.py
"""

from pydantic import BaseModel, Field

from locus.core.structured import (
    StructuredOutputError,
    create_output_instructions,
    create_schema_prompt,
    extract_json,
    parse_structured,
)


def main():
    print("=" * 60)
    print("Tutorial 13: Structured Output")
    print("=" * 60)

    # =========================================================================
    # Part 1: Basic JSON Extraction
    # =========================================================================
    print("\n=== Part 1: Basic JSON Extraction ===\n")

    # Extract JSON from plain text
    raw_text = '{"name": "Alice", "age": 30}'
    extracted = extract_json(raw_text)
    print(f"Plain text: {extracted}")

    # Extract JSON from markdown code blocks
    markdown_text = """Here's the result:
```json
{"name": "Bob", "age": 25}
```
"""
    extracted = extract_json(markdown_text)
    print(f"From markdown: {extracted}")

    # Extract from generic code block
    generic_block = """
```
{"name": "Charlie", "age": 35}
```
"""
    extracted = extract_json(generic_block)
    print(f"From generic block: {extracted}")

    # =========================================================================
    # Part 2: Parsing into Pydantic Models
    # =========================================================================
    print("\n=== Part 2: Parsing into Pydantic Models ===\n")

    class Person(BaseModel):
        """A person with name and age."""

        name: str
        age: int
        email: str | None = None

    # Successful parse
    content = '{"name": "Diana", "age": 28, "email": "diana@example.com"}'
    result = parse_structured(content, Person, strict=False)

    print(f"Success: {result.success}")
    print(f"Parsed: {result.parsed}")
    print(f"Raw: {result.raw}")

    # Parse with optional field missing
    content = '{"name": "Eve", "age": 22}'
    result = parse_structured(content, Person, strict=False)
    print(f"\nWith missing optional: {result.parsed}")

    # =========================================================================
    # Part 3: Error Handling
    # =========================================================================
    print("\n=== Part 3: Error Handling ===\n")

    # Invalid JSON (non-strict mode returns error in result)
    content = "not valid json"
    result = parse_structured(content, Person, strict=False)
    print(f"Invalid JSON - Success: {result.success}")
    print(f"Error: {result.error}")

    # Missing required field
    content = '{"name": "Frank"}'  # Missing 'age'
    result = parse_structured(content, Person, strict=False)
    print(f"\nMissing field - Success: {result.success}")
    print(f"Error: {result.error}")

    # Strict mode raises exception
    try:
        parse_structured("invalid", Person, strict=True)
    except StructuredOutputError as e:
        print(f"\nStrict mode exception: {type(e).__name__}")
        print(f"Raw content: {e.raw_content}")

    # =========================================================================
    # Part 4: Creating Schema Prompts
    # =========================================================================
    print("\n=== Part 4: Creating Schema Prompts ===\n")

    class TaskResult(BaseModel):
        """Result of a task execution."""

        success: bool = Field(..., description="Whether the task succeeded")
        message: str = Field(..., description="Result message")
        score: float = Field(default=0.0, description="Confidence score 0-1")
        tags: list[str] = Field(default_factory=list, description="Related tags")

    # Create prompt for the schema
    prompt = create_schema_prompt(TaskResult)
    print("Schema prompt:")
    print(prompt[:300] + "...")

    # Create detailed instructions
    instructions = create_output_instructions(TaskResult)
    print("\n\nOutput instructions:")
    print(instructions)

    # =========================================================================
    # Part 5: Complex Nested Structures
    # =========================================================================
    print("\n=== Part 5: Complex Nested Structures ===\n")

    class Address(BaseModel):
        """Physical address."""

        street: str
        city: str
        country: str = "USA"

    class Company(BaseModel):
        """Company information."""

        name: str
        founded: int
        address: Address
        employees: list[str] = Field(default_factory=list)

    complex_json = """
```json
{
    "name": "TechCorp",
    "founded": 2020,
    "address": {
        "street": "123 Main St",
        "city": "San Francisco",
        "country": "USA"
    },
    "employees": ["Alice", "Bob", "Charlie"]
}
```
"""

    result = parse_structured(complex_json, Company, strict=False)
    if result.success:
        company = result.parsed
        print(f"Company: {company.name}")
        print(f"Founded: {company.founded}")
        print(f"Location: {company.address.city}, {company.address.country}")
        print(f"Employees: {', '.join(company.employees)}")
    else:
        print(f"Parse error: {result.error}")

    # =========================================================================
    # Part 6: Real-World Pattern - Agent Response Parsing
    # =========================================================================
    print("\n=== Part 6: Real-World Pattern ===\n")

    class AnalysisResult(BaseModel):
        """Structured analysis result from an agent."""

        summary: str = Field(..., description="Brief summary of findings")
        root_cause: str | None = Field(None, description="Root cause if identified")
        confidence: float = Field(..., description="Confidence level 0-1")
        recommendations: list[str] = Field(default_factory=list)
        requires_action: bool = Field(default=False)

    # Simulate a model response with embedded JSON
    model_response = """Based on my analysis, here are the findings:

```json
{
    "summary": "Database connection pool exhaustion causing timeouts",
    "root_cause": "Connection leak in user service",
    "confidence": 0.85,
    "recommendations": [
        "Add connection pool monitoring",
        "Fix connection leak in UserRepository.findById()",
        "Increase pool size as temporary mitigation"
    ],
    "requires_action": true
}
```

Let me know if you need more details."""

    result = parse_structured(model_response, AnalysisResult, strict=False)
    if result.success:
        analysis = result.parsed
        print(f"Summary: {analysis.summary}")
        print(f"Root Cause: {analysis.root_cause}")
        print(f"Confidence: {analysis.confidence:.0%}")
        print(f"Requires Action: {analysis.requires_action}")
        print("Recommendations:")
        for rec in analysis.recommendations:
            print(f"  - {rec}")
    else:
        print(f"Failed to parse: {result.error}")

    # =========================================================================
    # Part 7: Using with Agent Prompts
    # =========================================================================
    print("\n=== Part 7: Agent System Prompt Pattern ===\n")

    class ToolSelection(BaseModel):
        """Tool selection decision."""

        tool_name: str = Field(..., description="Name of the tool to use")
        arguments: dict = Field(default_factory=dict, description="Tool arguments")
        reasoning: str = Field(..., description="Why this tool was selected")

    # Create a complete system prompt with output format
    system_prompt = f"""You are an AI assistant with access to various tools.

When you decide to use a tool, respond with a JSON object.

{create_output_instructions(ToolSelection)}

Think step by step before selecting a tool."""

    print("System prompt for structured tool selection:")
    print("-" * 40)
    print(system_prompt[:500] + "...")

    # =========================================================================
    # Part 8: Agent Integration — output_schema=
    # =========================================================================
    print("\n=== Part 8: Agent output_schema= ===\n")

    print(
        "When you want the agent's final answer to fill a shape, set\n"
        "`output_schema=YourPydanticModel` on the Agent constructor. The\n"
        "agent's last assistant message is parsed into an instance of that\n"
        "model and surfaced on `AgentResult.parsed`. On supporting providers\n"
        "(OpenAI / OCI OpenAI-compat) the request also carries a strict\n"
        "`response_format` for constrained decoding; on other providers\n"
        "locus falls back to prompted JSON + validate-and-retry.\n"
    )

    print("Sketch (requires real model credentials to run):\n")
    print(
        """    from pydantic import BaseModel, Field
    from locus import Agent

    class Vendor(BaseModel):
        name: str
        score: float = Field(ge=0.0, le=1.0)
        region: str

    class VendorList(BaseModel):
        vendors: list[Vendor]

    agent = Agent(
        model="oci:openai.gpt-5-mini",
        output_schema=VendorList,
        output_schema_retries=2,        # default
        system_prompt="Pick three vendors for cloud hosting.",
    )

    result = agent.run_sync("Top three for $2M of cloud spend.")
    picks: VendorList = result.parsed   # type: ignore[assignment]
    for v in picks.vendors:
        print(v.name, v.score, v.region)
"""
    )

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 14 - Reasoning Patterns")
    print("=" * 60)


if __name__ == "__main__":
    main()
