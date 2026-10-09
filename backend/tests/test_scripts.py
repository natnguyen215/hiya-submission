"""Checks the scripts in data/scripts: well-formed lines, valid expectations, and summon lines
that the wake-word detector actually recognizes. A typo here would silently skew the eval."""

import json

import pytest

from backend.app import config, docs
from backend.app.triggers import TRIGGERS
from backend.app.wakeword import find_summon
from eval.run import CLEAN_SCRIPTS, SCRIPTS, expected_outcomes

TRIGGER_NAMES = {t.name for t in TRIGGERS}
# Flag states, summon results, and "quiet": any state except spoken.
OUTCOMES = {"none", "nudged", "resolved", "spoken", "recap", "answered", "declined", "quiet"}


def load(name: str) -> list[dict]:
    return json.loads((config.SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_every_script_file_is_in_the_eval():
    assert sorted(SCRIPTS) == sorted(path.stem for path in config.SCRIPTS_DIR.glob("*.json"))
    assert CLEAN_SCRIPTS <= set(SCRIPTS)


@pytest.mark.parametrize("name", SCRIPTS)
def test_script_lines_are_well_formed(name):
    lines = load(name)
    assert len({line["id"] for line in lines}) == len(lines)
    for line in lines:
        assert line["role"] in ("counselor", "parent") and line["text"].strip()
        assert isinstance(line["pause_before_ms"], int) and line["pause_before_ms"] >= 0
        expect = line.get("expect")
        is_summon = bool(find_summon(line["text"]))
        if expect:
            assert expect["trigger"] is None or expect["trigger"] in TRIGGER_NAMES
            outcomes = expected_outcomes(expect)
            assert outcomes and set(outcomes) <= OUTCOMES, line["id"]
            # The eval grades what was said, not only the state: an answer must cite an expected
            # line, and an interjection must mention what the moment is about.
            if "answered" in outcomes:
                assert expect["refs"] and set(expect["refs"]) <= set(docs.LINES), line["id"]
            if "spoken" in outcomes:
                assert expect["mentions"] and all(m == m.lower() for m in expect["mentions"]), line["id"]
            # A summon moment must reach the summon path, and nothing else may.
            assert is_summon == (expect["trigger"] == "SUMMON"), line["id"]
        else:
            assert not is_summon, f"{line['id']} would summon Beacon without an expectation"


def test_clean_scripts_plant_nothing():
    for name in CLEAN_SCRIPTS:
        assert not any(line.get("expect", {}).get("trigger") for line in load(name))


def test_noisy_demo_keeps_the_demo_structure():
    demo, noisy = load("demo_call"), load("demo_call_stt_noise")
    assert [(d["role"], d.get("expect")) for d in demo] == [(n["role"], n.get("expect")) for n in noisy]
    assert all("?" not in n["text"] for n in noisy)  # Chrome rarely adds question marks
