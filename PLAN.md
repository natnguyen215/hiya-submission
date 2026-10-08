# Beacon: Build Plan

Beacon listens to a financial aid call between a counselor (Alex) and a parent (Maria) and
asks the question the family won't ask. This file is the working plan; the checklist at the
bottom is kept current as milestones land.

## Architecture

```
 Chrome tabs (Vite + React)                    FastAPI process (one per demo)
 ┌──────────────────────────┐   WebSocket   ┌──────────────────────────────────────────┐
 │ /call?role=counselor     │──────────────▶│ main.py   routes, /ws, serves web/dist   │
 │ /call?role=parent        │◀──────────────│ rooms.py  room state, broadcast,         │
 │ /observer                │  JSON msgs    │           analysis loop, speech queue    │
 │  - Web Speech STT (PTT)  │               │    │                 │                   │
 │  - speechSynthesis TTS   │               │    ▼ perceive        ▼ decide            │
 │  - simulation runner     │               │ analyzer.py ──▶ llm.py ──▶ Gemini         │
 └──────────────────────────┘               │ policy.py (pure: gates, ladder, timing)  │
                                            │ triggers.py, wakeword.py, docs.py        │
                                            └──────────────────────────────────────────┘
```

**Perceive vs. decide.** `analyzer.py` asks Gemini what it *perceives* (possible
misunderstandings with quotes, which flags the counselor resolved, which parent questions were
asked/answered). `policy.py` is pure Python that *decides* what Beacon does with that:
evidence gate, dedupe, severity, escalation ladder, staleness, cooldown, unanswered-question
counting. The LLM never makes Beacon speak; only `policy.py` returns a `SpeakLine` action.

**Per-room flow.**
1. A client sends a turn (typed, push-to-talk, or simulated). `rooms.py` stores it, broadcasts it,
   withdraws any not-yet-spoken interjection (the conversation moved on), checks the wake word,
   and requests an analysis.
2. At most one analysis runs per room. Turns that arrive meanwhile mark the room dirty; when the
   analysis returns it runs once more on the latest transcript (coalescing = rate limiting).
3. `policy.after_analysis()` updates flags/questions and returns actions: send card, update flag,
   speak line, log entry. `rooms.py` executes them.
4. Speech goes through a queue. The speaker waits until nobody holds push-to-talk and the room has
   been quiet for `PAUSE_BEFORE_SPEAK_MS`, broadcasts `beacon_say`, and waits for a tab to report
   playback done (with a timeout). Beacon's lines are stored as turns so the analyzer sees them.
5. On end of call, open flags move to the recap and `analyzer.generate_recap()` builds the Family
   Recap (structured JSON, every number cited and checked against its sources).

**Summon.** `wakeword.py` fuzzy-matches "Beacon" variants. A summon turn skips the ladder and the
cooldown: `analyzer.answer_summon()` answers from the grounding documents only, citing line ids.

## Files

| Path | Purpose |
|---|---|
| `backend/app/config.py` | every tunable default, overridable by env |
| `backend/app/models.py` | Turn, Flag, RoomState, analyzer/recap schemas, WebSocket messages |
| `backend/app/triggers.py` | the one list of trigger definitions |
| `backend/app/wakeword.py` | wake word detection |
| `backend/app/docs.py` | loads grounding documents with line ids |
| `backend/app/llm.py` | Gemini wrapper (throttle, timeout, backoff, cache) + FakeLLM |
| `backend/app/analyzer.py` | analyze / answer_summon / generate_recap: prompt, call, validate |
| `backend/app/policy.py` | pure decision logic |
| `backend/app/rooms.py` | rooms, broadcasting, analysis loop, speech queue, decision log |
| `backend/app/main.py` | FastAPI app, REST + WebSocket routes, static frontend |
| `backend/prompts/*.txt` | analyzer, summon, recap prompts |
| `backend/tests/` | pytest unit + WebSocket smoke tests (no network) |
| `eval/run.py` | offline eval over the demo and control scripts |
| `data/` | award letter, glossary, scripts |
| `web/src/` | React views: call, observer, recap; WebSocket hook; speech helpers |
| `tasks.py`, `Makefile` | install/dev/build/run/test/eval (Makefile delegates to tasks.py) |

## Assumptions

- One demo machine, Chrome, one or more tabs; client clocks are the same clock (`gap_ms` uses
  client timestamps).
- All state is in memory; restart = fresh rooms. Logs go to `logs/<room>-<time>.jsonl`.
- Backend tests use FakeLLM without network access. The real eval requires GEMINI_API_KEY;
  the uncached Beacon run passed on 2026-10-07 (see `eval_results.md`).
- Windows dev machine without `make`: `tasks.py` is the cross-platform runner; the Makefile is a
  thin alias for macOS/Linux.

## Milestones

- [x] M0 PLAN.md, DECISIONS.md skeleton
- [x] M1 rooms, WebSocket protocol, call + observer views with typed turns
- [x] M2 analyzer, policy, ladder, decision log, FakeLLM, unit + smoke tests
- [x] M3 simulate (text only), eval harness (uncached Gemini eval: 8/8 planted moments; control passed)
- [x] M4 voice: push-to-talk STT, persona/Beacon TTS, opening line, wake word + summon, echo guard, audio toggle
- [x] M5 Family Recap (structured, read aloud, download)
- [x] M6 README, WRITEUP, DEMO, cleanup pass (plus a whole-repo review; confirmed findings fixed)
- [ ] Stretch: hybrid demo mode. Not started. Manual Chrome verification of the renamed wake word remains pending.
