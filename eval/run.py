"""Offline eval: runs the real analyzer and policy over the demo and control scripts, turn by turn
(text only), scores each planted moment, and writes eval_results.md.

Usage: python -m eval.run [--cache] [--script demo_call]
--cache stores LLM responses in .cache/ by prompt hash, so tuning the policy costs no quota."""

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime

from backend.app import analyzer, config, policy, wakeword
from backend.app.llm import GeminiLLM
from backend.app.models import LogEntry, RoomState, Turn

SCRIPTS = ["demo_call", "control_call"]
RESULTS_FILE = config.ROOT / "eval_results.md"
MS_PER_WORD = 400  # ~150 words a minute; advances the virtual clock so cooldowns behave like a call
START_MS = 1_000_000_000


class Call:
    """A text-only call driven by a script, with a virtual clock instead of wall time."""

    def __init__(self):
        self.state = RoomState()
        self.clock = START_MS
        self.latencies: list[int] = []  # analyzer network calls (not the cache, not the rate-limit wait)
        self.analyzed_ok = 0  # transcript length covered by the last successful analysis, as in rooms.py
        self.errors: list[str] = []
        self.summons: dict[str, str] = {}  # turn id -> Beacon's answer
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
            try:
                answer = await analyzer.answer_summon(llm, call.state, turn)
                call.summons[turn.id] = answer.answer if answer.answered_from_documents else ""
                call.speak(answer.answer)
            except Exception as exc:
                call.errors.append(f"summon {turn.id}: {exc}")
        if not policy.should_analyze(call.state, call.analyzed_ok):
            call.analyzed_ok = len(call.state.turns)
            continue
        timed_before = len(llm.latencies_ms)
        result = await analyzer.analyze(llm, call.state)
        call.latencies += llm.latencies_ms[timed_before:]
        if result.error:
            call.errors.append(f"analysis {turn.id}: {result.error}")
            continue
        call.analyzed_ok = result.turn_count
        call.record(policy.after_analysis(call.state, result.output, result.turn_count, call.clock))
    call.record(policy.end_of_call(call.state, call.clock))
    return script, call


def score(line: dict, call: Call) -> dict:
    """Match a planted moment to flags citing its parent turn or the counselor turn just before."""
    expect = line["expect"]
    turns = call.state.turns
    index = next(i for i, t in enumerate(turns) if t.id == line["turn_id"])
    window = {line["turn_id"]}
    previous = next((t for t in reversed(turns[:index]) if t.role != "beacon"), None)
    if previous and previous.role == "counselor":
        window.add(previous.id)
    if expect["trigger"] == "SUMMON":
        outcome, trigger = ("answered" if call.summons.get(line["turn_id"]) else "none"), "SUMMON"
    else:
        flags = [f for f in call.state.flags if f.state != "dropped" and window & set(f.evidence_turn_ids)]
        flags.sort(key=lambda f: f.trigger != expect["trigger"])  # prefer the expected trigger
        outcome, trigger = (flags[0].state, flags[0].trigger) if flags else ("none", "")
    # "recap" means recap at most: anything except interrupting aloud passes.
    passed = outcome != "spoken" if expect["outcome"] == "recap" else outcome == expect["outcome"]
    return {"line": line, "window": window, "trigger": trigger, "outcome": outcome, "passed": passed}


def transcript_block(call: Call) -> list[str]:
    lines = ["<details><summary>Transcript and decisions</summary>", "", "```"]
    for turn in call.state.turns:
        pause = f" ({turn.gap_ms / 1000:.1f}s pause)" if (turn.gap_ms or 0) >= config.NOTABLE_GAP_MS else ""
        lines.append(f"{turn.id} {turn.role.upper()}{pause}: {turn.text}")
    lines += ["", *call.decisions, "```", "", "</details>", ""]
    return lines


def report(results: dict[str, tuple[list[dict], Call]], llm: GeminiLLM, cache: bool) -> str:
    out = [
        "# Eval results",
        "",
        f"{datetime.now():%Y-%m-%d %H:%M} · model `{config.GEMINI_MODEL}` · thinking `{config.GEMINI_THINKING_LEVEL}`"
        f" · cache {'on' if cache else 'off'}",
        "",
    ]
    errors = [error for _, call in results.values() for error in call.errors]
    if errors:
        warning = f"> **{len(errors)} LLM requests failed, so the outcomes below are not meaningful.**"
        out += [f"{warning} See the list at the end.", ""]
    all_latencies = []
    for name, (script, call) in results.items():
        all_latencies += call.latencies
        out += [f"## {name}", ""]
        planted = [line for line in script if "expect" in line]
        scored = [score(line, call) for line in planted]
        matched = set().union(*(s["window"] for s in scored)) if scored else set()
        if scored:
            out += ["| Line | Expected | Detected trigger | Outcome | Pass |", "|---|---|---|---|---|"]
            for s in scored:
                expect = s["line"]["expect"]
                expected = f"{expect['trigger'] or 'no flag'} → {expect['outcome']}"
                out.append(
                    f"| {s['line']['id']} ({s['line']['turn_id']}) | {expected} | {s['trigger'] or '—'} "
                    f"| {s['outcome']} | {'PASS' if s['passed'] else 'FAIL'} |"
                )
            out += ["", f"**{sum(s['passed'] for s in scored)}/{len(scored)} planted moments pass.**", ""]
        flags = [f for f in call.state.flags if f.state != "dropped"]
        unplanned = [f for f in flags if not matched & set(f.evidence_turn_ids)]
        spoken = [f for f in flags if f.state == "spoken"]
        if name == "control_call":
            ok = len(flags) <= 1 and not spoken
            out.append(f"**Flags: {len(flags)} (target ≤1) · spoken: {len(spoken)} (target 0) → {'PASS' if ok else 'FAIL'}**")
            out.append("")
        if unplanned:
            out += ["Flags not matched to a planted moment:", ""]
            out += [f"- {f.id} {f.trigger} `{f.issue_key}` → {f.state}, evidence {f.evidence_turn_ids}" for f in unplanned]
            out.append("")
        dropped = [f for f in call.state.flags if f.state == "dropped"]
        if dropped:
            out += ["Dropped by the evidence gate:", ""]
            out += [f"- {f.id} `{f.issue_key}`: {f.history[0].reason}" for f in dropped]
            out.append("")
        out += transcript_block(call)
    out += ["## LLM calls", ""]
    failed_early = llm.requests - llm.cache_hits - llm.api_calls  # e.g. no API key and not in the cache
    out.append(f"- Requests: {llm.requests} (network: {llm.api_calls}, from cache: {llm.cache_hits}, never sent: {failed_early})")
    if all_latencies:
        out.append(f"- Analyzer latency over {len(all_latencies)} network calls: mean {statistics.mean(all_latencies):.0f} ms, max {max(all_latencies)} ms")
    out.append(f"- Errors: {len(errors)}")
    out += [f"  - {e}" for e in errors]
    return "\n".join(out) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", action="store_true", help="reuse and store LLM responses in .cache/")
    parser.add_argument("--script", choices=SCRIPTS, help="run one script instead of both")
    args = parser.parse_args()
    if not config.GEMINI_API_KEY and not args.cache:
        sys.exit("GEMINI_API_KEY is not set. Add it to .env (see .env.example), or pass --cache to replay cached responses.")
    llm = GeminiLLM(cache=args.cache)
    results = {}
    for name in [args.script] if args.script else SCRIPTS:
        results[name] = await run_script(llm, name)
    RESULTS_FILE.write_text(report(results, llm, args.cache), encoding="utf-8")
    print(f"Wrote {RESULTS_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())
