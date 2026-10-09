"""Offline eval: runs the real analyzer and policy over the scripts in SCRIPTS (text only),
scores each planted moment, and writes eval_results.md.

Usage: python -m eval.run [--cache] [--script demo_call] [--runs 3] [--paced]
--cache stores LLM responses in .cache/ by prompt hash, so tuning the policy costs no quota.
--runs repeats every script, because the same prompt can get a different answer from the LLM:
a moment should reach its expected outcome in every run, not just once.

Two modes, each with a virtual clock instead of wall time:
- lock-step (the default): every turn is analyzed before the next one arrives, and Beacon speaks
  at once. The world the policy was tuned in; its numbers stay comparable from round to round.
- paced (--paced): turns arrive on the clock whether or not an analysis is running, as in a live
  call. An analysis sees only the turns that arrived before it started, takes as long as the LLM
  call did (--assumed-latency-ms with --cache), and a line Beacon queued is withdrawn when a
  person starts talking first. rooms.py's timing, rebuilt on the virtual clock.
Each run replaces its own mode's half of eval_results.md and keeps the other half."""

import argparse
import asyncio
import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime

from backend.app import analyzer, config, policy, wakeword
from backend.app.llm import GeminiLLM
from backend.app.models import Flag, LogEntry, RoomState, SummonAnswer, Turn

SCRIPTS = [
    "demo_call",  # the planted moments the demo video relies on
    "demo_call_stt_noise",  # the same call as Chrome's speech recognition would transcribe it
    "control_call",  # a clean call
    "adversarial_clean",  # a clean call full of near misses (restatements, explained jargon)
    "live_regressions",  # real failures from live testing
    "live_patterns",  # timing patterns of a live call: relapses, split replies, back-to-back misreads
    "summon_checks",  # questions to Beacon, inside and outside the documents
]
# Calls with nothing planted: the target is no spoken interjection and at most one private nudge.
CLEAN_SCRIPTS = {"control_call", "adversarial_clean"}
RESULTS_FILE = config.ROOT / "eval_results.md"
MODE_TITLES = {"lock-step": "Lock-step (default)", "paced": "Paced (--paced)"}
# The free tier's daily request quota (500 for gemini-3.5-flash-lite in October 2026) answers 429
# with "retry in 15h...". Waiting won't help, so the eval stops and reports the runs it finished.
DAILY_QUOTA = re.compile(r"retry in \d+h")
# A declined summon must not slip in a figure: "$6,000", "$ 6000" or "6,000 dollars".
DOLLAR_AMOUNT = re.compile(r"\$\s*\d|\d[\d,]*\s*dollars", re.IGNORECASE)
MS_PER_WORD = 400  # ~150 words a minute; advances the virtual clock so cooldowns behave like a call
START_MS = 1_000_000_000
# Log lines that name the flags the ladder found due: "f2 escalates: ..." and "f2, f3 due, ...".
DUE_FLAGS = re.compile(r"^(f\d+(?:, f\d+)*) (?:escalates|due,)")


class QuotaExhausted(Exception):
    pass


@dataclass
class QueuedLine:
    """A line waiting for a pause, as in rooms.Speech, plus when it joined the queue (paced mode)."""

    text: str
    kind: str  # "summon" or "flag"
    flag_id: str | None
    queued_at: int


