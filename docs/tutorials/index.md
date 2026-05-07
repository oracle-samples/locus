# Tutorials

55 runnable `examples/tutorial_NN_*.py` files in the repo. Every one
runs end-to-end against the bundled `MockModel` (no creds required) and
upgrades to live OCI / OpenAI / Anthropic / Ollama by setting one env
var.

Run any tutorial directly:

```bash
git clone https://github.com/oracle-samples/locus.git
cd locus && pip install -e .
python examples/tutorial_01_basic_agent.py
```

## Foundations

The agent loop, tools, state, memory, hooks, streaming.

| # | Tutorial |
|---|---|
| 1 | [Basic agent][t01] |
| 2 | [Agent with tools][t02] |
| 3 | [Conversation memory][t03] |
| 4 | [Streaming events][t04] |
| 5 | [Lifecycle hooks][t05] |
| 21 | [SSE streaming][t21] |
| 27 | [Hooks (advanced)][t27] |
| 28 | [Agent server (FastAPI)][t28] |
| 37 | [Termination conditions][t37] |

## Graphs & composition

`StateGraph`, conditional edges, reducers, retries, the functional API.

| # | Tutorial |
|---|---|
| 6 | [Basic graph][t06] |
| 7 | [Conditional routing][t07] |
| 8 | [State reducers][t08] |
| 9 | [Human-in-the-loop][t09] |
| 10 | [Command + advanced patterns][t10] |
| 25 | [Composition (Sequential / Parallel / Loop)][t25] |
| 35 | [Graph (advanced) — retries, subgraphs][t35] |
| 36 | [Functional API (`@task`, `@entrypoint`)][t36] |

## Multi-agent

In-process patterns plus A2A, DeepAgent, and real-world crew workflows.

| # | Tutorial | Shape |
|---|---|---|
| 11 | [Swarm][t11] | Peer-to-peer shared context |
| 16 | [Agent handoff][t16] | Sequential escalation |
| 17 | [Orchestrator pattern][t17] | Coordinator + parallel specialists |
| 18 | [Specialist agents][t18] | Named domain experts |
| 34 | [A2A protocol (cross-process)][t34] | HTTP + SSE mesh |
| 41 | [DeepAgent — research factory][t41] | Reflexion + grounding + subagents |
| 42 | [Map-reduce code review][t42] | `Send` fan-out / reduce |
| 43 | [Supervisor + critic loop][t43] | Refinement loop with cycles |
| 44 | [Adversarial debate + judge][t44] | Typed `Verdict` via `output_schema` |
| 45 | [Multi-agent + human-in-the-loop][t45] | 3 HITL patterns in one file |

## Reasoning

Reflexion, Grounding, Causal, GSAR (typed grounding).

| # | Tutorial |
|---|---|
| 13 | [Structured output (Pydantic)][t13] |
| 14 | [Reasoning patterns][t14] |
| 39 | [GSAR — typed grounding][t39] |

## RAG

| # | Tutorial |
|---|---|
| 22 | [RAG basics][t22] |
| 23 | [RAG providers (vector stores, embeddings)][t23] |
| 24 | [RAG agents][t24] |

## Skills, playbooks & plugins

| # | Tutorial |
|---|---|
| 12 | [MCP integration][t12] |
| 15 | [Playbooks][t15] |
| 31 | [Plugins][t31] |
| 32 | [Skills][t32] |
| 33 | [Steering (LLM-as-policy hook)][t33] |

## Production

Structured output, guardrails, checkpointers, multi-modal, DAC.

| # | Tutorial |
|---|---|
| 19 | [Guardrails / security basics][t19] |
| 20 | [Checkpoint backends][t20] |
| 26 | [Evaluation][t26] |
| 29 | [Model providers][t29] |
| 30 | [Guardrails (advanced)][t30] |
| 38 | [Multi-modal providers (web, images, audio)][t38] |
| 40 | [OCI Dedicated AI Cluster (DAC)][t40] |

## Real-world workflows

End-to-end use cases — incident response, contract review, audio chat.

| # | Tutorial |
|---|---|
| 46 | [On-call incident response][t46] |
| 47 | [Tiered approval workflow][t47] |
| 48 | [Contract review + negotiation][t48] |
| 49 | [Voice output (TTS)][t49] |
| 50 | [Voice in → voice out (gpt-audio)][t50] |

## Cognitive router & observability

Cognitive router + opt-in EventBus telemetry.

| # | Tutorial |
|---|---|
| 51 | [Cognitive router][t51] |
| 52 | [Observability basics — opt-in SSE telemetry][t52] |
| 53 | [Agent yield bridge + token usage][t53] |
| 54 | [EventBus subscriber patterns][t54] |
| 55 | [Full event catalogue tour][t55] |

[t01]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_01_basic_agent.py
[t02]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_02_agent_with_tools.py
[t03]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_03_agent_memory.py
[t04]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_04_agent_streaming.py
[t05]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_05_agent_hooks.py
[t06]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_06_basic_graph.py
[t07]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_07_conditional_routing.py
[t08]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_08_state_reducers.py
[t09]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_09_human_in_the_loop.py
[t10]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_10_advanced_patterns.py
[t11]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_11_swarm_multiagent.py
[t12]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_12_mcp_integration.py
[t13]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_13_structured_output.py
[t14]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_14_reasoning_patterns.py
[t15]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_15_playbooks.py
[t16]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_16_agent_handoff.py
[t17]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_17_orchestrator_pattern.py
[t18]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_18_specialist_agents.py
[t19]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_19_guardrails_security.py
[t20]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_20_checkpoint_backends.py
[t21]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_21_sse_streaming.py
[t22]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_22_rag_basics.py
[t23]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_23_rag_providers.py
[t24]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_24_rag_agents.py
[t25]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_25_composition.py
[t26]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_26_evaluation.py
[t27]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_27_hooks_advanced.py
[t28]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_28_agent_server.py
[t29]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_29_model_providers.py
[t30]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_30_guardrails_advanced.py
[t31]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_31_plugins.py
[t32]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_32_skills.py
[t33]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_33_steering.py
[t34]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_34_a2a_protocol.py
[t35]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_35_graph_advanced.py
[t36]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_36_functional_api.py
[t37]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_37_termination.py
[t38]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_38_multimodal_providers.py
[t39]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_39_gsar_typed_grounding.py
[t40]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_40_oci_dac.py
[t41]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_41_deepagent.py
[t42]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_42_map_reduce_code_review.py
[t43]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_43_supervisor_critic_loop.py
[t44]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_44_debate_with_judge.py
[t45]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_45_multiagent_human_in_loop.py
[t46]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_46_incident_response.py
[t47]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_47_procurement_approval.py
[t48]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_48_contract_review.py
[t49]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_49_audio_response.py
[t50]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_50_audio_chat.py
[t51]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_51_cognitive_router.py
[t52]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_52_observability_basics.py
[t53]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_53_agent_yield_bridge.py
[t54]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_54_eventbus_subscribers.py
[t55]: https://github.com/oracle-samples/locus/blob/main/examples/tutorial_55_event_catalogue.py
