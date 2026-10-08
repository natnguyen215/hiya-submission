# CLAUDE.md: orientation for an AI agent opening this repo cold

Beacon is a prototype for a voice AI challenge (Hiya, "Real-Time Assistance" track). It listens
to a financial aid call between a counselor (Alex) and a first-generation parent (Maria), privately
nudges the counselor when the parent seems to have misunderstood, and only if the counselor moves
on does it ask aloud, on the family's behalf. After the call it writes a plain-language Family
Recap. Everything is fictional (people, school, award letter). Out of scope by design: telephony,
real data, multilingual, auth, databases, deployment, non-Gemini LLMs.

The author will walk through, debug and extend this code live in a review session. Keep changes
explainable: plain functions and pydantic models, few files, a purpose docstring at the top of
every file, comments that say *why*, no dead code, no new dependencies without a reason in
DECISIONS.md, and LLM prompts in `backend/prompts/*.txt`, never in Python strings.

## Read in this order

1. `README.md`: what it does, how to run it, the architecture diagram.
2. `backend/app/policy.py`: every decision Beacon makes. Start at `after_analysis()`.
3. `backend/app/rooms.py`: how decisions are carried out (WebSocket rooms, analysis loop, speech
   queue, timing). Start at `add_turn()`.
4. `backend/app/analyzer.py` + `backend/prompts/analyzer.txt`: what the LLM is asked to perceive.
5. `DECISIONS.md`: why things are the way they are, including deliberate deviations from the
   original brief and the tuning log. Check it before "fixing" something that looks odd.

## The design rule: the LLM perceives, Python decides

Gemini never makes Beacon speak. `analyzer.analyze()` returns an `AnalysisResult` whose `.output`
is the validated JSON (`AnalyzerOutput` in `models.py`): candidate flags with exact quotes, which
open flags the counselor resolved, which parent questions were asked and answered. It never
raises; on failure `.output` is empty and `.error` is set. `policy.after_analysis()` decides what to do with it:
evidence gate, dedupe by `issue_key`, severity (`recap` flags never interrupt), the escalation
ladder (nudge → resolved / spoken / recap / dismissed), staleness, cooldown, and code-counted
unanswered questions. It returns actions (`SendCard`, `UpdateFlag`, `SpeakLine`, `LogEntry`) that
`rooms.execute()` carries out. `policy.py` does no I/O, reads no clock (callers pass `now_ms`) and
calls no LLM, so it is unit-testable.

The counselor can overrule Beacon from the nudge card: "Not an issue" (flag → `dismissed`, never
spoken) and "I'll clarify" (stays `nudged`, one extra counselor turn, once per flag). The click
arrives as a `flag_action` message; `policy.counselor_action()` validates and applies it, and
`rooms.flag_action()` carries out the result.

Two honest caveats. "Resolved" is the LLM's judgment: code only checks the flag is still
`nudged`, not which turn resolved it. And a few speech mechanics live in `rooms.py`: the speaker
drops a queued line whose flag is no longer `nudged`, `enqueue_speech()` dedupes by flag id,
`flag_action()` withdraws a flag's queued line when the counselor clicks a card button, and
summon answers share the queue but skip the ladder and cooldown and are never withdrawn.

## Life of a turn

