# Tutorial 43: Supervisor + critic refinement loop

The pattern this tutorial demonstrates is the *flagship multi-agent
demo* most SDKs ship — it shows up in every LangGraph keynote, AutoGen
example, and CrewAI starter. Locus expresses it cleanly:

    Supervisor                Researcher              Writer
        │                         │                     │
        └── delegates ──> Researcher ──> Writer ──> Critic
                                                          │
                                                  reject? ┴ ──> back to Writer
                                                  approve? ──> END

Roles:

* **Supervisor** decides which specialist to hand off to next based on
  the current task state.
* **Researcher** gathers facts about the topic.
* **Writer** drafts an answer using the research notes.
* **Critic** scores the draft and either accepts (END) or rejects
  with a revision instruction that loops back to the Writer.

What makes the Locus version differentiated:

* The control-flow loop is a ``StateGraph`` with conditional edges —
  not a hand-written ``while True`` plus message-passing.
* Each role is a fully-isolated Locus ``Agent`` with its own system
  prompt, ``max_iterations``, and (optionally) tools.
* Every node-completion event flows through the standard
  ``StreamMode.UPDATES`` stream, so a UI can show "Researcher done /
  Writer working / Critic rejected — revising…" with zero extra code.
* Set ``LOCUS_MODEL_PROVIDER=oci|openai`` to drive real specialists.

Run::

    python examples/tutorial_43_supervisor_critic_loop.py

Difficulty: Advanced
Prerequisites: tutorial_06_basic_graph, tutorial_16_agent_handoff

## Source

```python
--8<-- "examples/tutorial_43_supervisor_critic_loop.py"
```
