# CLAUDE.md: a guide to this repo for an AI agent

Beacon is a prototype for a voice AI challenge (Hiya, "Real-Time Assistance" track). It listens to
a financial aid call between a counselor (Alex) and a first-generation parent (Maria). When the
parent seems to misunderstand, Beacon shows the counselor a private card. If the counselor moves
on, Beacon asks aloud for the family. After the call, it writes a plain-language Family Recap.
All people, the school and the award letter are fictional. Not in scope: telephony, real data,
more languages, authentication, databases, deployment, other LLMs than Gemini.

The author must be able to explain, debug and extend this code alone, also in a live review.
Rules for changes:
- Use plain functions and pydantic models. Keep the number of files small.
- Each file starts with a docstring that says what it is for.
- Comments say *why*. Write them in simple English: short sentences, one idea in each sentence,
  active verbs (about 80% of ASD-STE100, Simplified Technical English).
- No dead code. No new dependency without a reason in DECISIONS.md.
- LLM prompts are in `backend/prompts/*.txt`, never in Python strings.

## Read in this order

1. `README.md`: what Beacon does, how to run it, the architecture.
2. `backend/app/policy.py`: all decisions. Start at `after_analysis()`.
3. `backend/app/rooms.py`: how the server does the decisions (rooms, analysis loop, speech queue,
   timing). Start at `add_turn()`.
4. `backend/app/analyzer.py` and `backend/prompts/analyzer.txt`: what the LLM must find.
5. `DECISIONS.md`: why the code is as it is, and the tuning log. Read it before you "fix"
   something that looks strange.

## The design rule: the LLM finds, Python decides

Gemini never makes Beacon speak. `analyzer.analyze()` returns an `AnalysisResult`. Its `.output`
is the checked JSON (`AnalyzerOutput` in `models.py`): new flags with exact quotes, the open
flags that the counselor resolved, and the parent questions that were asked and answered.
`analyze()` never raises an exception. If the LLM fails, `.output` is empty and `.error` has the
reason.

`policy.after_analysis()` decides what to do with the output:
- **Evidence gate:** each quote must be in a cited turn, and a parent turn must be cited.
- **Dedupe:** one flag per `issue_key` while a flag with that key is nudged, spoken, recap or
  dismissed (`resolved` and `dropped` free the key). Also one flag per moment (same trigger and
  same parent turn).
- **Severity:** a `recap` flag never interrupts.
- **Escalation ladder:** nudged → resolved, spoken, recap or dismissed. Also staleness and the
  cooldown.
- **Unanswered questions:** code counts the counselor turns after a question. A later parent
  turn can close the parent's own question ("withdrew").

It returns actions (`SendCard`, `UpdateFlag`, `SpeakLine`, `LogEntry`). `rooms.execute()` does
them. `policy.py` does no I/O, reads no clock (callers give `now_ms`) and calls no LLM, so tests
can call it directly.

The counselor can overrule Beacon on a card. "Not an issue" makes the flag `dismissed`: Beacon
never speaks about it. "I'll clarify" keeps the flag `nudged` and gives one more counselor turn,
once per flag. The click arrives as a `flag_action` message. `policy.counselor_action()` checks
and applies it, and `rooms.flag_action()` does the result.

Two limits to know:
- "Resolved" is the LLM's decision. Code checks only that the flag is still `nudged` and that a
  counselor turn comes after its evidence.
- Some speech rules are in `rooms.py`, not in `policy.py`. The speaker skips a line if its flag
  is no longer `nudged`. `enqueue_speech()` keeps one line per flag. `flag_action()` removes a
  flag's line from the queue after a click. Summon answers use the same queue, but they skip the
  ladder and the cooldown, and a new turn does not remove them.

## Life of a turn