The role is fixed per WebSocket by its `join` message; a `turn` carries no role. A `sim_turn`
(from the observer's script runner) names its persona and carries the script's `gap_ms`.

```
rooms.handle() ── turn / sim_turn ──▶ rooms.add_turn():
    store Turn (ids t1, t2, … in transcript order, Beacon's turns included)
    wake word? → count it in speech_pending, start _answer_summon task   (before any await, on purpose)
    write logs/*.jsonl, broadcast turn_added, withdraw queued interjections, send status
    request_analysis(): one _analysis_loop per room; a turn arriving mid-analysis sets analysis_dirty → one more pass
_analysis_loop:
    policy.should_analyze()? no  → log "skipped LLM", done
                             yes → analyzer.analyze()
                                   error  → status "analyzer unavailable", NO policy run, nothing retried until the next turn
                                   ok     → policy.after_analysis() → rooms.execute()
execute: SendCard/UpdateFlag → flag_card/flag_updated to the observer, and to the counselor only if the flag was ever nudged
         SpeakLine → enqueue_speech() → _speaker_loop waits until nobody holds push-to-talk and PAUSE_BEFORE_SPEAK_MS of quiet
         → _speak(): Beacon Turn + policy.mark_spoken() (state only, before any await; starts the cooldown)
                     → broadcast turn_added, beacon_say, status → flag_updated → wait for playback
end_call: cancels in-flight analysis and queued speech → policy.end_of_call() (nudged → recap)
          → analyzer.generate_recap() → add_missing_follow_ups() → unverified_numbers() → recap_ready

rooms.handle() ── flag_action {flag_id, action: "dismiss" | "will_clarify"} ──▶ rooms.flag_action():
    not the counselor? → log "ignored …", done
    policy.counselor_action(): flag unknown / not nudged / second "will_clarify" → log "ignored …", done
        dismiss      → state dismissed, counselor_action "dismissed"
        will_clarify → ladder_start_turn = newest turn, grace_turns = CLARIFY_GRACE_COUNSELOR_TURNS,
                       counselor_action "will_clarify", history entry "counselor: will clarify"
    withdraw that flag's queued line (before any await) → flag_updated to observer + counselor
    → write {"type": "counselor_feedback", action, flag, turn_id} to logs/*.jsonl
```

**The ladder has no timer.** It only runs inside a successful analysis, and analyses only start
when a human turn arrives. An expired cooldown, a recovered LLM or a failed parent-turn analysis is
only picked up at the next turn (by then the flag may be stale).

**Playback:** the server sets `speaking_turn_id`, broadcasts `beacon_say`, and waits for the first
`beacon_playback_done` with that turn id, or a fallback of 2 s + 800 ms per word. Who acks: any
tab with "Play Beacon audio here" on (default on only for the counselor; stored per role in
localStorage), except that call tabs stay silent while the call is simulated; and the observer tab
that is running a simulation, always (instantly when "Text only" is ticked, otherwise after playing
the line). `speech.speak()` resolves even on error, so a tab nobody has clicked in (Chrome blocks
its audio) acks instantly.

## File map

| Path | Purpose |
|---|---|
| `backend/app/config.py` | every tunable, each overridable by an env var of the same name (or `.env`) |
| `backend/app/models.py` | the shared data shapes: state, LLM output schemas, WebSocket messages (client messages form the `ClientMessage` union; there is no server-message union in Python). Other shapes live beside their code: `DocLine` in docs.py, `AnalysisResult` in analyzer.py, `Trigger` in triggers.py, the actions in policy.py, `Room`/`Speech` in rooms.py |
| `web/src/types.ts` | TypeScript mirror of `models.py`, including the `ServerMessage` union. **Change both together.** |
| `backend/app/triggers.py` | the one list of triggers; LLM ones are rendered into the prompt word for word |
| `backend/app/policy.py` | pure decision logic |
| `backend/app/rooms.py` | runtime: rooms, broadcasting, analysis loop, speech queue, decision log, recap |
| `backend/app/analyzer.py` | prompt building (`_fill` replaces `{{PLACEHOLDERS}}`), LLM calls with one retry on invalid output, recap checks |
| `backend/app/llm.py` | `GeminiLLM` (4 s throttle, timeout, 429 backoff, optional cache) and `FakeLLM` for tests |
| `backend/app/wakeword.py` | fuzzy "Beacon" detection + "is this a question?" |
| `backend/app/docs.py` | loads `data/award_letter.md` and `data/glossary.md`; line ids like `L14`, `G9` |
| `backend/app/main.py` | FastAPI: `/api/documents`, `/api/scripts/{name}`, `/ws`, serves `web/dist` |
| `backend/prompts/` | `analyzer.txt`, `summon.txt`, `recap.txt` |
| `backend/tests/` | `test_policy.py` (most behavior, including the counselor's card buttons; `helpers.py` builds states and fake outputs), `test_smoke.py` (three WebSocket clients + FakeLLM), `test_rooms.py` (turn-taking and speech-queue regressions), `test_analyzer.py` (prompt rendering; prompt examples must not reuse script lines), `test_wakeword.py`, `test_scripts.py` (every script well-formed and registered in the eval) |
| `eval/run.py` | offline eval over the scripts in its `SCRIPTS` list (add a new script there and to `SCRIPTS` in `ObserverView.tsx`; `CLEAN_SCRIPTS` get the "≤1 flag, 0 spoken" target), text only, virtual clock, no recap, `--runs N` repeats each script → `eval_results.md` |
| `data/scripts/` | `demo_call.json` (planted moments, each with an `expect`), `demo_call_stt_noise.json` (the same call as Chrome might transcribe it), `control_call.json` and `adversarial_clean.json` (clean calls), `live_regressions.json` (failures seen in live testing), `summon_checks.json` (questions to Beacon; `expect.outcome` "declined" = not in the documents) |
| `web/src/` | React: `useRoom.ts` (WebSocket hook), `CallView.tsx`, `ObserverView.tsx`, `Recap.tsx`, `components.tsx`, `speech.ts` (push-to-talk + TTS), `simulate.ts` (script runner) |
| `tasks.py` / `Makefile` | task runner; the Makefile only calls `tasks.py` |
| `PLAN.md`, `DECISIONS.md`, `WRITEUP.md`, `DEMO.md` | plan + milestone checklist; decision and tuning log; challenge write-up (its "AI tools used" section is a placeholder for the author); demo video run-of-show |

## Commands

- `python tasks.py install | test | build | run | dev | eval` (on macOS/Linux also `make <task>`;
  pass eval flags as `make eval ARGS=--cache`). `tasks.py` always uses `./.venv`, so run `install`
  first (it also needs Node 20.19+ on the 20.x line, or 22.12+, for `npm install` in `web/`).
- Without the task runner: `pip install -r requirements.txt`, then from the repo root
  `python -m pytest -q` (pytest.ini sets `pythonpath`) and `python -m eval.run [--cache] [--script demo_call] [--runs 3]`.
- `run` serves everything at http://localhost:8000: `/call?room=demo&role=counselor`,
  `/call?room=demo&role=parent`, `/observer?room=demo` (needs `build` first). `dev` runs uvicorn
  with reload on :8000 plus Vite on :5173.
- The eval needs `GEMINI_API_KEY` in `.env` (copy `.env.example`). `--cache` replays responses from
  `.cache/` (not shipped); any request that fails puts a warning at the top of `eval_results.md`.
- On Windows, set `PYTHONIOENCODING=utf-8` before printing decision-log text (it contains "→").
- Tests: all pass, no network, about 2 s. The frontend has no automated tests; it was checked by
  hand in Chromium during the build.

## Status

The uncached Gemini eval after the Beacon rename passed **8/8 planted moments** on 2026-10-07
(`gemini-3.5-flash-lite`, thinking `low`), with 36 network requests and no API errors. The control
call passed with one private nudge that resolved and no spoken interjections. See `eval_results.md`
and DECISIONS.md's "Tuning log" for details and the earlier stand-in checks. Live Chrome testing
revealed the old name's transcription problem; the renamed wake word still needs the README's
manual microphone/playback check. The stretch "hybrid demo mode" was not built.

## Gotchas

- **Two analysis counters:** `RoomStatus.analyzed_turn_count` advances even after a failed
  analysis (so the simulation runner never stalls; the observer may show "Analyzed N / N" while
  analyses are failing); `Room.analyzed_ok` advances only on success or skip and feeds
  `should_analyze()`, so a parent turn whose analysis failed is re-analyzed with the next turn.
- **`created_at_turn`** is the newest turn when the card appeared, possibly one the analyzer hadn't
  seen. **`ladder_start_turn`** starts equal to it and is what the ladder counts from (counselor
  turns for "due", human turns for "stale"); "I'll clarify" moves it to the newest turn and sets
  `grace_turns`, so the flag is due after `ESCALATE_AFTER_COUNSELOR_TURNS + grace_turns` counselor
  turns. The "not due yet" case logs nothing. The observer's flag details show "card shown after
  tN", plus "counting from tM" once the two differ.
- **`dismissed` is not `dropped`:** a dismissed flag still blocks its `issue_key`
  (`_active_flag_with_key`), is still listed for the analyzer (`state=dismissed`), and is still
  sent to the counselor. It is left out of the recap's open issues, but an unanswered parent
  question is listed from `parent_questions`, so it reaches the recap even if its card was
  dismissed.
- **Speaking is deferred** if any human turn arrived during the LLM call; the rerun decides.
- **Evidence rule lives on the trigger** (`Trigger.needs_parent_evidence`, default True). It drives
  both the evidence gate and `should_analyze()`'s skip after counselor turns.
- **Parent questions are quoted verbatim** by the LLM and checked with `policy.quote_in_text()`,
  because Beacon may read them aloud.
- **`rooms.handle()` silently ignores** an observer `turn`, `ptt_start` while someone else holds the
  floor or the call isn't live, `ptt_stop` from a non-holder, and a stale `beacon_playback_done`.
  A `flag_action` that can't be applied (wrong role, unknown flag, flag not `nudged`, second "I'll
  clarify") changes nothing either, but leaves an "ignored …" entry in the Decision Log.
  The only errors sent back are "Start the call first." (a `turn` or `sim_turn` before the call is
  live) and "bad message: …" (from `main.py`, for a message after the join that doesn't parse). A
  first message that isn't a valid `join` gets no error; the socket is closed with code 1008.
- **The parent** never receives flags or the decision log. **The counselor** receives flags that
  were nudged at some point, and never the decision log (`rooms._state_for`, `_counselor_sees`).
- **Card buttons blur themselves** after a click (`CardButton` in `components.tsx`): Space is the
  push-to-talk key, and a button that kept focus could be pressed again by it.
- **Frontend:** `useRoom.ts`'s `handle()` routes `error` and `beacon_say` as events before
  `apply()` folds state messages; there is no React StrictMode on purpose (its double mount opens a
  phantom WebSocket join).
- **Tests:** enter `TestClient` as a context manager so all WebSockets share one event loop (see
  `test_smoke.py`, whose first test is the "so it's covered" → housing → `beacon_say` scenario and a
  good template for reproducing bugs). Swap the LLM with
  `monkeypatch.setattr(rooms, "llm", FakeLLM(fn))`; key fake replies on transcript text, since every
  analyzer prompt also contains the full documents.
- Text-only simulations compress time (the cooldown is wall-clock), and the wake word's auxiliary
  rule ("can you…" works, "can help…" doesn't): both explained in DECISIONS.md.

## Common changes

- **Tune a threshold:** edit `config.py` (or set the env var) and log it in DECISIONS.md's "Tuned
  defaults" table.
- **Add an LLM-detected trigger:** add a `Trigger` to `triggers.py` with `detected_by="llm"` (plus
  name, description, positive and negative examples, and `needs_parent_evidence`). No `models.py`/`types.ts`/frontend change is needed:
  trigger names are plain strings. Check existing descriptions for overlap (dedupe compares
  `issue_key` only, so two triggers can flag one moment twice). Trigger examples go into the prompt
  verbatim, so like the few-shot examples in `analyzer.txt` they must not reuse demo-script content.
  Consider a few-shot example in `analyzer.txt`. Add a test in `test_policy.py`
  (`helpers.new_flag(..., trigger=...)`), check `data/scripts/*.json` `expect.trigger` labels, and
  note it in DECISIONS.md.
- **Add a code-detected trigger:** add the `Trigger` entry for documentation, then the detection in
  `policy.py` (`_raise_unanswered()` is the model).
- **Add a WebSocket message:** a pydantic model in `models.py` (client messages also go in the
  `ClientMessage` union), the matching type in `web/src/types.ts`, a `case` in `rooms.handle()` or
  a broadcast, and handling in `useRoom.ts` (`apply()` for state, `handle()` for events).
- **Change what the LLM sees:** edit `backend/prompts/*.txt`; placeholders are `{{NAME}}`, filled
  in `analyzer.py`.

## Debugging "why didn't Beacon speak?"

A card in the counselor's panel proves the flag was nudged, which rules out the evidence gate,
recap severity and stale-at-creation. Then read the observer's Decision Log (each analysis has its
raw output under "data"; the same entries are in `logs/<room>-<time>.jsonl`, which also holds one
`counselor_feedback` record per accepted card click: `action`, the full `flag`, `turn_id`):

| Log text | Meaning | Emitted at |
|---|---|---|
| `→ resolved: the counselor clarified it` | the LLM judged it resolved | `policy.after_analysis` |
| `due, deferred: newer turns not analyzed yet` | a turn arrived during the LLM call | `policy._run_ladder` |
| `due, waiting: cooldown Ns left` | 20 s cooldown since the last interjection | `policy._run_ladder` |
| `due, waiting: one interjection at a time` | several flags were due at once; the oldest was queued, the rest wait (and may go stale) | `policy._run_ladder` |
| `→ recap: stale: …` | too many turns passed before it could speak | `policy._run_ladder` |
| `→ dismissed: counselor: not an issue` | dismissed by the counselor ("Not an issue"); never spoken, and the issue is not raised again | `policy.counselor_action` |
| `counselor will clarify; waiting N counselor turn(s) before speaking` | the counselor clicked "I'll clarify": the count restarted at that turn, with one extra counselor turn | `policy.counselor_action` |
| `ignored counselor action …` / `ignored … only the counselor can act on a card` | a late or invalid card click; nothing changed | `policy.counselor_action` / `rooms.flag_action` |
| `analysis through … failed …` | LLM error; the ladder didn't run | `rooms._analysis_loop` |
| `withdrew queued line …` | a human turn arrived before the pause, or the counselor clicked a card button first | `rooms.add_turn` / `rooms.flag_action` |
| `skipped line for …` | the flag changed state while queued | `rooms._speaker_loop` |
| `no tab reported playback …` | it spoke, but no tab played or acked the audio | `rooms._speak` |
| (no ladder line after an analysis) | not due yet: too few counselor turns after "card shown after tN" (or after "counting from tM" once the counselor clicked "I'll clarify") | `policy._run_ladder` |

Also check the "Speech pending" chip: a line stuck in the queue usually means someone is still
holding push-to-talk (the observer doesn't show who).
