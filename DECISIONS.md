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
  documented fallback with a separate quota bucket. Free-tier limits, measured on 2026-10-08: the
  429 response names the quota, and for this model it is **500 requests per day** per project
  (third-party pages said about 1,500), resetting at midnight Pacific. A simulated demo call costs
  about 35 requests (one analysis per parent turn and per counselor turn with something open, plus
  summons and the recap); one run of every eval script costs about 100. Calls are spaced 4 s
  apart; at that pace a few per-minute 429s still occurred, which the backoff absorbs.
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
  rate-limit slot doesn't count against the analyzer, summon, or recap timeout. Summons have
  their own `SUMMON_TIMEOUT_SECONDS` (25 s), independent of the 15 s analyzer budget.
- **`notes` is the first field of the analyzer output.** Models generate fields in order; a one-
  sentence summary before the flags acts as a small reasoning step. Evidence fields also come
  before judgment fields (`severity`, `spoken_line`) for the same reason.
- **Response cache lives in `llm.py`, keyed by model + thinking level + schema + prompt.** Only
  the eval turns it on, and only valid responses are cached, so "retry once on invalid output"
  really asks again. Rejected: caching in the eval (it would need to know about prompts).
- **The eval stops at a daily-quota 429 and reports the runs it finished.** A per-minute 429 is
  retried by the backoff, but "retry in 15h" means every later request fails too; continuing
  would only produce a report of empty outputs at 20 s per failed request. The 429's own text
  (which names the quota) is kept in the error, so the decision log says which limit was hit.
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
  The count itself uses `ladder_start_turn`, which starts equal to `created_at_turn` and only
  moves when the counselor clicks "I'll clarify" (see "Counselor controls").
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
- **Dedupe also by moment: same trigger + same parent turn = same flag.** The prompt says never
  to reuse an `issue_key`, and Gemini obeyed by re-raising a resolved SAP flag as
  `sap_not_explained_2` with identical evidence, which then reached the recap as a follow-up
  about something the counselor had explained (seen in the real-Gemini browser run and in round
  0). Code now ignores a new flag whose trigger matches an existing flag's and which cites one
  of its parent turns, logged as "same ... moment as fN". Trade-off: two different misreads of
  the same kind in one parent turn become one card. Rejected: a stronger prompt line alone (the
  model already had one) and fuzzy-matching issue keys (opaque).
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

## Counselor controls

- **Two buttons on each nudge card: "I'll clarify" and "Not an issue".** The office deploys
  Beacon, but the counselor is the expert on the call and must be able to say "I've got this" or
  "that isn't a misunderstanding" without Beacon talking over them. It is also the answer to
  "what about false alarms?": one click ends one. And every dismissal is a labeled example: the
  click is written to the call's log file as `counselor_feedback` with the whole flag (trigger,
  evidence quotes, card text), so false alarms can be collected later to tune the analyzer.
  Rejected: more controls (snooze lengths, a reason picker, editing the card); two buttons are
  what a counselor can use mid-sentence.
- **Same split as everywhere else:** `policy.counselor_action()` validates the click and changes
  the flag (pure, unit-tested); `rooms.flag_action()` checks the role, sends the update, writes
  the feedback record and touches the speech queue.
- **`dismissed` is a new state, and it still blocks its `issue_key`.** A `dropped` flag frees its
  key because its evidence failed, so a better-evidenced flag may come back. A dismissed flag was
  judged by the expert, and raising it again would be nagging. Key-based dedupe can't catch the
  same issue under a reworded key, so the analyzer also sees `state=dismissed` under "Existing
  flags" and one prompt line tells it not to raise that issue again. Rejected: reusing `resolved`
  (it would mix "the counselor fixed it" with "the counselor said it wasn't one" in the log and
  in the tuning data).
- **A dismissed flag is not an open issue in the recap, but an unanswered question survives
  dismissal.** The recap lists unanswered questions from `parent_questions`, not from their
  flags. The counselor decides whether Beacon interrupts their call; the recap belongs to the
  family. "Maria asked this and nobody answered" is a fact counted by code, not a judgment the
  counselor can overrule, while for a dismissed misread or jargon flag the counselor's judgment
  is the best evidence there is. If the question is answered later, it drops out as usual.
