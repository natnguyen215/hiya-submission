"""Unit tests for wake word detection, including ordinary phrases that must not trigger it."""

import pytest

from backend.app.triggers import TRIGGERS
from backend.app.wakeword import find_summon


@pytest.mark.parametrize(
    "text, question",
    [
        ("Beacon, what's a Parent PLUS loan?", "whats a parent plus loan"),
        ("beacon what does SAP mean", "what does sap mean"),
        ("Beacon, can you explain SAP", "can you explain sap"),
        ("What does SAP mean, Beacon?", "what does sap mean"),
    ],
)
def test_wake_word_variants(text, question):
    # "bacon" scores 0.91 and would match; accepted since it is unlikely in a financial aid call.
    assert find_summon(text) == question


@pytest.mark.parametrize(
    "text",
    [
        "Could you pass the can of peas?",
        "He'll live on campus next year.",
        "The canopy over the quad is new.",
        "Thanks, Beacon.",  # the name without a question
        "Oh, good catch Beacon, thank you",
        "Can you open the portal?",
        "Beacon will send you a recap at the end.",  # statements about Beacon
        "Beacon can help with that later.",
        "The deacon asked what time it starts?",
        "What do you reckon, should we beckon him over?",
        "What will become of the grant?",
    ],
)
def test_not_a_summon(text):
    assert find_summon(text) is None


def test_summon_trigger_examples_match_the_detector():
    summon = next(t for t in TRIGGERS if t.name == "SUMMON")
    assert all(find_summon(e) for e in summon.positive_examples)
    assert not any(find_summon(e) for e in summon.negative_examples)
