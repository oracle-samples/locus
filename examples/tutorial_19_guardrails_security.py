"""
Tutorial 19: Guardrails & Security

This tutorial demonstrates Locus's security features including
input validation, PII detection, content filtering, and tool restrictions.

Topics covered:
1. GuardrailsHook for comprehensive security
2. PII detection and redaction
3. Content filtering
4. Tool allowlists and blocklists
5. Custom security policies

Run with:
    python examples/tutorial_19_guardrails_security.py
"""

import asyncio

from config import print_config

from locus.core.state import AgentState
from locus.hooks import HookRegistry
from locus.hooks.builtin.guardrails import (
    ContentFilterHook,
    GuardrailAction,
    GuardrailConfig,
    GuardrailsHook,
    GuardrailViolation,
)


async def main():
    print("=" * 60)
    print("Tutorial 19: Guardrails & Security")
    print("=" * 60)
    print()
    print_config()

    # =========================================================================
    # Part 1: Basic Guardrail Configuration
    # =========================================================================
    print("\n=== Part 1: Basic Guardrail Configuration ===\n")

    # Create default guardrails configuration
    config = GuardrailConfig(
        # Tools that should never be called
        block_dangerous_tools=frozenset(
            {
                "eval",
                "exec",
                "system",
                "shell",
                "rm",
                "delete",
                "drop",
                "truncate",
            }
        ),
        # Maximum prompt length
        max_prompt_length=100000,
        # Maximum tool result length
        max_tool_result_length=50000,
        # Default action for violations
        default_action=GuardrailAction.BLOCK,
    )

    print("Guardrail Configuration:")
    print(f"  Blocked tools: {list(config.block_dangerous_tools)[:5]}...")
    print(f"  Max prompt length: {config.max_prompt_length:,}")
    print(f"  Default action: {config.default_action.value}")

    # =========================================================================
    # Part 2: Creating a Guardrails Hook
    # =========================================================================
    print("\n=== Part 2: Creating Guardrails Hook ===\n")

    # Track violations
    violations_log = []

    def on_violation(violation: GuardrailViolation):
        violations_log.append(violation)
        print(f"  VIOLATION: {violation.rule_name} - {violation.description}")

    guardrails = GuardrailsHook(
        config=config,
        on_violation=on_violation,
    )

    print(f"Guardrails Hook: {guardrails.name}")
    print(f"Priority: {guardrails.priority}")

    # =========================================================================
    # Part 3: PII Detection
    # =========================================================================
    print("\n=== Part 3: PII Detection ===\n")

    # Built-in PII patterns
    print("Built-in PII patterns:")
    for name, pattern in config.pii_patterns.items():
        print(f"  {name}: {pattern[:50]}...")

    # Test PII detection
    test_inputs = [
        "Contact me at john@example.com for details",
        "Call 555-123-4567 for support",
        "SSN: 123-45-6789",
        "Card: 4111-1111-1111-1111",
        "Server IP: 192.168.1.100",
        "No sensitive data here",
    ]

    state = AgentState(agent_id="test")

    print("\nPII Detection Results:")
    for text in test_inputs:
        # Clear previous violations
        guardrails.clear_violations()
        try:
            await guardrails.on_before_invocation(text, state)
            violations = guardrails.violations
            if violations:
                print(f"  '{text[:40]}...' -> DETECTED: {[v.rule_name for v in violations]}")
            else:
                print(f"  '{text[:40]}...' -> Clean")
        except ValueError as e:
            print(f"  '{text[:40]}...' -> BLOCKED: {e}")

    # =========================================================================
    # Part 4: Blocked Content Patterns
    # =========================================================================
    print("\n=== Part 4: Content Pattern Blocking ===\n")

    print("Built-in blocked patterns:")
    for name, pattern in config.blocked_content_patterns.items():
        print(f"  {name}: {pattern[:40]}...")

    # Test blocked content detection
    dangerous_inputs = [
        "DROP TABLE users;",
        "../../etc/passwd",
        "ls -la; rm -rf /",
        "Normal query SELECT * FROM users",
    ]

    print("\nContent Blocking Results:")
    for text in dangerous_inputs:
        guardrails.clear_violations()
        try:
            await guardrails.on_before_invocation(text, state)
            print(f"  '{text[:40]}...' -> Allowed")
        except ValueError:
            print(f"  '{text[:40]}...' -> BLOCKED")

    # =========================================================================
    # Part 5: Tool Restrictions
    # =========================================================================
    print("\n=== Part 5: Tool Restrictions ===\n")

    # Test tool blocking
    tool_tests = [
        ("read_file", {"path": "/app/data.txt"}),
        ("exec", {"code": "print('hello')"}),
        ("shell", {"command": "ls"}),
        ("search", {"query": "test"}),
    ]

    print("Tool Access Control:")
    from locus.core.events import BeforeToolCallEvent

    for tool_name, args in tool_tests:
        guardrails.clear_violations()
        try:
            await guardrails.on_before_tool_call(
                BeforeToolCallEvent(tool_name=tool_name, arguments=args)
            )
            print(f"  {tool_name} -> Allowed")
        except ValueError:
            print(f"  {tool_name} -> BLOCKED")

    # =========================================================================
    # Part 6: Tool Allowlist Mode
    # =========================================================================
    print("\n=== Part 6: Tool Allowlist Mode ===\n")

    # Create config with allowlist (only specified tools allowed)
    allowlist_config = GuardrailConfig(
        allow_only_tools=frozenset({"read_file", "search", "analyze"}),
    )

    allowlist_guardrails = GuardrailsHook(config=allowlist_config)

    tool_tests = ["read_file", "write_file", "search", "delete"]

    print("Allowlist mode (only read_file, search, analyze allowed):")
    for tool_name in tool_tests:
        try:
            await allowlist_guardrails.on_before_tool_call(
                BeforeToolCallEvent(tool_name=tool_name, arguments={})
            )
            print(f"  {tool_name} -> Allowed")
        except ValueError:
            print(f"  {tool_name} -> BLOCKED")

    # =========================================================================
    # Part 7: Action Types
    # =========================================================================
    print("\n=== Part 7: Action Types ===\n")

    for action in GuardrailAction:
        descriptions = {
            GuardrailAction.BLOCK: "Block the request entirely",
            GuardrailAction.WARN: "Log warning but allow",
            GuardrailAction.REDACT: "Redact sensitive content",
            GuardrailAction.ALLOW: "Allow without modification",
        }
        print(f"  {action.value}: {descriptions[action]}")

    # Configure different actions per rule
    custom_config = GuardrailConfig(
        default_action=GuardrailAction.BLOCK,
        action_overrides={
            "pii_email": GuardrailAction.REDACT,  # Redact emails
            "pii_phone_us": GuardrailAction.WARN,  # Warn on phone numbers
            "blocked_sql_injection": GuardrailAction.BLOCK,  # Block SQL injection
        },
    )

    print("\nCustom action overrides:")
    for rule, action in custom_config.action_overrides.items():
        print(f"  {rule} -> {action.value}")

    # =========================================================================
    # Part 8: Content Filter Hook (Simplified)
    # =========================================================================
    print("\n=== Part 8: Content Filter Hook ===\n")

    # Simplified content filter for common cases
    content_filter = ContentFilterHook(
        blocked_words=["password", "secret", "api_key"],
        blocked_patterns=[r"sk-[a-zA-Z0-9]+", r"ghp_[a-zA-Z0-9]+"],  # API keys
        max_input_length=10000,
        case_sensitive=False,
    )

    print(f"Content Filter: {content_filter.name}")

    # Test content filtering
    filter_tests = [
        "What's my password?",
        "Here's my api_key for access",
        "Token: sk-abc123xyz",
        "Normal question about coding",
    ]

    print("\nContent Filter Results:")
    for text in filter_tests:
        try:
            await content_filter.on_before_invocation(text, state)
            print(f"  '{text[:40]}...' -> Allowed")
        except ValueError as e:
            print(f"  '{text[:40]}...' -> BLOCKED: {e}")

    # =========================================================================
    # Part 9: Integrating with Hook Registry
    # =========================================================================
    print("\n=== Part 9: Registry Integration ===\n")

    # Create a hook registry with security hooks
    registry = HookRegistry()

    # Add guardrails with high priority (runs first)
    registry.add_provider(
        GuardrailsHook(
            config=GuardrailConfig(
                block_dangerous_tools=frozenset({"exec", "eval"}),
            ),
        )
    )

    # Add content filter
    registry.add_provider(
        ContentFilterHook(
            blocked_words=["forbidden"],
        )
    )

    print(f"Registry providers: {len(registry.providers)}")
    for provider in registry.providers:
        print(f"  - {provider.name} (priority: {provider.priority})")

    # =========================================================================
    # Part 10: Custom Security Policies
    # =========================================================================
    print("\n=== Part 10: Custom Security Policies ===\n")

    def create_production_guardrails():
        """Create strict guardrails for production."""
        return GuardrailConfig(
            block_dangerous_tools=frozenset(
                {
                    "exec",
                    "eval",
                    "system",
                    "shell",
                    "delete",
                    "drop",
                    "truncate",
                    "rm",
                    "sudo",
                    "chmod",
                    "chown",
                }
            ),
            max_prompt_length=50000,
            max_tool_result_length=25000,
            default_action=GuardrailAction.BLOCK,
            action_overrides={
                "pii_email": GuardrailAction.REDACT,
                "pii_ssn": GuardrailAction.BLOCK,
                "pii_credit_card": GuardrailAction.BLOCK,
            },
        )

    def create_development_guardrails():
        """Create relaxed guardrails for development."""
        return GuardrailConfig(
            block_dangerous_tools=frozenset({"exec", "eval"}),
            max_prompt_length=200000,
            max_tool_result_length=100000,
            default_action=GuardrailAction.WARN,
        )

    prod_config = create_production_guardrails()
    dev_config = create_development_guardrails()

    print("Production vs Development Settings:")
    print(
        f"  Blocked tools: {len(prod_config.block_dangerous_tools)} vs {len(dev_config.block_dangerous_tools)}"
    )
    print(f"  Max prompt: {prod_config.max_prompt_length:,} vs {dev_config.max_prompt_length:,}")
    print(
        f"  Default action: {prod_config.default_action.value} vs {dev_config.default_action.value}"
    )

    # =========================================================================
    # Part 11: Best Practices
    # =========================================================================
    print("\n=== Part 11: Best Practices ===\n")

    print("1. Always enable guardrails in production")
    print("2. Use allowlists for tools when possible")
    print("3. Redact PII rather than blocking when appropriate")
    print("4. Log all violations for security auditing")
    print("5. Set reasonable length limits")
    print("6. Test guardrails with adversarial inputs")
    print("7. Use different configs for dev/staging/prod")
    print("8. Regularly review and update blocked patterns")

    # Show violation history
    print(f"\nTotal violations detected in this tutorial: {len(violations_log)}")

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 20 - Checkpoint Backends")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
