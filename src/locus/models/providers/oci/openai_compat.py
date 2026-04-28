# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""OCI GenAI access via the OpenAI-compatible ``/openai/v1`` endpoint.

This is the recommended OCI transport in locus for any model family that
speaks the OpenAI request shape on OCI (OpenAI / Meta / xAI / Mistral /
Gemini). Cohere R-series models are not supported by OCI on this endpoint
and will fail with a 400 from OCI — for those, use :class:`OCIModel` (the
OCI SDK transport).

Two mutually-exclusive auth modes are supported. Pass **exactly one**:

- ``profile=...`` — name of a profile in ``~/.oci/config`` (or
  ``config_file=``). Used for both API-key IAM signing and session-token
  signing — the profile shape determines which.
- ``auth_type="instance_principal"`` / ``"resource_principal"`` — for
  workloads running on OCI compute or in OCI Functions / OKE with
  workload identity.

The endpoint is ``/openai/v1/chat/completions``. We do **not** use the
Responses API and do **not** require a GenAI Project OCID — those imply
server-side conversation state that locus already owns.

Example::

    import os
    from locus.core.messages import Message
    from locus.models.providers.oci import OCIOpenAIModel

    # IAM via OCI config profile (typical local dev / CI)
    model = OCIOpenAIModel(
        model="meta.llama-3.3-70b-instruct",
        profile="DEFAULT",
    )

    # Workload identity (OCI VM / OKE / Functions)
    model = OCIOpenAIModel(
        model="meta.llama-3.3-70b-instruct",
        auth_type="instance_principal",
        compartment_id=os.environ["OCI_COMPARTMENT_ID"],
    )

    response = await model.complete([Message.user("Hello!")])
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from locus.models.native.openai import OpenAIConfig, OpenAIModel


if TYPE_CHECKING:
    import openai
    from oci.signer import AbstractBaseSigner


DEFAULT_OCI_GENAI_REGION = "us-chicago-1"

AuthType = Literal["instance_principal", "resource_principal"]
_VALID_AUTH_TYPES: tuple[str, ...] = ("instance_principal", "resource_principal")


def build_oci_openai_base_url(region: str) -> str:
    """Construct the OCI GenAI OpenAI-compatible base URL for a region."""
    return f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"


class OCIOpenAIConfig(OpenAIConfig):
    """Configuration for :class:`OCIOpenAIModel`.

    Inherits all OpenAI knobs from :class:`OpenAIConfig`. Adds region,
    profile, ``auth_type``, ``compartment_id``, and ``config_file`` for OCI
    auth selection.
    """

    region: str = Field(
        default=DEFAULT_OCI_GENAI_REGION,
        description="OCI region for the GenAI inference endpoint",
    )
    profile: str | None = Field(
        default=None,
        description="OCI config profile name (in config_file)",
    )
    auth_type: str | None = Field(
        default=None,
        description='"instance_principal" or "resource_principal"',
    )
    config_file: str = Field(
        default="~/.oci/config",
        description="Path to the OCI config file (only used with profile=)",
    )
    compartment_id: str | None = Field(
        default=None,
        description=(
            "OCI compartment OCID (sent as opc-compartment-id). "
            "Auto-derived from the profile's tenancy when profile= is used. "
            "Required for instance_principal / resource_principal."
        ),
    )


def _load_profile_config(profile: str, config_file: str) -> dict[str, Any]:
    """Load an OCI config profile as a dict (tenancy, user, key_file, ...)."""
    from oci import config as oci_config_module

    cfg_path = str(Path(config_file).expanduser())
    cfg: dict[str, Any] = oci_config_module.from_file(cfg_path, profile_name=profile)
    return cfg


def _build_signer_from_profile(profile: str, config_file: str) -> AbstractBaseSigner:
    """Build an OCI signer from a config profile.

    Picks security-token signing if the profile has ``security_token_file``,
    otherwise user-principal API-key signing.
    """
    cfg = _load_profile_config(profile, config_file)
    if cfg.get("security_token_file"):
        return _build_session_signer(cfg)
    return _build_user_principal_signer(cfg)


def _build_user_principal_signer(cfg: dict[str, Any]) -> AbstractBaseSigner:
    from oci.signer import Signer

    return Signer(
        tenancy=cfg["tenancy"],
        user=cfg["user"],
        fingerprint=cfg["fingerprint"],
        private_key_file_location=cfg["key_file"],
        pass_phrase=cfg.get("pass_phrase"),
    )


def _build_session_signer(cfg: dict[str, Any]) -> AbstractBaseSigner:
    from oci.auth.signers import SecurityTokenSigner
    from oci.signer import load_private_key_from_file

    token_path = Path(cfg["security_token_file"]).expanduser()
    token = token_path.read_text().strip()
    private_key = load_private_key_from_file(cfg["key_file"], cfg.get("pass_phrase"))
    return SecurityTokenSigner(token=token, private_key=private_key)


def _build_instance_principal_signer() -> AbstractBaseSigner:
    from oci.auth.signers import InstancePrincipalsSecurityTokenSigner

    return InstancePrincipalsSecurityTokenSigner()


