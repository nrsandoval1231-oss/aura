"""Current fail-closed boundary for the proposed Luna/Astra route."""

import pytest

from forge.providers import model_provider as mp
from forge.providers.capability import Capability


def test_luna_astra_same_family_cannot_activate_under_inherited_policy(monkeypatch):
    """The proposed exception needs owner approval and a separate implementation packet."""
    monkeypatch.setattr(mp, "PROVIDERS", {"openai": mp.PROVIDERS["openai"]})
    monkeypatch.setattr(mp, "ROUTING", {Capability.ROUTINE_AUDIT: "openai"})
    with pytest.raises(mp.ProviderError, match="No provider outside family"):
        mp.independent_auditor(Capability.ROUTINE_AUDIT, "openai")
