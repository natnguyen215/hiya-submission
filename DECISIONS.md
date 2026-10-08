# Decisions

Each entry: the decision, why, and the main alternative rejected. Changes to the brief's §5.6
defaults are logged under "Tuned defaults".

## Name

- **Renamed from Canopus to Beacon because Chrome's speech recognition mis-transcribed "Canopus"
  in live testing.** A common English word is transcribed reliably and is rarely said in a
  financial aid call. Rejected alternatives: Polaris and Iris (Iris is a common first name);
  Compass (too close to "campus", which appears in the scripts).
- Beacon: a light that guides people through unclear waters. It helps the family see what the call actually means.

## Repository and tooling

- **Own git repo in this folder.** The parent `CODE/` folder is an unrelated repo; the submission
  needs a clean history. Rejected: committing into the parent repo.
- **`tasks.py` is the task runner; the Makefile is a thin alias.** The dev machine is Windows
  without `make`, and `make dev` must start two processes. A 60-line Python script does that on
  every OS. Rejected: a Makefile with shell-only recipes (breaks on Windows), or npm scripts with
  `concurrently` (an extra dependency).
- **A `.venv` created by `tasks.py install`.** Keeps the global Python clean. Rejected: installing
  into whatever Python is active.
- **`httpx2` instead of `httpx` in requirements.** Starlette 1.7's TestClient warns that `httpx` is
  deprecated for it. (`httpx` is still installed because `google-genai` uses it.)
- **`pytest-timeout` (60 s).** A WebSocket smoke test that waits for a message that never comes
  would otherwise block forever; with the timeout it fails with a stack trace.
- **`tasks.py dev` stops Vite with `taskkill /T` on Windows.** `terminate()` only ends the
  `npm.cmd` wrapper there and leaves Vite holding port 5173.
- **M1–M3 landed in one commit.** The backend and the frontend were built in parallel against the
  shared protocol in `models.py`/`types.ts` and committed together once verified end to end; later
  milestones are separate commits.

## LLM

- **Model `gemini-3.5-flash-lite`, thinking level `low`.** Researched on 2026-10-07: it is on the
  free tier, stable, and Google's fastest 3.5 model; 2.5 models are now restricted to existing
  projects. `low` thinking trades a little latency for better judgment on severity and
  resolution, which is where the analyzer is most likely to be wrong. Both are env overrides.
  Rejected: `gemini-3.6-flash` (default `medium` thinking, slower) as the default; it is the
  documented fallback with a separate quota bucket. Free-tier RPM/RPD could not be verified (Google
  only shows them in AI Studio now).
- **`response_json_schema=Model.model_json_schema()`, then `Model.model_validate_json`.** The
  current SDK sends the JSON schema as-is; pydantic does the validation we rely on. Rejected:
  `response_schema=Model` (the SDK converts it to its own schema format, which mishandles some
  shapes) and `response.parsed` (silently `None` on failure).
- **No temperature setting.** Deprecated for Gemini 3.x, where values below 1.0 can degrade output.
- **SDK retries off (`attempts=1`); our own throttle and backoff.** One place decides retry
  behavior: `llm.py` spaces calls `MIN_SECONDS_BETWEEN_LLM_CALLS` apart across the whole process
  (the quota is per key, not per room) and pauses all calls for `LLM_BACKOFF_SECONDS` after a 429
  (a caller already waiting for a slot sees the pause too). A failed analysis is not retried at
  once; the next turn's analysis sees the whole transcript, and `should_analyze` counts from the
  last *successful* analysis, so a parent turn whose analysis failed is never skipped.
- **Timeouts with `asyncio.wait_for` around the network call only**, so time spent waiting for a
  rate-limit slot doesn't count against `ANALYZER_TIMEOUT_SECONDS`.
- **`notes` is the first field of the analyzer output.** Models generate fields in order; a one-
  sentence summary before the flags acts as a small reasoning step. Evidence fields also come
  before judgment fields (`severity`, `spoken_line`) for the same reason.
- **Response cache lives in `llm.py`, keyed by model + thinking level + schema + prompt.** Only
  the eval turns it on, and only valid responses are cached, so "retry once on invalid output"
  really asks again. Rejected: caching in the eval (it would need to know about prompts).
- **Eval latency is network time only** (`GeminiLLM.latencies_ms`), not the wait for a rate-limit
  slot, which would otherwise dominate every number.

## Perceive vs. decide

- **`policy.py` mutates the state it is given and returns actions; it does no I/O and reads no
  clock.** "Pure" here means deterministic and side-effect-free apart from the state passed in, so
  tests build a state, call a function, and assert on state + actions. Rejected: returning a new
  state (deep copies everywhere, harder to read).
- **Actions are four small types (`SendCard`, `UpdateFlag`, `SpeakLine`, `LogEntry`) executed with
  a `match` in `rooms.py`.** The eval executes the same actions without WebSockets.
- **A flag becomes `spoken` only when the line is actually said** (`policy.mark_spoken`), not when
  the policy queues it. The cooldown starts then too.
