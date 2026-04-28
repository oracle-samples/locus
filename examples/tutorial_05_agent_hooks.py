"""
Tutorial 05: Agent Hooks & Lifecycle

This tutorial covers:
- Lifecycle hooks (before/after invocation)
- Tool hooks (before/after tool calls)
- Building custom middleware
- Logging and telemetry hooks

Prerequisites: Tutorial 04 (Agent Streaming)
Difficulty: Intermediate
"""

from datetime import datetime

# Import shared config
from config import get_model, print_config

from locus.agent import Agent
from locus.hooks import HookPriority, HookProvider
from locus.tools import tool


# =============================================================================
# Part 1: Understanding Hooks
# =============================================================================


class SimpleLoggingHook(HookProvider):
    """A simple hook that logs agent lifecycle events."""

    @property
    def priority(self) -> int:
        return HookPriority.OBSERVABILITY_DEFAULT

    async def on_before_invocation(self, prompt, state):
        """Called before the agent starts processing."""
        print(f"  [HOOK] Starting: '{prompt[:50]}...'")
        return state

    async def on_after_invocation(self, state, success):
        """Called after the agent finishes."""
        print(f"  [HOOK] Finished: success={success}")

    async def on_before_tool_call(self, event):
        """Called before each tool execution."""
        print(f"  [HOOK] Tool call: {event.tool_name}({event.arguments})")

    async def on_after_tool_call(self, event):
        """Called after each tool execution."""
        if event.error:
            print(f"  [HOOK] Tool error: {event.tool_name} -> {event.error}")
        else:
            print(f"  [HOOK] Tool done: {event.tool_name} -> {str(event.result)[:50]}")


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def example_simple_hook():
    """Demonstrate basic hook usage."""
    print("=== Part 1: Understanding Hooks ===\n")

    model = get_model(max_tokens=100)

    # Create agent with a hook
    agent = Agent(
        model=model,
        tools=[add],
        system_prompt="Use the add tool for calculations.",
        hooks=[SimpleLoggingHook()],
    )

    print("Running agent with logging hook:\n")
    result = agent.run_sync("What is 5 + 3?")
    print(f"\nResult: {result.message}")
    print()


# =============================================================================
# Part 2: Timing Hook
# =============================================================================


class TimingHook(HookProvider):
    """Hook that measures execution time."""

    def __init__(self):
        self.start_time = None
        self.tool_times = {}

    @property
    def priority(self) -> int:
        return HookPriority.OBSERVABILITY_MIN

    async def on_before_invocation(self, prompt, state):
        self.start_time = datetime.now()
        self.tool_times = {}
        return state

    async def on_after_invocation(self, state, success):
        elapsed = (datetime.now() - self.start_time).total_seconds() * 1000
        print("\n  Timing Report:")
        print(f"    Total: {elapsed:.1f}ms")
        for name, ms in self.tool_times.items():
            print(f"    {name}: {ms:.1f}ms")

    async def on_before_tool_call(self, event):
        self.tool_times[event.tool_name] = datetime.now().timestamp() * 1000

    async def on_after_tool_call(self, event):
        start = self.tool_times.get(event.tool_name, 0)
        self.tool_times[event.tool_name] = (datetime.now().timestamp() * 1000) - start


def example_timing_hook():
    """Measure execution time with a hook."""
    print("=== Part 2: Timing Hook ===\n")

    model = get_model(max_tokens=100)

    agent = Agent(
        model=model,
        tools=[add],
        system_prompt="Use the add tool for calculations.",
        hooks=[TimingHook()],
    )

    result = agent.run_sync("Calculate 10 + 20")
    print(f"Result: {result.message}")
    print()


# =============================================================================
# Part 3: Validation Hook
# =============================================================================


class ValidationHook(HookProvider):
    """Hook that validates and modifies tool arguments."""

    def __init__(self, max_value: int = 1000):
        self.max_value = max_value
        self.blocked_count = 0

    @property
    def priority(self) -> int:
        return HookPriority.SECURITY_DEFAULT

    async def on_before_tool_call(self, event):
        """Validate arguments before tool execution."""
        if event.tool_name == "add":
            a = event.arguments.get("a", 0)
            b = event.arguments.get("b", 0)

            # Clamp values to max — event.arguments is writable.
            if a > self.max_value:
                print(f"  [VALIDATION] Clamping a={a} to {self.max_value}")
                event.arguments["a"] = self.max_value
            if b > self.max_value:
                print(f"  [VALIDATION] Clamping b={b} to {self.max_value}")
                event.arguments["b"] = self.max_value


