# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Agent-to-Agent (A2A) protocol — spec-compliant cross-framework interop.

Implements the public A2A protocol (https://a2aproject.github.io/A2A/)
so Locus agents can talk to peers from other frameworks (Strands, ADK,
Google A2A SDKs) without a translation shim.

Wire surface served by :class:`A2AServer`:

- ``GET  /.well-known/agent-card.json`` — public Agent Card (spec §5.5)
- ``POST /``                            — JSON-RPC 2.0 method dispatch
  (``message/send``, ``message/stream``, ``tasks/get``,
  ``tasks/cancel``)
- Backwards-compat: ``GET /agent-card``, ``POST /a2a/{invoke,stream}``

Re-exports the spec models so consumers can do ``from locus.a2a import
AgentCard, AgentSkill, Message, TextPart, Task`` directly.
"""

from locus.a2a.protocol import (
    A2AClient,
    A2AMessage,
    A2ARequest,
    A2AResponse,
    A2AServer,
)
from locus.a2a.spec import (
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
    Artifact,
    DataPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
    JsonRpcError,
    JsonRpcErrorResponse,
    JsonRpcRequest,
    JsonRpcSuccessResponse,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    Part,
    PushNotificationAuthenticationInfo,
    PushNotificationConfig,
    Task,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)


__all__ = [
    # Server / client.
    "A2AClient",
    "A2AServer",
    # Spec models.
    "AgentCapabilities",
    "AgentCard",
    "AgentProvider",
    "AgentSkill",
    "Artifact",
    "DataPart",
    "FilePart",
    "FileWithBytes",
    "FileWithUri",
    "JsonRpcError",
    "JsonRpcErrorResponse",
    "JsonRpcRequest",
    "JsonRpcSuccessResponse",
    "Message",
    "MessageSendConfiguration",
    "MessageSendParams",
    "Part",
    "PushNotificationAuthenticationInfo",
    "PushNotificationConfig",
    "Task",
    "TaskArtifactUpdateEvent",
    "TaskIdParams",
    "TaskPushNotificationConfig",
    "TaskQueryParams",
    "TaskState",
    "TaskStatus",
    "TaskStatusUpdateEvent",
    "TextPart",
    # Legacy flat models (kept for the pre-spec wire surface).
    "A2AMessage",
    "A2ARequest",
    "A2AResponse",
]
