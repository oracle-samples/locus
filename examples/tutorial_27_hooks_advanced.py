"""
Tutorial 27: Advanced Hooks — Write-Protected Events, Cancel, Retry

This tutorial covers:
- Write-protected event objects (read-only fields raise AttributeError)
- Cancelling tool calls via event.cancel
- Retrying model calls via event.retry
- Reverse ordering of "after" hooks

Prerequisites:
- Configure model via environment variables

Difficulty: Advanced
"""

from config import get_model

from locus.agent import Agent, AgentConfig
from locus.hooks.provider import HookProvider
from locus.tools.decorator import tool


# =============================================================================
# Part 1: Cancel a dangerous tool call
# =============================================================================


def example_cancel_tool():
    """Hook that blocks dangerous tools using write-protected events."""
    print("=== Part 1: Cancel Tool via Hook ===\n")

    model = get_model()

    class SecurityHook(HookProvider):
        """Block any tool with 'delete' in its name."""

        @property
        def priority(self):
            return 50  # Security hooks run first

        async def on_before_tool_call(self, event):
            if "delete" in event.tool_name:
                event.cancel = f"BLOCKED: {event.tool_name} is forbidden"
                # event.tool_name = "hacked"  # This would raise AttributeError!

    @tool
    def delete_file(path: str) -> str:
        """Delete a file."""
        return f"Deleted {path}"

    @tool
    def read_file(path: str) -> str:
        """Read a file."""
        return f"Contents of {path}"

    agent = Agent(
        config=AgentConfig(
            system_prompt="You manage files. If blocked, tell the user.",
            max_iterations=5,
            model=model,
            tools=[delete_file, read_file],
            hooks=[SecurityHook()],
        )
    )

    result = agent.run_sync("Delete /tmp/secret.txt")
    print(f"Response: {result.message[:150]}")
    for te in result.tool_executions:
        print(f"  Tool: {te.tool_name} → {te.result}")


# =============================================================================
# Part 2: Write protection demo
# =============================================================================


def example_write_protection():
    """Demonstrate read-only fields on events."""
    print("\n=== Part 2: Write Protection ===\n")

    from locus.hooks.provider import BeforeToolCallEvent

    event = BeforeToolCallEvent(tool_name="test", tool_call_id="c1", arguments={"x": 1})

    # Writable fields work fine
    event.arguments = {"x": 2}
    event.cancel = "blocked"
    print(f"arguments (writable): {event.arguments}")
    print(f"cancel (writable): {event.cancel}")

    # Read-only fields raise
    try:
        event.tool_name = "hacked"
    except AttributeError as e:
        print(f"tool_name (read-only): {e}")

    # AI commentary so this Part also exercises the configured provider
    import time as _t

    agent = Agent(model=get_model(max_tokens=80), system_prompt="Reply in one short sentence.")
    t0 = _t.perf_counter()
    res = agent.run_sync(
        "In one sentence, why does Locus mark BeforeToolCallEvent.tool_name as "
        "read-only while letting hooks edit `arguments` and `cancel`?"
    )
    dt = _t.perf_counter() - t0
    print(
        f"  [OCI call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    print(f"  AI rationale: {res.message.strip()}")


if __name__ == "__main__":
    example_cancel_tool()
    example_write_protection()
