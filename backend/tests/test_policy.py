"""Unit tests for policy.py: the evidence gate, dedupe, the ladder, staleness, the cooldown,
questions, and the counselor's card buttons."""

from helpers import add_turn, make_state, new_flag, now, output

from backend.app import analyzer, config, policy
from backend.app.models import LogEntry, Recap, RecapItem


def speak_actions(actions):
    return [a for a in actions if isinstance(a, policy.SpeakLine)]


def log_text(actions):
    return " | ".join(a.message for a in actions if isinstance(a, LogEntry))


def covered_state():
    """The counselor gives the aid package, the parent misreads it, and the analyzer flags it."""
    state = make_state(
        ("counselor", "Daniel's total aid package is $31,500."),
        ("parent", "Oh, thank goodness. So it's covered."),
    )
    flag = new_flag(["t1", "t2"], ["So it's covered", "total aid package is $31,500"])
    policy.after_analysis(state, output([flag]), len(state.turns), now(state))
    return state


def question_state():
    state = make_state(
        ("counselor", "Daniel has $2,500 in work-study."),
        ("parent", "Does the work-study money have to be paid back?"),
    )
    asked = [("t2", "Does the work-study money have to be paid back?")]
    policy.after_analysis(state, output(opened=asked), 2, now(state))
    return state


# ---------------------------------------------------------------- evidence gate


def test_quote_matching_tolerates_case_punctuation_and_contractions():
    assert policy.quote_in_text("so it is covered", "Oh, thank goodness. So it's covered.")
    assert policy.quote_in_text("OH GOOD so we're verified", "Oh good, so we're verified?")
    assert not policy.quote_in_text("we never have to pay anything", "Oh good, so we're verified?")


def test_real_quotes_create_a_nudged_flag():
    state = covered_state()
    assert [(f.id, f.state) for f in state.flags] == [("f1", "nudged")]


def test_bad_evidence_is_dropped_with_a_reason():
    state = make_state(("counselor", "You need SAP."), ("parent", "Okay."))
    fabricated = new_flag(["t1", "t2"], ["so we never pay anything back"], key="a")
    counselor_only = new_flag(["t1"], ["You need SAP"], key="b")
    actions = policy.after_analysis(state, output([fabricated, counselor_only]), 2, now(state))
    assert [f.state for f in state.flags] == ["dropped", "dropped"]
    assert "quote not found" in state.flags[0].history[0].reason
    assert "no parent turn" in state.flags[1].history[0].reason
    assert not speak_actions(actions)


# ---------------------------------------------------------------- dedupe


def test_same_issue_key_is_ignored_the_second_time():
    state = covered_state()
    add_turn(state, "parent", "So it's covered, right?")
    actions = policy.after_analysis(state, output([new_flag(["t3"], ["So it's covered"])]), 3, now(state))
    assert len(state.flags) == 1
    assert "duplicate of f1" in log_text(actions)


def test_same_moment_under_a_new_key_is_ignored_even_after_it_was_resolved():
    # Seen with Gemini: a resolved jargon flag came back as "..._2" with the same evidence.
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
    assert [f.state for f in state.flags] == ["resolved", "nudged"]


# ---------------------------------------------------------------- escalation ladder


def test_nudge_then_resolved_stays_silent():
    state = covered_state()
    add_turn(state, "counselor", "Let me be careful: $14,000 of that is loans you repay.")
    actions = policy.after_analysis(state, output(resolved=["f1"]), 3, now(state))
    assert state.flags[0].state == "resolved"
    assert not speak_actions(actions)


def test_a_resolution_needs_a_counselor_turn_after_the_evidence():
    state = covered_state()
    add_turn(state, "parent", "Oh,")
    actions = policy.after_analysis(state, output(resolved=["f1"]), 3, now(state))
    assert state.flags[0].state == "nudged"
    assert "no counselor turn after its evidence" in log_text(actions)


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


