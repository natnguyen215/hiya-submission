"""Builds prompts from room state, calls the LLM, and validates what comes back. analyze()
perceives what is happening in the call, answer_summon() answers a question put to Beacon, and
generate_recap() writes the Family Recap. The prompt text lives in backend/prompts/*.txt."""

import re
import time

from pydantic import BaseModel, ValidationError

from . import config, docs
from .llm import LLM
from .models import AnalyzerOutput, Recap, RecapFollowUp, RoomState, SummonAnswer, Turn
from .triggers import TRIGGERS

EMPTY_OUTPUT = AnalyzerOutput(notes="", new_flags=[], resolved_flag_ids=[], questions_opened=[], questions_answered=[])


class InvalidOutput(Exception):
    pass


class AnalysisResult(BaseModel):
    output: AnalyzerOutput
    turn_count: int  # how many turns the analyzer saw
    latency_ms: int
    error: str | None = None


# ---------------------------------------------------------------- prompt pieces


def _fill(template_name: str, values: dict[str, str]) -> str:
    """Load a prompt file and replace its {{PLACEHOLDERS}} (not str.format: prompts contain JSON)."""
    text = (config.PROMPTS_DIR / f"{template_name}.txt").read_text(encoding="utf-8")
    names = {"COUNSELOR_NAME": config.COUNSELOR_NAME, "PARENT_NAME": config.PARENT_NAME}
    for key, value in {**names, **values}.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def format_transcript(turns: list[Turn]) -> str:
    speakers = {
        "counselor": f"COUNSELOR ({config.COUNSELOR_NAME})",
        "parent": f"PARENT ({config.PARENT_NAME})",
        "beacon": "BEACON",
    }
    lines = []
    for turn in turns:
        pause = ""
        if turn.gap_ms is not None and turn.role != "beacon":
            long = ", LONG PAUSE" if turn.gap_ms >= config.NOTABLE_GAP_MS else ""
            pause = f" [after {turn.gap_ms} ms{long}]"
        lines.append(f"{turn.id} {speakers[turn.role]}{pause}: {turn.text}")
    return "\n".join(lines) or "(no turns yet)"


def format_triggers() -> str:
    blocks = []
    for trigger in TRIGGERS:
        if trigger.detected_by != "llm":
            continue
        lines = [f"{trigger.name}: {trigger.description}"]
        lines += [f"  Flag: {example}" for example in trigger.positive_examples]
        lines += [f"  Do not flag: {example}" for example in trigger.negative_examples]
        if trigger.needs_parent_evidence:
            lines.append("  Evidence must include the parent's reply.")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _format_flags(state: RoomState) -> str:
    lines = [
        f"{f.id} [{f.issue_key}] {f.trigger} state={f.state} evidence={','.join(f.evidence_turn_ids)}: {f.counselor_card}"
        for f in state.flags
        if f.state != "dropped"
    ]
    return "\n".join(lines) or "(none)"


def _format_questions(state: RoomState) -> str:
    lines = []
    for q in state.parent_questions:
        status = f"answered in {q.answered_turn_id}" if q.answered_turn_id else "UNANSWERED"
        lines.append(f"{q.asked_turn_id}: “{q.text}” ({status})")
    return "\n".join(lines) or "(none)"


def build_analysis_prompt(state: RoomState) -> str:
    return _fill(
        "analyzer",
        {
            "TRIGGERS": format_triggers(),
            "DOCUMENTS": docs.DOCUMENTS_TEXT,
            "FLAGS": _format_flags(state),
            "QUESTIONS": _format_questions(state),
            "TRANSCRIPT": format_transcript(state.turns),
        },
    )


# ---------------------------------------------------------------- LLM calls


async def _generate(llm: LLM, prompt: str, schema: type[BaseModel], timeout_s: float):
    """Call the LLM and validate against the schema, retrying once on invalid output."""
    problem = None
    for _ in range(2):
        text = await llm.generate_json(prompt, schema, timeout_s)
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            problem = exc
    raise InvalidOutput(f"invalid {schema.__name__} twice: {problem.errors()[0]['msg'] if problem else ''}")


async def analyze(llm: LLM, state: RoomState) -> AnalysisResult:
    """Never raises: any LLM failure becomes an empty result with an error, so the call goes on."""
    turn_count = len(state.turns)
    prompt = build_analysis_prompt(state)
    started = time.monotonic()
    try:
        output = await _generate(llm, prompt, AnalyzerOutput, config.ANALYZER_TIMEOUT_SECONDS)
        error = None
    except Exception as exc:
        output, error = EMPTY_OUTPUT, f"{type(exc).__name__}: {exc}"
    latency_ms = int((time.monotonic() - started) * 1000)
    return AnalysisResult(output=output, turn_count=turn_count, latency_ms=latency_ms, error=error)


