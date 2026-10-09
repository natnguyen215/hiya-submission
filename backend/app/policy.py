"""The decision logic. It decides if, when and how Beacon acts.

The input is the room state and one of these:
- what the analyzer found in the call (after_analysis),
- a click on a card by the counselor (counselor_action),
- the end of the call (end_of_call).

Each function changes the state (flags, questions, cooldown) and returns a list of actions.
rooms.py (or the eval) does the actions. This module does no I/O, reads no clock and calls no
LLM. The caller gives the time as `now_ms`. So the tests can call these functions directly."""

import re
from difflib import SequenceMatcher

from pydantic import BaseModel

from . import config, docs, wakeword
from .models import AnalyzerOutput, CardAction, Flag, FlagEvent, FlagState, LogEntry, ParentQuestion, RoomState, Turn
from .triggers import LLM_TRIGGER_NAMES, PARENT_EVIDENCED


# ---------------------------------------------------------------- actions


class SendCard(BaseModel):
    """Show a new flag to the observer. Show it to the counselor too if it is nudged."""

    flag_id: str


class UpdateFlag(BaseModel):
    """Send the changed flag to the tabs that can see it."""

    flag_id: str


class SpeakLine(BaseModel):
    """Put a line in the speech queue. rooms.py speaks it at the next pause, then calls mark_spoken()."""

    flag_id: str
    text: str


Action = SendCard | UpdateFlag | SpeakLine | LogEntry


def _log(now_ms: int, kind: str, message: str, flag_id: str | None = None, turn_id: str | None = None) -> LogEntry:
    return LogEntry(at=now_ms, kind=kind, message=message, flag_id=flag_id, turn_id=turn_id)


# ---------------------------------------------------------------- transcript helpers


def _human(turns: list[Turn]) -> list[Turn]:
    return [t for t in turns if t.role != "beacon"]


def _turns_after(turns: list[Turn], turn_id: str, roles: tuple[str, ...]) -> int:
    """The number of turns by `roles` after `turn_id`."""
    ids = [t.id for t in turns]
    if turn_id not in ids:
        return 0
    return sum(1 for t in turns[ids.index(turn_id) + 1 :] if t.role in roles)


def _newest_evidence_turn(seen: list[Turn], turn_ids: list[str]) -> Turn | None:
    """The last turn in the transcript that the evidence cites."""
    return max((t for t in seen if t.id in turn_ids), key=seen.index, default=None)


def find_flag(state: RoomState, flag_id: str | None) -> Flag | None:
    return next((f for f in state.flags if f.id == flag_id), None)


# ---------------------------------------------------------------- evidence gate


def _normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("'", "")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def quote_in_text(quote: str, text: str) -> bool:
    """True if the quote is in the text. Case, punctuation and small differences do not matter."""
    q, t = _normalize(quote), _normalize(text)
    if not q:
        return False
    if f" {q} " in f" {t} ":
        return True
    # Compare the quote with each window of words in the text. The window can be one word shorter
    # or longer than the quote, so "it is" in the quote matches "it's" in the text.
    q_words, t_words = q.split(), t.split()
    for size in (len(q_words) - 1, len(q_words), len(q_words) + 1):
        for i in range(max(1, len(t_words) - size + 1)):
            window = " ".join(t_words[i : i + size])
            if SequenceMatcher(None, q, window).ratio() >= config.QUOTE_MIN_SIMILARITY:
                return True
    return False


def evidence_problem(trigger: str, turn_ids: list[str], quotes: list[str], turns: list[Turn]) -> str | None:
    """Why the evidence fails the gate. None if each quote is in one of the cited turns."""
    if not turn_ids or not quotes:
        return "no evidence cited"
    by_id = {t.id: t for t in turns}
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
        # The card appears now. The ladder counts the counselor's turns from this point.
        # A counselor turn before the card does not count: the counselor did not see the card.
        # ladder_start_turn is the newest turn, also one that arrived during the LLM call.
        # ladder_start_ms excludes a turn that started before the card (push-to-talk held down).
        ladder_start_turn=state.turns[-1].id,
        ladder_start_ms=now_ms,
        history=[FlagEvent(state=flag_state, reason=reason, turn_id=turn_id)],
        **fields,
    )
    state.flags.append(flag)
    message = f"{flag.id} {flag.trigger} [{flag.issue_key}] → {flag_state}: {reason}"
    return [SendCard(flag_id=flag.id), _log(now_ms, "flag", message, flag.id, turn_id)]


