"""Unit tests for policy.py: evidence gate, dedupe, ladder, staleness, cooldown, questions, and
the counselor's card buttons (including what a dismissal means for the prompt and the recap)."""

import pytest
from helpers import add_turn, make_state, new_flag, now, output

from backend.app import analyzer, config, policy
from backend.app.models import LogEntry, Recap, RecapItem


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
    policy.after_analysis(state, output([flag]), len(state.turns), now(state))
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
    actions = policy.after_analysis(state, output([flag]), 2, now(state))
    assert state.flags[0].state == "dropped"
    assert "quote not found" in state.flags[0].history[0].reason
    assert not speak_actions(actions)


def test_quote_from_a_different_turn_is_dropped():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."), ("counselor", "Next, housing."))
    flag = new_flag(["t2"], ["Next, housing"])
    policy.after_analysis(state, output([flag]), 3, now(state))
    assert state.flags[0].state == "dropped"


def test_evidence_must_include_a_parent_turn():
    state = make_state(("counselor", "You need SAP."), ("parent", "Okay."))
    flag = new_flag(["t1"], ["You need SAP"], trigger="UNEXPLAINED_JARGON")
    policy.after_analysis(state, output([flag]), 2, now(state))
    assert "no parent turn" in state.flags[0].history[0].reason


def test_unknown_trigger_and_unknown_doc_refs():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."))
    bad = new_flag(["t2"], ["So it's covered"], trigger="MADE_UP")
    good = new_flag(["t2"], ["So it's covered"], key="other")
    good.doc_refs = ["L17", "L999"]
    actions = policy.after_analysis(state, output([bad, good]), 2, now(state))
    assert [f.issue_key for f in state.flags] == ["other"]
    assert state.flags[0].doc_refs == ["L17"]
    assert "unknown trigger" in log_text(actions)


# ---------------------------------------------------------------- dedupe


def test_same_issue_key_is_ignored_the_second_time():
    state = covered_state()
    add_turn(state, "parent", "So it's covered, right?")
    again = new_flag(["t3"], ["So it's covered"])
    actions = policy.after_analysis(state, output([again]), 3, now(state))
    assert len(state.flags) == 1
    assert "duplicate of f1" in log_text(actions)


def test_same_moment_under_a_new_key_is_ignored_even_after_it_was_resolved():
    # Seen with Gemini: a resolved jargon flag came back as "..._2" with identical evidence.
    state = covered_state()
    add_turn(state, "counselor", "To be clear, $14,000 of that is loans.")
    policy.after_analysis(state, output(resolved=["f1"]), 3, now(state))
    again = new_flag(["t1", "t2"], ["So it's covered"], key="aid_package_includes_loans_2")
    actions = policy.after_analysis(state, output([again]), 3, now(state))
    assert len(state.flags) == 1
    assert "same MISREAD_TERM moment as f1" in log_text(actions)


def test_a_relapse_after_a_resolved_flag_is_raised_again_under_the_same_key():
    state = covered_state()
    add_turn(state, "counselor", "To be clear, $14,000 of that is loans you repay.")
    policy.after_analysis(state, output(resolved=["f1"]), 3, now(state))
    add_turn(state, "parent", "Okay. Well, at least it's all covered.")
    relapse = new_flag(["t3", "t4"], ["at least it's all covered"])  # same issue_key as f1
    policy.after_analysis(state, output([relapse]), 4, now(state))
    assert [(f.id, f.issue_key, f.state) for f in state.flags] == [
        ("f1", "aid_package_includes_loans", "resolved"),
        ("f2", "aid_package_includes_loans", "nudged"),
    ]


def test_an_unanswered_question_gets_one_flag_even_if_the_analyzer_resolves_it():
    state = question_state()
    add_turn(state, "counselor", "Next, accept your awards in the portal.")
    add_turn(state, "counselor", "You'll get an email confirmation.")
    policy.after_analysis(state, output(), 4, now(state))
    policy.after_analysis(state, output(resolved=["f1"]), 4, now(state))
    add_turn(state, "counselor", "And the deadline is in May.")
    policy.after_analysis(state, output(), 5, now(state))
    assert [(f.trigger, f.state) for f in state.flags] == [("UNANSWERED_QUESTION", "resolved")]


def test_a_different_trigger_on_the_same_turn_is_still_raised():
    state = covered_state()
    jargon = new_flag(["t1", "t2"], ["So it's covered"], key="aid_package_jargon", trigger="UNEXPLAINED_JARGON")
    policy.after_analysis(state, output([jargon]), 2, now(state))
    assert [f.trigger for f in state.flags] == ["MISREAD_TERM", "UNEXPLAINED_JARGON"]


