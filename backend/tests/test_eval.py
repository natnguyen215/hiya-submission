"""Tests for eval/run.py without any LLM: how planted moments are scored, and the paced mode's
timing (turns that arrive during an analysis, lines withdrawn when a person speaks first)."""

import asyncio
import json

from helpers import add_turn, make_state, new_flag, now, output

from backend.app import config, policy
from backend.app.llm import FakeLLM
from backend.app.models import AnalyzerOutput, SummonAnswer
from eval import run


def scored_call(state):
    call = run.Call()
    call.state = state
    return call


def moment(turn_id, **expect):
    return {"id": "x01", "turn_id": turn_id, "expect": {"trigger": None, "note": "", **expect}}


# ---------------------------------------------------------------- scoring


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
    add_turn(state, "beacon", "Quick check for Maria: what is SAP?")  # another Beacon turn mentioning nothing
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


# ---------------------------------------------------------------- paced mode


def covered_reply(prompt, schema):
    if schema is AnalyzerOutput and "So it's covered." in prompt:  # repeats are ignored by dedupe
        return output([new_flag(["t2", "t3"], ["So it's covered"])])
    return output()


def paced_run(monkeypatch, tmp_path, lines, respond=covered_reply):
    """Run run_script_paced on a script of (role, text, pause) with a FakeLLM; return the call and
    the fake. A FakeLLM records no network time, so every call takes the assumed latency."""
    script = [{"id": f"x{i:02d}", "role": r, "text": t, "pause_before_ms": p} for i, (r, t, p) in enumerate(lines, 1)]
    (tmp_path / "paced_test.json").write_text(json.dumps(script), encoding="utf-8")
    monkeypatch.setattr(config, "SCRIPTS_DIR", tmp_path)
    fake = FakeLLM(respond)
    fake.latencies_ms, fake.cache = [], False  # what run_script_paced reads from GeminiLLM
    _, call = asyncio.run(run.run_script_paced(fake, "paced_test", assumed_latency_ms=1500))
    return call, fake


def test_paced_a_turn_arriving_during_an_analysis_is_seen_late_then_analyzed(monkeypatch, tmp_path):
    lines = [("counselor", "Daniel's total aid package is $31,500.", 300), ("parent", "So it's covered.", 500), ("parent", "Oh,", 200)]
    call, fake = paced_run(monkeypatch, tmp_path, lines)
    assert (call.analyses, call.seen_late) == (2, 1)
    assert "Oh," not in fake.prompts[0].split("## Transcript")[1]  # the first analysis didn't see it
    assert "t4 PARENT" in fake.prompts[1]


def test_paced_a_line_is_withdrawn_when_someone_speaks_first(monkeypatch, tmp_path):
    lines = [
        ("counselor", "Daniel's total aid package is $31,500.", 300),
        ("parent", "So it's covered.", 500),
        ("counselor", "Next, housing.", 3000),  # starts after the card: moving on, so the line is queued
        ("counselor", "And meals are included.", 1000),  # starts before latency + pause: Beacon waits
    ]
    call, _ = paced_run(monkeypatch, tmp_path, lines)
    assert call.withdrawn == 1
    assert "withdrew queued line for f1: t5 arrived first; re-deciding" in call.decisions
    # The next analysis finds it due again, and with nobody talking Beacon asks after t5.
    assert call.state.flags[0].state == "spoken"
    assert [t.role for t in call.state.turns][-1] == "beacon"
    assert call.state.turns[-1].started_at >= call.state.turns[-2].ended_at + config.PAUSE_BEFORE_SPEAK_MS
