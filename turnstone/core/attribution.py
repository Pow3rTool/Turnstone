"""Durable attribution for one trigger-to-ready harness excursion.

Turnstone's Primer models a coordinator as a daemon made from ordinary
trigger -> work -> ready runs ("excursions").  A long-lived workstream owner
is therefore not necessarily the trusted principal whose authority drives a
particular excursion.  This module keeps those identities separate and gives
the excursion attribution one wire/storage representation.

The values are shell-owned control state.  Models may reference a trusted
workstream that already carries attribution, but they never provide a raw
``principal_id``.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

ATTRIBUTION_VERSION = "1"

CONFIG_VERSION_KEY = "excursion_attribution_version"
CONFIG_STATE_KEY = "excursion_attribution_state"
CONFIG_PRINCIPAL_KEY = "excursion_principal_id"
CONFIG_EXCURSION_KEY = "excursion_id"
CONFIG_CAUSE_ACTION_KEY = "excursion_cause_action_id"
CONFIG_CAUSE_WORKSTREAM_KEY = "excursion_cause_workstream_id"
CONFIG_CONFLICTING_PRINCIPALS_KEY = "excursion_conflicting_principal_ids"

ATTRIBUTION_STATE_RESOLVED = "resolved"
ATTRIBUTION_STATE_AMBIGUOUS = "ambiguous"

CLAIM_VERSION_KEY = "excursion_attribution_version"
CLAIM_PRINCIPAL_KEY = "excursion_principal_id"
CLAIM_EXCURSION_KEY = "excursion_id"
CLAIM_CAUSE_ACTION_KEY = "excursion_cause_action_id"
CLAIM_CAUSE_WORKSTREAM_KEY = "excursion_cause_workstream_id"

_MAX_PRINCIPAL = 256
_MAX_ID = 256


def _clean(value: Any, *, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


@dataclass(frozen=True, slots=True)
class ExcursionAttribution:
    """Trusted principal and causal lineage for one harness excursion."""

    principal_id: str
    excursion_id: str
    cause_action_id: str = ""
    cause_workstream_id: str = ""

    def __post_init__(self) -> None:
        principal = _clean(self.principal_id, limit=_MAX_PRINCIPAL)
        excursion = _clean(self.excursion_id, limit=_MAX_ID)
        cause_action = _clean(self.cause_action_id, limit=_MAX_ID)
        cause_ws = _clean(self.cause_workstream_id, limit=_MAX_ID)
        if not principal:
            raise ValueError("excursion attribution requires a principal_id")
        if not excursion:
            raise ValueError("excursion attribution requires an excursion_id")
        object.__setattr__(self, "principal_id", principal)
        object.__setattr__(self, "excursion_id", excursion)
        object.__setattr__(self, "cause_action_id", cause_action)
        object.__setattr__(self, "cause_workstream_id", cause_ws)

    @classmethod
    def start(
        cls,
        principal_id: str,
        *,
        cause_action_id: str = "",
        cause_workstream_id: str = "",
        excursion_id: str = "",
    ) -> ExcursionAttribution:
        """Create a new root excursion, or reconstruct a trusted inherited one."""

        return cls(
            principal_id=principal_id,
            excursion_id=excursion_id or uuid.uuid4().hex,
            cause_action_id=cause_action_id,
            cause_workstream_id=cause_workstream_id,
        )

    def for_spawn_edge(
        self,
        *,
        action_id: str,
        cause_workstream_id: str,
    ) -> ExcursionAttribution:
        """Carry the principal/excursion across a newly-authorized spawn edge."""

        return replace(
            self,
            cause_action_id=action_id,
            cause_workstream_id=cause_workstream_id,
        )

    def to_config(self) -> dict[str, str]:
        return {
            CONFIG_VERSION_KEY: ATTRIBUTION_VERSION,
            CONFIG_STATE_KEY: ATTRIBUTION_STATE_RESOLVED,
            CONFIG_PRINCIPAL_KEY: self.principal_id,
            CONFIG_EXCURSION_KEY: self.excursion_id,
            CONFIG_CAUSE_ACTION_KEY: self.cause_action_id,
            CONFIG_CAUSE_WORKSTREAM_KEY: self.cause_workstream_id,
            CONFIG_CONFLICTING_PRINCIPALS_KEY: "",
        }

    def to_claims(self) -> dict[str, str]:
        return {
            CLAIM_VERSION_KEY: ATTRIBUTION_VERSION,
            CLAIM_PRINCIPAL_KEY: self.principal_id,
            CLAIM_EXCURSION_KEY: self.excursion_id,
            CLAIM_CAUSE_ACTION_KEY: self.cause_action_id,
            CLAIM_CAUSE_WORKSTREAM_KEY: self.cause_workstream_id,
        }

    def to_public_dict(self) -> dict[str, str]:
        """Model/UI-facing representation; values remain trusted metadata."""

        return {
            "principal_id": self.principal_id,
            "excursion_id": self.excursion_id,
            "cause_action_id": self.cause_action_id,
            "cause_workstream_id": self.cause_workstream_id,
        }

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> ExcursionAttribution | None:
        version = _clean(config.get(CONFIG_VERSION_KEY), limit=16)
        state = _clean(config.get(CONFIG_STATE_KEY), limit=16)
        principal = _clean(config.get(CONFIG_PRINCIPAL_KEY), limit=_MAX_PRINCIPAL)
        excursion = _clean(config.get(CONFIG_EXCURSION_KEY), limit=_MAX_ID)
        present = bool(version or state or principal or excursion)
        if not present:
            return None
        if version != ATTRIBUTION_VERSION:
            raise ValueError(f"unsupported excursion attribution version: {version!r}")
        if state == ATTRIBUTION_STATE_AMBIGUOUS:
            return None
        if state not in ("", ATTRIBUTION_STATE_RESOLVED):
            raise ValueError(f"unsupported excursion attribution state: {state!r}")
        return cls(
            principal_id=principal,
            excursion_id=excursion,
            cause_action_id=_clean(config.get(CONFIG_CAUSE_ACTION_KEY), limit=_MAX_ID),
            cause_workstream_id=_clean(config.get(CONFIG_CAUSE_WORKSTREAM_KEY), limit=_MAX_ID),
        )

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any]) -> ExcursionAttribution | None:
        version = _clean(claims.get(CLAIM_VERSION_KEY), limit=16)
        principal = _clean(claims.get(CLAIM_PRINCIPAL_KEY), limit=_MAX_PRINCIPAL)
        excursion = _clean(claims.get(CLAIM_EXCURSION_KEY), limit=_MAX_ID)
        present = bool(version or principal or excursion)
        if not present:
            return None
        if version != ATTRIBUTION_VERSION:
            raise ValueError(f"unsupported excursion attribution version: {version!r}")
        return cls(
            principal_id=principal,
            excursion_id=excursion,
            cause_action_id=_clean(claims.get(CLAIM_CAUSE_ACTION_KEY), limit=_MAX_ID),
            cause_workstream_id=_clean(claims.get(CLAIM_CAUSE_WORKSTREAM_KEY), limit=_MAX_ID),
        )


def attribution_from_auth(auth: Any) -> ExcursionAttribution | None:
    """Read signed coordinator attribution from an ``AuthResult``-like object.

    Ordinary human/service JWTs cannot opt into delegated identity by adding
    body fields.  Only a token whose validated ``src`` is ``coordinator`` may
    carry the claims across the console -> node proxy boundary.
    """

    if auth is None or getattr(auth, "token_source", "") != "coordinator":
        return None
    claims = getattr(auth, "extra_claims", None)
    if not isinstance(claims, Mapping):
        return None
    return ExcursionAttribution.from_claims(claims)


def ambiguous_attribution_config(principal_ids: set[str] | frozenset[str]) -> dict[str, str]:
    """Persist a fail-closed multi-principal attribution state.

    The principal list is diagnostic control metadata, not an authority set:
    no member may be selected implicitly for a delegated call.
    """

    cleaned = sorted(
        {principal for raw in principal_ids if (principal := _clean(raw, limit=_MAX_PRINCIPAL))}
    )
    if len(cleaned) < 2:
        raise ValueError("ambiguous attribution requires at least two principals")
    return {
        CONFIG_VERSION_KEY: ATTRIBUTION_VERSION,
        CONFIG_STATE_KEY: ATTRIBUTION_STATE_AMBIGUOUS,
        CONFIG_PRINCIPAL_KEY: "",
        CONFIG_EXCURSION_KEY: "",
        CONFIG_CAUSE_ACTION_KEY: "",
        CONFIG_CAUSE_WORKSTREAM_KEY: "",
        CONFIG_CONFLICTING_PRINCIPALS_KEY: json.dumps(cleaned, separators=(",", ":")),
    }


def conflicting_principals_from_config(config: Mapping[str, Any]) -> frozenset[str]:
    """Return persisted ambiguous principals, validating the state envelope."""

    state = _clean(config.get(CONFIG_STATE_KEY), limit=16)
    if state != ATTRIBUTION_STATE_AMBIGUOUS:
        return frozenset()
    version = _clean(config.get(CONFIG_VERSION_KEY), limit=16)
    if version != ATTRIBUTION_VERSION:
        raise ValueError(f"unsupported excursion attribution version: {version!r}")
    raw = config.get(CONFIG_CONFLICTING_PRINCIPALS_KEY)
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid conflicting excursion principals") from exc
    if not isinstance(decoded, list):
        raise ValueError("invalid conflicting excursion principals")
    principals = frozenset(
        principal for item in decoded if (principal := _clean(item, limit=_MAX_PRINCIPAL))
    )
    if len(principals) < 2:
        raise ValueError("ambiguous attribution requires at least two principals")
    return principals
