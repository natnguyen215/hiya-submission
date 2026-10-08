"""Unit tests for policy.py: evidence gate, dedupe, ladder, staleness, cooldown, questions."""

from helpers import add_turn, make_state, new_flag, output

from backend.app import config, policy
from backend.app.models import LogEntry

NOW = 1_000_000_000


def speak_actions(actions):
    return [a for a in actions if isinstance(a, policy.SpeakLine)]


def log_text(actions):
    return " | ".join(a.message for a in actions if isinstance(a, LogEntry))


def covered_state():
    """Counselor states the package, parent misreads it, analyzer flags it."""
    state = make_state(
        ("counselor", "Daniel's total aid package is $31,500."),
        ("parent", "Oh, thank goodness. So it's covered."),
    )
    flag = new_flag(["t1", "t2"], ["So it's covered", "total aid package is $31,500"])
    policy.after_analysis(state, output([flag]), len(state.turns), NOW)
    return state


# ---------------------------------------------------------------- evidence gate


def test_quote_matching_tolerates_case_punctuation_and_contractions():
    assert policy.quote_in_text("so it is covered", "Oh, thank goodness. So it's covered.")
    assert policy.quote_in_text("OH GOOD so we're verified", "Oh good, so we're verified?")
    assert not policy.quote_in_text("we never have to pay anything", "Oh good, so we're verified?")
    assert not policy.quote_in_text("", "anything")


def test_real_quotes_create_a_nudged_flag():
    state = covered_state()
    assert [(f.id, f.state) for f in state.flags] == [("f1", "nudged")]


def test_fabricated_quote_is_dropped_with_a_reason():
    state = make_state(("counselor", "Your aid package is $31,500."), ("parent", "Okay."))
    flag = new_flag(["t1", "t2"], ["so we never pay anything back"])
    actions = policy.after_analysis(state, output([flag]), 2, NOW)
    assert state.flags[0].state == "dropped"
    assert "quote not found" in state.flags[0].history[0].reason
    assert not speak_actions(actions)


def test_quote_from_a_different_turn_is_dropped():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."), ("counselor", "Next, housing."))
    flag = new_flag(["t2"], ["Next, housing"])
    policy.after_analysis(state, output([flag]), 3, NOW)
    assert state.flags[0].state == "dropped"


def test_evidence_must_include_a_parent_turn():
    state = make_state(("counselor", "You need SAP."), ("parent", "Okay."))
    flag = new_flag(["t1"], ["You need SAP"], trigger="UNEXPLAINED_JARGON")
    policy.after_analysis(state, output([flag]), 2, NOW)
    assert "no parent turn" in state.flags[0].history[0].reason


def test_unknown_trigger_and_unknown_doc_refs():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."))
    bad = new_flag(["t2"], ["So it's covered"], trigger="MADE_UP")
    good = new_flag(["t2"], ["So it's covered"], key="other")
    good.doc_refs = ["L17", "L999"]
    actions = policy.after_analysis(state, output([bad, good]), 2, NOW)
    assert [f.issue_key for f in state.flags] == ["other"]
    assert state.flags[0].doc_refs == ["L17"]
    assert "unknown trigger" in log_text(actions)


# ---------------------------------------------------------------- dedupe


def test_same_issue_key_is_ignored_the_second_time():
    state = covered_state()
    add_turn(state, "parent", "So it's covered, right?")
    again = new_flag(["t3"], ["So it's covered"])
    actions = policy.after_analysis(state, output([again]), 3, NOW)
    assert len(state.flags) == 1
    assert "duplicate of f1" in log_text(actions)


# ---------------------------------------------------------------- escalation ladder


def test_nudge_then_resolved_stays_silent():
    state = covered_state()
    add_turn(state, "counselor", "Let me be careful: $14,000 of that is loans you repay.")
    actions = policy.after_analysis(state, output(resolved=["f1"]), 3, NOW)
    assert state.flags[0].state == "resolved"
    assert not speak_actions(actions)


def test_nudge_then_spoken_after_counselor_turns_without_clarifying():
    state = covered_state()
    add_turn(state, "counselor", "Moving on to housing, that's $16,500.")
    actions = policy.after_analysis(state, output(), 3, NOW)
    [speak] = speak_actions(actions)
    assert speak.flag_id == "f1" and speak.text == state.flags[0].spoken_line
    assert state.flags[0].state == "nudged"  # becomes spoken only once actually said
    policy.mark_spoken(state, "f1", "t4", NOW + 2000)
    assert state.flags[0].state == "spoken"
    assert state.last_spoken_at == NOW + 2000