- **"I'll clarify" restarts the ladder and works once per flag.** It sets `ladder_start_turn` to
  the newest turn and `grace_turns` to `CLARIFY_GRACE_COUNSELOR_TURNS` (1), so Beacon waits for
  two counselor turns from the click instead of one; staleness is counted from the click too
  (`STALE_AFTER_TURNS` itself is unchanged: two counselor turns and a parent reply still fit in
  3). Once only, because a second click would let the counselor postpone the family's question
  for as long as they keep clicking; if it really isn't an issue, "Not an issue" says so and is
  logged as that. Rejected: a wall-clock snooze (the ladder has no timer and counts in turns).
- **Either click withdraws a line already queued for that flag, before any `await`.** After
  "I'll clarify" the flag is still `nudged`, so the speaker loop's own check (skip a line whose
  flag isn't nudged) would not stop it. A line that is already playing can't be taken back:
  `_speak()` marks the flag `spoken` before its first `await`, so the click finds a flag that is
  no longer nudged and is ignored like any other late click.
- **Invalid or late clicks are ignored and logged, never answered with an error:** a click from
  the parent or the observer, an unknown flag id, a flag that isn't `nudged`, a second "I'll
  clarify". The parent never receives cards, so a parent `flag_action` can only be hand-made.
- **Card buttons give up focus after a click.** Space is the push-to-talk key, and a button
  that keeps keyboard focus is pressed again by the next Space wherever the page doesn't cancel
  that key (it cancels it only while the call is live and the browser has speech recognition).
  Blurring in the click handler makes the next Space a talk key in every case.
- **The eval has no counselor clicks**, so it can only show that the feature (and its one prompt
  line) broke nothing; the behavior is covered by unit and WebSocket tests.

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
  the call isn't live, Beacon is speaking, or someone else holds the floor. The holding socket
  owns the floor, so another tab of the same role cannot release it. A disconnect or failed
  broadcast releases that socket's hold and restarts the quiet period.
- **Stopping speech also cancels a pending voice lookup.** A cancellation counter prevents an
  utterance from starting after Stop was clicked while Chrome was still loading voices.
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
- **Known limitation: one person playing both roles fakes hesitation.** `gap_ms` runs from the
  end of the previous turn to the next push-to-talk press, so in a solo live demo the time spent
  switching windows reads as a "LONG PAUSE" on nearly every turn and can produce false
  `UNEXPLAINED_JARGON` flags. Mitigation, documented in the README: `NOTABLE_GAP_MS=6000` in
  `.env` for solo live demos, the default 2000 for simulations (the planted 3-second pause needs
  it). Rejected: measuring from the first recognized word or detecting window focus; a real call
  has two people and doesn't have this problem, so it isn't worth code.
- **`sim_turn` carries the script's `gap_ms`.** Real elapsed time in a simulation includes waiting
  for analysis, which would fake hesitations everywhere. Only the observer may submit scripted
  turns for another persona. A simulation timeout raises an error instead of silently advancing.
- **Room log filenames sanitize the URL's room name and include microseconds.** Separators and
  Windows filename characters cannot escape or invalidate the logs directory, and calls started
  within the same second get separate files.

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

- **Eval scripts beyond the demo** (2026-10-08): `demo_call_stt_noise` (the demo as Chrome
  would transcribe it: lowercase, no question marks, numbers in mixed forms, a few mis-hearings
  like "pal grant" and "a sea average"), `adversarial_clean` (correct restatements, jargon
  explained at once, clarifying questions, "mm-hm" after logistics, a long pause before a
  substantive reply), `live_regressions` (the exact "$31,500" → "so it's covered" exchange after
  junk mic-check turns, and the broad summons that timed out or ran long), and `summon_checks`
  (one question per glossary family, award-letter facts, two questions the documents can't
  answer). `--runs N` repeats each script, because one passing run of an LLM proves little. A
  test fails if any analyzer prompt example shares a six-word phrase with any script line.
