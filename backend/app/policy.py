"""Pure decision logic: given the room state and what the analyzer perceived (or which button the
counselor clicked on a card), decide whether, when and how Beacon acts. No I/O, no clock, no LLM. Callers pass `now_ms`; each function records its
decisions in the state (flags, questions, cooldown) and returns the side effects as actions for
rooms.py, or the eval, to carry out."""

import re
from difflib import SequenceMatcher

from pydantic import BaseModel

from . import config, docs, wakeword
from .models import AnalyzerOutput, CardAction, Flag, FlagEvent, FlagState, LogEntry, ParentQuestion, RoomState, Turn
from .triggers import LLM_TRIGGER_NAMES, PARENT_EVIDENCED


# ---------------------------------------------------------------- actions


class SendCard(BaseModel):
    """A new flag exists: show it to the observer, and to the counselor if it is nudged."""

    flag_id: str


class UpdateFlag(BaseModel):
    flag_id: str


class SpeakLine(BaseModel):
    """Queue an interjection; rooms.py speaks it at the next pause and then calls mark_spoken()."""

    flag_id: str
    text: str


Action = SendCard | UpdateFlag | SpeakLine | LogEntry


def _log(now_ms: int, kind: str, message: str, flag_id: str | None = None, turn_id: str | None = None) -> LogEntry:
    return LogEntry(at=now_ms, kind=kind, message=message, flag_id=flag_id, turn_id=turn_id)


# ---------------------------------------------------------------- transcript helpers


def _human(turns: list[Turn]) -> list[Turn]:
    return [t for t in turns if t.role != "beacon"]


def _turns_after(turns: list[Turn], turn_id: str, roles: tuple[str, ...]) -> int:
    """How many turns by `roles` come after `turn_id`. Beacon turns never count."""
    ids = [t.id for t in turns]
    if turn_id not in ids:
        return 0
    return sum(1 for t in turns[ids.index(turn_id) + 1 :] if t.role in roles)


# ---------------------------------------------------------------- evidence gate


def _normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("'", "")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def quote_in_text(quote: str, text: str) -> bool:
    """True if the quote appears in the text, ignoring case, punctuation and small slips."""
    q, t = _normalize(quote), _normalize(text)
    if not q:
        return False
    if f" {q} " in f" {t} ":
        return True
    # Windows one word shorter or longer catch "it's" quoted as "it is".
    q_words, t_words = q.split(), t.split()
    for size in (len(q_words) - 1, len(q_words), len(q_words) + 1):
        for i in range(max(1, len(t_words) - size + 1)):
            window = " ".join(t_words[i : i + size])
            if SequenceMatcher(None, q, window).ratio() >= config.QUOTE_MIN_SIMILARITY:
                return True
    return False


def evidence_problem(trigger: str, turn_ids: list[str], quotes: list[str], turns: list[Turn]) -> str | None:
    """Why the cited evidence fails the gate, or None if every quote is in a cited turn."""
    by_id = {t.id: t for t in turns}
    if not turn_ids or not quotes:
        return "no evidence cited"
    cited = []
    for turn_id in turn_ids:
        turn = by_id.get(turn_id)
        if turn is None or turn.role == "beacon":
            return f"cited turn {turn_id} is not a counselor or parent turn in the transcript"
        cited.append(turn)
    if trigger in PARENT_EVIDENCED and not any(t.role == "parent" for t in cited):
        return f"no parent turn cited; {trigger} is shown by the parent's reply"
    for quote in quotes:
        if not any(quote_in_text(quote, t.text) for t in cited):
            return f"quote not found in cited turns: “{quote}”"
    return None


# ---------------------------------------------------------------- flags


def _transition(flag: Flag, new_state: FlagState, reason: str, turn_id: str, now_ms: int) -> list[Action]:
    flag.state = new_state
    flag.history.append(FlagEvent(state=new_state, reason=reason, turn_id=turn_id))
    return [UpdateFlag(flag_id=flag.id), _log(now_ms, "ladder", f"{flag.id} → {new_state}: {reason}", flag.id, turn_id)]