async def answer_summon(llm: LLM, state: RoomState, turn: Turn) -> SummonAnswer:
    """The LLM gets the whole turn as said (casing, punctuation, words before the name), not the
    lowercased question wakeword.find_summon() extracts for the log."""
    prompt = _fill(
        "summon",
        {
            "TURN_ID": turn.id,
            "TURN_TEXT": turn.text,
            "TRANSCRIPT": format_transcript(state.turns[-config.SUMMON_CONTEXT_TURNS :]),
            "DOCUMENTS": docs.DOCUMENTS_TEXT,
        },
    )
    answer = await _generate(llm, prompt, SummonAnswer, config.SUMMON_TIMEOUT_SECONDS)
    answer.doc_refs = [ref for ref in answer.doc_refs if ref in docs.LINES]
    return answer


def _open_issues(state: RoomState) -> str:
    # By now end_of_call() has moved every nudged flag to "recap". Flags the counselor dismissed
    # are left out on purpose. The parent's unanswered questions are listed from parent_questions,
    # not from their flags, so dismissing an UNANSWERED_QUESTION card silences Beacon during the
    # call but cannot remove the family's open question from the recap.
    lines = [f"{f.id} ({f.trigger}, saved for the recap): {f.counselor_card}" for f in state.flags if f.state == "recap"]
    lines += [f"{f.id} ({f.trigger}, asked aloud by Beacon): {f.counselor_card}" for f in state.flags if f.state == "spoken"]
    lines += [
        f"{q.asked_turn_id} (unanswered question): “{q.text}”"
        for q in state.parent_questions
        if q.answered_turn_id is None
    ]
    return "\n".join(lines) or "(none)"


async def generate_recap(llm: LLM, state: RoomState) -> Recap:
    prompt = _fill(
        "recap",
        {
            "OPEN_ISSUES": _open_issues(state),
            "DOCUMENTS": docs.DOCUMENTS_TEXT,
            "TRANSCRIPT": format_transcript(state.turns),
        },
    )
    return await _generate(llm, prompt, Recap, config.RECAP_TIMEOUT_SECONDS)


def add_missing_follow_ups(recap: Recap, state: RoomState) -> list[str]:
    """The recap must list every open issue (recap-state flags, unanswered questions). Add any the
    LLM left out, using the flag's question for Beacon (spoken_line) or the parent's own words,
    and return their ids for the log. As in _open_issues(), a dismissed flag is not an open issue,
    but a question the parent asked and nobody answered still is, dismissed card or not."""
    cited = {ref for follow_up in recap.follow_ups for ref in follow_up.refs}
    missing = [(f.id, f.spoken_line) for f in state.flags if f.state == "recap" and f.id not in cited]
    missing += [
        (q.asked_turn_id, q.text)
        for q in state.parent_questions
        if q.answered_turn_id is None and q.asked_turn_id not in cited
    ]
    recap.follow_ups += [RecapFollowUp(question=text, refs=[ref]) for ref, text in missing]
    return [ref for ref, _ in missing]


# ---------------------------------------------------------------- recap number check


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def unverified_numbers(recap: Recap, state: RoomState) -> list[str]:
    """Numbers in the recap that don't appear in any line, turn, or flag evidence the item cites."""
    turn_text = {t.id: t.text for t in state.turns}
    for flag in state.flags:
        turn_text[flag.id] = " ".join(turn_text.get(tid, "") for tid in flag.evidence_turn_ids)
    items = [recap.cost_of_attendance, *recap.grants, *recap.loans, *recap.work_study, *recap.still_to_pay]
    checks = [(i.label, f"{i.label} {i.amount} {i.note}", i.refs) for i in items]
    checks += [(t.task, f"{t.task} {t.deadline}", t.refs) for t in recap.todos]
    checks += [(f.question, f.question, f.refs) for f in recap.follow_ups]
    problems = []
    for label, text, refs in checks:
        sources = " ".join(docs.LINES[r].text if r in docs.LINES else turn_text.get(r, "") for r in refs)
        missing = sorted(_numbers(text) - _numbers(sources))
        if missing:
            problems.append(f"{label}: {', '.join(missing)} not found in {', '.join(refs) or 'any citation'}")
    return problems