- **Glossary lines don't cite studentaid.gov individually.** The glossary goes into every prompt;
  a URL per line costs tokens on every call, invites Beacon to read a link aloud, and would
  require re-running the whole eval on deadline day. The glossary header names studentaid.gov as
  the official reference, and the definitions avoid loan limits and interest rates, which change
  yearly. A line-by-line check against studentaid.gov is still open.

## Tuned defaults

| Setting | Brief default | Value | Why |
|---|---|---|---|
| UNANSWERED_AFTER_COUNSELOR_TURNS | 2 | 1 | The unanswered-question flag goes through the same ladder as every other flag, so the total wait before Beacon speaks is UNANSWERED_AFTER + ESCALATE_AFTER counselor turns. With 2 + 1 the counselor gets three turns to ignore a direct question, and the planted moment (d) (two non-answers, then the counselor answers) would come out `resolved`, not `spoken`. With 1 + 1: a private nudge after the first non-answer, Beacon asks after the second. Rejected: special-casing this trigger to skip the nudge. |

## Tuning log

### 2026-10-08: repeated runs and question tracking

- **Round 0** (prompts as of the 2026-10-07 entry below; 3 runs of six scripts, 305 requests, no
  cache): demo_call 7/8 moments in every run (all 8 in 2/3 runs); demo_call_stt_noise 7/8 (all 8
  in 1/3); control 0, 0, 1 flags and 0 spoken (pass); adversarial_clean 0 flags and 0 spoken in
  every run (pass); live_regressions: the "so it's covered" nudge in 2/3 runs and both broad
  summons answered in 18–23 words in 3/3; summon_checks 8/10 questions in every run. Analyzer
  latency mean 1,460 ms, max 5,650 ms; summons mean 929 ms, max 1,750 ms. 14 requests failed
  with per-minute 429s, and they explain every summon_checks miss and the live_regressions miss
  (a 429 on the analysis of the "so it's covered" turn, so the next analysis already saw the
  counselor's correction). The remaining misses were real, both in question tracking:
  - d17 (run 1) and s17 (run 3): the analyzer reported the counselor's next-steps turn ("you'll
    accept the awards in the student portal") as answering "does the work-study money have to
    be paid back?", so the unanswered-question flag never escalated.
  - s17 (run 2): with no question mark in the transcript, the question was opened one analysis
    late, so the ladder started late and the scripted answer arrived before Beacon could ask.
- **Round 1 prompt change:** `questions_opened` says speech recognition drops question marks and
  a question must be reported in the output for its own turn; `questions_answered` says a turn
  that moves on to another topic does not answer a question, even right after it. New few-shot
  Example G (a housing-deposit question without "?", then the counselor moves on) shows both;
  its content is unrelated to the scripts.
- **Round 1 result:** the free tier's daily quota (500 requests) ran out partway through round 1,
  so its numbers were discarded. The rest of the verification used a second key, lent by a
  friend, on the same model.
- **Real-Gemini browser run (Playwright, 20/20 checks):** the live "$31,500" → "so it's covered"
  exchange produced a card; "I'll clarify" held Beacon for one counselor turn, then it asked;
  "Not an issue" was never spoken; the broad summon was answered in 1.3 s; the demo simulation
  hit every scripted beat and its recap had 0 unverified numbers, correct grant/loan/work-study
  split and the July 15 deadline. One defect: the recap's only follow-up asked about SAP, which
  the counselor had explained. Gemini had re-raised the resolved SAP flag as
  `sap_not_explained_2` with identical evidence (round 0 shows `sap_not_explained_new` too).
  Fixed in code, not the prompt: dedupe by moment (see "Perceive vs. decide").
- **Round 2** (both changes; 3 runs of six scripts, 307 requests, no cache, 0 errors; calls spaced
  5 s apart via `MIN_SECONDS_BETWEEN_LLM_CALLS=5` so per-minute 429s don't hide perception
  results; the app default stays 4 s): **demo_call 8/8 in 3/3 runs; demo_call_stt_noise 8/8 in
  3/3; control 1 flag and 0 spoken in every run (pass); adversarial_clean 0 flags, 0 spoken
  (pass); live_regressions 3/3 in 3/3 (the "so it's covered" nudge, both broad summons in at most
  23 words); summon_checks 10/10 in 3/3**, out-of-documents questions declined and deferred to the
  counselor. The new dedupe ignored a re-raised SAP flag 4 times across the demo runs. The
  control call's one flag per run is a private unanswered-question nudge that resolved on the
  next analysis (the model credits an answer one analysis late), never spoken. Analyzer latency
  mean 1,451 ms, max 6,377 ms; summons mean 1,449 ms, max 11,384 ms (under the 25 s budget).
  Targets met; tuning stopped after this round.

### 2026-10-07: stated conclusions and broad summons

- Live testing showed the analyzer recognizing a parent's conclusion that an aid package meant
  everything was covered, but suppressing it as a minor/unconfirmed inference. `MISREAD_TERM`
  now explicitly includes wrong stated conclusions about money, repayment, amounts owed,
  deadlines, requirements, and approval status, even without misuse of a term. The trigger's
  $24,000 example and the analyzer's Cedar Vale College $27,000 example generalize a documented
  failure pattern rather than copying a script line: aid offers mix grants and loans, obscuring
  what families pay and repay. Sources: [GAO-23-104708](https://www.gao.gov/products/gao-23-104708)
  and [uAspire/New America, *Decoding the Cost of College* (2018)](https://www.newamerica.org/documents/2301/Decoding_the_Cost_of_College_Final_6218.pdf).
- Replaced the perception prompt's false-interruption framing and blanket uncertainty suppression
  with the actual private-card-first flow. A clear wrong belief that could change what the family
  pays, borrows, signs, or does by a deadline gets `interrupt` severity. Correct restatements,
  clarifying questions, and passive replies to simple logistics stay quiet. Evidence checks,
  visibility boundaries, the escalation ladder, and cooldown are unchanged. Rejected: matching
  demo phrases in Python or letting the LLM decide when to speak.
- A broad summon timed out at 15 s. Added environment-overridable `SUMMON_TIMEOUT_SECONDS=25`
  and used it only for summon answers. The summon prompt now requests a one-sentence document
  overview and a specific suggested question for broad requests, within the existing 25-word
  limit. Rejected: extending every analyzer call's budget or reading all documents aloud.
- Validation: `python tasks.py test` passed all 58 backend tests, including independent summon
  and analyzer timeout overrides. `python tasks.py eval` (no `--cache`), model
  `gemini-3.5-flash-lite`, thinking `low`: **8/8 demo moments passed**; **control 0 flags,
  0 spoken interjections** (targets: at most 1 flag, no spoken interjections). All 36 requests
  reached the network, with 0 cache hits and 0 API errors. Analyzer latency: mean 1,457 ms,
  max 3,732 ms. Per-moment outcomes:

  | Moment | Outcome | Result |
  |---|---|---|
  | d04: aid package means everything is covered | MISREAD_TERM, counselor clarified, resolved | PASS |
  | d10: selected for verification means approved | MISREAD_TERM, spoken | PASS |
  | d15: unexplained SAP after a long pause | UNEXPLAINED_JARGON, counselor clarified, resolved | PASS |
  | d17: work-study repayment question ignored | UNANSWERED_QUESTION, spoken | PASS |
  | d23: SAI mention with substantive parent reply | No flag (recap at most) | PASS |
  | d25: Parent PLUS summon | Answered from documents | PASS |
  | d29: correct remaining-cost restatement | No flag | PASS |
  | d31: correct net-price restatement | No flag | PASS |

- Two additional uncached Gemini requests verified the exact live exchange and broad summon.
  The live exchange produced an evidence-gated `MISREAD_TERM` private nudge with `interrupt`
  severity. The broad summon returned a 19-word overview and suggested asking about the total
  aid package in 963 ms, within its 25 s budget. Both requests succeeded with no cache hits or
  API errors. Full script results and supplemental checks: `eval_results.md`.

### Earlier build and rename checks

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