def test_parent_turns_alone_do_not_escalate():
    state = covered_state()
    add_turn(state, "parent", "Daniel will be so happy.")
    assert not speak_actions(policy.after_analysis(state, output(), 3, NOW))


def test_only_turns_the_analyzer_saw_are_counted():
    state = covered_state()
    add_turn(state, "counselor", "Moving on to housing.")
    # The analysis covered 2 turns; the counselor turn arrived during the LLM call.
    assert not speak_actions(policy.after_analysis(state, output(), 2, NOW))


def test_cooldown_delays_then_staleness_sends_to_recap():
    state = covered_state()
    state.last_spoken_at = NOW - 5_000
    add_turn(state, "counselor", "Moving on to housing.")
    actions = policy.after_analysis(state, output(), 3, NOW)
    assert not speak_actions(actions)
    assert "cooldown" in log_text(actions)
    for i in range(config.STALE_AFTER_TURNS):
        add_turn(state, "counselor" if i % 2 else "parent", f"More talk {i}.")
    actions = policy.after_analysis(state, output(), len(state.turns), NOW + 6_000)
    assert state.flags[0].state == "recap"
    assert "stale" in state.flags[0].history[-1].reason
    assert not speak_actions(actions)


def test_cooldown_expires():
    state = covered_state()
    state.last_spoken_at = NOW - (config.SPEAK_COOLDOWN_SECONDS + 1) * 1000
    add_turn(state, "counselor", "Moving on to housing.")
    assert speak_actions(policy.after_analysis(state, output(), 3, NOW))


def test_beacon_turns_do_not_count_toward_staleness():
    state = covered_state()
    state.last_spoken_at = NOW
    add_turn(state, "counselor", "Moving on.")
    for _ in range(5):
        add_turn(state, "beacon", "Something.")
    policy.after_analysis(state, output(), len(state.turns), NOW + 1000)
    assert state.flags[0].state == "nudged"


def test_recap_severity_is_never_spoken():
    state = make_state(("counselor", "Your SAI came from the FAFSA."), ("parent", "He loves the library."))
    flag = new_flag(["t1", "t2"], ["Your SAI", "He loves the library"], key="sai", severity="recap")
    policy.after_analysis(state, output([flag]), 2, NOW)
    for i in range(3):
        add_turn(state, "counselor", f"Logistics {i}.")
        assert not speak_actions(policy.after_analysis(state, output(), len(state.turns), NOW))
    assert state.flags[0].state == "recap"


def test_one_interjection_at_a_time():
    state = make_state(("counselor", "It's $31,500 and SAP applies."), ("parent", "So it's covered. Okay."))
    flags = [new_flag(["t2"], ["So it's covered"], key="a"), new_flag(["t2"], ["Okay"], key="b")]
    policy.after_analysis(state, output(flags), 2, NOW)
    add_turn(state, "counselor", "Moving on.")
    actions = policy.after_analysis(state, output(), 3, NOW)
    assert [s.flag_id for s in speak_actions(actions)] == ["f1"]
    assert "one interjection at a time" in log_text(actions)


def test_old_evidence_goes_straight_to_recap():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."))
    for i in range(config.STALE_AFTER_TURNS + 1):
        add_turn(state, "counselor", f"Later topic {i}.")
    policy.after_analysis(state, output([new_flag(["t2"], ["So it's covered"])]), len(state.turns), NOW)
    assert state.flags[0].state == "recap"


def test_end_of_call_moves_open_flags_to_recap():
    state = covered_state()
    policy.end_of_call(state, NOW)
    assert state.flags[0].state == "recap"


# ---------------------------------------------------------------- unanswered questions


def question_state():
    state = make_state(
        ("counselor", "Daniel has $2,500 in work-study."),
        ("parent", "Does the work-study money have to be paid back?"),
    )
    asked = [("t2", "Does the work-study money have to be paid back?")]
    policy.after_analysis(state, output(opened=asked), 2, NOW)
    return state


