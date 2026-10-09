# Repository guidance

## Project and architecture

Beacon is a prototype AI mediator for fictional financial aid calls. Read
`README.md` for setup, `CLAUDE.md` for detailed orientation, and `DECISIONS.md`
before changing intentional behavior.

- `backend/app/`: FastAPI, WebSocket rooms, Gemini integration, and policy.
- `backend/app/policy.py`: deterministic decisions; no I/O, clock reads, or LLM calls.
- `backend/app/rooms.py`: runtime state, broadcasting, analysis, and speech queues.
- `backend/prompts/*.txt`: LLM prompts; keep prompts out of Python strings.
- `web/src/`: React and TypeScript call, observer, and recap views.
- `data/`: fictional grounding documents and the eval's call scripts.
- `backend/tests/`: network-free pytest tests using `FakeLLM`.
- `eval/run.py`: real Gemini evaluation, writing `eval_results.md`.

The LLM perceives; Python decides whether to nudge or speak. Preserve the evidence
gate, escalation ladder, cooldown, and parent/counselor visibility boundaries.
Keep `backend/app/models.py` and `web/src/types.ts` aligned when changing shared
data or the WebSocket protocol.

## Setup and commands

Run commands from the project root with Python 3.11+ and Node 20.19+ (20.x) or
22.12+. Chrome is required for the speech UI.

- `python tasks.py install`: creates `.venv`, installs Python requirements and web dependencies.
- `python tasks.py test`: runs pytest using `.venv` without Gemini/network access.
- `python tasks.py build`: checks TypeScript and builds the frontend.
- `python tasks.py dev`: backend on port 8000 and Vite on port 5173.
- `python tasks.py run`: serves backend and built frontend on port 8000; build first.
- `python tasks.py eval`: evaluates every script in `eval/run.py`'s `SCRIPTS` against Gemini (about 100 requests; the free tier allows 500 a day).
- `python tasks.py eval --cache`: stores/reuses valid responses in `.cache/`.
- `python tasks.py eval --script demo_call --runs 3`: one script, three times.
- `python tasks.py eval --paced`: the paced mode (turns arrive on the clock while analyses run, as in a live call); it rewrites only its half of `eval_results.md`.
- `eval/browser_check.js`: optional Playwright check of the UI against a running server (see its header).

The task runner uses `.venv` automatically; activation is optional. On Windows,
set `PYTHONIOENCODING=utf-8` when printing Unicode decision logs. Configure
`GEMINI_API_KEY` and optional setting overrides in `.env`, using `.env.example`
as the template. Never print or commit API keys. `.env`, `.venv`, `.cache`, logs,
frontend dependencies, and build output are ignored.

## Changes and validation

Keep changes small and explainable, using plain functions and Pydantic models.
Add purpose docstrings to Python modules and comments explaining why. Record
new dependency reasons and policy/default tuning in `DECISIONS.md`.

Run backend tests after backend changes and the frontend build after UI/type
changes. Real microphone and speech playback behavior needs manual Chrome
verification using the README checklist. Inspect `eval_results.md` after an eval:
the runner can exit successfully even when requests or expected outcomes fail.
Report API failures separately from valid evaluation scores.