def _create_flag(state: RoomState, fields: dict, flag_state: FlagState, reason: str, turn_id: str, now_ms: int) -> list[Action]:
    flag = Flag(
        id=f"f{len(state.flags) + 1}",
        state=flag_state,
        # The card appears now, after every turn so far, including any that arrived during the LLM
        # call. The ladder counts from here, so a counselor turn spoken before the card existed
        # never counts as "saw the card and didn't clarify". ladder_start_ms does the same for a
        # turn that was already in progress (push-to-talk held) when the card appeared.
        created_at_turn=state.turns[-1].id,
        ladder_start_turn=state.turns[-1].id,
        ladder_start_ms=now_ms,
        history=[FlagEvent(state=flag_state, reason=reason, turn_id=turn_id)],
        **fields,
    )
    state.flags.append(flag)
    message = f"{flag.id} {flag.trigger} [{flag.issue_key}] → {flag_state}: {reason}"
    return [SendCard(flag_id=flag.id), _log(now_ms, "flag", message, flag.id, turn_id)]


# States in which a flag owns its issue_key. "resolved" frees it: a parent who later relapses into
# the corrected belief is a new moment, and the model may reuse the key for it. "dropped" frees it
# because its evidence failed. A dismissed flag keeps blocking it, so Beacon doesn't raise again
# what the counselor already called a non-issue.
KEY_BLOCKING_STATES = ("nudged", "spoken", "recap", "dismissed")


def _active_flag_with_key(state: RoomState, issue_key: str) -> Flag | None:
    return next((f for f in state.flags if f.issue_key == issue_key and f.state in KEY_BLOCKING_STATES), None)


def _flag_for_same_moment(state: RoomState, trigger: str, turn_ids: list[str], seen: list[Turn]) -> Flag | None:
    """An existing flag with the same trigger that cites the same parent turn. Told never to reuse
    an issue_key, the LLM has re-raised an issue it already flagged (even one since resolved) as
    "sap_not_explained_2" with identical evidence; the parent turn identifies the moment."""
    parent_turns = {t.id for t in seen if t.role == "parent"}
    cited = set(turn_ids) & parent_turns
    for flag in state.flags:
        if flag.state != "dropped" and flag.trigger == trigger and cited & set(flag.evidence_turn_ids):
            return flag
    return None


def _add_new_flags(state: RoomState, out: AnalyzerOutput, seen: list[Turn], now_ms: int) -> list[Action]:
    actions: list[Action] = []
    latest = seen[-1].id
    for new in out.new_flags:
        fields = new.model_dump()
        if new.trigger not in LLM_TRIGGER_NAMES:
            actions.append(_log(now_ms, "flag", f"ignored flag with unknown trigger {new.trigger!r}", turn_id=latest))
            continue
        duplicate = _active_flag_with_key(state, new.issue_key)
        if duplicate:
            actions.append(_log(now_ms, "flag", f"ignored [{new.issue_key}]: duplicate of {duplicate.id}", duplicate.id, latest))
            continue
        same = _flag_for_same_moment(state, new.trigger, new.evidence_turn_ids, seen)
        if same:
            message = f"ignored [{new.issue_key}]: same {new.trigger} moment as {same.id} (same parent turn)"
            actions.append(_log(now_ms, "flag", message, same.id, latest))
            continue
        problem = evidence_problem(new.trigger, new.evidence_turn_ids, new.evidence_quotes, seen)
        if problem:
            already = any(f.issue_key == new.issue_key and f.state == "dropped" for f in state.flags)
            if already:
                actions.append(_log(now_ms, "flag", f"dropped [{new.issue_key}] again: {problem}", turn_id=latest))
            else:
                actions += _create_flag(state, fields, "dropped", f"evidence gate: {problem}", latest, now_ms)
            continue
        unknown_refs = [r for r in new.doc_refs if r not in docs.LINES]
        if unknown_refs:
            fields["doc_refs"] = [r for r in new.doc_refs if r in docs.LINES]
            actions.append(_log(now_ms, "flag", f"removed unknown doc refs {unknown_refs} from [{new.issue_key}]", turn_id=latest))
        newest = max((t for t in seen if t.id in new.evidence_turn_ids), key=seen.index)
        turns_since = _turns_after(seen, newest.id, ("counselor", "parent"))
        if new.severity == "recap":
            actions += _create_flag(state, fields, "recap", "recap severity: kept for the end-of-call recap", latest, now_ms)
        elif turns_since > config.STALE_AFTER_TURNS:
            actions += _create_flag(state, fields, "recap", f"evidence is already {turns_since} turns old", latest, now_ms)
        else:
            actions += _create_flag(state, fields, "nudged", "private card for the counselor", latest, now_ms)
    return actions


