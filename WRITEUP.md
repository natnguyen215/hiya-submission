# Beacon: asking the question the family won't ask

**Track:** Real-Time Assistance

## The problem

Building a scholarship portal for a nonprofit, I saw families struggle most with language:
institutional terms they didn't understand and didn't ask about.

A counselor says "the total aid package is $31,500" and a parent hears
"it's covered," when $14,000 of it is loans. "Selected for verification" sounds like "approved"
but means paperwork is due. Families say "okay" and hang up believing something wrong.

This isn't hypothetical. A 2022 GAO review estimated 91% of colleges leave out or understate the
net price in aid offers, often counting loans as if they reduced the cost. A uAspire/New America
review of 515 award letters found about 70% lumped grants, loans and work-study together without
explaining the difference, and nearly 15% listed Parent PLUS loans as an "award." The demo's
planted moments are these documented failures.

## Who it's for

First-generation college families on calls with financial aid counselors. The office deploys
Beacon, but its job is the family's understanding, like a hospital patient advocate.

## What it does

When the parent's words show a misunderstanding, or jargon went by unexplained and the reply was a
hesitant "...okay", Beacon first shows the counselor a private card with a suggested clarification.
Usually the counselor fixes it and Beacon stays silent. If the counselor moves on, Beacon waits for
a pause and asks on the family's behalf: "Quick check for Maria: what does 'selected for
verification' mean for her?" It asks rather than answers, so the expert stays in charge. Two
buttons on the card let the counselor say "I'll clarify" or "Not an issue"; dismissals are logged
as tuning data. The family can also ask Beacon by name. After the call comes a plain-language,
read-aloud Family Recap (free money vs. loans vs. work-study, what's left to pay, deadlines, open
questions), every number checked against its citation.

## Why voice

- These conversations already happen by voice; typing would break them.
- The misunderstanding must be caught during the call, before the wrong belief sets in.
- A three-second pause before "...okay" carries information text doesn't.
- Families less comfortable reading English hear the clarification and the recap.

## How it's built

A React app uses browser speech recognition (push-to-talk) and synthesis, with a FastAPI WebSocket
server. The core design choice: Gemini (3.5 Flash-Lite, structured JSON) only perceives:
misunderstandings with exact quotes, resolutions, answered questions. Plain Python decides: it
verifies every quote, ignores duplicates, sends minor issues to the recap, and escalates from
private nudge to spoken question only when the counselor doesn't clarify, with a cooldown and
staleness rule. An observer dashboard logs every decision. An offline eval replays scripted calls
(planted misunderstandings, clean controls, speech-recognition noise) repeatedly, checking each
outcome.

## What's next

Phone integration, a counselor-only whisper mode, the family's own language, and testing with
real counselors and families to tune when Beacon speaks.

## AI tools used

_[To fill in, at most 60 words (the rest of this page is 490 words; the limit is 550): which coding agents you used, for what
(for example scaffolding, tests, demo scripts, review), and what you designed, checked or
rewrote yourself.]_
