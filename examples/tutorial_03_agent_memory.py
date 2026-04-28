"""
Tutorial 03: Agent Memory & Checkpointing

This tutorial covers:
- Using conversation memory to maintain context
- Checkpointing agent state for persistence
- Resuming conversations with thread IDs
- Memory backends (in-memory, file, etc.)

Prerequisites: Tutorial 02 (Agent with Tools)
Difficulty: Beginner-Intermediate
"""

import asyncio
import os
import tempfile

# Import shared config
from config import get_model, print_config

from locus.agent import Agent
from locus.memory.backends.file import FileCheckpointer
from locus.memory.backends.memory import MemoryCheckpointer as InMemoryCheckpointer
from locus.tools import tool


# =============================================================================
# Part 1: Basic Conversation Memory
# =============================================================================


def example_conversation_memory():
    """Agent remembers previous turns in a conversation."""
    print("=== Part 1: Conversation Memory ===\n")

    model = get_model(max_tokens=100)

    # Create checkpointer for memory
    checkpointer = InMemoryCheckpointer()

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant. Remember what the user tells you.",
        checkpointer=checkpointer,
    )

    # Use thread_id to maintain conversation context
    thread_id = "conversation_001"

    # First message
    result1 = agent.run_sync("My name is Alice.", thread_id=thread_id)
    print("User: My name is Alice.")
    print(f"Agent: {result1.message}")

    # Second message - agent should remember the name
    result2 = agent.run_sync("What's my name?", thread_id=thread_id)
    print("\nUser: What's my name?")
    print(f"Agent: {result2.message}")
    print()


# =============================================================================
# Part 2: Checkpointing with Tools
# =============================================================================


@tool
def save_note(content: str) -> str:
    """Save a note for later reference."""
    return f"Note saved: {content}"


@tool
def get_notes() -> str:
    """Get all saved notes."""
    # In a real app, this would retrieve from storage
    return "No notes saved yet."


def example_checkpointing_with_tools():
    """Checkpoint state after tool usage."""
    print("=== Part 2: Checkpointing with Tools ===\n")

    model = get_model(max_tokens=150)
    checkpointer = InMemoryCheckpointer()

    agent = Agent(
        model=model,
        tools=[save_note, get_notes],
        system_prompt="You are a note-taking assistant.",
        checkpointer=checkpointer,
        checkpoint_every_n_iterations=1,  # Checkpoint after each iteration
    )

    thread_id = "notes_session"

    # Save a note
    result1 = agent.run_sync("Save a note: Buy groceries", thread_id=thread_id)
    print("User: Save a note: Buy groceries")
    print(f"Agent: {result1.message}")
    print(f"Tool calls: {result1.metrics.tool_calls}")

    # Ask about notes
    result2 = agent.run_sync("What notes do I have?", thread_id=thread_id)
    print("\nUser: What notes do I have?")
    print(f"Agent: {result2.message}")
    print()


# =============================================================================
# Part 3: File-Based Persistence
# =============================================================================


def example_file_checkpointer():
    """Persist conversation state to disk."""
    print("=== Part 3: File-Based Persistence ===\n")

    # Create a temp directory for checkpoints
    checkpoint_dir = tempfile.mkdtemp()
    print(f"Checkpoint directory: {checkpoint_dir}")

    model = get_model(max_tokens=100)

    # Use FileCheckpointer for persistence
    checkpointer = FileCheckpointer(base_dir=checkpoint_dir)

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant.",
        checkpointer=checkpointer,
    )

    thread_id = "persistent_chat"

    # First interaction
    result1 = agent.run_sync("Remember: The secret code is 42.", thread_id=thread_id)
    print("User: Remember: The secret code is 42.")
    print(f"Agent: {result1.message}")

    # Check that checkpoint file was created
    files = os.listdir(checkpoint_dir)
    print(f"\nCheckpoint files created: {files}")

    # Simulate a new session by creating a new agent
    agent2 = Agent(
        model=model,
        system_prompt="You are a helpful assistant.",
        checkpointer=FileCheckpointer(base_dir=checkpoint_dir),
    )

    # Resume the conversation
    result2 = agent2.run_sync("What was the secret code?", thread_id=thread_id)
    print("\n[New session]")
    print("User: What was the secret code?")
    print(f"Agent: {result2.message}")
    print()


# =============================================================================
# Part 4: Multiple Threads
# =============================================================================


def example_multiple_threads():
    """Manage multiple independent conversations."""
    print("=== Part 4: Multiple Threads ===\n")

    model = get_model(max_tokens=100)
    checkpointer = InMemoryCheckpointer()

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant.",
        checkpointer=checkpointer,
    )

    # Start two independent conversations
    thread_alice = "thread_alice"
    thread_bob = "thread_bob"

    # Alice's conversation
    agent.run_sync("I'm Alice and I like pizza.", thread_id=thread_alice)

    # Bob's conversation
    agent.run_sync("I'm Bob and I like sushi.", thread_id=thread_bob)

    # Each thread has independent memory
    result_alice = agent.run_sync("What's my favorite food?", thread_id=thread_alice)
    print("Thread 'alice': What's my favorite food?")
    print(f"Agent: {result_alice.message}")

    result_bob = agent.run_sync("What's my favorite food?", thread_id=thread_bob)
    print("\nThread 'bob': What's my favorite food?")
    print(f"Agent: {result_bob.message}")
    print()


# =============================================================================
# Part 5: Inspecting Checkpoint State
# =============================================================================


async def example_inspect_checkpoint():
    """Inspect what's stored in a checkpoint."""
    print("=== Part 5: Inspecting Checkpoints ===\n")

    model = get_model(max_tokens=100)
    checkpointer = InMemoryCheckpointer()

    agent = Agent(
        model=model,
        system_prompt="You are a helpful assistant.",
        checkpointer=checkpointer,
    )

    thread_id = "inspect_thread"

    # Have a short conversation
    agent.run_sync("Hello, my name is Charlie.", thread_id=thread_id)
    agent.run_sync("I work as a data scientist.", thread_id=thread_id)

    # Load and inspect the checkpoint
    state = await checkpointer.load(thread_id)

    if state:
        print(f"Thread ID: {thread_id}")
        print(f"Agent ID: {state.agent_id}")
        print(f"Iteration: {state.iteration}")
        print(f"Message count: {len(state.messages)}")
        print(f"Confidence: {state.confidence:.2f}")

        print("\nMessages:")
        for i, msg in enumerate(state.messages):
            content = (
                msg.content[:50] + "..." if msg.content and len(msg.content) > 50 else msg.content
            )
            print(f"  {i}. [{msg.role.value}] {content}")
    print()


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tutorial parts."""
    print("=" * 60)
    print("Tutorial 03: Agent Memory & Checkpointing")
    print("=" * 60)
    print()

    print_config()
    print()

    example_conversation_memory()
    example_checkpointing_with_tools()
    example_file_checkpointer()
    example_multiple_threads()
    asyncio.run(example_inspect_checkpoint())

    print("=" * 60)
    print("Next: Tutorial 04 - Agent Streaming")
    print("=" * 60)


if __name__ == "__main__":
    main()