def test_unanswered_question_is_counted_by_code_then_escalates():
    state = question_state()
    assert state.parent_questions[0].asked_turn_id == "t2"
    add_turn(state, "counselor", "Next, accept your awards in the portal.")
    actions = policy.after_analysis(state, output(), 3, NOW)
    flag = state.flags[0]
    assert (flag.trigger, flag.state) == ("UNANSWERED_QUESTION", "nudged")
    assert not speak_actions(actions)
    add_turn(state, "counselor", "You'll get an email confirmation.")
    [speak] = speak_actions(policy.after_analysis(state, output(), 4, NOW))
    assert "paid back" in speak.text


def test_answered_question_resolves_its_flag():
    state = question_state()
    add_turn(state, "counselor", "Next, the portal.")
    policy.after_analysis(state, output(), 3, NOW)
    add_turn(state, "counselor", "And no, work-study is a paycheck, never repaid.")
    policy.after_analysis(state, output(answered=[("t2", "t4")]), 4, NOW)
    assert state.parent_questions[0].answered_turn_id == "t4"
    assert state.flags[0].state == "resolved"


def test_question_already_covered_by_a_flag_is_not_tracked_twice():
    state = make_state(("counselor", "He was selected for verification."), ("parent", "Oh good, so we're verified?"))
    flag = new_flag(["t2"], ["so we're verified"], key="verification_means_approved")
    actions = policy.after_analysis(state, output([flag], opened=[("t2", "so we're verified?")]), 2, NOW)
    assert state.parent_questions == []
    assert "already covered by f1" in log_text(actions)


def test_question_text_must_be_in_the_turn():
    state = make_state(("counselor", "He has work-study."), ("parent", "Does that get paid back?"))
    actions = policy.after_analysis(state, output(opened=[("t2", "Is work-study a loan we repay?")]), 2, NOW)
    assert state.parent_questions == []
    assert "is not in the turn" in log_text(actions)


def test_old_unanswered_question_goes_to_recap():
    state = question_state()
    for i in range(config.STALE_AFTER_TURNS + 1):
        add_turn(state, "parent" if i % 2 else "counselor", f"Later topic {i}.")
    # Earlier analyses failed; this one is the first to see that the question went unanswered.
    actions = policy.after_analysis(state, output(), len(state.turns), NOW)
    assert state.flags[0].state == "recap"
    assert not speak_actions(actions)


def test_questions_to_beacon_are_not_tracked():
    state = make_state(("parent", "Beacon, what's a Parent PLUS loan?"))
    policy.after_analysis(state, output(opened=[("t1", "What's a Parent PLUS loan?")]), 1, NOW)
    assert state.parent_questions == []


# ---------------------------------------------------------------- when to call the LLM


def test_should_analyze():
    state = make_state(("counselor", "Hello!"))
    assert not policy.should_analyze(state, 0)
    add_turn(state, "parent", "Hi.")
    assert policy.should_analyze(state, 1)
    state = covered_state()
    add_turn(state, "counselor", "Moving on.")
    assert policy.should_analyze(state, 2)  # f1 is open, so a counselor turn might resolve it


def test_a_parent_turn_whose_analysis_failed_is_analyzed_later():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."), ("counselor", "Next."))
    assert policy.should_analyze(state, 1)  # the analysis of t2 failed, so t2 is still waiting
    assert not policy.should_analyze(state, 2)  # t2 was analyzed and nothing is open


# ---------------------------------------------------------------- turns that arrive during an analysis


def test_speaking_waits_for_turns_that_arrived_during_the_analysis():
    state = covered_state()
    add_turn(state, "counselor", "So, on to housing.")
    add_turn(state, "counselor", "Sorry, $14,000 of that is loans.")  # arrived during the LLM call
    actions = policy.after_analysis(state, output(), 3, NOW)
    assert not speak_actions(actions)
    assert "deferred" in log_text(actions)
    policy.after_analysis(state, output(resolved=["f1"]), 4, NOW)
    assert state.flags[0].state == "resolved"


def test_ladder_counts_from_when_the_card_appeared():
    state = make_state(("counselor", "Daniel's total aid package is $31,500."), ("parent", "So it's covered."))
    add_turn(state, "counselor", "Next, housing.")  # spoken before the card existed
    flag = new_flag(["t1", "t2"], ["So it's covered"])
    policy.after_analysis(state, output([flag]), 2, NOW)
    assert state.flags[0].created_at_turn == "t3"
    assert not speak_actions(policy.after_analysis(state, output(), 3, NOW))
    add_turn(state, "counselor", "And meals are included.")
    assert speak_actions(policy.after_analysis(state, output(), 4, NOW))
