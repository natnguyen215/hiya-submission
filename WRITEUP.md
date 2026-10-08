# Beacon: asking the question the family won't ask

**Track:** Real-Time Assistance

## The problem

I built and launched a scholarship portal for a nonprofit, replacing its staff's spreadsheets.
Working on it, I saw that much of what made the process hard for families was language:
institutional terms they didn't understand and didn't ask about.

On financial aid calls, a counselor says "the total aid package is $31,500" and a parent hears
"it's covered," when $14,000 of it is loans. "Selected for verification" sounds like "approved"
but means paperwork is due. Not wanting to look uninformed, families say "okay" and hang up
believing something wrong.

## Who it's for

First-generation college families on calls with financial aid counselors. The financial aid
office deploys Beacon, but its job is the family's understanding, like a hospital patient
advocate.

## What it does

Beacon listens to the call. When the parent's words show a misunderstanding, or jargon went by
unexplained and the reply was a hesitant "...okay", it first shows the counselor a private card
with a suggested clarification. Usually the counselor fixes it and Beacon never speaks. If the
counselor moves on, Beacon waits for a pause and asks on the family's behalf: "Quick check for
Maria: what does 'selected for verification' mean for her?" About the family's money it asks
rather than answers, so the expert stays in charge. The family can also ask it by name. After
the call, everyone gets a plain-language Family Recap (free money vs. loans vs. work-study, what's
left to pay, deadlines, open questions), every number cited, with a read-aloud button.

## Why voice

- These conversations already happen by voice; typing would break them.
- The misunderstanding must be caught during the call, before the wrong belief sets in.
- A three-second pause before "...okay" carries information text doesn't; Beacon uses response
  timing as a signal.
- Families less comfortable reading English get a spoken clarification and a spoken recap.

## How it's built

A React web app uses the browser's speech recognition (push-to-talk) and speech synthesis and
talks to a FastAPI server over a WebSocket. The core design choice: Gemini (3.5 Flash-Lite,
structured JSON) only perceives: possible misunderstandings (with exact quotes), resolved issues,
and answered questions. Plain Python decides.
It checks every quote against the transcript, drops what it can't verify, ignores duplicates,
sends minor issues to the recap, and escalates from private nudge to spoken question only when
the counselor doesn't clarify, with a cooldown and a staleness rule. Every decision is logged on
an observer dashboard. An offline eval replays a scripted call with planted misunderstandings,
plus a clean control call, and checks each outcome.

## What's next

Phone integration; a counselor-only whisper mode; explaining things in the family's own language;
and testing with real counselors and families to tune when Beacon should speak.

## AI tools used

_[To fill in, about 60 words (the page limit is 550): which coding agents you used, for what
(for example scaffolding, tests, demo scripts, review), and what you designed, checked or
rewrote yourself.]_