# ---------------------------------------------------------------- questions


def _apply_questions(state: RoomState, out: AnalyzerOutput, seen: list[Turn], now_ms: int) -> list[Action]:
    actions: list[Action] = []
    by_id = {t.id: t for t in seen}
    latest = seen[-1].id
    tracked = {q.asked_turn_id: q for q in state.parent_questions}
    for opened in out.questions_opened:
        turn = by_id.get(opened.turn_id)
        if turn is None or turn.role != "parent" or opened.turn_id in tracked:
            continue
        if wakeword.find_summon(turn.text):
            continue  # addressed to Beacon, which answers it directly
        # Same evidence gate as flags: Beacon may later read this question aloud as a quote.
        if not quote_in_text(opened.text, turn.text):
            message = f"ignored question for {turn.id}: “{opened.text}” is not in the turn"
            actions.append(_log(now_ms, "question", message, turn_id=turn.id))
            continue
        covering = next((f for f in state.flags if f.state != "dropped" and opened.turn_id in f.evidence_turn_ids), None)
        if covering:
            actions.append(_log(now_ms, "question", f"question in {turn.id} is already covered by {covering.id}", covering.id, turn.id))
            continue
        question = ParentQuestion(text=opened.text, asked_turn_id=turn.id)
        state.parent_questions.append(question)
        tracked[turn.id] = question
        actions.append(_log(now_ms, "question", f"parent asked: “{opened.text}”", turn_id=turn.id))
    order = {t.id: i for i, t in enumerate(seen)}
    for answered in out.questions_answered:
        question = tracked.get(answered.asked_turn_id)
        answer_turn = by_id.get(answered.answered_turn_id)
        if question is None or question.answered_turn_id or answer_turn is None:
            continue
        if order[answer_turn.id] <= order[question.asked_turn_id] or answer_turn.role == "beacon":
            continue
        # A later parent turn closes the question too: "oh never mind, I see it" or the parent
        # answering it themselves. Beacon must not then ask it on their behalf.
        withdrawn = answer_turn.role == "parent"
        question.answered_turn_id = answer_turn.id
        verb = "withdrew the question from" if withdrawn else "answered the question from"
        actions.append(_log(now_ms, "question", f"{answer_turn.id} {verb} {question.asked_turn_id}", turn_id=answer_turn.id))
        flag = _active_flag_with_key(state, f"unanswered_{question.asked_turn_id}")
        if flag and flag.state == "nudged":
            reason = "the parent withdrew the question" if withdrawn else "the counselor answered the question"
            actions += _transition(flag, "resolved", reason, latest, now_ms)
    return actions


def _raise_unanswered(state: RoomState, seen: list[Turn], now_ms: int) -> list[Action]:
    actions: list[Action] = []
    latest = seen[-1].id
    for question in state.parent_questions:
        key = f"unanswered_{question.asked_turn_id}"
        # One flag per question, whatever happened to it: the analyzer may list an unanswered-
        # question flag as resolved without reporting the answer, and that must not re-raise it.
        if question.answered_turn_id or any(f.issue_key == key for f in state.flags):
            continue
        waited = _turns_after(seen, question.asked_turn_id, ("counselor",))
        if waited < config.UNANSWERED_AFTER_COUNSELOR_TURNS:
            continue
        names = {"parent": config.PARENT_NAME, "question": question.text}
        fields = {
            "trigger": "UNANSWERED_QUESTION",
            "issue_key": key,
            "severity": "interrupt",
            "evidence_turn_ids": [question.asked_turn_id],
            "evidence_quotes": [question.text],
            "counselor_card": config.UNANSWERED_CARD.format(**names),
            "suggested_clarification": config.UNANSWERED_CLARIFICATION.format(**names),
            "spoken_line": config.UNANSWERED_LINE.format(**names),
            "family_question": question.text,  # the parent's own words, as UNANSWERED_LINE quotes them
            "doc_refs": [],
        }
        age = _turns_after(seen, question.asked_turn_id, ("counselor", "parent"))
        if age > config.STALE_AFTER_TURNS:  # a late detection shouldn't interrupt, as for flags
            actions += _create_flag(state, fields, "recap", f"question is already {age} turns old", latest, now_ms)
        else:
            reason = f"unanswered after {waited} counselor turn(s)"
            actions += _create_flag(state, fields, "nudged", reason, latest, now_ms)
    return actions