# A flag in one of these states blocks new flags with the same issue_key.
# - "resolved" does not block. If the parent goes back to the wrong belief later, that is a new
#   moment, and the LLM can use the same key for it.
# - "dropped" does not block. Its evidence was bad.
# - "dismissed" blocks. The counselor said that it is not an issue, so Beacon must not raise it again.
KEY_BLOCKING_STATES = ("nudged", "spoken", "recap", "dismissed")


def _flag_with_key(state: RoomState, issue_key: str) -> Flag | None:
    return next((f for f in state.flags if f.issue_key == issue_key and f.state in KEY_BLOCKING_STATES), None)


def _flag_for_same_moment(state: RoomState, trigger: str, turn_ids: list[str], seen: list[Turn]) -> Flag | None:
    """An existing flag with the same trigger that cites the same parent turn.

    The prompt tells the LLM not to use a key again. But Gemini sometimes raises a flag again
    with a new key ("sap_not_explained_2") and the same evidence. The parent turn identifies the
    moment, so this check finds it."""
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

        duplicate = _flag_with_key(state, new.issue_key)
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
            # Keep one dropped flag per key, so that the observer can see why. Log the repeats only.
            if any(f.issue_key == new.issue_key and f.state == "dropped" for f in state.flags):
                actions.append(_log(now_ms, "flag", f"dropped [{new.issue_key}] again: {problem}", turn_id=latest))
            else:
                actions += _create_flag(state, fields, "dropped", f"evidence gate: {problem}", latest, now_ms)
            continue

        unknown_refs = [r for r in new.doc_refs if r not in docs.LINES]
        if unknown_refs:
            fields["doc_refs"] = [r for r in new.doc_refs if r in docs.LINES]
            actions.append(_log(now_ms, "flag", f"removed unknown doc refs {unknown_refs} from [{new.issue_key}]", turn_id=latest))

        age = _turns_after(seen, _newest_evidence_turn(seen, new.evidence_turn_ids).id, ("counselor", "parent"))
        if new.severity == "recap":
            actions += _create_flag(state, fields, "recap", "recap severity: kept for the end-of-call recap", latest, now_ms)
        elif age > config.STALE_AFTER_TURNS:
            actions += _create_flag(state, fields, "recap", f"evidence is already {age} turns old", latest, now_ms)
        else:
            actions += _create_flag(state, fields, "nudged", "private card for the counselor", latest, now_ms)
    return actions


# ---------------------------------------------------------------- questions


def _open_questions(state: RoomState, out: AnalyzerOutput, seen: list[Turn], now_ms: int) -> list[Action]:
    """Start to track the parent's questions that the analyzer found."""
    actions: list[Action] = []
    by_id = {t.id: t for t in seen}
    tracked = {q.asked_turn_id for q in state.parent_questions}
    for opened in out.questions_opened:
        turn = by_id.get(opened.turn_id)
        if turn is None or turn.role != "parent" or turn.id in tracked:
            continue
        if wakeword.find_summon(turn.text):
            continue  # a question to Beacon. Beacon answers it directly.
        # Beacon can read the question aloud later, so it must be the parent's own words.
        if not quote_in_text(opened.text, turn.text):
            message = f"ignored question for {turn.id}: “{opened.text}” is not in the turn"
            actions.append(_log(now_ms, "question", message, turn_id=turn.id))
            continue
        covering = next((f for f in state.flags if f.state != "dropped" and turn.id in f.evidence_turn_ids), None)
        if covering:
            actions.append(_log(now_ms, "question", f"question in {turn.id} is already covered by {covering.id}", covering.id, turn.id))
            continue
        state.parent_questions.append(ParentQuestion(text=opened.text, asked_turn_id=turn.id))
        tracked.add(turn.id)
        actions.append(_log(now_ms, "question", f"parent asked: “{opened.text}”", turn_id=turn.id))
    return actions