The `join` message sets the role of a WebSocket. A `turn` message has no role. A `sim_turn` (from
the observer's script runner) gives its role and the script's `gap_ms`.

```
rooms.handle() ── turn / sim_turn ──▶ rooms.add_turn():
    _new_turn(): store the Turn (ids t1, t2, … in transcript order, Beacon's turns too) and write it to logs/*.jsonl
                 (a voice turn's gap_ms does not include PTT_REACTION_MS)
    wake word? → count it in speech_pending, start the _answer_summon task   (before the first await, on purpose)
    broadcast turn_added, remove flag lines from the speech queue, send status
    request_analysis(): one _analysis_loop per room. A turn during an analysis sets analysis_dirty → one more pass.
_analysis_loop:
    policy.should_analyze()? no  → log "skipped LLM", done
                             yes → analyzer.analyze()
                                   error → status "analyzer unavailable". No policy run. The next turn tries again.
                                   ok    → policy.after_analysis() → rooms.execute()
execute: SendCard/UpdateFlag → flag_card/flag_updated to the observer, and to the counselor if the flag was nudged at some time
         SpeakLine → enqueue_speech() → _speaker_loop waits until nobody holds push-to-talk and PAUSE_BEFORE_SPEAK_MS is quiet
         → _speak(): Beacon Turn + policy.mark_spoken() (state only, before the first await; starts the cooldown)
                     → broadcast turn_added, beacon_say, status → flag_updated → wait for playback
end_call: cancel the analysis and the speech queue → policy.end_of_call() (nudged → recap)
          → analyzer.generate_recap() → add_missing_follow_ups() → unverified_numbers() → recap_ready

rooms.handle() ── flag_action {flag_id, action: "dismiss" | "will_clarify"} ──▶ rooms.flag_action():
    not the counselor? → log "ignored …", done
    policy.counselor_action(): unknown flag / not nudged / second "will_clarify" → log "ignored …", done
        dismiss      → state dismissed, counselor_action "dismissed"
        will_clarify → ladder_start_turn = newest turn, ladder_start_ms = now, grace_turns = CLARIFY_GRACE_COUNSELOR_TURNS,
                       counselor_action "will_clarify", history entry "counselor: will clarify"
    remove that flag's line from the queue (before the first await) → flag_updated to observer + counselor
    → write {"type": "counselor_feedback", action, flag, turn_id} to logs/*.jsonl
```

**The ladder** (`policy._run_ladder`, for each `nudged` flag) counts the counselor turns after
`ladder_start_turn` that *started* at or after `ladder_start_ms`. (A turn that started before the
card appeared does not count.) If there are none, the flag is not due and not stale. The first of
these turns is the counselor's "first chance". More than `STALE_AFTER_TURNS` human turns after it
→ `recap` ("stale"). Else, with `ESCALATE_AFTER_COUNSELOR_TURNS + grace_turns` of these turns,
the flag is due. A due flag waits if a person spoke during the LLM call ("deferred") or during
the cooldown. Only one flag speaks at a time. Else the ladder returns a `SpeakLine`.

**The ladder has no timer.** It runs only after a successful analysis, and an analysis starts
only when a person's turn arrives. So the end of a cooldown, a working LLM again, or a failed
analysis of a parent turn has an effect only at the next turn. By then, the flag can be stale.

**Playback:** the server sets `speaking_turn_id`, broadcasts `beacon_say`, and waits for the first
`beacon_playback_done` with that turn id. If none comes, it continues after 2 s + 800 ms per word.
These tabs send `beacon_playback_done`:
- A tab with "Play Beacon audio here" on. The default is on only for the counselor. The choice is
  kept per role in localStorage. During a simulated call, the call tabs stay silent.
- The observer tab that runs a simulation, always. With "Text only", it reports after the time
  to read the line (`readingTimeMs` in `simulate.ts`), and it waits as long before each script line.
`speech.speak()` resolves also after an error. So a tab that nobody clicked in (Chrome blocks its
audio) reports at once.

## File map

| Path | What it is for |
|---|---|
| `backend/app/config.py` | all settings. An env var with the same name (or a line in `.env`) changes each one. |
| `backend/app/models.py` | the shared data shapes: state, LLM output schemas, WebSocket messages (the client messages form the `ClientMessage` union). Other shapes are next to their code: `DocLine` in docs.py, `AnalysisResult` in analyzer.py, `Trigger` in triggers.py, the actions in policy.py, `Room`/`Speech` in rooms.py. |
| `web/src/types.ts` | the same shapes in TypeScript, and the `ServerMessage` union. **Change it together with `models.py`.** |
| `backend/app/triggers.py` | the list of triggers. LLM triggers go into the prompt word for word. |
| `backend/app/policy.py` | the decision logic (no I/O) |
| `backend/app/rooms.py` | rooms, broadcasts, analysis loop, speech queue, decision log, recap |
| `backend/app/analyzer.py` | prompts (`_fill` fills `{{PLACEHOLDERS}}`), LLM calls with one retry after an invalid reply, recap checks |
| `backend/app/llm.py` | `GeminiLLM` (4 s between calls, timeout, wait after a 429, optional cache) and `FakeLLM` for tests |
| `backend/app/wakeword.py` | finds "Beacon" (fuzzy match) and decides if a question follows |
| `backend/app/docs.py` | reads `data/award_letter.md` and `data/glossary.md`. Line ids such as `L14`, `G9`. |
| `backend/app/main.py` | FastAPI: `/api/documents`, `/api/scripts/{name}`, `/ws`, and `web/dist` |
| `backend/prompts/` | `analyzer.txt`, `summon.txt`, `recap.txt` |
| `backend/tests/` | `test_policy.py` (most behavior; `helpers.py` makes states and fake outputs), `test_smoke.py` (three WebSocket clients and a FakeLLM), `test_rooms.py` (push-to-talk and the speech queue), `test_analyzer.py` (prompts; prompt examples must not copy script lines), `test_wakeword.py`, `test_scripts.py` (each script is valid and in the eval), `test_eval.py` (the eval's scoring) |
| `eval/run.py` | the offline eval over its `SCRIPTS` (add a new script there, and in `SCRIPTS` in `ObserverView.tsx` only if it is for demos; `CLEAN_SCRIPTS` have the target "≤1 flag, 0 spoken"). Text only, virtual clock, no recap. Each turn is analyzed before the next, so it does not test live timing. `--runs N` runs each script N times. The scoring checks what Beacon said: summon refs and word count, `expect.mentions` in the spoken line, and the trigger. |
| `eval/browser_check.js` | an optional Playwright check of the UI on a running server. Its header tells how to install Playwright outside the repo. |
| `data/scripts/` | `demo_short.json` (the demo video: the planted moments in 18 lines), `demo_call.json` (planted moments in a full call, each with an `expect`), `demo_call_stt_noise.json` (the same call as Chrome can write it), `control_call.json` and `adversarial_clean.json` (clean calls), `live_regressions.json` (failures from live tests), `live_patterns.json` (a relapse, a split reply, two misreads in a row, "never mind", a pause after logistics), `summon_checks.json` (questions to Beacon; "declined" = not in the documents). `expect.outcome` can be a list. "quiet" = any state except spoken (`flag_required` also needs a flag). Answered summons have `refs`; spoken moments have `mentions`. |
| `web/src/` | React: `useRoom.ts` (WebSocket hook), `CallView.tsx`, `ObserverView.tsx`, `Recap.tsx`, `components.tsx`, `speech.ts` (push-to-talk and text-to-speech), `simulate.ts` (script runner) |
| `tasks.py` / `Makefile` | the task runner. The Makefile only calls `tasks.py`. |
| `DECISIONS.md`, `WRITEUP.md` | the decision and tuning log; the challenge write-up (the author writes its "AI tools used" part) |

## Commands

- `python tasks.py install | test | build | run | dev | eval` (on macOS/Linux also `make <task>`;
  give eval flags as `make eval ARGS=--cache`). `tasks.py` always uses `./.venv`, so run
  `install` first. It also needs Node 20.19+ (20.x) or 22.12+ for `npm install` in `web/`.
- Without the task runner: `pip install -r requirements.txt`, then from the repo root
  `python -m pytest -q` (pytest.ini sets `pythonpath`) and
  `python -m eval.run [--cache] [--script demo_call] [--runs 3]`.
- `run` serves all pages at http://localhost:8000: `/call?room=demo&role=counselor`,
  `/call?room=demo&role=parent`, `/observer?room=demo`. Run `build` first. `dev` runs uvicorn
  (it reloads) on :8000 and Vite on :5173.
- The eval needs `GEMINI_API_KEY` in `.env` (copy `.env.example`). `--cache` uses the responses
  in `.cache/` (not in git). If a request fails, the top of `eval_results.md` says so.
- On Windows, set `PYTHONIOENCODING=utf-8` before you print decision-log text (it contains "→").
- Tests: all pass, no network, about 2 s. The frontend has no unit tests. `eval/browser_check.js`
  tests it in Chromium (24/24 checks with a fake LLM, 20/20 with Gemini on 2026-10-08).

## Status

Latest Gemini eval: 2026-10-09, after the ladder and grading changes, **1 run** per script,
`gemini-3.5-flash-lite`, thinking `low`, 0 errors. All targets met: demo_call and
demo_call_stt_noise 7/7 moments plus the quiet d23; control 1 private card (resolved at the next
analysis), 0 spoken; adversarial_clean 0 cards; live_regressions 3/3; live_patterns 7/7;
summon_checks 10/10.
`demo_short` (added after this eval) has not run with Gemini yet.

Before the changes (round 2, 2026-10-08, 3 runs per script, 0 errors): demo_call and
demo_call_stt_noise 8/8 in every run; clean calls ≤1 private card and 0 spoken in every run;
live_regressions and summon_checks pass in every run. That round graded summons and spoken lines
by state only. See `eval_results.md` and the "Tuning log" in DECISIONS.md.

A Playwright run with real Gemini passed 20/20 browser checks. The free tier allows **500
requests per day** for this model. A full `--runs 3` eval uses about 300.

Not done: the README's manual microphone and playback check of the renamed wake word. Live timing
is not measured: a fake-LLM test showed that in a fast call, a person often talks before Beacon
gets its pause (see README "Limitations").

## Gotchas

- **Two analysis counters.** `RoomStatus.analyzed_turn_count` moves also after a failed analysis,
  so the simulation runner does not stop. (The observer can show "Analyzed N / N" while analyses
  fail.) `Room.analyzed_ok` moves only after a successful or skipped analysis, and
  `should_analyze()` uses it. So the next turn analyzes a failed parent turn again.
- **`ladder_start_turn` and `ladder_start_ms`** are the newest turn and the time when the card
  appeared. "I'll clarify" moves both to now and sets `grace_turns`. The case "not due yet" logs
  nothing. The observer's flag details show "counting after tN".
- **Turn times come from the browser** (`started_at` is the push-to-talk press or the first key).
  `ladder_start_ms` comes from the server. So the rule "started after the card" needs one clock:
  correct on one machine, not across machines. Tests stamp turns with `helpers.add_turn` (1000 ms
  apart) and give `now(state)`. The smoke tests' `typed()` uses the server clock.
- **`dismissed` is not `dropped`.** A dismissed flag still blocks its `issue_key`
  (`_flag_with_key`), the analyzer still sees it (`state=dismissed`), and the counselor still
  gets it. It is not an open issue in the recap. But an unanswered question comes from
  `parent_questions`, so it is in the recap also if its card was dismissed.
- **Speaking is deferred** if a person spoke during the LLM call. The next analysis decides.
- **The evidence rule is on the trigger** (`Trigger.needs_parent_evidence`, default True). The
  evidence gate and the skip in `should_analyze()` both use it.
- **Parent questions are quoted word for word** by the LLM. `policy.quote_in_text()` checks them,
  because Beacon can read them aloud.
- **`rooms.handle()` ignores these messages with no reply:** a `turn` from the observer,
  `ptt_start` while another person holds push-to-talk or the call is not live, `ptt_stop` from a
  tab that does not hold it, and an old `beacon_playback_done`. A `flag_action` that cannot apply
  (wrong role, unknown flag, flag not `nudged`, second "I'll clarify") changes nothing, but it
  logs "ignored …". The only errors sent back are "Start the call first." (a `turn` or
  `sim_turn` before the call is live) and "bad message: …" (from `main.py`). If the first message
  is not a valid `join`, the socket closes with code 1008.
- **The parent** never gets flags or the decision log. **The counselor** gets the flags that were
  nudged at some time, and never the decision log (`rooms._state_for`, `_counselor_sees`).
- **Card buttons remove their own focus** after a click (`CardButton` in `components.tsx`). Space
  is the push-to-talk key, and it would click a button that has the focus.
- **Frontend:** in `useRoom.ts`, `handle()` sends `error` and `beacon_say` to callbacks, and
  `apply()` puts the other messages into the state. There is no React StrictMode, on purpose: its
  double mount opens an extra WebSocket join.
- **Tests:** use `TestClient` as a context manager, so all WebSockets share one event loop (see
  `test_smoke.py`. Its first test, "so it's covered" → housing → `beacon_say`, is a good start to
  reproduce a bug). Replace the LLM with `monkeypatch.setattr(rooms, "llm", FakeLLM(fn))`. Choose
  the fake reply from the transcript text, because each analyzer prompt also has the full documents.
- Text-only simulations make time shorter (the cooldown uses the real clock). The wake word's rule
  for "can" ("can you…" works, "can help…" does not) is in DECISIONS.md.

## Common changes

- **Tune a setting:** change `config.py` (or set the env var). Add a row to the "Tuned defaults"
  table in DECISIONS.md.
- **Add an LLM trigger:** add a `Trigger` to `triggers.py` with `detected_by="llm"`, a name, a
  description, positive and negative examples, and `needs_parent_evidence`. `models.py`,
  `types.ts` and the frontend do not change: trigger names are plain strings. Make sure that the
  description does not overlap another trigger (two different triggers can flag the same moment).
  The examples go into the prompt word for word, so they must not copy lines from the scripts.
  You can add a few-shot example in `analyzer.txt`. Add a test in `test_policy.py`
  (`helpers.new_flag(..., trigger=...)`), check the `expect.trigger` labels in
  `data/scripts/*.json`, and add a note in DECISIONS.md.
- **Add a code trigger:** add the `Trigger` entry as documentation, then the detection in
  `policy.py` (`_raise_unanswered()` is the example).
- **Add a WebSocket message:** a pydantic model in `models.py` (client messages also go in the
  `ClientMessage` union), the same type in `web/src/types.ts`, a `case` in `rooms.handle()` or a
  broadcast, and the handling in `useRoom.ts` (`apply()` for state, `handle()` for events).
- **Change what the LLM sees:** change `backend/prompts/*.txt`. Placeholders are `{{NAME}}`.
  `analyzer.py` fills them.

## Debugging "why did Beacon not speak?"

If the counselor's panel shows a card, the flag was nudged. So the evidence gate, recap severity
and "stale at creation" are not the cause. Then read the observer's Decision Log. Each analysis
has its raw output under "data". The same entries are in `logs/<room>-<time>.jsonl`, with one
`counselor_feedback` record per accepted card click (`action`, the full `flag`, `turn_id`).

| Log text | Meaning | Written by |
|---|---|---|
| `→ resolved: the counselor clarified it` | the LLM decided that it is resolved | `policy._resolve_flags` |
| `ignored resolution of fN: no counselor turn after its evidence` | the LLM said resolved, but only the parent spoke after the evidence | `policy._resolve_flags` |
| `ignored [key]: same … moment as fN` | the LLM raised a flagged moment again with a new key | `policy._add_new_flags` |
| `due, deferred: newer turns not analyzed yet` | a turn arrived during the LLM call | `policy._run_ladder` |
| `due, waiting: cooldown Ns left` | less than 20 s since the last line for a flag | `policy._run_ladder` |
| `due, waiting: one interjection at a time` | more than one flag was due. The oldest is in the queue. The others wait (and can become stale). | `policy._run_ladder` |
| `→ recap: stale: N turns since tM, the counselor's first chance; …` | more than `STALE_AFTER_TURNS` human turns after the counselor's first counted turn | `policy._run_ladder` |
| `→ dismissed: counselor: not an issue` | the counselor clicked "Not an issue". Beacon never speaks about it or raises it again. | `policy.counselor_action` |
| `counselor will clarify; waiting N counselor turn(s) before speaking` | the counselor clicked "I'll clarify". The count starts again at that turn, with one more turn. | `policy.counselor_action` |
| `ignored counselor action …` / `ignored … only the counselor can act on a card` | a late or invalid click. Nothing changed. | `policy.counselor_action` / `rooms.flag_action` |
| `analysis through … failed …` | LLM error. The ladder did not run. | `rooms._analysis_loop` |
| `withdrew queued line for fN: tM arrived first; re-deciding` / `…: the counselor answered the card first` | a person spoke before the pause, or the counselor clicked a card button first. The flag stays nudged. | `rooms.add_turn` / `rooms.flag_action` |
| `tN withdrew the question from tM` | the parent took the question back, or answered it. No unanswered-question card (an open one → resolved). | `policy._close_questions` |
| `skipped line for …` | the flag changed state while its line was in the queue | `rooms._speaker_loop` |
| `no tab reported playback …` | Beacon spoke, but no tab played the audio or reported it | `rooms._speak` |
| (no ladder line after an analysis) | not due yet: too few counselor turns after "counting after tN", or the counselor turn started before the card appeared | `policy._run_ladder` |

Also look at the "Speech pending" chip. If a line stays in the queue, usually a person still
holds push-to-talk. (The observer does not show who.)