def test_staleness_counts_from_the_counselors_first_chance():
    # After the card, the parent splits a reply over three push-to-talk presses. The counselor's
    # next turn is still the first chance. The counselor moves on, so Beacon asks.
    state = covered_state()
    for text in ("Oh, wow.", "That's such a relief.", "Daniel will be thrilled."):
        add_turn(state, "parent", text)
        assert not speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))
    add_turn(state, "counselor", "So, on to housing.")
    assert speak_actions(policy.after_analysis(state, output(), len(state.turns), now(state)))


def test_cooldown_delays_then_staleness_sends_to_recap():
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


def test_a_counselor_turn_already_in_progress_when_the_card_appeared_does_not_count():
    state = make_state(("counselor", "Daniel's total aid package is $31,500."), ("parent", "So it's covered."))
    card_at = now(state) + 4_000  # the analysis ended while the counselor held push-to-talk
    policy.after_analysis(state, output([new_flag(["t1", "t2"], ["So it's covered"])]), 2, card_at)
    turn = add_turn(state, "counselor", "And housing is $16,500.")
    turn.started_at, turn.ended_at = card_at - 3_000, card_at + 1_000  # started 3 s before the card
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))
    add_turn(state, "counselor", "Meals are included in that.")
    assert speak_actions(policy.after_analysis(state, output(), 4, now(state)))


def test_speaking_waits_for_turns_that_arrived_during_the_analysis():
    state = covered_state()
    add_turn(state, "counselor", "So, on to housing.")
    add_turn(state, "counselor", "Sorry, $14,000 of that is loans.")  # arrived during the LLM call
    actions = policy.after_analysis(state, output(), 3, now(state))
    assert not speak_actions(actions)
    assert "deferred" in log_text(actions)
    policy.after_analysis(state, output(resolved=["f1"]), 4, now(state))
    assert state.flags[0].state == "resolved"


def test_one_interjection_at_a_time():
    state = make_state(("counselor", "It's $31,500 and SAP applies."), ("parent", "So it's covered. Okay."))
    flags = [new_flag(["t2"], ["So it's covered"], key="a"), new_flag(["t2"], ["Okay"], key="b", trigger="UNEXPLAINED_JARGON")]
    policy.after_analysis(state, output(flags), 2, now(state))
    add_turn(state, "counselor", "Moving on.")
    actions = policy.after_analysis(state, output(), 3, now(state))
    assert [s.flag_id for s in speak_actions(actions)] == ["f1"]
    assert "one interjection at a time" in log_text(actions)


def test_recap_severity_is_never_spoken_and_open_flags_end_in_the_recap():
    state = make_state(("counselor", "Your SAI came from the FAFSA."), ("parent", "He loves the library."))
    flag = new_flag(["t1", "t2"], ["Your SAI", "He loves the library"], key="sai", severity="recap")
    policy.after_analysis(state, output([flag]), 2, now(state))
    add_turn(state, "counselor", "Logistics.")
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))
    assert state.flags[0].state == "recap"

    state = covered_state()
    policy.end_of_call(state, now(state))
    assert state.flags[0].state == "recap"


def test_should_analyze():
    state = make_state(("counselor", "It's $31,500."), ("parent", "So it's covered."), ("counselor", "Next."))
    assert policy.should_analyze(state, 1)  # the analysis of t2 failed, so t2 is still waiting
    assert not policy.should_analyze(state, 2)  # only a counselor turn since, and nothing is open
    state = covered_state()
    add_turn(state, "counselor", "Moving on.")
    assert policy.should_analyze(state, 2)  # f1 is open, so a counselor turn might resolve it


# ---------------------------------------------------------------- unanswered questions


def test_unanswered_question_is_counted_by_code_then_escalates():
    state = question_state()
    add_turn(state, "counselor", "Next, accept your awards in the portal.")
    policy.after_analysis(state, output(), 3, now(state))
    assert state.flags == []  # after one counselor turn, the analyzer can still find the answer late
    add_turn(state, "counselor", "You'll get an email confirmation.")
    actions = policy.after_analysis(state, output(), 4, now(state))
    assert [(f.trigger, f.state) for f in state.flags] == [("UNANSWERED_QUESTION", "nudged")]
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
    assert state.flags[0].state == "resolved"