def _close_questions(state: RoomState, out: AnalyzerOutput, seen: list[Turn], now_ms: int) -> list[Action]:
    """Mark the questions that the analyzer found answered. Resolve their flags."""
    actions: list[Action] = []
    by_id = {t.id: t for t in seen}
    order = {t.id: i for i, t in enumerate(seen)}
    tracked = {q.asked_turn_id: q for q in state.parent_questions}
    for answered in out.questions_answered:
        question = tracked.get(answered.asked_turn_id)
        answer = by_id.get(answered.answered_turn_id)
        if question is None or question.answered_turn_id or answer is None or answer.role == "beacon":
            continue
        if order[answer.id] <= order[question.asked_turn_id]:
            continue  # an answer must come after the question
        # A later parent turn can also close the question: "Oh, never mind, I see it on the
        # letter." Then Beacon must not ask the question for the parent.
        withdrawn = answer.role == "parent"
        question.answered_turn_id = answer.id
        verb = "withdrew the question from" if withdrawn else "answered the question from"
        actions.append(_log(now_ms, "question", f"{answer.id} {verb} {question.asked_turn_id}", turn_id=answer.id))
        flag = _flag_with_key(state, f"unanswered_{question.asked_turn_id}")
        if flag and flag.state == "nudged":
            reason = "the parent withdrew the question" if withdrawn else "the counselor answered the question"
            actions += _transition(flag, "resolved", reason, seen[-1].id, now_ms)
    return actions


def _raise_unanswered(state: RoomState, seen: list[Turn], now_ms: int) -> list[Action]:
    """Make a flag for each question that has no answer after enough counselor turns. Code counts
    the turns, not the LLM."""
    actions: list[Action] = []
    latest = seen[-1].id
    for question in state.parent_questions:
        key = f"unanswered_{question.asked_turn_id}"
        # One flag per question, in any state. The analyzer can mark the flag resolved without
        # an answer to the question. That must not make a second flag.
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
            "family_question": question.text,
            "doc_refs": [],
        }
        age = _turns_after(seen, question.asked_turn_id, ("counselor", "parent"))
        if age > config.STALE_AFTER_TURNS:  # found too late to interrupt, as for other flags
            actions += _create_flag(state, fields, "recap", f"question is already {age} turns old", latest, now_ms)
        else:
            actions += _create_flag(state, fields, "nudged", f"unanswered after {waited} counselor turn(s)", latest, now_ms)
    return actions


# ---------------------------------------------------------------- escalation ladder


def _turns_before_speaking(flag: Flag) -> int:
    """The counselor turns without a clarification before Beacon can speak. "I'll clarify" adds
    grace turns."""
    return config.ESCALATE_AFTER_COUNSELOR_TURNS + flag.grace_turns


def _counselor_turns_since_card(flag: Flag, seen: list[Turn]) -> list[Turn]:
    """The counselor turns that came after the card appeared.

    A turn counts if it is after ladder_start_turn and it started at or after ladder_start_ms.
    A turn that started before the card appeared does not count. The counselor did not decide
    to move on, because they did not see the card yet."""
    ids = [t.id for t in seen]
    if flag.ladder_start_turn not in ids:
        return []
    later = seen[ids.index(flag.ladder_start_turn) + 1 :]
    return [t for t in later if t.role == "counselor" and t.started_at >= flag.ladder_start_ms]


def _run_ladder(state: RoomState, seen: list[Turn], unseen_human_turns: bool, now_ms: int) -> list[Action]:
    """Find the nudged flags that are due or stale. Speak for the oldest due flag, if Beacon can."""
    actions: list[Action] = []
    latest = seen[-1].id
    due: list[Flag] = []
    for flag in [f for f in state.flags if f.state == "nudged"]:
        counselor_turns = _counselor_turns_since_card(flag, seen)
        if not counselor_turns:
            continue  # the counselor did not speak since the card: not due and not stale
        # Count staleness from the counselor's first turn after the card, not from the card.
        # A parent can split one reply over several push-to-talk presses. Those turns must not
        # use up the counselor's chance to clarify.
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
        # A person spoke during the LLM call. That turn can be the clarification, so the next
        # analysis decides.
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
    """False if the LLM cannot find anything new. Then rooms.py does not call it.

    `analyzed_ok` is the number of turns that the last successful analysis covered. Each LLM
    trigger needs a parent turn as evidence. So if only counselor turns are new, the LLM can only
    find resolutions and answers. That is useful only if a flag or a question is open."""
    new_turns = _human(state.turns[analyzed_ok:])
    if not new_turns:
        return False
    if any(t.role == "parent" for t in new_turns) or set(LLM_TRIGGER_NAMES) - PARENT_EVIDENCED:
        return True
    open_flags = any(f.state == "nudged" for f in state.flags)
    open_questions = any(q.answered_turn_id is None for q in state.parent_questions)
    return open_flags or open_questions


