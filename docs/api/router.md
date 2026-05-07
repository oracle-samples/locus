# Cognitive Router

The cognitive router compiles natural-language tasks onto proven
orchestration shapes. The LLM fills one typed `GoalFrame`; everything
after that — protocol selection, policy gating, compilation — is
rule-based.

## Dispatch

::: locus.router.runtime.Router
::: locus.router.runnable.RunnableResult

## Goal Frame

::: locus.router.goal_frame.GoalFrame
::: locus.router.goal_frame.TaskType
::: locus.router.goal_frame.Risk
::: locus.router.goal_frame.Complexity

## Protocol registry

::: locus.router.protocol.Protocol
::: locus.router.protocol.ProtocolRegistry
::: locus.router.protocol.builtin_protocols

## Policy gate

::: locus.router.policy.PolicyGate
::: locus.router.policy.PolicyVerdict

## Compiler

::: locus.router.compiler.CognitiveCompiler

## Capabilities

::: locus.router.capability.Capability
::: locus.router.capability.CapabilityIndex
::: locus.router.skill_index.SkillIndex
