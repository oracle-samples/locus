"""
Tutorial 19: Guardrails & Security — every part runs a real Agent

Every Part fires the configured GenAI provider. Each section prints
``[OCI call: X.XXs · prompt→completion tokens]`` so you can see the
network round-trip happen, and the SDK feature being demonstrated
(``GuardrailsHook``, ``ContentFilterHook``, ``HookRegistry``,
``GuardrailConfig``, ``GuardrailAction``) is exercised on top of a real
agent loop wherever it makes sense.

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
import time

from config import get_model, print_config

from locus.agent import Agent
from locus.core.events import BeforeToolCallEvent
from locus.core.state import AgentState
from locus.hooks import HookRegistry
from locus.hooks.builtin.guardrails import (
    ContentFilterHook,
    GuardrailAction,
    GuardrailConfig,
    GuardrailsHook,
    GuardrailViolation,
)


# ---------------------------------------------------------------------------
# Helper: one-shot LLM call with a banner showing the round-trip cost.
# Used by every Part to *prove* the model is being called.
# ---------------------------------------------------------------------------


def _llm_call(
    prompt: str,
    *,
    system: str = "Reply in one short sentence.",
    max_tokens: int = 100,
    hooks: list | None = None,
) -> str:
    agent = Agent(
        model=get_model(max_tokens=max_tokens),
        system_prompt=system,
        hooks=hooks,
    )
    t0 = time.perf_counter()
    result = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [OCI call: {dt:.2f}s · "
        f"{result.metrics.prompt_tokens}→{result.metrics.completion_tokens} tokens]"
    )
    return result.message.strip()


async def main():
    print("=" * 60)
    print("Tutorial 19: Guardrails & Security (every part calls gpt-5)")
    print("=" * 60)
    print()
    print_config()

    # =========================================================================
    # Part 1: Basic Guardrail Configuration — model summarises the policy
    # =========================================================================
    print("\n=== Part 1: Basic Guardrail Configuration ===\n")
    config = GuardrailConfig(
        block_dangerous_tools=frozenset(
            {"eval", "exec", "system", "shell", "rm", "delete", "drop", "truncate"}
        ),
        max_prompt_length=100000,
        max_tool_result_length=50000,
        default_action=GuardrailAction.BLOCK,
    )
    print(f"  block_dangerous_tools: {sorted(config.block_dangerous_tools)[:5]}…")
    print(f"  max_prompt_length: {config.max_prompt_length:,}")
    print(f"  default_action: {config.default_action.value}")
    summary = _llm_call(
        "In one sentence, summarise what a security policy that blocks "
        "{eval, exec, system, shell, rm, delete, drop, truncate} protects "
        "an LLM agent against.",
        max_tokens=80,
    )
    print(f"AI policy summary: {summary}")

    # =========================================================================
    # Part 2: Creating a GuardrailsHook + running a real agent through it
    # =========================================================================
    print("\n=== Part 2: GuardrailsHook on a live agent ===\n")
    violations_log: list[GuardrailViolation] = []

    def on_violation(v: GuardrailViolation):
        violations_log.append(v)
        print(f"  VIOLATION: {v.rule_name} - {v.description}")

    guardrails = GuardrailsHook(config=config, on_violation=on_violation)
    print(f"  Hook: {guardrails.name}, priority={guardrails.priority}")
    answer = _llm_call(
        "What's a sensible default password policy length?",
        system="Reply in one short sentence.",
        hooks=[guardrails],
    )
    print(f"Guarded answer: {answer}")

    # =========================================================================
    # Part 3: PII detection — exercised on the SDK + AI for explanation
    # =========================================================================
    print("\n=== Part 3: PII Detection ===\n")
    print("Built-in PII patterns:")
    for name in list(config.pii_patterns)[:5]:
        print(f"  - {name}")

    test_inputs = [
        "Contact me at john@example.com for details",
        "Call 555-123-4567 for support",
        "SSN: 123-45-6789",
        "No sensitive data here",
    ]
    state = AgentState(agent_id="test")
    print("\nSDK-side PII detection:")
    for text in test_inputs:
        guardrails.clear_violations()
        try:
            await guardrails.on_before_invocation(text, state)
            seen = guardrails.violations
            label = ", ".join(v.rule_name for v in seen) if seen else "Clean"
            print(f"  '{text[:40]}…' -> {label}")
        except ValueError as e:
            print(f"  '{text[:40]}…' -> BLOCKED: {e}")

    pii_advice = _llm_call(
        "Give one concrete piece of advice for an SRE on what to do when an "
        "LLM application logs PII like emails or SSNs.",
        max_tokens=80,
    )
    print(f"AI advice: {pii_advice}")

    # =========================================================================
    # Part 4: Content blocking — model explains the categories
    # =========================================================================
    print("\n=== Part 4: Content Pattern Blocking ===\n")
    dangerous_inputs = [
        "DROP TABLE users;",
        "../../etc/passwd",
        "ls -la; rm -rf /",
        "Normal query SELECT * FROM users",
    ]
    for text in dangerous_inputs:
        guardrails.clear_violations()
        try:
            await guardrails.on_before_invocation(text, state)
            print(f"  '{text[:40]}…' -> Allowed")
        except ValueError:
            print(f"  '{text[:40]}…' -> BLOCKED")
    risk_summary = _llm_call(
        "List the top three classes of malicious input an LLM service should "
        "filter at the gateway. Three short bullets.",
        max_tokens=120,
    )
    print(f"AI risk summary:\n{risk_summary}")

    # =========================================================================
    # Part 5: Tool restriction — tested on the SDK + AI rationale
    # =========================================================================
    print("\n=== Part 5: Tool Restrictions ===\n")
    tool_tests = [
        ("read_file", {"path": "/app/data.txt"}),
        ("exec", {"code": "print('hello')"}),
        ("shell", {"command": "ls"}),
        ("search", {"query": "test"}),
    ]
    for name, args in tool_tests:
        guardrails.clear_violations()
        try:
            await guardrails.on_before_tool_call(
                BeforeToolCallEvent(tool_name=name, arguments=args)
            )
            print(f"  {name} -> Allowed")
        except ValueError:
            print(f"  {name} -> BLOCKED")
    rationale = _llm_call(
        "Why is it dangerous to expose `exec` or `shell` tools to an LLM agent?",
        max_tokens=80,
    )
    print(f"AI rationale: {rationale}")

    # =========================================================================
    # Part 6: Tool allowlist mode + AI explanation of denylist vs allowlist
    # =========================================================================
    print("\n=== Part 6: Tool Allowlist Mode ===\n")
    allowlist_config = GuardrailConfig(
        allow_only_tools=frozenset({"read_file", "search", "analyze"})
    )
    allowlist_guardrails = GuardrailsHook(config=allowlist_config)
    for name in ["read_file", "write_file", "search", "delete"]:
        try:
            await allowlist_guardrails.on_before_tool_call(
                BeforeToolCallEvent(tool_name=name, arguments={})
            )
            print(f"  {name} -> Allowed")
        except ValueError:
            print(f"  {name} -> BLOCKED")
    contrast = _llm_call(
        "In one sentence, compare allowlist vs denylist for tool access in an "
        "LLM agent — which is safer and why?",
        max_tokens=80,
    )
    print(f"AI contrast: {contrast}")

    # =========================================================================
    # Part 7: Action types — model explains REDACT vs BLOCK vs WARN
    # =========================================================================
    print("\n=== Part 7: Action Types ===\n")
    for action in GuardrailAction:
        print(f"  {action.value}")
    custom_config = GuardrailConfig(
        default_action=GuardrailAction.BLOCK,
        action_overrides={
            "pii_email": GuardrailAction.REDACT,
            "pii_phone_us": GuardrailAction.WARN,
            "blocked_sql_injection": GuardrailAction.BLOCK,
        },
    )
    print("\naction_overrides:")
    for rule, act in custom_config.action_overrides.items():
        print(f"  {rule} -> {act.value}")
    explainer = _llm_call(
        "Briefly explain when an LLM service should REDACT vs BLOCK vs WARN "
        "on policy violations. One sentence per action.",
        max_tokens=140,
    )
    print(f"AI explainer:\n{explainer}")

    # =========================================================================
    # Part 8: ContentFilterHook — wired into a real Agent
    # =========================================================================
    print("\n=== Part 8: ContentFilterHook on a live agent ===\n")
    content_filter = ContentFilterHook(
        blocked_words=["password", "secret", "api_key"],
        blocked_patterns=[r"sk-[a-zA-Z0-9]+", r"ghp_[a-zA-Z0-9]+"],
        max_input_length=10000,
        case_sensitive=False,
    )
    benign = _llm_call(
        "Suggest one good practice for handling developer credentials in CI.",
        hooks=[content_filter],
    )
    print(f"Filtered answer: {benign}")
    try:
        _llm_call("What's my password?", hooks=[content_filter])
    except Exception as e:  # noqa: BLE001
        print(f"  (filter blocked the input as expected: {type(e).__name__})")

    # =========================================================================
    # Part 9: Stack hooks via HookRegistry on a live Agent
    # =========================================================================
    print("\n=== Part 9: Stacking guardrail hooks ===\n")
    registry = HookRegistry()
    registry.add_provider(
        GuardrailsHook(config=GuardrailConfig(block_dangerous_tools=frozenset({"exec", "eval"})))
    )
    registry.add_provider(ContentFilterHook(blocked_words=["forbidden"]))
    print("Registered hook providers:")
    for prov in registry.providers:
        print(f"  - {prov.name} (priority={prov.priority})")
    stacked = _llm_call(
        "Name two security risks of giving an LLM agent unrestricted shell "
        "access. One bullet each.",
        hooks=[
            GuardrailsHook(
                config=GuardrailConfig(block_dangerous_tools=frozenset({"exec", "eval"}))
            ),
            ContentFilterHook(blocked_words=["forbidden"]),
        ],
    )
    print(f"Stacked-hooks answer: {stacked}")

    # =========================================================================
    # Part 10: Custom security policies — AI proposes prod vs dev defaults
    # =========================================================================
    print("\n=== Part 10: Custom Security Policies ===\n")

    def production_config() -> GuardrailConfig:
        return GuardrailConfig(
            block_dangerous_tools=frozenset(
                {"exec", "eval", "system", "shell", "delete", "drop", "truncate", "rm", "sudo"}
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

    def development_config() -> GuardrailConfig:
        return GuardrailConfig(
            block_dangerous_tools=frozenset({"exec", "eval"}),
            max_prompt_length=200000,
            max_tool_result_length=100000,
            default_action=GuardrailAction.WARN,
        )

    prod = production_config()
    dev = development_config()
    print(
        f"prod blocks {len(prod.block_dangerous_tools)} tools, "
        f"dev blocks {len(dev.block_dangerous_tools)}; "
        f"prod default={prod.default_action.value}, dev default={dev.default_action.value}"
    )
    suggestion = _llm_call(
        "List one extra guardrail rule a fintech company should add on top of "
        "blocking shell tools. One short sentence.",
        max_tokens=80,
    )
    print(f"AI suggestion: {suggestion}")

    # =========================================================================
    # Part 11: Best practices — model writes the cheat-sheet
    # =========================================================================
    print("\n=== Part 11: Best Practices ===\n")
    best = _llm_call(
        "Write a six-line cheat sheet of best practices for guarding LLM "
        "agents in production. Six bullets, terse.",
        max_tokens=240,
    )
    print(best)

    # =========================================================================
    # Part 12: Live Agent guarded by GuardrailsHook (already AI-driven)
    # =========================================================================
    print("\n=== Part 12: Live Agent + Guardrails ===\n")
    safe_guardrails = GuardrailsHook(
        config=GuardrailConfig(
            block_dangerous_tools=frozenset({"exec", "eval", "shell"}),
            default_action=GuardrailAction.WARN,
        ),
    )
    safe_agent = Agent(
        model=get_model(max_tokens=200),
        system_prompt=(
            "You are a friendly assistant. Refuse to share secrets or "
            "anything the guardrails would block."
        ),
        hooks=[safe_guardrails],
    )
    t0 = time.perf_counter()
    safe_result = safe_agent.run_sync("How can I improve the security posture of a small SaaS app?")
    dt = time.perf_counter() - t0
    print(
        f"  [OCI call: {dt:.2f}s · "
        f"{safe_result.metrics.prompt_tokens}→{safe_result.metrics.completion_tokens} tokens]"
    )
    print(f"Guarded answer: {safe_result.message[:300]}")

    print(f"\nTotal violations logged in this tutorial: {len(violations_log)}")
    print("\n" + "=" * 60)
    print("Next: Tutorial 20 - Checkpoint Backends")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