def _resolve_flags(state: RoomState, out: AnalyzerOutput, seen: list[Turn], now_ms: int) -> list[Action]:
    """Resolve the nudged flags that the analyzer found clarified."""
    actions: list[Action] = []
    latest = seen[-1].id
    for flag_id in out.resolved_flag_ids:
        flag = find_flag(state, flag_id)
        if not flag or flag.state != "nudged":
            continue
        # Only the counselor can clarify, so a counselor turn must come after the evidence.
        # Gemini once marked a flag resolved after a short parent turn ("Oh,").
        newest = _newest_evidence_turn(seen, flag.evidence_turn_ids)
        if newest is None or not _turns_after(seen, newest.id, ("counselor",)):
            actions.append(_log(now_ms, "ladder", f"ignored resolution of {flag.id}: no counselor turn after its evidence", flag.id, latest))
            continue
        actions += _transition(flag, "resolved", "the counselor clarified it", latest, now_ms)
    return actions


def after_analysis(state: RoomState, out: AnalyzerOutput, turn_count: int, now_ms: int) -> list[Action]:
    """Apply one result from the analyzer.

    `turn_count` is the number of turns that the analyzer saw. Turns that arrived during the LLM
    call are not in `seen`. The next analysis sees them."""
    seen = state.turns[:turn_count]
    if not seen:
        return []
    actions = _resolve_flags(state, out, seen, now_ms)
    actions += _add_new_flags(state, out, seen, now_ms)
    actions += _open_questions(state, out, seen, now_ms)
    actions += _close_questions(state, out, seen, now_ms)
    actions += _raise_unanswered(state, seen, now_ms)
    unseen_human_turns = bool(_human(state.turns[turn_count:]))
    actions += _run_ladder(state, seen, unseen_human_turns, now_ms)
    return actions


def mark_spoken(state: RoomState, flag_id: str, turn_id: str, now_ms: int) -> list[Action]:
    """Record that Beacon spoke the line for a flag. This starts the cooldown."""
    flag = find_flag(state, flag_id)
    state.last_spoken_at = now_ms
    return _transition(flag, "spoken", "Beacon asked aloud", turn_id, now_ms)


def counselor_action(state: RoomState, flag_id: str, action: CardAction, latest_turn_id: str, now_ms: int) -> list[Action]:
    """Apply a click on a card. rooms.py makes sure that the click came from the counselor.

    - "dismiss" (Not an issue): the flag ends. Beacon never speaks about it.
    - "will_clarify" (I'll clarify): the ladder starts again at the newest turn, with grace turns.
      The counselor can use this once per flag.
    Only a nudged flag accepts a click. Other clicks change nothing and make a log entry."""

    def ignored(why: str) -> list[Action]:
        return [_log(now_ms, "ladder", f"ignored counselor action {action} on {flag_id}: {why}", turn_id=latest_turn_id)]

    flag = find_flag(state, flag_id)
    if flag is None:
        return ignored("no such flag")
    if flag.state != "nudged":
        # This includes a line that Beacon is speaking now: _speak() marks the flag spoken first.
        return ignored(f"it is already {flag.state}")
    if action == "dismiss":
        flag.counselor_action = "dismissed"
        return _transition(flag, "dismissed", "counselor: not an issue", latest_turn_id, now_ms)
    if flag.counselor_action == "will_clarify":
        # A second click must not delay the family's question again.
        return ignored("the counselor already said they will clarify")
    flag.counselor_action = "will_clarify"
    flag.ladder_start_turn = latest_turn_id
    flag.ladder_start_ms = now_ms
    flag.grace_turns = config.CLARIFY_GRACE_COUNSELOR_TURNS
    flag.history.append(FlagEvent(state="nudged", reason="counselor: will clarify", turn_id=latest_turn_id))
    message = f"{flag.id} counselor will clarify; waiting {_turns_before_speaking(flag)} counselor turn(s) before speaking"
    return [UpdateFlag(flag_id=flag.id), _log(now_ms, "ladder", message, flag.id, latest_turn_id)]


def end_of_call(state: RoomState, now_ms: int) -> list[Action]:
    """Move the flags that still wait for the counselor to the recap."""
    latest = state.turns[-1].id if state.turns else ""
    actions: list[Action] = []
    for flag in [f for f in state.flags if f.state == "nudged"]:
        actions += _transition(flag, "recap", "the call ended before it was clarified", latest, now_ms)
    return actions
