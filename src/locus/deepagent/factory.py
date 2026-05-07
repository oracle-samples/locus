# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""``deepagent()`` — a research-shaped Agent factory.

Bundles the standard deep-research configuration into one call:

- ``reflexion=True`` and ``grounding=True`` so the agent self-corrects
  hallucinations against the tool-call evidence trail.
- Typed termination::

      (ToolCalled(submit_tool) & ConfidenceMet(min_confidence))
       | TokenLimit(max_tokens)
       | MaxIterations(max_iterations)

  greppable, unit-testable, and per-recipe overridable.
- ``output_schema=`` enforced — the model provider's strict
  structured-output mode rejects non-conforming submissions before
  they reach the caller.
- Optional ``checkpointer`` for resume across days / process restarts.

This is a pure convenience layer over ``locus.Agent`` — it does not
change agent semantics. Callers who need finer control can build the
Agent directly.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def create_deepagent(
    *,
    model: str | Any,
    tools: list[Any],
    system_prompt: str,
    output_schema: type[BaseModel] | None = None,
    submit_tool: str = "submit_research",
    min_confidence: float = 0.8,
    max_tokens: int = 80_000,
    max_iterations: int = 40,
    reflexion: bool = True,
    grounding: bool = True,
    checkpointer: Any | None = None,
    enable_filesystem: bool = False,
    backend: Any | None = None,
    enable_todos: bool = False,
    todo_state: Any | None = None,
    memory_files: list[str] | tuple[str, ...] | None = None,
    subagents: list[Any] | None = None,
    summarize_after_messages: int | None = None,
    summarize_keep_recent: int = 10,
    **agent_kwargs: Any,
) -> Any:
    """Construct a research-shaped ``locus.Agent``.

    Args:
        model: A locus model string (``"oci:openai.gpt-5.5"``) or a
            ``ModelProtocol`` instance built via
            ``locus.models.get_model``.
        tools: All tools the agent can call — MCP-derived,
            ``@tool``-decorated Python tools, and the ``submit_tool``
            that ends the loop.
        system_prompt: The agent's identity, rules, and contract for
            calling ``submit_tool`` with the structured payload.
        output_schema: Pydantic model the agent's ``submit_tool``
            payload must validate against. Locus uses the model
            provider's strict structured-output mode to enforce it.
        submit_tool: The tool name whose call signals "I'm done — here
            is my structured answer". Default ``submit_research``.
        min_confidence: Confidence threshold the submission must clear
            for early-exit. Default 0.8.
        max_tokens: Token budget. Default 80k.
        max_iterations: Cap on reasoning steps. Default 40.
        reflexion: Self-critique pass after each step. Default True.
        grounding: Citation-grounding eval against tool-call evidence.
            Default True.
        checkpointer: Optional ``locus.memory`` checkpointer for
            resume. Default None (no persistence).
        enable_filesystem: When True, attaches the six filesystem-as-
            memory tools (``write_file``, ``read_file``, ``ls``,
            ``edit_file``, ``glob``, ``grep``) to the agent's tool list
            so it can use a scratchspace for intermediate work. Default
            False.
        backend: Optional :class:`BackendProtocol` used by the FS
            tools. Honored only when ``enable_filesystem=True``.
            Defaults to a fresh :class:`StateBackend` (in-memory,
            ephemeral, scoped to the agent run). Pass a
            :class:`FilesystemBackend` for real-disk persistence.
        enable_todos: When True, attaches ``write_todos`` and
            ``read_todos`` tools backed by an in-memory
            :class:`TodoState`. Lets the agent maintain a structured
            task list across reasoning steps. Default False.
        todo_state: Optional pre-built :class:`TodoState`. Honored
            only when ``enable_todos=True``. Pass one to inspect the
            list externally after the agent runs.
        memory_files: Optional list of ``AGENTS.md``-style Markdown
            file paths whose contents are joined and prepended to the
            ``system_prompt``. Missing paths are skipped silently
            (so defaults like ``["~/AGENTS.md", "./AGENTS.md"]`` work
            without checking each one).
        subagents: Optional list of :class:`SubAgentDef` declaring
            subagents the parent can spawn mid-run via a ``task()``
            tool. Each subagent runs as a stateless one-shot.
        summarize_after_messages: If set, attaches locus's
            :class:`SummarizingManager` so older messages are
            condensed once the conversation exceeds this count.
            Recent ``summarize_keep_recent`` messages are always
            preserved verbatim. Default ``None`` (no summarization
            — all messages kept verbatim, may blow context on long
            runs).
        summarize_keep_recent: How many recent messages
            ``SummarizingManager`` preserves untouched. Default 10.
            Honored only when ``summarize_after_messages`` is set.
        **agent_kwargs: Forwarded to ``locus.Agent`` for advanced
            knobs (hooks, conversation_manager, plugins, …).

    Returns:
        A configured ``locus.Agent`` ready for ``agent.run(prompt)``
        or ``agent.run_sync(prompt)``.
    """
    from locus.agent.agent import (
        Agent,
    )  # direct import — avoids the lazy-import-as-object mypy false positive
    from locus.core.termination import (
        ConfidenceMet,
        MaxIterations,
        TokenLimit,
        ToolCalled,
    )

    termination = (
        (ToolCalled(submit_tool) & ConfidenceMet(min_confidence))
        | TokenLimit(max_tokens)
        | MaxIterations(max_iterations)
    )

    # Splice filesystem-as-memory tools into the user-supplied list
    # before constructing the Agent. The default backend is an
    # ephemeral in-memory StateBackend so callers who flip the flag
    # don't have to think about cleanup.
    final_tools = list(tools)
    if enable_filesystem:
        from locus.deepagent.backends import StateBackend
        from locus.deepagent.tools import make_filesystem_tools

        fs_backend = backend if backend is not None else StateBackend()
        final_tools = [*final_tools, *make_filesystem_tools(fs_backend)]

    if enable_todos:
        from locus.deepagent.todos import TodoState, make_todo_tools

        td_state = todo_state if todo_state is not None else TodoState()
        final_tools = [*final_tools, *make_todo_tools(td_state)]

    # Subagent dispatch: attach a single ``task()`` tool the parent
    # can call to spawn one-shot subagents mid-run. The tool's catalog
    # of available subagents is implicit in its docstring; callers
    # who want it surfaced in the parent's system prompt can do so
    # via ``memory_files`` or by appending to ``system_prompt``.
    if subagents:
        from locus.deepagent.subagent import task_tool

        final_tools = [
            *final_tools,
            task_tool(subagents, parent_model=model),
        ]

    # Memory files: prepend to the system prompt so AGENTS.md-style
    # instructions land in front of the recipe-specific identity
    # block. Layered so users can stack base / user / project files.
    final_system_prompt = system_prompt
    if memory_files:
        from locus.deepagent.memory import load_agents_md

        memory_block = load_agents_md(list(memory_files))
        if memory_block:
            final_system_prompt = f"{memory_block}\n\n---\n\n{system_prompt}"

    # Summarization: thin pass-through to locus's SummarizingManager.
    # Active only when the caller asks for it; otherwise the agent
    # keeps every message (default locus behavior). Tier-3 knob —
    # avoids reinventing what locus already ships.
    conversation_manager: Any | None = None
    if summarize_after_messages is not None:
        from locus.memory.conversation import SummarizingManager

        conversation_manager = SummarizingManager(
            threshold=summarize_after_messages,
            keep_recent=summarize_keep_recent,
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "tools": final_tools,
        "system_prompt": final_system_prompt,
        "max_iterations": max_iterations,
        "reflexion": reflexion,
        "grounding": grounding,
    }
    if conversation_manager is not None:
        kwargs["conversation_manager"] = conversation_manager
    if output_schema is not None:
        kwargs["output_schema"] = output_schema
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    kwargs.update(agent_kwargs)

    agent = Agent(**kwargs)
    # Locus's Agent constructor accepts ``max_iterations`` but the
    # typed ``termination`` is the load-bearing exit criterion; attach
    # it via the public AgentConfig setter so the algebra runs.
    config = getattr(agent, "config", None)
    if config is not None and hasattr(config, "termination"):
        config.termination = termination
    return agent
