"""Offline eval. It sends the scripts in SCRIPTS through the real analyzer and policy, as text. It
scores each planted moment and writes eval_results.md.

Usage: python -m eval.run [--cache] [--script demo_call] [--runs 3]
--cache  keeps LLM responses in .cache/, so a second run of the same prompts costs no quota.
--runs   runs each script more than once. The LLM can give a different answer to the same
         prompt, so a moment must pass in every run, not only once.

The eval uses a virtual clock, not wall time. Each turn is analyzed, and the policy acts on it,
before the next turn arrives. Beacon speaks at once. So the eval measures perception and policy.
It does not measure live timing (a person who talks before Beacon gets its pause)."""

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
    "demo_short",  # the demo video: the planted moments of demo_call in 18 lines
    "demo_call",  # the planted moments in a full-length call
    "demo_call_stt_noise",  # the same call, as Chrome's speech recognition writes it
    "control_call",  # a clean call
    "adversarial_clean",  # a clean call with near misses (correct restatements, explained jargon)
    "live_regressions",  # failures found in live tests
    "live_patterns",  # live-call patterns: a relapse, split replies, two misreads in a row
    "summon_checks",  # questions to Beacon, in the documents and not in the documents
]
# Calls with nothing planted. Target: no spoken line and a maximum of one private card.
CLEAN_SCRIPTS = {"control_call", "adversarial_clean"}
RESULTS_FILE = config.ROOT / "eval_results.md"
# When the daily free-tier quota is used up, Gemini answers 429 with "retry in 15h". All later
# requests will also fail, so the eval stops and reports the runs that it completed.
DAILY_QUOTA = re.compile(r"retry in \d+h")
# A declined summon must not give a figure: "$6,000", "$ 6000" or "6,000 dollars".
DOLLAR_AMOUNT = re.compile(r"\$\s*\d|\d[\d,]*\s*dollars", re.IGNORECASE)
MS_PER_WORD = 400  # about 150 words a minute. The cooldown uses the clock, so the clock must move.
START_MS = 1_000_000_000


class QuotaExhausted(Exception):
    pass


class Call:
    """A text-only call that a script drives, with a virtual clock."""

    def __init__(self):
        self.state = RoomState()
        self.clock = START_MS
        self.analyzed_ok = 0  # turns that the last successful analysis covered (as in rooms.py)
        self.errors: list[str] = []
        self.decisions: list[str] = []  # the decision log
        self.summons: dict[str, SummonAnswer] = {}  # turn id -> Beacon's answer (none if it failed)
        self.latencies: list[int] = []  # network time of each analyzer call
        self.summon_latencies: list[int] = []

    def add(self, role: str, text: str, gap_ms: int, source: str) -> Turn:
        """Add a turn. It starts after the pause, and the clock moves to its end."""
        started = self.clock + gap_ms
        self.clock = started + len(text.split()) * MS_PER_WORD
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

    def speak(self, text: str, flag_id: str | None = None) -> None:
        """Beacon speaks at once. Nobody else talks in the eval, so it does not wait for a pause."""
        turn = self.add("beacon", text, config.PAUSE_BEFORE_SPEAK_MS, "beacon")
        if flag_id:
            self.record(policy.mark_spoken(self.state, flag_id, turn.id, self.clock))

    def record(self, actions: list[policy.Action]) -> None:
        """Do what the policy decided: speak the lines and keep the log entries."""
        for action in actions:
            if isinstance(action, policy.SpeakLine):
                self.speak(action.text, action.flag_id)
            elif isinstance(action, LogEntry):
                self.decisions.append(action.message)

    def error(self, message: str) -> None:
        self.errors.append(message)
        if DAILY_QUOTA.search(message):
            raise QuotaExhausted(message)


