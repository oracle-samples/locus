# Tutorial 46: Incident-response runbook (SRE-grade workflow)

Models the loop a real on-call engineer runs when a page fires:

    Page fires
      │
      └──> Triage  ──>  scatter to 3 parallel investigators
                          ├── log analyst
                          ├── metric analyst
                          └── trace analyst
                          ▼
                   Synthesizer (root-cause hypothesis)
                          │
                          ▼
            Severity gate ─── critical? ──> page humans (interrupt)
                          │                     │
                          │                  approve mitigation? yes/no
                          │                     │
                          ▼                     ▼
                       Mitigator <──────────────┘
                          │
                          ▼
                       Postmortem (structured)

Locus primitives in play:

* ``Send`` — fan out to 3 investigators in parallel, each a Locus
  ``Agent`` with its own role.
* ``add_conditional_edges`` — severity-based routing decides whether
  the workflow auto-mitigates or escalates to a human.
* ``interrupt()`` — when severity is critical, pause for explicit
  human approval before applying any mitigation.
* ``output_schema=Postmortem`` — final report is a typed Pydantic
  instance, not free text. Pipeable to a runbook database.

Why this is enterprise-shaped:

* The whole runbook is a single ``StateGraph.execute`` call. Audit
  log = the graph's execution_order. Replay = re-execute with the
  saved state snapshot.
* Each investigator runs independently, so adding a fourth analyst
  (e.g. config-drift) is a new node + a new ``Send`` line.
* The severity gate is data-driven, not hard-coded.

Run::

    python examples/tutorial_46_incident_response.py

Difficulty: Advanced
Prerequisites: tutorial_42 (Send), tutorial_45 (HITL multi-agent)

## Source

```python
--8<-- "examples/tutorial_46_incident_response.py"
```
