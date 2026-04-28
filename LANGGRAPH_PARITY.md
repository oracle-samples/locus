# Locus LangGraph Parity Implementation Plan

## Executive Summary

This document outlines the features Locus needs to implement to achieve feature parity with LangGraph while maintaining Locus's unique architectural advantages (immutable state, delta checkpointing, hooks system, playbooks).

## Current Locus Strengths

1. **Immutable State** - Perfect auditability via frozen Pydantic models
2. **Delta Checkpointing** - ~77% storage reduction with chain reconstruction
3. **Multiple Backends** - 9 checkpointer implementations vs LangGraph's 4
4. **Hook System** - Priority-based lifecycle hooks
5. **Playbooks** - Declarative step-by-step execution guides
6. **Multi-Pattern Coordination** - Orchestrator, Specialist, Swarm, Handoff patterns

## Implementation Priority Matrix

### P0: Critical (Required for Production Parity)

#### 1. State Reducers

**What**: Composable state update functions for specific fields
**Why**: Enables clean message list management, counters, and aggregations
**LangGraph Pattern**:

```python
from typing import Annotated
from langgraph.graph import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]  # Uses reducer
    count: int  # Default: last-write-wins
```

**Locus Implementation**:

```python
# src/locus/core/reducers.py
from typing import Annotated, Callable, TypeVar

T = TypeVar("T")

class Reducer(Protocol[T]):
    def __call__(self, current: T, update: T) -> T: ...

def add_messages(current: list[Message], update: list[Message]) -> list[Message]:
    """Append with ID-based deduplication."""
    existing_ids = {m.id for m in current if m.id}
    result = list(current)
    for msg in update:
        if msg.id and msg.id in existing_ids:
            # Replace existing
            result = [m if m.id != msg.id else msg for m in result]
        else:
            result.append(msg)
    return result

# Usage in state:
class GraphState(BaseModel):
    messages: Annotated[list[Message], add_messages]
    findings: Annotated[dict, operator.or_]  # Merge dicts
```

**Files to Create/Modify**:

- `src/locus/core/reducers.py` (new)
- `src/locus/core/state.py` (add reducer support)
- `src/locus/multiagent/graph.py` (apply reducers in data flow)

---

#### 2. Conditional Edges (Dynamic Routing)

**What**: Route to different nodes based on state evaluation
**Why**: Enables complex branching workflows without node-level conditions
**LangGraph Pattern**:

```python
def route_by_type(state):
    if state["type"] == "error":
        return "error_handler"
    return "normal_flow"

graph.add_conditional_edges("classifier", route_by_type, {
    "error_handler": "error_node",
    "normal_flow": "process_node"
})
```

**Locus Implementation**:

```python
# src/locus/multiagent/graph.py

class ConditionalEdge(BaseModel):
    """Edge with dynamic target selection."""
    source_id: str
    router: Callable[[dict[str, Any]], str]  # Returns target node ID
    targets: dict[str, str]  # {router_return_value: target_node_id}
    default_target: str | None = None

class Graph(BaseModel):
    edges: list[Edge] = Field(default_factory=list)
    conditional_edges: list[ConditionalEdge] = Field(default_factory=list)

    def add_conditional_edge(
        self,
        source: str | Node,
        router: Callable[[dict[str, Any]], str],
        targets: dict[str, str],
        default: str | None = None,
    ) -> Graph:
        """Add conditional edge with dynamic routing."""
        ...
```

**Files to Modify**:

- `src/locus/multiagent/graph.py`

---

#### 3. Human-in-the-Loop (HITL)

**What**: Pause execution for human input, resume with response
**Why**: Critical for approval workflows, tool confirmation, review gates
**LangGraph Pattern**:

```python
from langgraph.types import interrupt, Command

def review_node(state):
    approval = interrupt({"action": "delete_user", "user_id": 123})
    if approval == "approved":
        return {"status": "approved"}
    return Command(goto="cancelled")

# Resume:
graph.invoke(Command(resume="approved"), config)
```

**Locus Implementation**:

```python
# src/locus/core/interrupt.py

class InterruptValue(BaseModel):
    """Value passed during interrupt for human review."""
    interrupt_id: str = Field(default_factory=lambda: f"int_{uuid4().hex[:8]}")
    payload: Any
    node_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class InterruptException(Exception):
    """Raised to pause graph execution."""
    def __init__(self, value: InterruptValue):
        self.value = value

def interrupt(payload: Any) -> Any:
    """
    Pause execution and wait for human input.

    When resumed, returns the value passed to Command(resume=...).
    """
    # Get current node context from context var
    node_id = _current_node_context.get()
    value = InterruptValue(payload=payload, node_id=node_id)
    raise InterruptException(value)

# src/locus/core/command.py

class Command(BaseModel):
    """Control flow command combining state update with routing."""
    update: dict[str, Any] = Field(default_factory=dict)
    goto: str | list[str] | None = None
    resume: Any = None  # Value to pass back to interrupted node

    model_config = {"frozen": True}

# Graph execution handles InterruptException:
# - Saves checkpoint with interrupt state
# - Returns pending interrupt to caller
# - On resume, loads checkpoint, injects resume value, continues
```

**Files to Create**:

- `src/locus/core/interrupt.py` (new)
- `src/locus/core/command.py` (new)

**Files to Modify**:

- `src/locus/multiagent/graph.py` (handle InterruptException, Command)
- `src/locus/memory/checkpointer.py` (save interrupt state)

---

#### 4. Command Primitive

**What**: Unified control flow object for state + routing
**Why**: Clean API for node return values that affect both state and flow
**See**: Implementation above in HITL section

**Usage Pattern**:

```python
async def router_node(inputs):
    if inputs["urgency"] == "high":
        return Command(
            update={"priority": 1},
            goto="fast_track"
        )
    return Command(goto="standard_queue")

async def handoff_node(inputs):
    return Command(
        update={"context": inputs["summary"]},
        goto="specialist_agent"
    )
```

---

### P1: Important (Required for Advanced Workflows)

#### 5. Send for Map-Reduce (Fan-Out)

**What**: Dynamically spawn parallel node executions
**Why**: Enables map-reduce patterns, parallel task processing
**LangGraph Pattern**:

```python
from langgraph.types import Send

def create_workers(state):
    return [Send("worker", {"task": t}) for t in state["tasks"]]

graph.add_conditional_edges("splitter", create_workers)
```

**Locus Implementation**:

```python
# src/locus/core/send.py

class Send(BaseModel):
    """Direct a copy of inputs to a specific node."""
    node: str
    payload: dict[str, Any]

# In graph execution:
# - If router returns list[Send], spawn parallel executions
# - Collect results using aggregation reducer
# - Continue after all complete
```

---

#### 6. Cycle Support (Stateful Loops)

**What**: Allow cycles in graph with iteration limits
**Why**: Enables iterative refinement, retry loops, conversational agents
**Current**: Locus strictly enforces DAG (acyclic)

**Implementation Approach**:

```python
class Graph(BaseModel):
    allow_cycles: bool = False
    max_iterations: int = 100  # Prevent infinite loops

    def _validate_graph(self) -> None:
        if not self.allow_cycles and self._has_cycle():
            raise ValueError("Graph contains cycle")

    async def execute(self, inputs, ...):
        iteration = 0
        while iteration < self.max_iterations:
            # Execute nodes ready to run
            # Track which nodes have been visited this iteration
            # Continue until reaching END or max_iterations
            iteration += 1
```

---

#### 7. Cross-Thread Store (Long-Term Memory)

**What**: Key-value store accessible across threads/conversations
**Why**: User preferences, learned facts, cross-session context
**LangGraph Pattern**:

```python
store = InMemoryStore()
graph = builder.compile(store=store)

def my_node(state, *, store):
    memories = store.search(namespace=["user", user_id])
    return state
```

**Locus Implementation**:

```python
# src/locus/memory/store.py

class StoreProtocol(Protocol):
    """Cross-thread persistent storage."""

    async def put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: Any,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    async def get(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> Any | None: ...

    async def search(
        self,
        namespace: tuple[str, ...],
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]: ...

    async def delete(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> bool: ...

# Implementations:
# - InMemoryStore
# - RedisStore
# - PostgreSQLStore
# - (reuse checkpointer backends)
```

