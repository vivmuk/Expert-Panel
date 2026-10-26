"""Contract tests for the mode system.

A mode is a module that registers a ModeSpec and ships its prompts. These tests
fail when a mode is registered without its prompts, when a prompt needs a slot
the runner does not pass, or when a structured-output schema is not closed.

Run:  python -m pytest tests/test_modes.py -q
(They need no network and no Venice key.)
"""
import os
import re
import sys
import types

import pytest

# The mode registry is intentionally importable without Flask: an API process is
# not required to add or test a mode. When Flask is absent, give the package a
# namespace shell so `server.modes` loads on its own.
if __import__("importlib.util", fromlist=["find_spec"]).find_spec("flask") is None:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _pkg = types.ModuleType("server")
    _pkg.__path__ = [os.path.join(_root, "server")]
    sys.modules.setdefault("server", _pkg)

from server.modes import MODE_REGISTRY, modes  # noqa: E402

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "server", "prompts")
INSIGHT_SLOTS = {"name", "title", "background", "focus_areas", "perspective", "problem", "market_context"}
SYNTH_SLOTS = {"panel_size", "problem", "insights_block", "market_block", "extra_block"}
PRESTAGE_SLOTS = {"problem", "scenario_count", "horizon"}


def _slots(name):
    with open(os.path.join(PROMPT_DIR, name + ".md"), encoding="utf-8") as f:
        return set(re.findall(r"\{(\w+)\}", f.read()))


def test_all_modes_available():
    assert modes(), "no modes registered"
    assert all(m.available for m in modes()), [m.id for m in modes() if not m.available]


def test_mode_ids_unique_and_stable():
    ids = [m.id for m in MODE_REGISTRY.values()]
    assert len(ids) == len(set(ids))
    for expected in ("deep_dive", "red_team", "quick_pulse", "board_meeting", "workchart",
                     "scenario_planning", "due_diligence", "ai_opportunity_scan", "digital_twin"):
        assert expected in MODE_REGISTRY, f"{expected} not registered"


@pytest.mark.parametrize("mode", modes(), ids=[m.id for m in modes()])
def test_prompts_exist_and_slots_match(mode):
    if mode.flow == "panel":
        assert not (_slots(mode.insight_prompt) - INSIGHT_SLOTS), mode.insight_prompt
        if not mode.quantitative:
            assert not (_slots(mode.synthesis_prompt) - SYNTH_SLOTS), mode.synthesis_prompt
    if mode.pre_stage == "scenarios":
        assert not (_slots("modes/scenario_generate") - PRESTAGE_SLOTS)
    if mode.pre_stage == "twin":
        assert not (_slots("modes/twin_generate") - PRESTAGE_SLOTS)


@pytest.mark.parametrize("mode", modes(), ids=[m.id for m in modes()])
def test_schemas_are_closed(mode):
    schema = mode.insight_schema
    if not schema:
        return
    assert schema.get("additionalProperties") is False
    item = schema.get("properties", {}).get("insights_and_analysis", {}).get("items")
    if item is None:
        return  # pulse-style flat schema
    assert item.get("additionalProperties") is False
    for field in mode.extra_fields:
        assert field in item["properties"], f"{field} missing from schema"
        assert field in item["required"], f"{field} must be required"


@pytest.mark.parametrize("mode", modes(), ids=[m.id for m in modes()])
def test_public_payload_has_no_internals(mode):
    public = mode.to_public()
    assert public["status"] in ("available", "coming_soon")
    assert "defaults" in public and public["defaults"]["panelSize"] >= 3
    assert "insight_prompt" not in public
