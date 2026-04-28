# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Structured output support - 100% Pydantic."""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Error parsing structured output."""

    def __init__(self, message: str, raw_content: str, errors: list[Any] | None = None):
        super().__init__(message)
        self.raw_content = raw_content
        self.errors = errors or []


class StructuredOutput(BaseModel):
    """Wrapper for structured output with validation."""

    raw: str
    parsed: BaseModel | None = None
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def success(self) -> bool:
        """Whether parsing succeeded."""
        return self.parsed is not None and self.error is None

    def unwrap(self) -> BaseModel:
        """Get parsed value or raise error."""
        if self.parsed is None:
            raise StructuredOutputError(
                self.error or "No parsed output",
                self.raw,
            )
        return self.parsed


def extract_json(content: str) -> str:
    """Extract JSON from content (handles markdown code blocks)."""
    content = content.strip()

    # Try to find JSON in code blocks
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        if end > start:
            return content[start:end].strip()

    if "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        if end > start:
            extracted = content[start:end].strip()
            # Skip language identifier if present
            if extracted and not extracted.startswith("{"):
                lines = extracted.split("\n", 1)
                if len(lines) > 1:
                    extracted = lines[1].strip()
            return extracted

    # Try to find raw JSON object
    if "{" in content:
        start = content.find("{")
        # Find matching closing brace
        depth = 0
        for i, char in enumerate(content[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start : i + 1]

    return content


def parse_structured(
    content: str,
    schema: type[T],
    strict: bool = True,
) -> StructuredOutput:
    """
    Parse content into a structured Pydantic model.

    Args:
        content: Raw content from model
        schema: Pydantic model class to parse into
        strict: Whether to raise on parse failure

    Returns:
        StructuredOutput with parsed model or error
    """
    try:
        # Extract JSON from content
        json_str = extract_json(content)

        # Parse JSON
        data = json.loads(json_str)

        # Validate with Pydantic
        parsed = schema.model_validate(data)

        return StructuredOutput(raw=content, parsed=parsed)

    except json.JSONDecodeError as e:
        error = f"JSON parse error: {e}"
        if strict:
            raise StructuredOutputError(error, content) from e
        return StructuredOutput(raw=content, error=error)

    except ValidationError as e:
        error = f"Validation error: {e}"
        if strict:
            raise StructuredOutputError(error, content, e.errors()) from e
        return StructuredOutput(raw=content, error=error)


def create_schema_prompt(schema: type[BaseModel]) -> str:
    """Create a prompt fragment describing the expected schema."""
    json_schema = schema.model_json_schema()

    # Clean up schema for prompt
    if "title" in json_schema:
        del json_schema["title"]

    return f"""Respond with a JSON object matching this schema:

```json
{json.dumps(json_schema, indent=2)}
```

Return ONLY the JSON object, no additional text."""


def create_output_instructions(schema: type[BaseModel]) -> str:
    """Create detailed instructions for structured output."""
    json_schema = schema.model_json_schema()
    properties = json_schema.get("properties", {})
    required = json_schema.get("required", [])

    lines = ["Your response must be a valid JSON object with these fields:", ""]

    for name, prop in properties.items():
        prop_type = prop.get("type", "any")
        description = prop.get("description", "")
        is_required = name in required
        req_marker = "(required)" if is_required else "(optional)"

        lines.append(f"- `{name}` ({prop_type}) {req_marker}: {description}")

    lines.extend(
        [
            "",
            "Return ONLY the JSON object. Do not include markdown code blocks or explanations.",
        ]
    )

    return "\n".join(lines)