# ---------------------------------------------------------------- escalation ladder


def test_nudge_then_resolved_stays_silent():
    state = covered_state()
    add_turn(state, "counselor", "Let me be careful: $14,000 of that is loans you repay.")
    actions = policy.after_analysis(state, output(resolved=["f1"]), 3, now(state))
    assert state.flags[0].state == "resolved"
    assert not speak_actions(actions)


def test_nudge_then_spoken_after_counselor_turns_without_clarifying():
    state = covered_state()
    add_turn(state, "counselor", "Moving on to housing, that's $16,500.")
    actions = policy.after_analysis(state, output(), 3, now(state))
    [speak] = speak_actions(actions)
    assert speak.flag_id == "f1" and speak.text == state.flags[0].spoken_line
    assert state.flags[0].state == "nudged"  # becomes spoken only once actually said
    policy.mark_spoken(state, "f1", "t4", now(state) + 2000)
    assert state.flags[0].state == "spoken"
    assert state.last_spoken_at == now(state) + 2000


def test_parent_turns_alone_do_not_escalate():
    state = covered_state()
    add_turn(state, "parent", "Daniel will be so happy.")
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))


def test_only_turns_the_analyzer_saw_are_counted():
    state = covered_state()
    add_turn(state, "counselor", "Moving on to housing.")
    # The analysis covered 2 turns; the counselor turn arrived during the LLM call.
    assert not speak_actions(policy.after_analysis(state, output(), 2, now(state)))


def test_cooldown_delays_then_staleness_sends_to_recap():
    # Card, one counselor turn while the cooldown is active, then four more human turns.
    state = covered_state()
    state.last_spoken_at = now(state) - 5_000
    add_turn(state, "counselor", "Moving on to housing.")
    actions = policy.after_analysis(state, output(), 3, now(state))
    assert not speak_actions(actions)
    assert "cooldown" in log_text(actions)
    for i in range(config.STALE_AFTER_TURNS + 1):
        add_turn(state, "counselor" if i % 2 else "parent", f"More talk {i}.")
    actions = policy.after_analysis(state, output(), len(state.turns), now(state))
    assert state.flags[0].state == "recap"
    assert "stale: 4 turns since t3, the counselor's first chance" in state.flags[0].history[-1].reason
    assert not speak_actions(actions)


def test_staleness_counts_from_the_counselors_first_chance():
    # The parent splits a reply over three push-to-talk presses after the card; the counselor's
    # first turn after them still gets its chance, and moving on makes Beacon ask.
    state = covered_state()
    for text in ("Oh, wow.", "That's such a relief.", "Daniel will be thrilled."):
        add_turn(state, "parent", text)
        assert not speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))
    add_turn(state, "counselor", "So, on to housing.")
    [speak] = speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))
    assert speak.flag_id == "f1"
    assert state.flags[0].state == "nudged"


def test_a_counselor_turn_already_in_progress_when_the_card_appeared_does_not_count():
    state = make_state(("counselor", "Daniel's total aid package is $31,500."), ("parent", "So it's covered."))
    card_at = now(state) + 4_000  # the analysis finished while the counselor held push-to-talk
    policy.after_analysis(state, output([new_flag(["t1", "t2"], ["So it's covered"])]), 2, card_at)
    assert state.flags[0].ladder_start_ms == card_at
    turn = add_turn(state, "counselor", "And housing is $16,500.")
    turn.started_at, turn.ended_at = card_at - 3_000, card_at + 1_000  # started 3 s before the card
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))
    add_turn(state, "counselor", "Meals are included in that.")
    assert speak_actions(policy.after_analysis(state, output(), 4, now(state)))


def test_cooldown_expires():
    state = covered_state()
    state.last_spoken_at = now(state) - (config.SPEAK_COOLDOWN_SECONDS + 1) * 1000
    add_turn(state, "counselor", "Moving on to housing.")
    assert speak_actions(policy.after_analysis(state, output(), 3, now(state)))


def test_beacon_turns_do_not_count_toward_staleness():
    state = covered_state()
    state.last_spoken_at = now(state)
    add_turn(state, "counselor", "Moving on.")
    for _ in range(5):
        add_turn(state, "beacon", "Something.")
    policy.after_analysis(state, output(), len(state.turns), now(state) + 1000)
    assert state.flags[0].state == "nudged"