def _build_resource_principal_signer() -> AbstractBaseSigner:
    from oci.auth.signers import get_resource_principals_signer

    return get_resource_principals_signer()


class OCIOpenAIModel(OpenAIModel):
    """OCI GenAI model accessed through the ``/openai/v1`` endpoint.

    Reuses :class:`OpenAIModel` for message conversion, tool handling,
    response parsing, and streaming. The only thing this class adds is
    the OCI-specific auth wiring.

    Pass exactly one of ``profile``, ``auth_type``.
    """

    config: OCIOpenAIConfig

    def __init__(
        self,
        model: str,
        *,
        profile: str | None = None,
        auth_type: str | None = None,
        compartment_id: str | None = None,
        region: str = DEFAULT_OCI_GENAI_REGION,
        config_file: str = "~/.oci/config",
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> None:
        """Initialize the OCI OpenAI-compat model.

        Args:
            model: OCI model identifier (e.g. ``openai.gpt-5.5``,
                ``meta.llama-3.3-70b-instruct``).
            profile: OCI config profile name from ``config_file``. Mutually
                exclusive with ``auth_type``.
            auth_type: ``"instance_principal"`` or ``"resource_principal"``.
                Mutually exclusive with ``profile``. Requires
                ``compartment_id``.
            compartment_id: OCI compartment OCID, sent as
                ``opc-compartment-id``. Auto-derived from the profile's
                tenancy under ``profile=``. Must be supplied explicitly
                under ``auth_type=``.
            region: OCI region hosting the inference endpoint.
            config_file: Path to the OCI config file (used with ``profile``).
            base_url: Override the derived endpoint URL (e.g. for a custom
                realm). Defaults to the OpenAI-compat URL for ``region``.
            max_tokens: Default max tokens. For ``o1``/``o3``/``gpt-5*``
                this is automatically forwarded as
                ``max_completion_tokens`` — see :class:`OpenAIModel`.
            temperature: Default sampling temperature.
            **kwargs: Forwarded to :class:`OCIOpenAIConfig` (top_p, seed,
                frequency_penalty, presence_penalty, ...).

        Raises:
            ValueError: If zero or both auth modes are set, if ``auth_type``
                is invalid, or if ``auth_type`` is set without
                ``compartment_id``.
        """
        modes_set = sum(x is not None for x in (profile, auth_type))
        if modes_set != 1:
            msg = "specify exactly one of profile=, auth_type="
            raise ValueError(msg)
        if auth_type is not None and auth_type not in _VALID_AUTH_TYPES:
            msg = f"auth_type must be one of {_VALID_AUTH_TYPES}, got {auth_type!r}"
            raise ValueError(msg)
        if auth_type is not None and compartment_id is None:
            msg = "compartment_id is required when auth_type= is set"
            raise ValueError(msg)

        # Pop fields we set explicitly to avoid duplicate-kwarg errors
        # when callers splat a config dict that includes the same keys.
        for explicit in (
            "model",
            "profile",
            "auth_type",
            "compartment_id",
            "region",
            "config_file",
            "base_url",
            "max_tokens",
            "temperature",
        ):
            kwargs.pop(explicit, None)

        # Auto-derive compartment from the profile's tenancy when the user
        # didn't pass one explicitly. Same fallback OCIClient uses for the
        # OCI-SDK transport.
        if compartment_id is None and profile is not None:
            try:
                profile_cfg = _load_profile_config(profile, config_file)
                compartment_id = profile_cfg.get("tenancy")
            except Exception:  # noqa: BLE001 — profile load may fail; keep None
                compartment_id = None

        config = OCIOpenAIConfig(
            model=model,
            api_key=None,
            base_url=base_url or build_oci_openai_base_url(region),
            region=region,
            profile=profile,
            auth_type=auth_type,
            compartment_id=compartment_id,
            config_file=config_file,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        # Skip OpenAIModel.__init__ — it would rebuild the config without
        # OCI fields. Go straight to the Pydantic BaseModel init.
        super(OpenAIModel, self).__init__(config=config)

    @property
    def client(self) -> openai.AsyncOpenAI:
        """Build the AsyncOpenAI client wired with the OCI request signer."""
        if self._client is None:
            import httpx
            import openai

            from locus.models.providers.oci._signing import OCIRequestSigner

            signer = self._build_signer()
            http_client = httpx.AsyncClient(
                auth=OCIRequestSigner(
                    signer,
                    compartment_id=self.config.compartment_id,
                ),
            )
            self._client = openai.AsyncOpenAI(
                api_key="not-used",
                base_url=self.config.base_url,
                http_client=http_client,
            )
        return self._client

    def _build_signer(self) -> AbstractBaseSigner:
        if self.config.auth_type == "instance_principal":
            return _build_instance_principal_signer()
        if self.config.auth_type == "resource_principal":
            return _build_resource_principal_signer()
        # Validation in __init__ guarantees profile is set if we got here.
        assert self.config.profile is not None  # noqa: S101 — invariant
        return _build_signer_from_profile(self.config.profile, self.config.config_file)


__all__ = [
    "DEFAULT_OCI_GENAI_REGION",
    "OCIOpenAIConfig",
    "OCIOpenAIModel",
    "build_oci_openai_base_url",
]