# ---------------------------------------------------------------- escalation ladder


def _turns_before_speaking(flag: Flag) -> int:
    """Counselor turns without a fix before Beacon may ask aloud; "I'll clarify" adds the grace."""
    return config.ESCALATE_AFTER_COUNSELOR_TURNS + flag.grace_turns


def _counselor_turns_since_card(flag: Flag, seen: list[Turn]) -> list[Turn]:
    """Counselor turns that had a chance to act on the card: after ladder_start_turn in the
    transcript, and started once the card was showing (or after "I'll clarify"). A turn already in
    progress when the card appeared was not a decision to move on."""
    ids = [t.id for t in seen]
    if flag.ladder_start_turn not in ids:
        return []
    later = seen[ids.index(flag.ladder_start_turn) + 1 :]
    return [t for t in later if t.role == "counselor" and t.started_at >= flag.ladder_start_ms]


def _run_ladder(state: RoomState, seen: list[Turn], unseen_human_turns: bool, now_ms: int) -> list[Action]:
    actions: list[Action] = []
    latest = seen[-1].id
    due: list[Flag] = []
    for flag in [f for f in state.flags if f.state == "nudged"]:
        counselor_turns = _counselor_turns_since_card(flag, seen)
        if not counselor_turns:
            continue  # the counselor hasn't had a turn since the card: neither due nor stale
        # Staleness counts from the counselor's first chance, not from the card: a parent who
        # splits a reply over several push-to-talk presses must not use up the counselor's turns.
        first_chance = counselor_turns[0].id
        human_turns = _turns_after(seen, first_chance, ("counselor", "parent"))
        if human_turns > config.STALE_AFTER_TURNS:
            reason = f"stale: {human_turns} turns since {first_chance}, the counselor's first chance; too late to raise aloud"
            actions += _transition(flag, "recap", reason, latest, now_ms)
        elif len(counselor_turns) >= _turns_before_speaking(flag):
            due.append(flag)
    if not due:
        return actions
    waiting = ", ".join(f.id for f in due)
    if unseen_human_turns:
        # Someone spoke during the LLM call, maybe the very clarification; the next analysis decides.
        actions.append(_log(now_ms, "ladder", f"{waiting} due, deferred: newer turns not analyzed yet", turn_id=latest))
        return actions
    if state.last_spoken_at is not None:
        remaining = config.SPEAK_COOLDOWN_SECONDS - (now_ms - state.last_spoken_at) / 1000
        if remaining > 0:
            actions.append(_log(now_ms, "ladder", f"{waiting} due, waiting: cooldown {remaining:.0f}s left", turn_id=latest))
            return actions
    flag = due[0]
    reason = f"not clarified after {_turns_before_speaking(flag)} counselor turn(s)"
    actions.append(_log(now_ms, "ladder", f"{flag.id} escalates: {reason}; speaking at the next pause", flag.id, latest))
    actions.append(SpeakLine(flag_id=flag.id, text=flag.spoken_line))
    if len(due) > 1:
        others = ", ".join(f.id for f in due[1:])
        actions.append(_log(now_ms, "ladder", f"{others} due, waiting: one interjection at a time", turn_id=latest))
    return actions


# ---------------------------------------------------------------- entry points


def should_analyze(state: RoomState, analyzed_ok: int) -> bool:
    """Skip the LLM when it can't perceive anything new. `analyzed_ok` is how many turns the last
    successful analysis covered. While every LLM trigger needs the parent's reply as evidence and
    no parent turn is waiting to be analyzed, only resolutions and answers could change."""
    waiting = _human(state.turns[analyzed_ok:])
    if not waiting:
        return False
    if any(t.role == "parent" for t in waiting) or set(LLM_TRIGGER_NAMES) - PARENT_EVIDENCED:
        return True
    open_flags = any(f.state == "nudged" for f in state.flags)
    open_questions = any(q.answered_turn_id is None for q in state.parent_questions)
    return open_flags or open_questions