def test_recap_severity_is_never_spoken():
    state = make_state(("counselor", "Your SAI came from the FAFSA."), ("parent", "He loves the library."))
    flag = new_flag(["t1", "t2"], ["Your SAI", "He loves the library"], key="sai", severity="recap")
    policy.after_analysis(state, output([flag]), 2, now(state))
    for i in range(3):
        add_turn(state, "counselor", f"Logistics {i}.")
        assert not speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))
    assert state.flags[0].state == "recap"


def test_one_interjection_at_a_time():
    state = make_state(("counselor", "It's $31,500 and SAP applies."), ("parent", "So it's covered. Okay."))
    flags = [new_flag(["t2"], ["So it's covered"], key="a"), new_flag(["t2"], ["Okay"], key="b", trigger="UNEXPLAINED_JARGON")]
    policy.after_analysis(state, output(flags), 2, now(state))
    add_turn(state, "counselor", "Moving on.")
    actions = policy.after_analysis(state, output(), 3, now(state))
    assert [s.flag_id for s in speak_actions(actions)] == ["f1"]
    assert "one interjection at a time" in log_text(actions)


def test_old_evidence_goes_straight_to_recap():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."))
    for i in range(config.STALE_AFTER_TURNS + 1):
        add_turn(state, "counselor", f"Later topic {i}.")
    policy.after_analysis(state, output([new_flag(["t2"], ["So it's covered"])]), len(state.turns), now(state))
    assert state.flags[0].state == "recap"


def test_end_of_call_moves_open_flags_to_recap():
    state = covered_state()
    policy.end_of_call(state, now(state))
    assert state.flags[0].state == "recap"


# ---------------------------------------------------------------- unanswered questions


def question_state():
    state = make_state(
        ("counselor", "Daniel has $2,500 in work-study."),
        ("parent", "Does the work-study money have to be paid back?"),
    )
    asked = [("t2", "Does the work-study money have to be paid back?")]
    policy.after_analysis(state, output(opened=asked), 2, now(state))
    return state


def test_unanswered_question_is_counted_by_code_then_escalates():
    state = question_state()
    assert state.parent_questions[0].asked_turn_id == "t2"
    add_turn(state, "counselor", "Next, accept your awards in the portal.")
    policy.after_analysis(state, output(), 3, now(state))
    assert state.flags == []  # one counselor turn: the answer may still be credited late
    add_turn(state, "counselor", "You'll get an email confirmation.")
    actions = policy.after_analysis(state, output(), 4, now(state))
    flag = state.flags[0]
    assert (flag.trigger, flag.state) == ("UNANSWERED_QUESTION", "nudged")
    assert not speak_actions(actions)
    add_turn(state, "counselor", "You can change your mind on any award later.")
    [speak] = speak_actions(policy.after_analysis(state, output(), 5, now(state)))
    assert "paid back" in speak.text


def test_answered_question_resolves_its_flag():
    state = question_state()
    add_turn(state, "counselor", "Next, the portal.")
    add_turn(state, "counselor", "Then an email confirmation.")
    policy.after_analysis(state, output(), 4, now(state))
    add_turn(state, "counselor", "And no, work-study is a paycheck, never repaid.")
    policy.after_analysis(state, output(answered=[("t2", "t5")]), 5, now(state))
    assert state.parent_questions[0].answered_turn_id == "t5"
    assert state.flags[0].state == "resolved"


def test_a_parent_can_withdraw_their_own_question():
    state = question_state()
    add_turn(state, "parent", "Oh, never mind, it says so right on the letter.")
    actions = policy.after_analysis(state, output(answered=[("t2", "t3")]), 3, now(state))
    assert state.parent_questions[0].answered_turn_id == "t3"
    assert "t3 withdrew the question from t2" in log_text(actions)
    for text in ("Next, the portal.", "Then an email confirmation.", "And you can change your mind later."):
        add_turn(state, "counselor", text)
        assert not speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))
    assert state.flags == []


def test_the_question_turn_itself_cannot_close_the_question():
    state = question_state()
    actions = policy.after_analysis(state, output(answered=[("t2", "t2")]), 2, now(state))
    assert state.parent_questions[0].answered_turn_id is None
    assert "withdrew" not in log_text(actions)


