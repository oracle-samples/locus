# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Unit tests for :class:`OCIResponsesModel` with mocked HTTP.

Uses :mod:`respx` to intercept the outbound POST to ``/responses`` so
these tests run without OCI credentials or network access. Covers:

- Request body shape (continuation id, tools, instructions).
- Successful response parsing through the model.
- Error mapping: project-required, state-lost, generic errors.

Live integration is gated separately under ``tests/integration/`` and
requires real OCI auth.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from locus.core.messages import Message
from locus.models.providers.oci import (
    OCIProjectRequiredError,
    OCIResponsesModel,
    OCIResponsesStateLostError,
)


# Every test in this file constructs the model with auth_type+compartment_id
# (no real OCI auth) and stubs `_build_signer` so the httpx client doesn't
# try to load real signers. The OCIRequestSigner expects a signer object
# that exposes sign(); since respx intercepts before signing matters,
# we replace _build_signer with a no-op.


class _NoopSigner:
    """OCI signer stub. The real signer's only entry point used by
    ``OCIRequestSigner._sign`` is ``do_request_sign(prepared)`` — a
    no-op here is enough because respx intercepts before the signed
    request would actually be transmitted.
    """

    def do_request_sign(self, prepared: Any) -> None:  # noqa: PLR6301
        return None


def _make_model(**overrides: Any) -> OCIResponsesModel:
    """Construct an OCIResponsesModel pointed at a fake OCI base URL."""
    kwargs = {
        "model": "openai.gpt-5.5-pro",
        "auth_type": "instance_principal",
        "compartment_id": "ocid1.compartment.oc1..fake",
        "base_url": "https://fake-oci.test/openai/v1",
    }
    kwargs.update(overrides)
    model = OCIResponsesModel(**kwargs)
    # Replace the signer builder so the httpx client init doesn't try to
    # actually authenticate. Signing happens after respx intercepts.
    object.__setattr__(model, "_build_signer", lambda: _NoopSigner())
    return model


@respx.mock
@pytest.mark.asyncio
async def test_complete_sends_expected_request_body() -> None:
    model = _make_model()

    captured: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "id": "resp_first",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Hi."}],
                    }
                ],
                "usage": {"input_tokens": 5, "output_tokens": 1, "total_tokens": 6},
            },
        )

    respx.post("https://fake-oci.test/openai/v1/responses").mock(side_effect=_handler)

    response = await model.complete(
        [Message.system("Be brief."), Message.user("Hi.")],
        provider_state=None,
    )

    assert response.message.content == "Hi."
    assert response.provider_state == {"previous_response_id": "resp_first"}
    assert response.usage["prompt_tokens"] == 5

    body = captured["body"]
    assert body["model"] == "openai.gpt-5.5-pro"
    assert body["instructions"] == "Be brief."
    assert body["input"][0]["role"] == "user"
    assert "previous_response_id" not in body
    await model.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_complete_threads_previous_response_id() -> None:
    model = _make_model()

    captured: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "resp_second",
                "status": "completed",
                "output": [],
                "usage": {"input_tokens": 1, "output_tokens": 0, "total_tokens": 1},
            },
        )

    respx.post("https://fake-oci.test/openai/v1/responses").mock(side_effect=_handler)

    await model.complete(
        [Message.user("continue")],
        provider_state={"previous_response_id": "resp_first"},
    )

    assert captured["body"]["previous_response_id"] == "resp_first"
    await model.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_complete_passes_project_ocid_header_when_set() -> None:
    model = _make_model(project_ocid="ocid1.genaiagentproject.oc1..fake")

    captured: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={"id": "resp_x", "output": [], "usage": {}},
        )

    respx.post("https://fake-oci.test/openai/v1/responses").mock(side_effect=_handler)

    await model.complete([Message.user("hi")])
    assert captured["headers"].get("opc-project-id") == "ocid1.genaiagentproject.oc1..fake"
    await model.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_403_project_required_maps_to_typed_exception() -> None:
    model = _make_model()

    respx.post("https://fake-oci.test/openai/v1/responses").mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "code": "InvalidParameter",
                    "message": "GenAI Project OCID is required for this feature",
                }
            },
        )
    )

    with pytest.raises(OCIProjectRequiredError) as exc_info:
        await model.complete([Message.user("hi")])

    assert "project_ocid=" in str(exc_info.value)
    await model.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_404_unknown_previous_response_id_maps_to_state_lost() -> None:
    model = _make_model()

    respx.post("https://fake-oci.test/openai/v1/responses").mock(
        return_value=httpx.Response(
            404,
            json={
                "error": {
                    "code": "NotFound",
                    "message": "previous_response_id not found or expired",
                }
            },
        )
    )

    with pytest.raises(OCIResponsesStateLostError):
        await model.complete(
            [Message.user("hi")],
            provider_state={"previous_response_id": "resp_old"},
        )
    await model.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_500_yields_generic_runtime_error_with_body() -> None:
    model = _make_model()

    respx.post("https://fake-oci.test/openai/v1/responses").mock(
        return_value=httpx.Response(500, text="upstream timeout")
    )

    with pytest.raises(RuntimeError) as exc_info:
        await model.complete([Message.user("hi")])

    assert "500" in str(exc_info.value)
    assert "upstream timeout" in str(exc_info.value)
    await model.aclose()


def test_init_rejects_both_auth_modes_set() -> None:
    with pytest.raises(ValueError, match="exactly one of"):
        OCIResponsesModel(
            model="x",
            profile="some-profile",
            auth_type="instance_principal",
        )


def test_init_rejects_invalid_auth_type() -> None:
    with pytest.raises(ValueError, match="auth_type must be one of"):
        OCIResponsesModel(
            model="x",
            auth_type="garbage",
            compartment_id="ocid1.compartment.oc1..fake",
        )


def test_init_requires_compartment_for_workload_identity() -> None:
    with pytest.raises(ValueError, match="compartment_id is required"):
        OCIResponsesModel(model="x", auth_type="instance_principal")


def test_server_stateful_marker_is_true() -> None:
    """Runtime loop branches on this flag — locked in by test."""
    assert OCIResponsesModel.server_stateful is True


@respx.mock
@pytest.mark.asyncio
async def test_complete_does_not_send_temperature_by_default() -> None:
    """OpenAI reasoning families (gpt-5, o-series) reject temperature
    on the Responses endpoint. Verified live against OCI gpt-5: the
    server returns 400 ``Unsupported parameter: 'temperature'`` when
    we send it. Drop it unless the caller explicitly overrides.
    """
    model = _make_model()
    captured: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "r", "output": [], "usage": {}})

    respx.post("https://fake-oci.test/openai/v1/responses").mock(side_effect=_handler)

    await model.complete([Message.user("hi")])
    assert "temperature" not in captured["body"]
    await model.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_complete_drops_temperature_even_when_kwarg_passed() -> None:
    """Reasoning models (gpt-5, o-series) reject temperature. The Agent
    loop always passes temperature as a kwarg from its config default,
    so we drop it unconditionally on the Responses path."""
    model = _make_model()
    captured: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "r", "output": [], "usage": {}})

    respx.post("https://fake-oci.test/openai/v1/responses").mock(side_effect=_handler)

    await model.complete([Message.user("hi")], temperature=0.3)
    assert "temperature" not in captured["body"]
    await model.aclose()