def after_analysis(state: RoomState, out: AnalyzerOutput, turn_count: int, now_ms: int) -> list[Action]:
    """Apply one analyzer result. `turn_count` is how many turns the analyzer saw; turns that
    arrived during the call to the LLM wait for the next analysis."""
    seen = state.turns[:turn_count]
    if not seen:
        return []
    latest = seen[-1].id
    actions: list[Action] = []
    for flag_id in out.resolved_flag_ids:
        flag = next((f for f in state.flags if f.id == flag_id), None)
        if not flag or flag.state != "nudged":
            continue
        # Only the counselor can clarify, so a counselor turn must follow the evidence. Seen with
        # Gemini: a flag listed as resolved after the parent's next short press ("Oh,").
        newest = max((t for t in seen if t.id in flag.evidence_turn_ids), key=seen.index, default=None)
        if newest is None or not _turns_after(seen, newest.id, ("counselor",)):
            message = f"ignored resolution of {flag.id}: no counselor turn after its evidence"
            actions.append(_log(now_ms, "ladder", message, flag.id, latest))
            continue
        actions += _transition(flag, "resolved", "the counselor clarified it", latest, now_ms)
    actions += _add_new_flags(state, out, seen, now_ms)
    actions += _apply_questions(state, out, seen, now_ms)
    actions += _raise_unanswered(state, seen, now_ms)
    unseen_human_turns = bool(_human(state.turns[turn_count:]))
    actions += _run_ladder(state, seen, unseen_human_turns, now_ms)
    return actions


def mark_spoken(state: RoomState, flag_id: str, turn_id: str, now_ms: int) -> list[Action]:
    """Record that an interjection was actually spoken, which starts the cooldown."""
    flag = next(f for f in state.flags if f.id == flag_id)
    state.last_spoken_at = now_ms
    return _transition(flag, "spoken", "Beacon asked aloud", turn_id, now_ms)


def counselor_action(state: RoomState, flag_id: str, action: CardAction, latest_turn_id: str, now_ms: int) -> list[Action]:
    """A click on a nudge card. "dismiss" ends the flag without Beacon ever speaking about it;
    "will_clarify" (once per flag) restarts the ladder at the newest turn and adds grace turns.
    Only a nudged flag can be acted on; anything else is ignored with a log entry. rooms.py
    checks that the click came from the counselor."""

    def ignored(why: str) -> list[Action]:
        return [_log(now_ms, "ladder", f"ignored counselor action {action} on {flag_id}: {why}", turn_id=latest_turn_id)]

    flag = next((f for f in state.flags if f.id == flag_id), None)
    if flag is None:
        return ignored("no such flag")
    if flag.state != "nudged":
        # Includes a line that is already playing: _speak() marks the flag spoken before any audio.
        return ignored(f"it is already {flag.state}")
    if action == "dismiss":
        flag.counselor_action = "dismissed"
        return _transition(flag, "dismissed", "counselor: not an issue", latest_turn_id, now_ms)
    if flag.counselor_action == "will_clarify":
        # Once per flag: a second click must not postpone the family's question again.
        return ignored("the counselor already said they will clarify")
    flag.counselor_action = "will_clarify"
    flag.ladder_start_turn = latest_turn_id
    flag.ladder_start_ms = now_ms
    flag.grace_turns = config.CLARIFY_GRACE_COUNSELOR_TURNS
    flag.history.append(FlagEvent(state="nudged", reason="counselor: will clarify", turn_id=latest_turn_id))
    message = f"{flag.id} counselor will clarify; waiting {_turns_before_speaking(flag)} counselor turn(s) before speaking"
    return [UpdateFlag(flag_id=flag.id), _log(now_ms, "ladder", message, flag.id, latest_turn_id)]


def end_of_call(state: RoomState, now_ms: int) -> list[Action]:
    """Flags still waiting on the counselor go to the recap."""
    latest = state.turns[-1].id if state.turns else ""
    actions: list[Action] = []
    for flag in [f for f in state.flags if f.state == "nudged"]:
        actions += _transition(flag, "recap", "the call ended before it was clarified", latest, now_ms)
    return actions
