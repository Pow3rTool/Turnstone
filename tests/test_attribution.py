"""Excursion-attribution control-state tests."""

from __future__ import annotations

import pytest

from turnstone.core.attribution import (
    ATTRIBUTION_STATE_AMBIGUOUS,
    CONFIG_STATE_KEY,
    ExcursionAttribution,
    ambiguous_attribution_config,
    attribution_from_auth,
    conflicting_principals_from_config,
)
from turnstone.core.auth import AuthResult


def test_excursion_attribution_round_trips_config_and_claims():
    attribution = ExcursionAttribution.start(
        "john",
        excursion_id="exc-1",
        cause_action_id="call-1",
        cause_workstream_id="coord-1",
    )

    assert ExcursionAttribution.from_config(attribution.to_config()) == attribution
    assert ExcursionAttribution.from_claims(attribution.to_claims()) == attribution


def test_ambiguous_config_has_no_implicit_principal():
    config = ambiguous_attribution_config({"john", "jared"})

    assert config[CONFIG_STATE_KEY] == ATTRIBUTION_STATE_AMBIGUOUS
    assert ExcursionAttribution.from_config(config) is None
    assert conflicting_principals_from_config(config) == frozenset({"jared", "john"})


def test_partial_or_unknown_attribution_fails_loudly():
    with pytest.raises(ValueError, match="version"):
        ExcursionAttribution.from_config({"excursion_principal_id": "john"})
    with pytest.raises(ValueError, match="version"):
        ExcursionAttribution.from_claims({"excursion_principal_id": "john"})


def test_only_coordinator_auth_may_supply_inherited_attribution():
    attribution = ExcursionAttribution.start("john", excursion_id="exc-1")
    human = AuthResult(
        user_id="jared",
        scopes=frozenset({"write"}),
        token_source="jwt",
        permissions=frozenset(),
        extra_claims=attribution.to_claims(),
    )
    coordinator = AuthResult(
        user_id="jared",
        scopes=frozenset({"write"}),
        token_source="coordinator",
        permissions=frozenset({"admin.coordinator"}),
        extra_claims=attribution.to_claims(),
    )

    assert attribution_from_auth(human) is None
    assert attribution_from_auth(coordinator) == attribution