def example_validation_hook():
    """Validate and modify tool arguments."""
    print("=== Part 3: Validation Hook ===\n")

    model = get_model(max_tokens=150)

    agent = Agent(
        model=model,
        tools=[add],
        system_prompt="Use the add tool. Try large numbers if asked.",
        hooks=[ValidationHook(max_value=100)],
    )

    result = agent.run_sync("Add 5000 and 3000")
    print(f"Result: {result.message}")
    print()


# =============================================================================
# Part 4: Multiple Hooks
# =============================================================================


class AuditHook(HookProvider):
    """Hook that records all tool calls for auditing."""

    def __init__(self):
        self.audit_log = []

    @property
    def priority(self) -> int:
        return HookPriority.BUSINESS_DEFAULT

    async def on_before_tool_call(self, event):
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tool": event.tool_name,
                "arguments": dict(event.arguments),
                "status": "started",
            }
        )

    async def on_after_tool_call(self, event):
        self.audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tool": event.tool_name,
                "result": str(event.result)[:100] if event.result else None,
                "error": event.error,
                "status": "completed" if not event.error else "failed",
            }
        )

    def get_log(self):
        return self.audit_log


def example_multiple_hooks():
    """Use multiple hooks together."""
    print("=== Part 4: Multiple Hooks ===\n")

    model = get_model(max_tokens=100)

    # Create multiple hooks
    timing = TimingHook()
    audit = AuditHook()

    # Hooks execute in priority order (lower = earlier)
    agent = Agent(
        model=model,
        tools=[add],
        system_prompt="Use the add tool.",
        hooks=[timing, audit],  # timing (priority 100) runs first, then audit (200)
    )

    result = agent.run_sync("What is 7 + 8?")
    print(f"Result: {result.message}")

    # Show audit log
    print("\nAudit Log:")
    for entry in audit.get_log():
        print(f"  {entry}")
    print()


# =============================================================================
# Part 5: Guardrails Hook
# =============================================================================


class GuardrailsHook(HookProvider):
    """Hook that enforces safety guardrails."""

    def __init__(self, blocked_patterns: list[str] | None = None):
        self.blocked_patterns = blocked_patterns or []
        self.blocked_calls = []

    @property
    def priority(self) -> int:
        return HookPriority.SECURITY_MIN  # Run first

    async def on_before_invocation(self, prompt, state):
        """Check prompt for blocked patterns."""
        prompt_lower = prompt.lower()
        for pattern in self.blocked_patterns:
            if pattern.lower() in prompt_lower:
                print(f"  [GUARDRAIL] Blocked pattern detected: '{pattern}'")
                # Could raise an exception to stop execution
        return state

    async def on_before_tool_call(self, event):
        """Check tool arguments for blocked patterns."""
        args_str = str(event.arguments).lower()
        for pattern in self.blocked_patterns:
            if pattern.lower() in args_str:
                self.blocked_calls.append(
                    {
                        "tool": event.tool_name,
                        "pattern": pattern,
                        "arguments": dict(event.arguments),
                    }
                )
                print(f"  [GUARDRAIL] Warning: '{pattern}' in {event.tool_name} args")


@tool
def process_text(text: str) -> str:
    """Process some text."""
    return f"Processed: {text}"


def example_guardrails_hook():
    """Enforce safety guardrails."""
    print("=== Part 5: Guardrails Hook ===\n")

    model = get_model(max_tokens=100)

    guardrails = GuardrailsHook(blocked_patterns=["password", "secret", "credit card"])

    agent = Agent(
        model=model,
        tools=[process_text],
        system_prompt="Process any text the user provides.",
        hooks=[guardrails],
    )

    # This should trigger a warning
    result = agent.run_sync("Process this text: 'my password is 1234'")
    print(f"Result: {result.message}")

    if guardrails.blocked_calls:
        print(f"\nBlocked calls detected: {len(guardrails.blocked_calls)}")
    print()


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 05: Agent Hooks & Lifecycle")
    print("=" * 60)
    print()

    print_config()
    print()

    example_simple_hook()
    example_timing_hook()
    example_validation_hook()
    example_multiple_hooks()
    example_guardrails_hook()

    print("=" * 60)
    print("Next: Tutorial 06 - Introduction to StateGraph")
    print("=" * 60)


if __name__ == "__main__":
    main()