def load_script(name: str) -> list[dict]:
    return json.loads((config.SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


async def run_script(llm: GeminiLLM, name: str) -> tuple[list[dict], Call]:
    """Play one script. Each turn is analyzed, and the policy acts, before the next turn."""
    script = load_script(name)
    call = Call()
    call.speak(config.OPENING_LINE)
    for line in script:
        turn = call.add(line["role"], line["text"], line["pause_before_ms"], "script")
        line["turn_id"] = turn.id
        print(f"  {name} {line['id']} -> {turn.id} {line['role']}: {line['text'][:60]}", flush=True)
        if wakeword.find_summon(turn.text):
            count = len(llm.latencies_ms)
            try:
                answer = await analyzer.answer_summon(llm, call.state, turn)
                call.summons[turn.id] = answer
                call.speak(answer.answer)
            except Exception as exc:
                call.error(f"{name} summon {turn.id}: {exc}")
            call.summon_latencies += llm.latencies_ms[count:]
        if not policy.should_analyze(call.state, call.analyzed_ok):
            call.analyzed_ok = len(call.state.turns)
            continue
        count = len(llm.latencies_ms)
        result = await analyzer.analyze(llm, call.state)
        call.latencies += llm.latencies_ms[count:]
        if result.error:
            call.error(f"{name} analysis {turn.id}: {result.error}")
            continue
        call.analyzed_ok = result.turn_count
        call.record(policy.after_analysis(call.state, result.output, result.turn_count, call.clock))
    # The eval does not call end_of_call(). It scores each moment as the call left it, so a flag
    # that still waits for the counselor shows "nudged", not "recap".
    return script, call


# ---------------------------------------------------------------- scoring


def expected_outcomes(expect: dict) -> list[str]:
    """`outcome` is one outcome or a list of outcomes that pass."""
    outcome = expect["outcome"]
    return outcome if isinstance(outcome, list) else [outcome]


def is_quiet_only(expect: dict) -> bool:
    """A moment that only checks that Beacon did not speak. It passes with no flag, so the
    summary does not count it as a detection."""
    return expected_outcomes(expect) == ["quiet"] and not expect.get("flag_required")


def summon_outcome(answer: SummonAnswer | None, expect: dict) -> str:
    """What Beacon did with a summon. If an answer fails a check, the outcome says why.
    "answered" needs the documents, the word limit, and one of the expected refs.
    "declined" must not give a dollar amount."""
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
    """The Beacon turn that mark_spoken() recorded for this flag."""
    turn_id = next(event.turn_id for event in flag.history if event.state == "spoken")
    return next(turn.text for turn in call.state.turns if turn.id == turn_id)


def score(line: dict, call: Call) -> dict:
    """Score one planted moment. A flag matches the moment if its evidence cites the moment's
    turn, or the counselor turn just before it."""
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
        flags.sort(key=lambda f: f.trigger != expect["trigger"])  # the expected trigger first
        outcome, trigger = (flags[0].state, flags[0].trigger) if flags else ("none", "")
        mentions = expect.get("mentions")
        if outcome == "spoken" and mentions and not any(m in spoken_line(flags[0], call).lower() for m in mentions):
            outcome = "spoken, off topic"  # Beacon spoke, but its line has none of the keywords

    if "quiet" in expected:
        # "quiet" passes with any outcome except spoken. With flag_required, a flag must exist too.
        passed = not outcome.startswith("spoken") and not (expect.get("flag_required") and outcome == "none")
    else:
        passed = outcome in expected
    if expect["trigger"] and outcome != "none" and trigger != expect["trigger"]:
        passed = False  # the correct outcome, but for the wrong reason
    return {"line": line, "window": window, "trigger": trigger, "outcome": outcome, "passed": passed}


def clean_call_check(call: Call) -> tuple[int, int, bool]:
    """For a clean call: the number of flags (dropped flags not included), the number of spoken
    lines, and whether the call passes."""
    flags = [f for f in call.state.flags if f.state != "dropped"]
    spoken = [f for f in flags if f.state == "spoken"]
    return len(flags), len(spoken), len(flags) <= 1 and not spoken


# ---------------------------------------------------------------- report


def summarize(name: str, runs: list[tuple[list[dict], Call]]) -> str:
    """One cell of the summary table: how often the script met its targets."""
    parts = []
    scored = [[score(line, call) for line in script if "expect" in line] for script, call in runs]
    if scored[0]:
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


def transcript_block(call: Call, title: str) -> list[str]:
    lines = [f"<details><summary>{title}: transcript and decisions</summary>", "", "```"]
    for turn in call.state.turns:
        pause = f" ({turn.gap_ms / 1000:.1f}s pause)" if (turn.gap_ms or 0) >= config.NOTABLE_GAP_MS else ""
        lines.append(f"{turn.id} {turn.role.upper()}{pause}: {turn.text}")
    lines += ["", *call.decisions, "```", "", "</details>", ""]
    return lines


def script_section(name: str, runs: list[tuple[list[dict], Call]]) -> list[str]:
    out = [f"## {name}", ""]
    planted = [line for line in runs[0][0] if "expect" in line]
    scored = [[score(line, call) for line in script if "expect" in line] for script, call in runs]
    if planted:
        header = " | ".join(f"Run {i + 1}" for i in range(len(runs)))
        out += [f"| Line | Expected | {header} | Passed |", "|---|---|" + "---|" * len(runs) + "---|"]
        for i, line in enumerate(planted):
            expect = line["expect"]
            outcomes = " or ".join(expected_outcomes(expect))
            if expect.get("flag_required"):
                outcomes += " (a flag must exist)"
            cells = []
            for run in scored:
                s = run[i]
                cell = s["outcome"] if s["trigger"] in ("", "SUMMON") else f"{s['trigger']} → {s['outcome']}"
                cells.append(cell if s["passed"] else f"**{cell} (FAIL)**")
            passes = sum(run[i]["passed"] for run in scored)
            expected = f"{expect['trigger'] or 'no flag'} → {outcomes}"
            out.append(f"| {line['id']} ({line['turn_id']}) | {expected} | {' | '.join(cells)} | {passes}/{len(runs)} |")
        out.append("")

    for number, ((_, call), run) in enumerate(zip(runs, scored), start=1):
        title = f"Run {number}"
        if name in CLEAN_SCRIPTS:
            flags, spoken, ok = clean_call_check(call)
            out += [f"**{title}: flags {flags} (target ≤1) · spoken {spoken} (target 0) → {'PASS' if ok else 'FAIL'}**", ""]
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
                source = "yes" if answer.answered_from_documents else "no"
                refs = ", ".join(answer.doc_refs) or "—"
                out.append(f"| {turn_id} | {len(answer.answer.split())} | {source} | {refs} | {answer.answer} |")
            out.append("")
        out += transcript_block(call, title)
    return out


def latency_line(label: str, values: list[int]) -> str:
    if not values:
        return f"- {label}: no network calls"
    return f"- {label} over {len(values)} network calls: mean {statistics.mean(values):.0f} ms, max {max(values)} ms"


def write_report(results: dict[str, list[tuple[list[dict], Call]]], llm: GeminiLLM, cache: bool, stopped: str) -> None:
    runs = len(next(iter(results.values())))
    calls = [call for script_runs in results.values() for _, call in script_runs]
    errors = [error for call in calls for error in call.errors]
    header = (
        f"{datetime.now():%Y-%m-%d %H:%M} · model `{config.GEMINI_MODEL}` · thinking `{config.GEMINI_THINKING_LEVEL}`"
        f" · cache {'on' if cache else 'off'} · {runs} run(s) per script"
    )
    if errors:
        header += f" · **{len(errors)} LLM requests failed, so these outcomes are not meaningful**"
    if stopped:
        header += f" · {stopped}"

    out = ["# Eval results", "", header, "", "| Script | Result |", "|---|---|"]
    out += [f"| {name} | {summarize(name, script_runs)} |" for name, script_runs in results.items()]
    out.append("")
    for name, script_runs in results.items():
        out += script_section(name, script_runs)
    never_sent = llm.requests - llm.cache_hits - llm.api_calls  # for example, no API key and not in the cache
    out += [
        "## LLM calls",
        "",
        f"- Requests: {llm.requests} (network: {llm.api_calls}, from cache: {llm.cache_hits}, never sent: {never_sent})",
        latency_line("Analyzer latency", [ms for call in calls for ms in call.latencies]),
        latency_line("Summon latency", [ms for call in calls for ms in call.summon_latencies]),
        f"- Errors: {len(errors)}",
        *[f"  - {e}" for e in errors],
        "",
    ]
    RESULTS_FILE.write_text("\n".join(out), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", action="store_true", help="use and keep LLM responses in .cache/")
    parser.add_argument("--script", choices=SCRIPTS, action="append", help="run only this script (you can repeat it)")
    parser.add_argument("--runs", type=int, default=1, help="run each script this many times")
    args = parser.parse_args()
    if not config.GEMINI_API_KEY and not args.cache:
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (see .env.example), or use --cache to replay cached responses.")
    llm = GeminiLLM(cache=args.cache)
    results: dict[str, list[tuple[list[dict], Call]]] = {}
    stopped = ""
    try:
        for name in args.script or SCRIPTS:
            for run in range(1, args.runs + 1):
                print(f"{name}, run {run} of {args.runs}", flush=True)
                results.setdefault(name, []).append(await run_script(llm, name))
    except QuotaExhausted as exc:
        stopped = f"**Stopped early: the daily LLM quota ran out during {name}, run {run}.** {exc}"
        print(stopped)
    if not results:
        sys.exit("No run finished, so there is nothing to report.")
    write_report(results, llm, args.cache, stopped)
    print(f"Wrote {RESULTS_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())