def test_question_already_covered_by_a_flag_is_not_tracked_twice():
    state = make_state(("counselor", "He was selected for verification."), ("parent", "Oh good, so we're verified?"))
    flag = new_flag(["t2"], ["so we're verified"], key="verification_means_approved")
    actions = policy.after_analysis(state, output([flag], opened=[("t2", "so we're verified?")]), 2, now(state))
    assert state.parent_questions == []
    assert "already covered by f1" in log_text(actions)


def test_question_text_must_be_in_the_turn():
    state = make_state(("counselor", "He has work-study."), ("parent", "Does that get paid back?"))
    actions = policy.after_analysis(state, output(opened=[("t2", "Is work-study a loan we repay?")]), 2, now(state))
    assert state.parent_questions == []
    assert "is not in the turn" in log_text(actions)


def test_old_unanswered_question_goes_to_recap():
    state = question_state()
    for i in range(config.STALE_AFTER_TURNS + 1):
        add_turn(state, "parent" if i % 2 else "counselor", f"Later topic {i}.")
    # Earlier analyses failed; this one is the first to see that the question went unanswered.
    actions = policy.after_analysis(state, output(), len(state.turns), now(state))
    assert state.flags[0].state == "recap"
    assert not speak_actions(actions)


def test_questions_to_beacon_are_not_tracked():
    state = make_state(("parent", "Beacon, what's a Parent PLUS loan?"))
    policy.after_analysis(state, output(opened=[("t1", "What's a Parent PLUS loan?")]), 1, now(state))
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
    actions = policy.after_analysis(state, output(), 3, now(state))
    assert not speak_actions(actions)
    assert "deferred" in log_text(actions)
    policy.after_analysis(state, output(resolved=["f1"]), 4, now(state))
    assert state.flags[0].state == "resolved"


def test_ladder_counts_from_when_the_card_appeared():
    state = make_state(("counselor", "Daniel's total aid package is $31,500."), ("parent", "So it's covered."))
    add_turn(state, "counselor", "Next, housing.")  # spoken before the card existed
    flag = new_flag(["t1", "t2"], ["So it's covered"])
    policy.after_analysis(state, output([flag]), 2, now(state))
    assert state.flags[0].created_at_turn == "t3"
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))
    add_turn(state, "counselor", "And meals are included.")
    assert speak_actions(policy.after_analysis(state, output(), 4, now(state)))


# ---------------------------------------------------------------- counselor controls


def click(state, action, flag_id="f1"):
    return policy.counselor_action(state, flag_id, action, state.turns[-1].id, now(state))


def empty_recap():
    total = RecapItem(label="Total cost", amount="", note="", refs=[])
    return Recap(cost_of_attendance=total, grants=[], loans=[], work_study=[], still_to_pay=[], todos=[], follow_ups=[])


def test_dismissed_flag_is_never_spoken():
    state = covered_state()
    actions = click(state, "dismiss")
    flag = state.flags[0]
    assert (flag.state, flag.counselor_action) == ("dismissed", "dismissed")
    assert flag.history[-1].reason == "counselor: not an issue"
    assert [type(a) for a in actions] == [policy.UpdateFlag, LogEntry]
    for i in range(config.STALE_AFTER_TURNS + 2):
        add_turn(state, "counselor", f"Moving on {i}.")
        assert not speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))
    policy.end_of_call(state, now(state))
    assert flag.state == "dismissed"  # not moved to the recap either


def test_dismissed_issue_key_still_blocks_a_new_flag():
    state = covered_state()
    click(state, "dismiss")
    add_turn(state, "parent", "So it's covered, right?")
    again = new_flag(["t3"], ["So it's covered"])
    actions = policy.after_analysis(state, output([again]), 3, now(state))
    assert len(state.flags) == 1
    assert "duplicate of f1" in log_text(actions)


def test_dismissed_flag_is_shown_to_the_analyzer_with_its_state():
    state = covered_state()
    click(state, "dismiss")
    assert "f1 [aid_package_includes_loans] MISREAD_TERM state=dismissed" in analyzer.build_analysis_prompt(state)


def test_will_clarify_gives_the_counselor_one_more_turn():
    state = covered_state()
    actions = click(state, "will_clarify")
    flag = state.flags[0]
    assert (flag.state, flag.counselor_action, flag.ladder_start_turn) == ("nudged", "will_clarify", "t2")
    assert flag.history[-1].reason == "counselor: will clarify"
    assert "counselor will clarify; waiting 2 counselor turn(s)" in log_text(actions)
    add_turn(state, "counselor", "Moving on to housing, that's $16,500.")
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))  # without the click, due here
    add_turn(state, "parent", "Okay.")
    add_turn(state, "counselor", "And meals are $5,200.")
    [speak] = speak_actions(policy.after_analysis(state, output(), 5, now(state)))
    assert speak.flag_id == "f1"