class Call:
    """A text-only call driven by a script, with a virtual clock instead of wall time."""

    def __init__(self, paced: bool = False):
        self.state = RoomState()
        self.clock = START_MS
        self.paced = paced
        self.latencies: list[int] = []  # analyzer network calls (not the cache, not the rate-limit wait)
        self.analyzed_ok = 0  # transcript length covered by the last successful analysis, as in rooms.py
        self.errors: list[str] = []
        self.summons: dict[str, SummonAnswer] = {}  # turn id -> Beacon's answer (missing if it failed)
        self.summon_latencies: list[int] = []
        self.decisions: list[str] = []
        # Timing counters for the report.
        self.analyses = 0  # analyzer LLM calls
        self.seen_late = 0  # turns that arrived while an analysis was running
        self.withdrawn = 0  # queued lines withdrawn because a person spoke first
        self.due_flags: set[str] = set()  # flags the ladder found due at least once
        self.deferred_flags: set[str] = set()  # flags due while newer turns were not analyzed yet
        self.queue: list[QueuedLine] = []  # paced mode only: lines waiting for a pause

    def append_turn(self, role: str, text: str, started: int, ended: int, gap_ms: int | None, source: str) -> Turn:
        turn = Turn(
            id=f"t{len(self.state.turns) + 1}",
            role=role,
            text=text,
            started_at=started,
            ended_at=ended,
            gap_ms=gap_ms,
            source=source,
        )
        self.state.turns.append(turn)
        return turn

    def add(self, role: str, text: str, gap_ms: int, source: str) -> Turn:
        """Lock-step: the turn starts after the pause and the clock moves to its end."""
        started = self.clock + gap_ms
        self.clock = started + len(text.split()) * MS_PER_WORD
        return self.append_turn(role, text, started, self.clock, gap_ms, source)

    def error(self, message: str) -> None:
        self.errors.append(message)
        if DAILY_QUOTA.search(message):  # every later request would fail too
            raise QuotaExhausted(message)

    def speak(self, text: str, flag_id: str | None = None) -> None:
        """Lock-step: Beacon speaks immediately (no other speaker to wait for)."""
        turn = self.add("beacon", text, config.PAUSE_BEFORE_SPEAK_MS, "beacon")
        if flag_id:
            self.record(policy.mark_spoken(self.state, flag_id, turn.id, self.clock))

    def enqueue(self, text: str, kind: str, flag_id: str | None = None) -> None:
        """Paced: queue a line for the next pause; one line per flag, as in rooms.enqueue_speech()."""
        if flag_id and any(line.flag_id == flag_id for line in self.queue):
            return
        self.queue.append(QueuedLine(text, kind, flag_id, self.clock))

    def record(self, actions: list[policy.Action]) -> None:
        for action in actions:
            if isinstance(action, policy.SpeakLine):
                if self.paced:
                    self.enqueue(action.text, "flag", action.flag_id)
                else:
                    self.speak(action.text, action.flag_id)
            elif isinstance(action, LogEntry):
                self.decisions.append(action.message)
                due = DUE_FLAGS.match(action.message)
                if due:
                    self.due_flags.update(due.group(1).split(", "))
                    if "deferred" in action.message:
                        self.deferred_flags.update(due.group(1).split(", "))


