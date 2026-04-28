# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Built-in hook providers for Locus.

This module provides ready-to-use hook providers for common use cases:

- LoggingHook: Log all lifecycle events
- TelemetryHook: OpenTelemetry integration
- GuardrailsHook: Security guardrails and content filtering

Example:
    from locus.hooks import HookRegistry
    from locus.hooks.builtin import LoggingHook, GuardrailsHook

    registry = HookRegistry()
    registry.add_provider(LoggingHook())
    registry.add_provider(GuardrailsHook())
"""

from locus.hooks.builtin.guardrails import (
    ContentFilterHook,
    GuardrailAction,
    GuardrailConfig,
    GuardrailsHook,
    GuardrailViolation,
)
from locus.hooks.builtin.logging import LoggingHook, StructuredLoggingHook
from locus.hooks.builtin.telemetry import (
    NoOpTelemetryHook,
    TelemetryHook,
    create_telemetry_hook,
)


__all__ = [
    # Logging
    "LoggingHook",
    "StructuredLoggingHook",
    # Telemetry
    "TelemetryHook",
    "NoOpTelemetryHook",
    "create_telemetry_hook",
    # Guardrails
    "GuardrailsHook",
    "GuardrailConfig",
    "GuardrailAction",
    "GuardrailViolation",
    "ContentFilterHook",
]
