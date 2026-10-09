"""Helpers for the tests: they make transcripts and analyzer outputs without an LLM."""

from backend.app.models import AnalyzerOutput, NewFlag, QuestionAnswered, QuestionOpened, RoomState, Turn

# Each turn starts 500 ms after the previous turn ended, and lasts 500 ms. So turns start 1000 ms
# apart. The ladder compares the start time of a turn with the time when a card appeared.
START_MS = 1_000_000_000


def make_state(*lines: tuple[str, str]) -> RoomState:
    state = RoomState()
    for role, text in lines:
        add_turn(state, role, text)
    return state


def add_turn(state: RoomState, role: str, text: str, gap_ms: int = 500) -> Turn:
    started = state.turns[-1].ended_at + 500 if state.turns else START_MS
    turn = Turn(
        id=f"t{len(state.turns) + 1}",
        role=role,
        text=text,
        started_at=started,
        ended_at=started + 500,
        gap_ms=gap_ms,
        source="typed",
    )
    state.turns.append(turn)
    return turn


def now(state: RoomState) -> int:
    """The time when the newest turn ended. An analysis of that turn finishes at this time."""
    return state.turns[-1].ended_at


def new_flag(turn_ids, quotes, key="aid_package_includes_loans", severity="interrupt", trigger="MISREAD_TERM") -> NewFlag:
    return NewFlag(
        trigger=trigger,
        issue_key=key,
        evidence_turn_ids=turn_ids,
        evidence_quotes=quotes,
        counselor_card="Maria may think the whole package is free money.",
        severity=severity,
        suggested_clarification="Explain which parts are loans.",
        spoken_line="Quick check for Maria: how much of that is loans?",
        family_question="How much of the aid package is loans we have to repay?",
        doc_refs=["L17"],
    )


def output(flags=(), resolved=(), opened=(), answered=()) -> AnalyzerOutput:
    return AnalyzerOutput(
        notes="test",
        new_flags=list(flags),
        resolved_flag_ids=list(resolved),
        questions_opened=[QuestionOpened(turn_id=t, text=q) for t, q in opened],
        questions_answered=[QuestionAnswered(asked_turn_id=a, answered_turn_id=b) for a, b in answered],
    )
