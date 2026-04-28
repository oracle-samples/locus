"""
Tutorial 20: Checkpoint Backends

This tutorial demonstrates different checkpoint storage backends
for persisting agent state and conversation history.

Topics covered:
1. Memory checkpointer (development)
2. SQLite backend (local persistence)
3. File checkpointer (simple storage)
4. Backend interface and operations
5. Backend selection patterns

Note: Redis, PostgreSQL, and cloud backends require additional setup.

Run with:
    python examples/tutorial_20_checkpoint_backends.py
"""

import asyncio
import os
import tempfile

from locus.core.messages import Message
from locus.core.state import AgentState
from locus.memory.backends import (
    FileCheckpointer,
    MemoryCheckpointer,
    SQLiteBackend,
)


# SQLite backend requires aiosqlite - check if it's available
try:
    import aiosqlite

    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


async def main():
    print("=" * 60)
    print("Tutorial 20: Checkpoint Backends")
    print("=" * 60)

    # Create temp directory for demo
    temp_dir = tempfile.mkdtemp()

    # =========================================================================
    # Part 1: Memory Checkpointer
    # =========================================================================
    print("\n=== Part 1: Memory Checkpointer ===\n")

    # Memory checkpointer for development and testing
    memory_cp = MemoryCheckpointer()

    # Create an agent state
    state = AgentState(agent_id="demo_agent")
    state = state.with_message(Message.user("Hello!"))
    state = state.with_message(Message.assistant("Hi there!"))

    # Save checkpoint
    checkpoint_id = await memory_cp.save(state, "thread_1")
    print(f"Saved checkpoint: {checkpoint_id}")

    # Load checkpoint
    loaded = await memory_cp.load("thread_1")
    print(f"Loaded state with {len(loaded.messages)} messages")

    # List checkpoints
    checkpoints = await memory_cp.list_checkpoints("thread_1")
    print(f"Available checkpoints: {checkpoints}")

    # Memory checkpointer is cleared on restart
    print("\nNote: Memory checkpointer loses data on restart")

    # =========================================================================
    # Part 2: SQLite Backend (Dict-based)
    # =========================================================================
    print("\n=== Part 2: SQLite Backend ===\n")

    sqlite_backend = None  # Will be set if aiosqlite is available

    if HAS_SQLITE:
        db_path = os.path.join(temp_dir, "checkpoints.db")
        sqlite_backend = SQLiteBackend(path=db_path)

        # Save raw dict checkpoints
        for i in range(3):
            await sqlite_backend.save(
                f"thread_{i}",
                {
                    "agent_id": f"agent_{i}",
                    "messages": [{"role": "user", "content": f"Message {i}"}],
                    "iteration": i,
                },
            )

        print("Saved 3 threads to SQLite")

        # Load and verify
        data = await sqlite_backend.load("thread_1")
        print(f"Loaded thread_1: {data}")

        # List threads
        threads = await sqlite_backend.list_threads()
        print(f"All threads: {threads}")

        # Check exists
        exists = await sqlite_backend.exists("thread_1")
        print(f"Thread exists: {exists}")

        # Delete a thread
        deleted = await sqlite_backend.delete("thread_2")
        print(f"Deleted thread_2: {deleted}")

        # List again
        threads = await sqlite_backend.list_threads()
        print(f"Remaining threads: {threads}")

        print(f"\nSQLite database: {db_path}")
    else:
        print("SQLite backend requires 'aiosqlite' package.")
        print("Install with: pip install aiosqlite")
        print("Skipping SQLite demo...")

    # =========================================================================
    # Part 3: File Checkpointer
    # =========================================================================
    print("\n=== Part 3: File Checkpointer ===\n")

    file_dir = os.path.join(temp_dir, "checkpoints")
    file_cp = FileCheckpointer(base_dir=file_dir)

    # Save agent states
    state1 = AgentState(agent_id="file_agent_1")
    state1 = state1.with_message(Message.system("You are helpful."))
    state1 = state1.with_message(Message.user("Help me code."))

    await file_cp.save(state1, "conversation_a")

    state2 = AgentState(agent_id="file_agent_2")
    state2 = state2.with_message(Message.user("Different conversation"))

    await file_cp.save(state2, "conversation_b")

    print("Saved to file checkpointer")

    # Load and verify
    loaded = await file_cp.load("conversation_a")
    print(f"Loaded: {len(loaded.messages)} messages")

    # Check if list_threads is supported
    if file_cp.capabilities.list_threads:
        threads = await file_cp.list_threads()
        print(f"Saved conversations: {threads}")
    else:
        print("Note: FileCheckpointer doesn't support list_threads")

    print(f"\nFile storage: {file_dir}")

    # =========================================================================
    # Part 4: Checkpointer Interface
    # =========================================================================
    print("\n=== Part 4: Checkpointer Interface ===\n")

    print("Checkpointers (MemoryCheckpointer, FileCheckpointer) implement:")
    print("  save(state, thread_id)     - Save AgentState")
    print("  load(thread_id)            - Load AgentState")
    print("  delete(thread_id)          - Delete checkpoint")
    print("  list_checkpoints(thread_id)- List checkpoint IDs")
    print("  list_threads()             - List all thread IDs")

    print("\nBackends (SQLiteBackend, RedisBackend) work with dicts:")
    print("  save(thread_id, data)      - Save dict data")
    print("  load(thread_id)            - Load dict data")
    print("  delete(thread_id)          - Delete data")
    print("  exists(thread_id)          - Check existence")
    print("  list_threads()             - List thread IDs")

    # =========================================================================
    # Part 5: Checkpointer Capabilities
    # =========================================================================
    print("\n=== Part 5: Checkpointer Capabilities ===\n")

    # Each checkpointer reports its capabilities
    print("Memory checkpointer capabilities:")
    print(f"  list_threads: {memory_cp.capabilities.list_threads}")
    print(f"  persistent_checkpoint_ids: {memory_cp.capabilities.persistent_checkpoint_ids}")

    print("\nFile checkpointer capabilities:")
    print(f"  list_threads: {file_cp.capabilities.list_threads}")
    print(f"  persistent_checkpoint_ids: {file_cp.capabilities.persistent_checkpoint_ids}")

    # =========================================================================
    # Part 6: Multiple Checkpoints per Thread
    # =========================================================================
    print("\n=== Part 6: Multiple Checkpoints ===\n")

    # Create multiple checkpoints for the same thread
    thread_id = "multi_checkpoint_thread"

    state = AgentState(agent_id="agent")

    # Checkpoint 1
    state = state.with_message(Message.user("First message"))
    cp1 = await memory_cp.save(state, thread_id)

    # Checkpoint 2 (more progress)
    state = state.with_message(Message.assistant("Response"))
    state = state.with_iteration(1)
    cp2 = await memory_cp.save(state, thread_id)

    # Checkpoint 3 (even more progress)
    state = state.with_message(Message.user("Follow up"))
    cp3 = await memory_cp.save(state, thread_id)

    # List all checkpoints
    all_cps = await memory_cp.list_checkpoints(thread_id)
    print(f"Checkpoints for {thread_id}: {len(all_cps)}")
    for cp_id in all_cps:
        print(f"  - {cp_id}")

    # Load specific checkpoint
    loaded = await memory_cp.load(thread_id, checkpoint_id=cp1)
    print(f"\nLoaded checkpoint 1: {len(loaded.messages)} messages")

    # Load latest (default)
    latest = await memory_cp.load(thread_id)
    print(f"Loaded latest: {len(latest.messages)} messages")

    # =========================================================================
    # Part 7: Backend Selection Patterns
    # =========================================================================
    print("\n=== Part 7: Backend Selection ===\n")

    def get_checkpointer(environment: str):
        """Select checkpointer based on environment."""
        if environment == "development":
            return MemoryCheckpointer()
        elif environment == "testing":
            return MemoryCheckpointer()  # Fast, in-memory
        elif environment == "production":
            # In production, use persistent storage
            return FileCheckpointer(base_dir="/var/lib/locus/checkpoints")
        else:
            raise ValueError(f"Unknown environment: {environment}")

    for env in ["development", "testing", "production"]:
        cp = get_checkpointer(env)
        print(f"  {env}: {type(cp).__name__}")

    # =========================================================================
    # Part 8: Available Backends
    # =========================================================================
    print("\n=== Part 8: Available Backends ===\n")

    backends = [
        ("MemoryCheckpointer", "In-memory, no dependencies", "Development, testing"),
        ("FileCheckpointer", "JSON files, no dependencies", "Simple persistence"),
        ("SQLiteBackend", "Local file, requires aiosqlite", "Single-node storage"),
        ("RedisBackend", "Redis server, requires redis", "Distributed, high performance"),
        ("PostgreSQLBackend", "PostgreSQL, requires asyncpg", "Production, ACID compliance"),
        ("OCIBucketBackend", "OCI Object Storage", "Cloud, scalable storage"),
        ("OpenSearchBackend", "OpenSearch/Elasticsearch", "Searchable checkpoints"),
        ("OracleBackend", "Oracle Database", "Enterprise, JSON support"),
    ]

    print("Backend options:")
    for name, deps, use_case in backends:
        print(f"\n  {name}")
        print(f"    Dependencies: {deps}")
        print(f"    Use case: {use_case}")

    # =========================================================================
    # Part 9: Thread Listing and Filtering
    # =========================================================================
    print("\n=== Part 9: Thread Management ===\n")

    if sqlite_backend is not None:
        # Create multiple threads with pattern
        for user in ["alice", "bob", "charlie"]:
            for session in range(2):
                thread_id = f"user_{user}_session_{session}"
                await sqlite_backend.save(thread_id, {"user": user, "session": session})

        # List all threads
        all_threads = await sqlite_backend.list_threads()
        print(f"Total threads: {len(all_threads)}")

        # List with pattern (SQLite supports LIKE patterns)
        alice_threads = await sqlite_backend.list_threads(pattern="user_alice%")
        print(f"Alice's threads: {alice_threads}")

        # List with pagination
        page1 = await sqlite_backend.list_threads(limit=3, offset=0)
        page2 = await sqlite_backend.list_threads(limit=3, offset=3)
        print(f"Page 1: {page1}")
        print(f"Page 2: {page2}")
    else:
        print("SQLite not available - skipping thread management demo")
        print("Install aiosqlite to see this functionality")

    # =========================================================================
    # Part 10: Best Practices
    # =========================================================================
    print("\n=== Part 10: Best Practices ===\n")

    print("1. Use MemoryCheckpointer for unit tests")
    print("2. Use FileCheckpointer for development")
    print("3. Use Redis/PostgreSQL for production")
    print("4. Use meaningful thread IDs (user_id + session)")
    print("5. Implement cleanup for old checkpoints")
    print("6. Test checkpoint restore after changes")
    print("7. Consider encryption for sensitive data")
    print("8. Monitor storage usage over time")

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)

    # =========================================================================
    print("\n" + "=" * 60)
    print("Next: Tutorial 21 - SSE Streaming")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
