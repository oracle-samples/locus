# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Agent configuration - 100% Pydantic."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ReflexionConfig(BaseModel):
    """Configuration for Reflexion reasoning pattern."""

    enabled: bool = True
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    diminishing_returns: bool = True
    evaluate_every_n_iterations: int = Field(default=1, ge=1)
    include_guidance: bool = True
    model: str | None = None  # Optional separate model for reflection

    model_config = {"extra": "forbid"}


class GroundingConfig(BaseModel):
    """Configuration for Grounding evaluation."""

    enabled: bool = True
    threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    max_replans: int = Field(default=2, ge=0)
    check_before_final: bool = True
    model: str | None = None  # Optional separate model for grounding

    model_config = {"extra": "forbid"}


class AgentConfig(BaseModel):
    """
    Configuration for an Agent instance.

    All parameters can be validated before agent creation.
    """

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    # Model specification
    model: str | Any = Field(
        ...,
        description="Model string ('openai:gpt-4o' or 'oci:cohere.command-r-plus') or ModelProtocol instance",
    )

    # Auxiliary (cheap/fast) model for summarization, classification,
    # and other side-calls where quality matters less than cost /
    # latency. Defaults to the primary model when unset.
    #
    # Typical use:
    #   config.auxiliary_model = "openai:gpt-4o-mini"
    #   # Context compactor uses it for middle-turn summarization,
    #   # keeping the primary model's budget for the actual task.
    auxiliary_model: str | Any | None = Field(
        default=None,
        description=(
            "Cheap / fast model for non-primary calls. When set, the "
            "agent uses it for the max-iterations final summary, "
            "grounding evaluation (when ``grounding.model`` isn't set "
            "explicitly), and any conversation manager that supports "
            "an auxiliary fallback (``LLMCompactor``). The primary "
            "ReAct loop and structured-output repair stay on "
            "``model``. String (``'openai:gpt-4o-mini'``) or "
            "ModelProtocol instance. ``None`` (default) falls back to "
            "``model`` everywhere."
        ),
    )

    # Tools
    tools: list[Any] = Field(
        default_factory=list,
        description="List of tools available to the agent",
    )

    # System prompt — string or callable(context) -> str for dynamic prompts
    system_prompt: Any = Field(
        default="You are a helpful AI assistant.",
        description="System prompt for the agent. Can be a string or a callable "
        "that receives context dict and returns a string for dynamic prompts.",
    )

    # Iteration limits
    max_iterations: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Maximum iterations before stopping",
    )

    # Budget limits
    token_budget: int | None = Field(
        default=None,
        ge=1,
        description="Maximum total tokens before stopping (None = unlimited)",
    )

    time_budget_seconds: float | None = Field(
        default=None,
        gt=0.0,
        description="Maximum wall-clock seconds before stopping (None = unlimited)",
    )

    # Reasoning patterns
    reflexion: ReflexionConfig | None = Field(
        default=None,
        description="Reflexion configuration (None to disable)",
    )

    grounding: GroundingConfig | None = Field(
        default=None,
        description="Grounding evaluation configuration (None to disable)",
    )

    # Planning
    planning: bool = Field(
        default=False,
        description=(
            "When True, the agent generates an explicit plan on the first "
            "iteration before taking action. The plan is stored in state "
            "metadata and can be revised if the agent gets stuck."
        ),
    )

    # Terminal tools
    terminal_tools: set[str] = Field(
        default_factory=lambda: {"submit", "done", "finish", "complete", "task_complete"},
        description="Tool names that signal task completion",
    )

    # Completion mode
    completion_mode: Literal["auto", "explicit"] = Field(
        default="auto",
        description=(
            "How the agent decides it's done. "
            "'auto' = stops on confidence, no tool calls, or terminal tool. "
            "'explicit' = only stops on terminal tool, max_iterations, or budgets. "
            "Use 'explicit' for multi-step tasks that require verification."
        ),
    )

    # Verification reminders
    verify_tools: set[str] = Field(
        default_factory=lambda: {"write_file", "write", "save", "create_file", "update_file"},
        description=(
            "Tool names that trigger a verification reminder. "
            "When tools in this set are called, a system message is injected "
            "reminding the agent to verify changes before completing."
        ),
    )

    # Verification gate for task_complete
    require_verification: bool = Field(
        default=True,
        description=(
            "When True and completion_mode='explicit', task_complete is blocked "
            "unless a verification tool (run_command, run_tests, etc.) was called "
            "after the last write. Forces write→test→fix→complete workflow."
        ),
    )
    verification_tools: set[str] = Field(
        default_factory=lambda: {"run_command", "run_tests", "run", "execute", "pytest", "test"},
        description="Tool names that count as verification (running tests/commands).",
    )

    # Tool loop detection
    tool_loop_threshold: int = Field(
        default=3,
        ge=2,
        description="Consecutive same-tool calls to trigger loop detection",
    )

    # Execution strategy
    tool_execution: Literal["sequential", "concurrent"] = Field(
        default="concurrent",
        description="How to execute multiple tool calls",
    )

    max_concurrency: int = Field(
        default=10,
        ge=1,
        description="Max concurrent tool executions",
    )

    max_tool_result_length: int = Field(
        default=32000,
        ge=0,
        description="Max chars per tool result (0 = unlimited). Long results are truncated.",
    )

    # Optional external offload for oversized tool results. When set,
    # results above ``max_tool_result_length`` are persisted via the
    # store and replaced inline with a recoverable reference key
    # instead of being head-truncated. See
    # ``locus.tools.result_storage.ToolResultStore`` for the contract.
    tool_result_store: Any | None = Field(
        default=None,
        description=(
            "Optional ToolResultStore. When set, oversized tool "
            "results are offloaded to its backend and a reference "
            "key is inlined; without it the agent falls back to "
            "head-truncation."
        ),
    )

    # State management
    conversation_manager: Any | None = Field(
        default=None,
        description="Conversation manager for message pruning/summarization",
    )

    checkpointer: Any | None = Field(
        default=None,
        description="Checkpointer for state persistence",
    )

    checkpoint_every_n_iterations: int = Field(
        default=0,
        ge=0,
        description="Auto-checkpoint interval (0 to disable)",
    )

    # Hooks and plugins
    hooks: list[Any] = Field(
        default_factory=list,
        description="Lifecycle hooks (HookProvider instances)",
    )
    plugins: list[Any] = Field(
        default_factory=list,
        description="Plugins that bundle hooks + tools (Plugin instances)",
    )
    callback_handler: Any = Field(
        default=None,
        description="Simple callback function: fn(event) called for every agent event",
    )
    skills: list[Any] = Field(
        default_factory=list,
        description="Skills (Skill instances or paths to skill directories)",
    )

    # Termination (composable conditions)
    termination: Any | None = Field(
        default=None,
        description="Composable termination condition (TerminationCondition instance). "
        "Overrides default termination logic when set.",
    )

    # Output auto-save
    output_key: str | None = Field(
        default=None,
        description="If set, agent's final message is saved to state metadata under this key. "
        "Enables simple data flow between agents in multi-agent setups.",
    )

    # Structured output — coerce the agent's final answer into a Pydantic model.
    output_schema: Any | None = Field(
        default=None,
        description=(
            "Optional Pydantic ``BaseModel`` subclass. When set, the agent's "
            "final assistant message is parsed into an instance of this schema "
            "and surfaced on ``AgentResult.parsed``. Supporting providers "
            "(OpenAI / OCI OpenAI-compat) receive a strict ``response_format`` "
            "for constrained decoding; others fall back to prompted JSON + "
            "validate-and-retry."
        ),
    )

    output_schema_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description=(
            "Maximum re-prompts after a structured-output validation failure. "
            "Each retry feeds the Pydantic ``ValidationError`` details back to "
            "the model so it can repair the response. Set to 0 to disable."
        ),
    )

    output_schema_strict: bool = Field(
        default=True,
        description=(
            "When True (default), request provider-enforced strict mode for "
            "``output_schema`` on supporting providers. Disable for providers "
            "that reject strict ``json_schema`` mode (some OCI model families)."
        ),
    )

    @field_validator("output_schema")
    @classmethod
    def _validate_output_schema(cls, v: Any) -> Any:
        """Ensure output_schema is a Pydantic BaseModel subclass."""
        if v is None:
            return None
        if not (isinstance(v, type) and issubclass(v, BaseModel)):
            raise TypeError(f"output_schema must be a pydantic.BaseModel subclass, got: {v!r}")
        return v

    # Playbook enforcement (optional). When set, a PlaybookEnforcerHook is
    # auto-installed during Agent initialization so the model is held to the
    # playbook's step sequence and tool constraints.
    playbook: Any | None = Field(
        default=None,
        description=(
            "Optional ``locus.playbooks.models.Playbook`` instance. When "
            "provided, ``Agent`` installs a ``PlaybookEnforcerHook`` that "
            "validates each tool call against the current step and "
            "auto-advances when the step's ``expected_tools`` are exhausted."
        ),
    )

    # Agent identity
    agent_id: str | None = Field(
        default=None,
        description="Unique agent identifier",
    )

    # Model parameters
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Model temperature",
    )

    max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Max tokens per completion",
    )

    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata passed to tools",
    )

    @field_validator("model", mode="before")
    @classmethod
    def validate_model(cls, v: Any) -> Any:
        """Validate model is a string or ModelProtocol."""
        if isinstance(v, str):
            if ":" not in v:
                raise ValueError(
                    f"Model string must be 'provider:model', got: {v}. Example: 'openai:gpt-4o'"
                )
            return v
        # Assume it's a ModelProtocol instance
        return v

    @field_validator("tools", mode="before")
    @classmethod
    def validate_tools(cls, v: Any) -> list[Any]:
        """Ensure tools is a list."""
        if v is None:
            return []
        if not isinstance(v, list):
            return [v]
        return v

    def with_reflexion(
        self,
        enabled: bool = True,
        confidence_threshold: float = 0.85,
        **kwargs: Any,
    ) -> AgentConfig:
        """Return a copy with Reflexion configured."""
        return self.model_copy(
            update={
                "reflexion": ReflexionConfig(
                    enabled=enabled,
                    confidence_threshold=confidence_threshold,
                    **kwargs,
                )
            }
        )

    def with_grounding(
        self,
        enabled: bool = True,
        threshold: float = 0.65,
        **kwargs: Any,
    ) -> AgentConfig:
        """Return a copy with Grounding configured."""
        return self.model_copy(
            update={
                "grounding": GroundingConfig(
                    enabled=enabled,
                    threshold=threshold,
                    **kwargs,
                )
            }
        )

    def with_hooks(self, *hooks: Any) -> AgentConfig:
        """Return a copy with additional hooks."""
        return self.model_copy(update={"hooks": [*self.hooks, *hooks]})