def load_script(name: str) -> list[dict]:
    return json.loads((config.SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


async def run_script(llm: GeminiLLM, name: str) -> tuple[list[dict], Call]:
    """Lock-step: each turn is analyzed, and acted on, before the next one arrives."""
    script = load_script(name)
    call = Call()
    call.speak(config.OPENING_LINE)
    for line in script:
        turn = call.add(line["role"], line["text"], line["pause_before_ms"], "script")
        line["turn_id"] = turn.id
        print(f"  {name} {line['id']} -> {turn.id} {line['role']}: {line['text'][:60]}", flush=True)
        if wakeword.find_summon(turn.text):
            timed_before = len(llm.latencies_ms)
            try:
                answer = await analyzer.answer_summon(llm, call.state, turn)
                call.summons[turn.id] = answer
                call.speak(answer.answer)
            except Exception as exc:
                call.error(f"{name} summon {turn.id}: {exc}")
            call.summon_latencies += llm.latencies_ms[timed_before:]
        if not policy.should_analyze(call.state, call.analyzed_ok):
            call.analyzed_ok = len(call.state.turns)
            continue
        timed_before = len(llm.latencies_ms)
        result = await analyzer.analyze(llm, call.state)
        call.analyses += 1
        call.latencies += llm.latencies_ms[timed_before:]
        if result.error:
            call.error(f"{name} analysis {turn.id}: {result.error}")
            continue
        call.analyzed_ok = result.turn_count
        call.record(policy.after_analysis(call.state, result.output, result.turn_count, call.clock))
    # No end_of_call(): moments are scored as the call left them, so a flag still waiting on the
    # counselor reads "nudged" rather than the recap state end_of_call() would move it to.
    return script, call


def playback_ms(text: str) -> int:
    """How long Beacon's line holds the floor: rooms.py's fallback when no tab reports playback."""
    return 2000 + len(text.split()) * config.PLAYBACK_FALLBACK_MS_PER_WORD


async def run_script_paced(llm: GeminiLLM, name: str, assumed_latency_ms: int) -> tuple[list[dict], Call]:
    """Paced: replays rooms.py's timing on the virtual clock. Each step finds the next event
    (a person presses or releases push-to-talk, an analysis starts or finishes, a summon answer
    is ready, Beacon starts a line), moves the clock there and handles it the way rooms.py does.
    The LLM call itself happens when an analysis starts, on the transcript as it is then."""
    script = load_script(name)
    call = Call(paced=True)
    # Beacon's opening line plays before anyone talks (the observer's runner waits for it too).
    last_end = call.clock + playback_ms(config.OPENING_LINE)  # end of the newest turn, anyone's
    call.append_turn("beacon", config.OPENING_LINE, call.clock, last_end, None, "beacon")
    lines = list(script)
    speaker: tuple[dict, int, int] | None = None  # (script line, start, end) of the person talking
    analysis = None  # (finishes at, result, dirty) of the running analysis
    analysis_wanted = False  # a turn arrived that no analysis has started on yet
    last_start = None  # when the previous analysis started, for the throttle
    summons: list[tuple[int, str]] = []  # (ready at, answer text) of summon answers being prepared
    throttle_ms = int(config.MIN_SECONDS_BETWEEN_LLM_CALLS * 1000)

    async def timed(make_request, latencies: list[int]):
        """Run one LLM request; return its result and the virtual time it takes: the network
        time it really took, or the assumed latency for a cached replay (which takes no time)."""
        before = len(llm.latencies_ms)
        try:
            result = await make_request()
        finally:
            measured = llm.latencies_ms[before:]
            latencies += measured
        return result, sum(measured) if measured and not llm.cache else assumed_latency_ms

    while lines or speaker or analysis or analysis_wanted or summons or call.queue:
        # Candidate events as (time, tie-break order, kind). Ties: a release before an analysis
        # result, a result before Beacon speaks, and Beacon before a person presses the key.
        events = []
        if speaker:
            events.append((speaker[2], 0, "release"))
        if analysis:
            events.append((analysis[0], 1, "analysis done"))
        events += [(ready, 2, "summon ready") for ready, _ in summons]
        if call.queue and not speaker:
            # Beacon waits for PAUSE_BEFORE_SPEAK_MS of quiet after the line is queued, the last
            # turn ends, or its own previous line ends.
            events.append((max(call.queue[0].queued_at, last_end) + config.PAUSE_BEFORE_SPEAK_MS, 3, "speak"))
        if analysis_wanted and not analysis:
            slot = last_start + throttle_ms if last_start is not None else call.clock
            events.append((max(call.clock, slot), 4, "analysis start"))
        if lines and not speaker:
            events.append((last_end + lines[0]["pause_before_ms"], 5, "press"))
        call.clock, _, kind = min(events)

        if kind == "press":  # push-to-talk is disabled while Beacon speaks, so last_end includes it
            line = lines.pop(0)
            speaker = (line, call.clock, call.clock + len(line["text"].split()) * MS_PER_WORD)
        elif kind == "release":
            line, started, ended = speaker
            speaker = None
            turn = call.append_turn(line["role"], line["text"], started, ended, line["pause_before_ms"], "script")
            line["turn_id"] = turn.id
            last_end = ended
            print(f"  {name} {line['id']} -> {turn.id} {line['role']}: {line['text'][:60]}", flush=True)
            if wakeword.find_summon(turn.text):
                try:
                    answer, latency = await timed(lambda: analyzer.answer_summon(llm, call.state, turn), call.summon_latencies)
                    call.summons[turn.id] = answer
                    summons.append((call.clock + latency, answer.answer))
                except Exception as exc:
                    call.error(f"{name} summon {turn.id}: {exc}")
                    summons.append((call.clock, config.SUMMON_FAILED_LINE.format(counselor=config.COUNSELOR_NAME)))
            # As in rooms.add_turn(): the conversation moved on, so a queued interjection may no
            # longer fit. The flag stays nudged and the next analysis decides again.
            withdrawn = [q for q in call.queue if q.kind == "flag"]
            if withdrawn:
                call.queue = [q for q in call.queue if q.kind != "flag"]
                call.withdrawn += len(withdrawn)
                ids = ", ".join(q.flag_id for q in withdrawn)
                call.decisions.append(f"withdrew queued line for {ids}: {turn.id} arrived first; re-deciding")
            if analysis:
                analysis = (analysis[0], analysis[1], True)  # rooms.request_analysis(): one more pass
                call.seen_late += 1
            else:
                analysis_wanted = True
        elif kind == "analysis start":
            analysis_wanted = False
            if not policy.should_analyze(call.state, call.analyzed_ok):
                call.analyzed_ok = len(call.state.turns)
                continue
            last_start = call.clock
            result, latency = await timed(lambda: analyzer.analyze(llm, call.state), call.latencies)
            call.analyses += 1
            analysis = (call.clock + latency, result, False)
        elif kind == "analysis done":
            _, result, dirty = analysis
            analysis = None
            last = call.state.turns[result.turn_count - 1].id
            if result.error:
                call.error(f"{name} analysis {last}: {result.error}")
            else:
                call.analyzed_ok = result.turn_count
                call.record(policy.after_analysis(call.state, result.output, result.turn_count, call.clock))
            analysis_wanted = analysis_wanted or dirty
        elif kind == "summon ready":
            ready = min(summons)
            summons.remove(ready)
            call.enqueue(ready[1], "summon")
        elif kind == "speak":
            queued = call.queue.pop(0)
            flag = next((f for f in call.state.flags if f.id == queued.flag_id), None)
            if flag and flag.state != "nudged":
                call.decisions.append(f"skipped line for {flag.id}: it is already {flag.state}")
                continue
            gap = call.clock - last_end
            last_end = call.clock + playback_ms(queued.text)
            turn = call.append_turn("beacon", queued.text, call.clock, last_end, gap, "beacon")
            if queued.flag_id:  # as in rooms._speak(): marked spoken when the line starts
                call.record(policy.mark_spoken(call.state, queued.flag_id, turn.id, call.clock))
    return script, call


def expected_outcomes(expect: dict) -> list[str]:
    """`outcome` is one outcome or a list of acceptable ones."""
    outcome = expect["outcome"]
    return outcome if isinstance(outcome, list) else [outcome]


def is_quiet_only(expect: dict) -> bool:
    """A moment that only checks Beacon stayed quiet. It passes on "none", so the summary reports
    it apart from the moments that need a detection."""
    return expected_outcomes(expect) == ["quiet"] and not expect.get("flag_required")


def summon_outcome(answer: SummonAnswer | None, expect: dict) -> str:
    """What Beacon did with a summon. An answer that fails a check says why, so it can't pass:
    "answered" needs the documents, the word limit and one of the expected refs; "declined" must
    not slip in a dollar amount."""
    if answer is None:
        return "none"
    if not answer.answered_from_documents:
        return "declined, but with a dollar amount" if DOLLAR_AMOUNT.search(answer.answer) else "declined"
    words = len(answer.answer.split())
    if words > config.SPOKEN_WORDS_WARNING:
        return f"answered, too long ({words} words)"
    if not set(answer.doc_refs) & set(expect.get("refs", [])):
        return f"answered, without an expected ref (cited {', '.join(answer.doc_refs) or 'none'})"
    return "answered"


def spoken_line(flag: Flag, call: Call) -> str:
    """The Beacon turn that mark_spoken() recorded for this flag, not just any Beacon turn."""
    turn_id = next(event.turn_id for event in flag.history if event.state == "spoken")
    return next(turn.text for turn in call.state.turns if turn.id == turn_id)


def score(line: dict, call: Call) -> dict:
    """Match a planted moment to flags citing its parent turn or the counselor turn just before."""
    expect = line["expect"]
    expected = expected_outcomes(expect)
    turns = call.state.turns
    index = next(i for i, t in enumerate(turns) if t.id == line["turn_id"])
    window = {line["turn_id"]}
    previous = next((t for t in reversed(turns[:index]) if t.role != "beacon"), None)
    if previous and previous.role == "counselor":
        window.add(previous.id)
    if expect["trigger"] == "SUMMON":
        trigger, outcome = "SUMMON", summon_outcome(call.summons.get(line["turn_id"]), expect)
    else:
        flags = [f for f in call.state.flags if f.state != "dropped" and window & set(f.evidence_turn_ids)]
        flags.sort(key=lambda f: f.trigger != expect["trigger"])  # prefer the expected trigger
        outcome, trigger = (flags[0].state, flags[0].trigger) if flags else ("none", "")
        mentions = expect.get("mentions")
        if outcome == "spoken" and mentions and not any(m in spoken_line(flags[0], call).lower() for m in mentions):
            outcome = "spoken, off topic"  # Beacon spoke, but its line mentions none of the keywords
    if "quiet" in expected:
        # "quiet": any state except spoken. With flag_required, a flag must also exist.
        passed = not outcome.startswith("spoken") and not (expect.get("flag_required") and outcome == "none")
    else:
        passed = outcome in expected
    if expect["trigger"] and outcome != "none" and trigger != expect["trigger"]:
        passed = False  # the right outcome for the wrong reason
    return {"line": line, "window": window, "trigger": trigger, "outcome": outcome, "passed": passed}


def transcript_block(call: Call, title: str) -> list[str]:
    lines = [f"<details><summary>{title}: transcript and decisions</summary>", "", "```"]
    for turn in call.state.turns:
        pause = f" ({turn.gap_ms / 1000:.1f}s pause)" if (turn.gap_ms or 0) >= config.NOTABLE_GAP_MS else ""
        lines.append(f"{turn.id} {turn.role.upper()}{pause}: {turn.text}")
    lines += ["", *call.decisions, "```", "", "</details>", ""]
    return lines


def clean_call_check(call: Call) -> tuple[int, int, bool]:
    """Flags (not counting dropped ones), spoken interjections, and whether a clean call passes."""
    flags = [f for f in call.state.flags if f.state != "dropped"]
    spoken = [f for f in flags if f.state == "spoken"]
    return len(flags), len(spoken), len(flags) <= 1 and not spoken


def summarize(name: str, runs: list[tuple[list[dict], Call]]) -> str:
    """One cell of the summary table: how consistently the script met its targets."""
    parts = []
    scored = [[score(line, call) for line in script if "expect" in line] for script, call in runs]
    if scored[0]:
        # Quiet-only moments pass when nothing is detected, so they are not counted as detections.
        quiet = [i for i, s in enumerate(scored[0]) if is_quiet_only(s["line"]["expect"])]
        moments = [i for i in range(len(scored[0])) if i not in quiet]
        if moments:
            always = sum(all(run[i]["passed"] for run in scored) for i in moments)
            clean_runs = sum(all(run[i]["passed"] for i in moments) for run in scored)
            parts.append(f"{always}/{len(moments)} moments pass in every run; all moments pass in {clean_runs}/{len(runs)} runs")
        if quiet:
            stayed = sum(all(run[i]["passed"] for run in scored) for i in quiet)
            parts.append(f"{stayed}/{len(quiet)} quiet moments (never spoken) stay quiet in every run")
    if name in CLEAN_SCRIPTS:
        checks = [clean_call_check(call) for _, call in runs]
        flags = ", ".join(str(f) for f, _, _ in checks)
        spoken = ", ".join(str(s) for _, s, _ in checks)
        verdict = "PASS" if all(ok for _, _, ok in checks) else "FAIL"
        parts.append(f"flags per run {flags} (target ≤1), spoken {spoken} (target 0) → {verdict}")
    return "; ".join(parts)


def script_section(name: str, runs: list[tuple[list[dict], Call]]) -> list[str]:
    out = [f"## {name}", ""]
    script = runs[0][0]
    planted = [line for line in script if "expect" in line]
    scored = [[score(line, call) for line in s if "expect" in line] for s, call in runs]
    if planted:
        header = " | ".join(f"Run {i + 1}" for i in range(len(runs)))
        out += [f"| Line | Expected | {header} | Passed |", "|---|---|" + "---|" * len(runs) + "---|"]
        for i, line in enumerate(planted):
            expect = line["expect"]
            outcomes = " or ".join(expected_outcomes(expect))
            if expect.get("flag_required"):
                outcomes += " (a flag must exist)"
            expected = f"{expect['trigger'] or 'no flag'} → {outcomes}"
            cells = []
            for run in scored:
                s = run[i]
                cell = s["outcome"] if s["trigger"] in ("", "SUMMON") else f"{s['trigger']} → {s['outcome']}"
                cells.append(cell if s["passed"] else f"**{cell} (FAIL)**")
            passes = sum(run[i]["passed"] for run in scored)
            out.append(f"| {line['id']} ({run[i]['line']['turn_id']}) | {expected} | {' | '.join(cells)} | {passes}/{len(runs)} |")
        out.append("")
    for index, ((_, call), run) in enumerate(zip(runs, scored), start=1):
        title = f"Run {index}"
        flags, spoken, ok = clean_call_check(call)
        if name in CLEAN_SCRIPTS:
            out.append(f"**{title}: flags {flags} (target ≤1) · spoken {spoken} (target 0) → {'PASS' if ok else 'FAIL'}**")
            out.append("")
        matched = set().union(*(s["window"] for s in run)) if run else set()
        unplanned = [f for f in call.state.flags if f.state != "dropped" and not matched & set(f.evidence_turn_ids)]
        if unplanned:
            out += [f"{title}, flags not matched to a planted moment:", ""]
            out += [f"- {f.id} {f.trigger} `{f.issue_key}` → {f.state}, evidence {f.evidence_turn_ids}" for f in unplanned]
            out.append("")
        dropped = [f for f in call.state.flags if f.state == "dropped"]
        if dropped:
            out += [f"{title}, dropped by the evidence gate:", ""]
            out += [f"- {f.id} `{f.issue_key}`: {f.history[0].reason}" for f in dropped]
            out.append("")
        if call.summons:
            out += [f"{title}, summon answers:", "", "| Turn | Words | From documents | Refs | Answer |", "|---|---|---|---|---|"]
            for turn_id, answer in call.summons.items():
                words = len(answer.answer.split())
                out.append(f"| {turn_id} | {words} | {'yes' if answer.answered_from_documents else 'no'} | {', '.join(answer.doc_refs) or '—'} | {answer.answer} |")
            out.append("")
        out += transcript_block(call, title)
    return out


def _latency(label: str, values: list[int]) -> str:
    if not values:
        return f"- {label}: no network calls"
    return f"- {label} over {len(values)} network calls: mean {statistics.mean(values):.0f} ms, max {max(values)} ms"


def flags_stale(call: Call) -> int:
    """Flags that went to the recap because it was too late to speak: stale on the ladder, or
    already stale when they were created."""
    return sum(any(e.reason.startswith("stale") or "turns old" in e.reason for e in f.history) for f in call.state.flags)


def timing_rows(name: str, runs: list[tuple[list[dict], Call]]) -> list[str]:
    """Per run: how the timing went. In lock-step mode nothing arrives late or is withdrawn."""
    rows = []
    for index, (_, call) in enumerate(runs, start=1):
        spoken = {f.id for f in call.state.flags if f.state == "spoken"}
        due = call.due_flags
        ratio = f"{len(due & spoken)}/{len(due)}" if due else "—"
        rows.append(
            f"| {name} | {index} | {call.analyses} | {call.seen_late} | {call.withdrawn} | "
            f"{len(call.deferred_flags)} | {flags_stale(call)} | {ratio} |"
        )
    return rows


def report(results: dict[str, list[tuple[list[dict], Call]]], llm: GeminiLLM, cache: bool, mode: str) -> tuple[dict, str]:
    """This mode's summary (for the side-by-side table at the top) and its detailed section."""
    runs = len(next(iter(results.values())))
    calls = [call for script_runs in results.values() for _, call in script_runs]
    errors = [error for call in calls for error in call.errors]
    header = (
        f"{datetime.now():%Y-%m-%d %H:%M} · model `{config.GEMINI_MODEL}` · thinking `{config.GEMINI_THINKING_LEVEL}`"
        f" · cache {'on' if cache else 'off'} · {runs} run(s) per script"
    )
    if errors:
        header += f" · **{len(errors)} LLM requests failed, so these outcomes are not meaningful**"
    summary = {"header": header, "rows": {name: summarize(name, script_runs) for name, script_runs in results.items()}}
    out = [f"# {MODE_TITLES[mode]}", "", header, ""]
    out += [
        "Timing per run. \"Spoke when due\": of the flags the ladder found due, how many Beacon said aloud.",
        "",
        "| Script | Run | Analyses | Turns seen late | Lines withdrawn | Flags deferred | Flags stale | Spoke when due |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, script_runs in results.items():
        out += timing_rows(name, script_runs)
    out.append("")
    for name, script_runs in results.items():
        out += script_section(name, script_runs)
    out += ["## LLM calls", ""]
    failed_early = llm.requests - llm.cache_hits - llm.api_calls  # e.g. no API key and not in the cache
    out.append(f"- Requests: {llm.requests} (network: {llm.api_calls}, from cache: {llm.cache_hits}, never sent: {failed_early})")
    out.append(_latency("Analyzer latency", [ms for call in calls for ms in call.latencies]))
    out.append(_latency("Summon latency", [ms for call in calls for ms in call.summon_latencies]))
    out.append(f"- Errors: {len(errors)}")
    out += [f"  - {e}" for e in errors]
    return summary, "\n".join(out)


def _block(text: str, mode: str) -> str | None:
    """A mode's section of an existing eval_results.md, markers included."""
    found = re.search(f"<!-- BEGIN {mode} -->.*?<!-- END {mode} -->", text, re.DOTALL)
    return found.group(0) if found else None


def write_results(mode: str, summary: dict, details: str) -> None:
    """Replace this mode's section of eval_results.md, keep the other mode's, and rebuild the
    side-by-side summary at the top from both. Each section starts with its summary as JSON in a
    comment, so the next run of the other mode can rebuild the table without parsing markdown."""
    old = RESULTS_FILE.read_text(encoding="utf-8") if RESULTS_FILE.exists() else ""
    blocks = {m: _block(old, m) for m in MODE_TITLES}
    blocks[mode] = f"<!-- BEGIN {mode} -->\n<!-- summary {json.dumps(summary)} -->\n{details}\n<!-- END {mode} -->"
    summaries = {}
    for m, block in blocks.items():
        if block:
            summaries[m] = json.loads(re.search(r"<!-- summary (.*?) -->", block).group(1))
    names = [n for n in SCRIPTS if any(n in found["rows"] for found in summaries.values())]
    out = ["# Eval results", ""]
    for m in MODE_TITLES:
        out.append(f"- {MODE_TITLES[m]}: {summaries[m]['header'] if m in summaries else 'not run yet'}")
    out += ["", f"| Script | {' | '.join(MODE_TITLES.values())} |", "|---|---|---|"]
    for name in names:
        cells = [summaries.get(m, {}).get("rows", {}).get(name, "—") for m in MODE_TITLES]
        out.append(f"| {name} | {' | '.join(cells)} |")
    out.append("")
    out += [blocks[m] + "\n" for m in MODE_TITLES if blocks[m]]
    RESULTS_FILE.write_text("\n".join(out), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", action="store_true", help="reuse and store LLM responses in .cache/")
    parser.add_argument("--script", choices=SCRIPTS, action="append", help="run only this script (repeatable)")
    parser.add_argument("--runs", type=int, default=1, help="run each script this many times")
    parser.add_argument("--paced", action="store_true", help="turns arrive on the clock, as in a live call")
    parser.add_argument(
        "--assumed-latency-ms", type=int, default=1500, help="paced mode: virtual duration of a cached LLM call"
    )
    args = parser.parse_args()
    if not config.GEMINI_API_KEY and not args.cache:
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (see .env.example), or pass --cache to replay cached responses.")
    llm = GeminiLLM(cache=args.cache)
    mode = "paced" if args.paced else "lock-step"
    results: dict[str, list[tuple[list[dict], Call]]] = {}
    stopped = ""
    try:
        for name in args.script or SCRIPTS:
            for run in range(1, args.runs + 1):
                print(f"{name}, run {run} of {args.runs} ({mode})", flush=True)
                if args.paced:
                    outcome = await run_script_paced(llm, name, args.assumed_latency_ms)
                else:
                    outcome = await run_script(llm, name)
                results.setdefault(name, []).append(outcome)
    except QuotaExhausted as exc:
        stopped = f"**Stopped early: the daily LLM quota ran out during {name}, run {run}.** {exc}"
        print(stopped)
    if not results:
        sys.exit("No run finished, so there is nothing to report.")
    summary, details = report(results, llm, args.cache, mode)
    if stopped:  # in the header, so nobody mistakes the partial report for a full one
        summary["header"] += f" · {stopped}"
        details = details.replace("\n", f"\n\n> {stopped}\n", 1)
    write_results(mode, summary, details)
    print(f"Wrote the {mode} half of {RESULTS_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())