def test_will_clarify_restarts_the_staleness_count():
    state = covered_state()
    add_turn(state, "counselor", "Next, housing.")
    add_turn(state, "parent", "Daniel will be so happy.")
    add_turn(state, "parent", "He worked hard for this.")
    click(state, "will_clarify")  # the count now starts at t5, not at the card (t2)
    add_turn(state, "counselor", "He did. Meals are next.")
    add_turn(state, "parent", "Okay.")
    add_turn(state, "counselor", "Then books.")
    # From the card, the first chance was t3 and 5 turns have passed since: stale. From the
    # click, the first chance is t6 and 2 turns have passed, with the 2 counselor turns it needs.
    assert speak_actions(policy.after_analysis(state, output(), 8, now(state)))

    state = covered_state()
    click(state, "will_clarify")
    for role in ("counselor", "parent", "parent", "parent", "parent"):
        add_turn(state, role, "Something else.")
    actions = policy.after_analysis(state, output(), 7, now(state))
    assert state.flags[0].state == "recap"
    assert "stale: 4 turns since t3" in state.flags[0].history[-1].reason
    assert not speak_actions(actions)


def test_will_clarify_then_the_counselor_clarifies():
    state = covered_state()
    click(state, "will_clarify")
    add_turn(state, "counselor", "To be clear, $14,000 of that is loans you repay.")
    actions = policy.after_analysis(state, output(resolved=["f1"]), 3, now(state))
    assert state.flags[0].state == "resolved"
    assert not speak_actions(actions)


def test_will_clarify_works_once_but_dismiss_stays_available():
    state = covered_state()
    click(state, "will_clarify")
    add_turn(state, "counselor", "Moving on to housing.")
    actions = click(state, "will_clarify")
    assert [type(a) for a in actions] == [LogEntry]
    assert "ignored" in log_text(actions) and "already said" in log_text(actions)
    assert state.flags[0].ladder_start_turn == "t2"  # the second click did not postpone it again
    click(state, "dismiss")
    assert state.flags[0].state == "dismissed"


@pytest.mark.parametrize("flag_state", ["resolved", "spoken", "recap", "dropped", "dismissed"])
@pytest.mark.parametrize("action", ["dismiss", "will_clarify"])
def test_actions_on_flags_that_are_not_nudged_are_ignored_and_logged(flag_state, action):
    state = covered_state()
    flag = state.flags[0]
    flag.state = flag_state
    before = flag.model_copy(deep=True)
    actions = click(state, action)
    assert [type(a) for a in actions] == [LogEntry]
    assert f"ignored counselor action {action} on f1: it is already {flag_state}" in log_text(actions)
    assert flag == before


def test_action_on_an_unknown_flag_is_ignored_and_logged():
    state = covered_state()
    actions = click(state, "dismiss", flag_id="f9")
    assert [type(a) for a in actions] == [LogEntry]
    assert "ignored counselor action dismiss on f9: no such flag" in log_text(actions)
    assert state.flags[0].state == "nudged"


def test_dismissed_unanswered_question_stays_in_the_recap_but_a_dismissed_misread_does_not():
    state = question_state()
    add_turn(state, "counselor", "Next, accept your awards in the portal.")
    add_turn(state, "counselor", "You'll get an email confirmation.")
    policy.after_analysis(state, output(), 4, now(state))
    assert state.flags[0].trigger == "UNANSWERED_QUESTION"
    click(state, "dismiss")
    add_turn(state, "counselor", "You can change your mind on any award later.")
    actions = policy.after_analysis(state, output(), 5, now(state))
    assert not speak_actions(actions) and len(state.flags) == 1  # silenced, and not raised again
    policy.end_of_call(state, now(state))
    # The question itself was never answered, so the family still gets it as a follow-up.
    assert "f1" not in analyzer._open_issues(state)
    assert "t2 (unanswered question)" in analyzer._open_issues(state)
    recap = empty_recap()
    assert analyzer.add_missing_follow_ups(recap, state) == ["t2"]
    assert recap.follow_ups[0].question == "Does the work-study money have to be paid back?"

    state = covered_state()
    click(state, "dismiss")
    policy.end_of_call(state, now(state))
    assert analyzer._open_issues(state) == "(none)"
    assert analyzer.add_missing_follow_ups(empty_recap(), state) == []