def test_a_parent_can_withdraw_their_own_question():
    state = question_state()
    add_turn(state, "parent", "Oh, never mind, it says so right on the letter.")
    actions = policy.after_analysis(state, output(answered=[("t2", "t3")]), 3, now(state))
    assert state.parent_questions[0].answered_turn_id == "t3"
    assert "t3 withdrew the question from t2" in log_text(actions)


def test_question_text_must_be_in_the_turn():
    # Beacon may read a question aloud, so it must be the parent's own words.
    state = make_state(("counselor", "He has work-study."), ("parent", "Does that get paid back?"))
    actions = policy.after_analysis(state, output(opened=[("t2", "Is work-study a loan we repay?")]), 2, now(state))
    assert state.parent_questions == []
    assert "is not in the turn" in log_text(actions)


# ---------------------------------------------------------------- counselor controls


def click(state, action, flag_id="f1"):
    return policy.counselor_action(state, flag_id, action, state.turns[-1].id, now(state))


def empty_recap():
    total = RecapItem(label="Total cost", amount="", note="", refs=[])
    return Recap(cost_of_attendance=total, grants=[], loans=[], work_study=[], still_to_pay=[], todos=[], follow_ups=[])


def test_dismissed_flag_is_never_spoken_or_raised_again():
    state = covered_state()
    click(state, "dismiss")
    flag = state.flags[0]
    assert (flag.state, flag.counselor_action) == ("dismissed", "dismissed")
    add_turn(state, "counselor", "Moving on.")
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))
    add_turn(state, "parent", "So it's covered, right?")
    actions = policy.after_analysis(state, output([new_flag(["t4"], ["So it's covered"])]), 4, now(state))
    assert "duplicate of f1" in log_text(actions)
    policy.end_of_call(state, now(state))
    assert flag.state == "dismissed"  # not moved to the recap either


def test_will_clarify_gives_the_counselor_one_more_turn_once():
    state = covered_state()
    actions = click(state, "will_clarify")
    assert state.flags[0].counselor_action == "will_clarify"
    assert "counselor will clarify; waiting 2 counselor turn(s)" in log_text(actions)
    add_turn(state, "counselor", "Moving on to housing, that's $16,500.")
    assert not speak_actions(policy.after_analysis(state, output(), 3, now(state)))  # without the click, due here
    assert "already said" in log_text(click(state, "will_clarify"))  # a second click doesn't postpone again
    add_turn(state, "counselor", "And meals are $5,200.")
    assert speak_actions(policy.after_analysis(state, output(), 4, now(state)))


def test_actions_on_flags_that_are_not_nudged_are_ignored_and_logged():
    state = covered_state()
    state.flags[0].state = "resolved"
    before = state.flags[0].model_copy(deep=True)
    assert "it is already resolved" in log_text(click(state, "dismiss"))
    assert "no such flag" in log_text(click(state, "dismiss", flag_id="f9"))
    assert state.flags[0] == before


def test_recap_follow_ups_use_the_family_question_and_keep_dismissed_unanswered_questions():
    state = covered_state()
    policy.end_of_call(state, now(state))
    recap = empty_recap()
    assert analyzer.add_missing_follow_ups(recap, state) == ["f1"]
    assert recap.follow_ups[0].question == "How much of the aid package is loans we have to repay?"

    # "Not an issue" on an unanswered-question card stops Beacon, but the family still gets the question.
    state = question_state()
    for text in ("Next, the portal.", "Then an email confirmation."):
        add_turn(state, "counselor", text)
    policy.after_analysis(state, output(), 4, now(state))
    click(state, "dismiss")
    policy.end_of_call(state, now(state))
    recap = empty_recap()
    assert analyzer.add_missing_follow_ups(recap, state) == ["t2"]
    assert recap.follow_ups[0].question == "Does the work-study money have to be paid back?"