- **A queued interjection is withdrawn when any human turn arrives first.** The flag stays
  `nudged` and the next analysis (which sees the new turn) decides again: maybe resolved, maybe
  speak, maybe stale. Speaking about something the counselor just fixed would be worse than
  waiting one turn. Summon answers are never withdrawn.
- **The same rule applies to turns that arrive during an analysis:** if a human turn came in while
  the LLM was working, the policy defers speaking ("deferred: newer turns not analyzed yet") and
  the rerun decides.
- **The ladder counts from when the card appeared** (`created_at_turn` = the newest turn when the
  flag is created, including turns the analyzer hadn't seen yet), and only counts turns an
  analysis has checked. A counselor turn spoken before the card existed never counts as "saw the
  card and didn't clarify". The analyzer judges resolution against the flag's evidence turns.
- **One interjection per analysis**, oldest due flag first; others wait (and may go stale).
- **Staleness is also checked at creation:** a flag whose evidence (or an unanswered question)
  is already more than `STALE_AFTER_TURNS` turns old goes straight to the recap. Late detections
  shouldn't interrupt.
- **Evidence gate details:** quotes are matched after normalizing case, punctuation and
  apostrophes; then fuzzy-matched (≥ 0.85 similarity) against word windows of the quote's length ±1
  so "it's" vs "it is" passes. Cited turns must exist and must be counselor/parent turns. A
  trigger with `needs_parent_evidence` (both current LLM triggers) must also cite a parent turn;
  that rule lives on the trigger in `triggers.py`, so a new trigger evidenced by the counselor's
  words only needs `needs_parent_evidence=False`. Known limitation: a one-word insertion like
  "not" can still pass; the gate stops invented quotes, not every paraphrase.
- **Dropped flags are kept (state `dropped`) so the observer can show why**, but they don't count
  for dedupe, so a later, well-evidenced flag with the same `issue_key` can still be raised.
- **Skip the LLM after a counselor turn when no flag is nudged and no question is open.** While
  every LLM trigger needs the parent's reply as evidence, nothing new could be perceived. This
  roughly halves calls on the free tier and is logged in the decision log.
- **A parent question that is already the evidence for a flag is not tracked separately** ("Oh
  good, so we're verified?" is a misread, not a second, unanswered-question flag).
- **Questions addressed to Beacon are not tracked** as parent questions; the summon path answers
  them.
- **Unanswered-question lines are templates in `config.py`**, not LLM output: the trigger is
  code-decided, so its words are too. The question they quote goes through the same evidence
  gate as flags: the analyzer must copy it word for word, and code checks it against the turn.

## Speaking and turn-taking

- **Pause = `PAUSE_BEFORE_SPEAK_MS` since the last turn, push-to-talk release, or Beacon line,
  with nobody holding push-to-talk.** The speaker loop polls every 100 ms; simple to explain.
- **Playback fallback:** if no tab reports `beacon_playback_done`, the server assumes the line
  finished after 2 s + `PLAYBACK_FALLBACK_MS_PER_WORD` (800 ms) per word, so a call with every
  audio toggle off never stalls. At 500 ms the server sometimes gave up on a real Windows voice
  mid-sentence. The tab that is playing keeps its own "speaking" flag until its audio really
  ends, so push-to-talk stays disabled there (echo guard).
- **The opening line and summon answers don't start the cooldown.** The cooldown limits
  unprompted interjections.
- **The opening line says Beacon is an AI** and teaches the summon form ("just start with my
  name"): disclosure matters, and a family shouldn't mistake it for another staff member.
- **Summon answers: about 20 words, never more than 25.** A definition needs a sentence or two;
  anything over 25 words is logged as a warning like every other line.
- **Push-to-talk is first come, first served on the server too:** `ptt_start` is ignored while
  the call isn't live or someone else holds the floor.
- **The microphone stays open 400 ms after release** (`RELEASE_TAIL_MS` in `speech.ts`). People
  let go while the last syllable is still sounding, and stopping at once clipped it ("beacon" →
  "beac"). The tab holds the floor through the tail, so Beacon's pause starts after it.
- **Both roles can summon.** The counselor saying "Beacon, can you explain SAP?" is plausible.
- **Counselor tab also has Start/End call**, so a two-window LIVE demo works without the observer.
- **`start_call {simulated}` marks a simulated call; call tabs then stay silent** and the observer
  plays every voice, so a one-laptop demo never doubles audio.
- **`status` message instead of `analysis_status`.** One message carries everything a tab needs
  (call status, push-to-talk holder, speaking, queued speech, analysis state, analyzed turn count,
  recap status). The simulation runner needs several of these at once, and the server sends the
  speech count and the analyzed count in the same message so the runner can't race between them.
- **Broadcasts are serialized with a per-room lock**, so a newer `status` can never overtake an
  older one on its way to a tab.
- **A summon is counted in `speech_pending` before the turn is broadcast**, so the simulation
  runner never sees the summon turn without the pending answer.
- **Text-only simulation compresses time.** The cooldown is in wall-clock seconds, so a very fast
  silent run can push a second interjection into the 20 s cooldown and then to the recap. Runs
  with audio, live calls, and the eval (virtual clock based on words spoken) keep real
  conversational timing. Rejected: a turn-based cooldown (the brief specifies seconds).
- **`sim_turn` carries the script's `gap_ms`.** Real elapsed time in a simulation includes waiting
  for analysis, which would fake hesitations everywhere.

## Wake word

- **Fuzzy match of 1–3 word windows (joined without spaces) against the variants, ratio ≥ 0.85.**
  The only variant is "beacon". Measured: "beacon" 1.00, "beacons" 0.92, "bacon" 0.91
  (accepted: unlikely in a financial aid call), "deacon" 0.83, "beckon" 0.83, "become" 0.67,
  "campus" 0.17. Rejected: "becon" and "beakon", because they make "beckon" match.
- **"Followed by a question" = at least two words that start with a question word, or a "?"**,
  taken from after the name, or before it if nothing follows ("What's SAP, Beacon?"). Chrome's
  recognizer rarely adds punctuation, so the first word does most of the work. An auxiliary
  (can, is, does, will...) counts only when a subject follows it: "Beacon, can you explain SAP"
  is a summon, "Beacon can help with that later" is not. Trade-off: "Beacon, is work-study a
  loan" (no subject word) is missed unless Chrome adds a "?"; "what"/"how" questions always work.

## Data

- **Document line ids live in the files** (`- L14 ...`) rather than being assigned at load time,
  so a citation can be checked by searching the file. The LLM receives the raw files, ids included.
- **Recap numbers are checked by code**: every number in a recap item must appear in a line, turn
  or flag evidence the item cites; misses are listed as "unverified" in the recap and the log.
- **Recap open issues are checked by code too:** every recap-state flag and unanswered question
  must be cited by a follow-up; any the LLM left out is added by code (using the flag's question
  for Beacon or the parent's own question), logged, and number-checked like the rest. Flags Beacon asked aloud are passed to the
  LLM so it can add a follow-up if the counselor never answered.
- **Demo script trimmed to 35 turns (~600 words).** The first draft ran about 4.5 minutes; the
  clear stretch was cut from 6 to 4 turns and several lines shortened. Planted moments unchanged.

## Tuned defaults

| Setting | Brief default | Value | Why |
|---|---|---|---|
| UNANSWERED_AFTER_COUNSELOR_TURNS | 2 | 1 | The unanswered-question flag goes through the same ladder as every other flag, so the total wait before Beacon speaks is UNANSWERED_AFTER + ESCALATE_AFTER counselor turns. With 2 + 1 the counselor gets three turns to ignore a direct question, and the planted moment (d) (two non-answers, then the counselor answers) would come out `resolved`, not `spoken`. With 1 + 1: a private nudge after the first non-answer, Beacon asks after the second. Rejected: special-casing this trigger to skip the nudge. |

## Tuning log

No Gemini key was available during the original build. Before the real Gemini run recorded below,
two substitutes were used, and neither is a Gemini result:

1. **Ideal-perception check of the policy.** A throwaway harness replaced the analyzer with an
   oracle derived from the scripts' `expect` fields and ran `eval/run.py` unchanged: 8/8 planted
   moments reached their expected outcome and the control call had 0 flags. This shows the
   policy, timing defaults and script structure line up; it says nothing about perception.
2. **Stand-in model for prompt clarity.** The same eval was run with every LLM request answered
   by Claude Haiku 4.5 reading the exact prompt (one fresh agent per request).
   - Run 1: 7/8 planted moments, control call 1 flag / 0 spoken (pass). Misses: (a) the analyzer
     framed "so it's covered" as "covers the whole cost", then did not count the counselor's
     "it isn't all free money, $14,000 is loans" as resolving it, so Beacon spoke; and in the
     control call a question's answer was recognized one analysis late, creating a private
     nudge that resolved itself on the next turn.
   - Prompt change: a flag counts as resolved when the counselor fixes the core of the
     misunderstanding, even if not every detail is covered; every unanswered question is
     checked against each later counselor turn, including the newest.
   - Run 2 (after that change): 8/8 planted moments; control call 0 flags, 0 spoken.
   - Prompt change after the code review: parent questions are copied word for word (and checked
     against the turn) instead of restated, because Beacon may quote them aloud.
   - Run 3 (final prompts): 8/8 planted moments; control call 0 flags, 0 spoken; all three control
     questions passed the quote check and were marked answered by the next counselor turn.

3. **Uncached Gemini eval after the Beacon rename (2026-10-07).** `python tasks.py eval`,
   model `gemini-3.5-flash-lite`, thinking `low`: 8/8 planted moments passed. d04 and d15
   resolved; d10 and d17 spoken; d23 no flag (passes the recap-at-most rule); d25 answered;
   d29 and d31 no flag. The demo also produced an extra SAP nudge that resolved without speech.
   Control: one private unanswered-question nudge, resolved on the next analysis; zero spoken
   interjections (pass). All 36 requests reached the network; zero API errors and zero cache hits.
   Analyzer latency: mean 1,357 ms, max 3,050 ms. Full transcript and decisions: `eval_results.md`.
   Validation: 53 backend tests passed and the frontend build passed. Manual Chrome verification
   of the renamed wake word remains pending.
