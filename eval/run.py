"""Offline eval: runs the real analyzer and policy over the scripts in SCRIPTS, turn by turn
(text only), scores each planted moment, and writes eval_results.md.

Usage: python -m eval.run [--cache] [--script demo_call] [--runs 3]
--cache stores LLM responses in .cache/ by prompt hash, so tuning the policy costs no quota.
--runs repeats every script, because the same prompt can get a different answer from the LLM:
a moment should reach its expected outcome in every run, not just once."""

import argparse
import asyncio
import json
import re
import statistics
import sys
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
# The free tier's daily request quota (500 for gemini-3.5-flash-lite in October 2026) answers 429
# with "retry in 15h...". Waiting won't help, so the eval stops and reports the runs it finished.
DAILY_QUOTA = re.compile(r"retry in \d+h")
# A declined summon must not slip in a figure: "$6,000", "$ 6000" or "6,000 dollars".
DOLLAR_AMOUNT = re.compile(r"\$\s*\d|\d[\d,]*\s*dollars", re.IGNORECASE)
MS_PER_WORD = 400  # ~150 words a minute; advances the virtual clock so cooldowns behave like a call
START_MS = 1_000_000_000


class QuotaExhausted(Exception):
    pass


class Call:
    """A text-only call driven by a script, with a virtual clock instead of wall time."""

    def __init__(self):
        self.state = RoomState()
        self.clock = START_MS
        self.latencies: list[int] = []  # analyzer network calls (not the cache, not the rate-limit wait)
        self.analyzed_ok = 0  # transcript length covered by the last successful analysis, as in rooms.py
        self.errors: list[str] = []
        self.summons: dict[str, SummonAnswer] = {}  # turn id -> Beacon's answer (missing if it failed)
        self.summon_latencies: list[int] = []
        self.decisions: list[str] = []

    def add(self, role: str, text: str, gap_ms: int, source: str) -> Turn:
        self.clock += gap_ms
        started = self.clock
        self.clock += len(text.split()) * MS_PER_WORD
        turn = Turn(
            id=f"t{len(self.state.turns) + 1}",
            role=role,
            text=text,
            started_at=started,
            ended_at=self.clock,
            gap_ms=gap_ms,
            source=source,
        )
        self.state.turns.append(turn)
        return turn

    def error(self, message: str) -> None:
        self.errors.append(message)
        if DAILY_QUOTA.search(message):  # every later request would fail too
            raise QuotaExhausted(message)

    def speak(self, text: str, flag_id: str | None = None) -> None:
        """Beacon speaks immediately (no other speaker to wait for in a text-only replay)."""
        turn = self.add("beacon", text, config.PAUSE_BEFORE_SPEAK_MS, "beacon")
        if flag_id:
            self.record(policy.mark_spoken(self.state, flag_id, turn.id, self.clock))

    def record(self, actions: list[policy.Action]) -> None:
        for action in actions:
            if isinstance(action, policy.SpeakLine):
                self.speak(action.text, action.flag_id)
            elif isinstance(action, LogEntry):
                self.decisions.append(action.message)


async def run_script(llm: GeminiLLM, name: str) -> tuple[list[dict], Call]:
    script = json.loads((config.SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))
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
        call.latencies += llm.latencies_ms[timed_before:]
        if result.error:
            call.error(f"{name} analysis {turn.id}: {result.error}")
            continue
        call.analyzed_ok = result.turn_count
        call.record(policy.after_analysis(call.state, result.output, result.turn_count, call.clock))
    # No end_of_call(): moments are scored as the call left them, so a flag still waiting on the
    # counselor reads "nudged" rather than the recap state end_of_call() would move it to.
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
    """One line for the summary table: how consistently the script met its targets."""
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
    return f"| {name} | {'; '.join(parts)} |"


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


def report(results: dict[str, list[tuple[list[dict], Call]]], llm: GeminiLLM, cache: bool) -> str:
    runs = len(next(iter(results.values())))
    out = [
        "# Eval results",
        "",
        f"{datetime.now():%Y-%m-%d %H:%M} · model `{config.GEMINI_MODEL}` · thinking `{config.GEMINI_THINKING_LEVEL}`"
        f" · cache {'on' if cache else 'off'} · {runs} run(s) per script",
        "",
    ]
    calls = [call for script_runs in results.values() for _, call in script_runs]
    errors = [error for call in calls for error in call.errors]
    if errors:
        warning = f"> **{len(errors)} LLM requests failed, so the outcomes below are not meaningful.**"
        out += [f"{warning} See the list at the end.", ""]
    out += ["| Script | Result |", "|---|---|"]
    out += [summarize(name, script_runs) for name, script_runs in results.items()]
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
    return "\n".join(out) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", action="store_true", help="reuse and store LLM responses in .cache/")
    parser.add_argument("--script", choices=SCRIPTS, action="append", help="run only this script (repeatable)")
    parser.add_argument("--runs", type=int, default=1, help="run each script this many times")
    args = parser.parse_args()
    if not config.GEMINI_API_KEY and not args.cache:
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (see .env.example), or pass --cache to replay cached responses.")
    llm = GeminiLLM(cache=args.cache)
    results: dict[str, list[tuple[list[dict], Call]]] = {}
    stopped = ""
    try:
        for name in args.script or SCRIPTS:
            for run in range(1, args.runs + 1):
                print(f"{name}, run {run} of {args.runs}", flush=True)
                outcome = await run_script(llm, name)
                results.setdefault(name, []).append(outcome)
    except QuotaExhausted as exc:
        stopped = f"> **Stopped early: the daily LLM quota ran out during {name}, run {run}.** {exc}"
        print(stopped)
    if not results:
        sys.exit("No run finished, so there is nothing to report.")
    text = report(results, llm, args.cache)
    if stopped:  # right under the title line, so nobody mistakes the partial report for a full one
        title, rest = text.split("\n", 1)
        text = f"{title}\n\n{stopped}\n{rest}"
    RESULTS_FILE.write_text(text, encoding="utf-8")
    print(f"Wrote {RESULTS_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())
