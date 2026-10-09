"""Tests for how eval/run.py scores planted moments. No LLM is used."""

from helpers import add_turn, make_state, new_flag, now, output

from backend.app import policy
from backend.app.models import SummonAnswer
from eval import run


def scored_call(state):
    call = run.Call()
    call.state = state
    return call


def moment(turn_id, **expect):
    return {"id": "x01", "turn_id": turn_id, "expect": {"trigger": None, "note": "", **expect}}


def test_an_answered_summon_must_cite_an_expected_line():
    call = scored_call(make_state(("parent", "Beacon, what's a Parent PLUS loan?")))
    line = moment("t1", trigger="SUMMON", outcome="answered", refs=["G9", "L15"])
    call.summons["t1"] = SummonAnswer(answer="It's a loan the parent borrows.", answered_from_documents=True, doc_refs=["G4"])
    assert not run.score(line, call)["passed"]
    call.summons["t1"].doc_refs = ["G9"]
    assert run.score(line, call)["passed"]


def test_a_declined_summon_must_not_give_a_dollar_amount():
    call = scored_call(make_state(("parent", "Beacon, when is the first payment due?")))
    line = moment("t1", trigger="SUMMON", outcome="declined")
    call.summons["t1"] = SummonAnswer(answer="I don't have that; it's about $6,500. Ask Alex.", answered_from_documents=False, doc_refs=[])
    assert run.score(line, call)["outcome"] == "declined, but with a dollar amount"
    call.summons["t1"].answer = "I don't have that in the documents. Alex can tell you."
    assert run.score(line, call)["passed"]


def spoken_state(beacon_text):
    state = make_state(("counselor", "Daniel's total aid package is $31,500."), ("parent", "So it's covered."))
    policy.after_analysis(state, output([new_flag(["t1", "t2"], ["So it's covered"])]), 2, now(state))
    add_turn(state, "counselor", "Next, housing.")
    add_turn(state, "beacon", "Quick check for Maria: what is SAP?")  # another Beacon turn, about something else
    beacon = add_turn(state, "beacon", beacon_text)
    policy.mark_spoken(state, "f1", beacon.id, now(state))
    return state


def test_a_spoken_line_must_mention_the_moment():
    line = moment("t2", trigger="MISREAD_TERM", outcome="spoken", mentions=["loan"])
    off_topic = run.score(line, scored_call(spoken_state("Quick check for Maria: when is the deadline?")))
    assert (off_topic["outcome"], off_topic["passed"]) == ("spoken, off topic", False)
    assert run.score(line, scored_call(spoken_state("Quick check for Maria: how much is loans?")))["passed"]


def test_quiet_passes_on_anything_but_spoken_and_can_require_a_flag():
    quiet = moment("t2", outcome="quiet")
    required = moment("t2", trigger="MISREAD_TERM", outcome="quiet", flag_required=True)
    nothing = scored_call(make_state(("counselor", "It's $31,500."), ("parent", "So it's covered.")))
    assert run.score(quiet, nothing)["passed"] and not run.score(required, nothing)["passed"]
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."))
    policy.after_analysis(state, output([new_flag(["t1", "t2"], ["So it's covered"])]), 2, now(state))
    assert run.score(required, scored_call(state))["passed"]
    spoken = scored_call(spoken_state("Quick check for Maria: how much is loans?"))
    assert not run.score(quiet, spoken)["passed"]
