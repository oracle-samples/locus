# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for MCP integration utilities."""

import pytest
from pydantic import BaseModel

from locus.integrations.fastmcp import (
    _json_schema_type_to_python,
    _ToolArgsBase,
    build_args_model,
    locus_tool_to_mcp,
    mcp_tool_to_locus,
)
from locus.tools.decorator import tool


class TestJsonSchemaTypeToPython:
    """Tests for _json_schema_type_to_python."""

    def test_string_type(self):
        """Convert string type."""
        result = _json_schema_type_to_python({"type": "string"})
        assert result is str

    def test_integer_type(self):
        """Convert integer type."""
        result = _json_schema_type_to_python({"type": "integer"})
        assert result is int

    def test_number_type(self):
        """Convert number type."""
        result = _json_schema_type_to_python({"type": "number"})
        assert result is float

    def test_boolean_type(self):
        """Convert boolean type."""
        result = _json_schema_type_to_python({"type": "boolean"})
        assert result is bool

    def test_object_type(self):
        """Convert object type."""
        from typing import Any

        result = _json_schema_type_to_python({"type": "object"})
        assert result == dict[str, Any]

    def test_array_type_simple(self):
        """Convert simple array type."""
        result = _json_schema_type_to_python({"type": "array"})
        # Should return list[Any]
        assert "list" in str(result).lower()

    def test_array_type_with_items(self):
        """Convert array type with items schema."""
        result = _json_schema_type_to_python({"type": "array", "items": {"type": "string"}})
        # Should return list[str]
        assert "list" in str(result).lower()

    def test_nullable_type(self):
        """Handle nullable types (type as list)."""
        result = _json_schema_type_to_python({"type": ["string", "null"]})
        assert result is str

    def test_unknown_type(self):
        """Unknown type returns Any."""
        from typing import Any

        result = _json_schema_type_to_python({"type": "unknown"})
        assert result is Any


class TestBuildArgsModel:
    """Tests for build_args_model."""

    def test_simple_schema(self):
        """Build model from simple schema."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "User name"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }

        model = build_args_model("test_tool", schema)

        assert model is not None
        assert issubclass(model, BaseModel)
        assert "name" in model.model_fields
        assert "age" in model.model_fields

    def test_none_schema(self):
        """Return None for None schema."""
        result = build_args_model("test_tool", None)
        assert result is None

    def test_invalid_schema(self):
        """Return None for invalid schema."""
        result = build_args_model("test_tool", "not a dict")
        assert result is None

    def test_no_properties(self):
        """Return None if no properties."""
        result = build_args_model("test_tool", {"type": "object"})
        assert result is None

    def test_empty_properties(self):
        """Return None if properties empty."""
        result = build_args_model("test_tool", {"type": "object", "properties": {}})
        assert result is None

    def test_invalid_property(self):
        """Skip invalid property entries."""
        schema = {
            "properties": {
                "valid": {"type": "string"},
                "invalid": "not a dict",
            }
        }
        model = build_args_model("test_tool", schema)
        assert model is not None
        assert "valid" in model.model_fields
        assert "invalid" not in model.model_fields

    def test_with_defaults(self):
        """Handle default values."""
        schema = {
            "properties": {
                "name": {"type": "string", "default": "anonymous"},
            },
        }
        model = build_args_model("test_tool", schema)
        assert model is not None

    def test_model_name_sanitization(self):
        """Model name is sanitized."""
        schema = {"properties": {"x": {"type": "string"}}}
        model = build_args_model("my-tool name", schema)
        assert model is not None
        assert "_" in model.__name__  # Dashes/spaces replaced


class TestMcpToolToLocus:
    """Tests for mcp_tool_to_locus."""

    @pytest.mark.asyncio
    async def test_convert_basic_tool(self):
        """Convert basic MCP tool to Locus."""

        async def my_func(x: int) -> str:
            return f"result: {x}"

        locus_tool = mcp_tool_to_locus(
            name="my_tool",
            description="A test tool",
            func=my_func,
        )

        assert locus_tool.name == "my_tool"
        assert locus_tool.description == "A test tool"

    @pytest.mark.asyncio
    async def test_execute_converted_tool_string_result(self):
        """Converted tool returns string result as-is."""

        async def my_func(x: int) -> str:
            return f"result: {x}"

        locus_tool = mcp_tool_to_locus(
            name="my_tool",
            description="Test",
            func=my_func,
        )

        result = await locus_tool.execute(x=42)
        assert "result: 42" in result

    @pytest.mark.asyncio
    async def test_execute_converted_tool_dict_result(self):
        """Converted tool JSON-serializes non-string results."""

        async def my_func(x: int) -> dict:
            return {"value": x}

        locus_tool = mcp_tool_to_locus(
            name="my_tool",
            description="Test",
            func=my_func,
        )

        result = await locus_tool.execute(x=42)
        assert '"value": 42' in result or '"value":42' in result


class TestLocusToolToMcp:
    """Tests for locus_tool_to_mcp."""

    def test_convert_basic_tool(self):
        """Convert Locus tool to MCP schema."""

        @tool
        def my_tool(x: int) -> str:
            """A test tool."""
            return str(x)

        mcp_schema = locus_tool_to_mcp(my_tool)

        assert mcp_schema["name"] == "my_tool"
        assert mcp_schema["description"] == "A test tool."
        assert "inputSchema" in mcp_schema

    def test_convert_tool_without_description(self):
        """Handle tool without description."""

        @tool
        def bare_tool(x: int) -> str:
            return str(x)

        # Force no description
        bare_tool.description = None

        mcp_schema = locus_tool_to_mcp(bare_tool)
        assert mcp_schema["description"] == ""

    def test_convert_tool_without_parameters(self):
        """Handle tool without parameters."""

        @tool
        def no_params_tool() -> str:
            """No params."""
            return "done"

        # Force no parameters
        no_params_tool.parameters = None

        mcp_schema = locus_tool_to_mcp(no_params_tool)
        assert mcp_schema["inputSchema"] == {"type": "object", "properties": {}}


class TestToolArgsBase:
    """Tests for _ToolArgsBase."""

    def test_extra_forbid(self):
        """Extra fields are forbidden."""
        assert _ToolArgsBase.model_config.get("extra") == "forbid"