---

#### 8. Subgraph Composition

**What**: Use compiled graphs as nodes in parent graph
**Why**: Modular, reusable workflow components
**LangGraph Pattern**:

```python
subgraph = create_specialist_graph().compile()
parent.add_node("specialist", subgraph)
```

**Locus Implementation**:

```python
class Graph(BaseModel):
    def add_subgraph(
        self,
        name: str,
        subgraph: Graph,
        input_mapping: dict[str, str] | None = None,
        output_mapping: dict[str, str] | None = None,
    ) -> Graph:
        """Add a subgraph as a node."""
        # Create wrapper node that:
        # 1. Maps parent inputs to subgraph inputs
        # 2. Executes subgraph
        # 3. Maps subgraph outputs to parent format
        ...
```

---

### P2: Nice to Have (Polish Features)

#### 9. START/END Special Nodes

```python
from locus.multiagent.graph import START, END

graph.add_edge(START, "first_node")
graph.add_edge("last_node", END)
```

#### 10. Multiple Stream Modes

```python
class StreamMode(StrEnum):
    VALUES = "values"      # Full state after each step
    UPDATES = "updates"    # State deltas only
    MESSAGES = "messages"  # LLM tokens with metadata
    CUSTOM = "custom"      # User-emitted data
    DEBUG = "debug"        # Maximum detail

async for chunk in graph.stream(inputs, mode=StreamMode.UPDATES):
    print(chunk)
```

#### 11. Cache Policies

```python
from locus.core.cache import CachePolicy

graph.add_node(
    "expensive_api",
    call_api,
    cache_policy=CachePolicy(ttl_seconds=3600, key_fn=lambda x: x["query"])
)
```

#### 12. Time Travel / Fork from Checkpoint

```python
# Already supported by checkpointer, just need API:
state = await checkpointer.load(thread_id, checkpoint_id="specific-uuid")
graph.invoke(new_inputs, initial_state=state)
```

---

## Implementation Order

### Phase 1: Core Primitives (Week 1-2)

1. State Reducers (`src/locus/core/reducers.py`)
2. Command Primitive (`src/locus/core/command.py`)
3. Conditional Edges (modify `graph.py`)

### Phase 2: HITL & Control Flow (Week 2-3)

1. Interrupt/Resume (`src/locus/core/interrupt.py`)
2. Update graph execution to handle interrupts
3. Send for map-reduce

### Phase 3: Memory & Composition (Week 3-4)

1. Cross-Thread Store (`src/locus/memory/store.py`)
2. Cycle support (optional, config-based)
3. Subgraph composition

### Phase 4: Polish (Week 4+)

1. START/END nodes
2. Stream modes
3. Cache policies
4. Time travel API

---

## File Structure After Implementation

```
src/locus/
├── core/
│   ├── command.py      # NEW: Command primitive
│   ├── interrupt.py    # NEW: HITL interrupt/resume
│   ├── reducers.py     # NEW: State reducers (add_messages, etc.)
│   ├── send.py         # NEW: Send for map-reduce
│   └── ...
├── memory/
│   ├── store.py        # NEW: Cross-thread Store protocol
│   ├── stores/         # NEW: Store implementations
│   │   ├── memory.py
│   │   ├── redis.py
│   │   └── postgresql.py
│   └── ...
└── multiagent/
    └── graph.py        # MODIFIED: conditional edges, cycles, subgraphs
```

---

## Testing Strategy

Each feature should have:

1. Unit tests for core logic
2. Integration tests with real graph execution
3. Example in `examples/` directory

Key test scenarios:

- Conditional edge routing with multiple paths
- Interrupt/resume with checkpointed state
- Map-reduce with Send
- Subgraph with different state schema
- Cross-thread store with multiple threads

---

## Migration Notes

### For Existing Locus Users

- All new features are additive (no breaking changes)
- Existing DAG graphs continue to work unchanged
- Cycles only enabled with `allow_cycles=True`
- Reducers are opt-in via Annotated type hints

### API Compatibility

- Maintain Locus's Pydantic-first approach
- All new primitives are frozen BaseModel where appropriate
- Async-first, with sync wrappers where needed
