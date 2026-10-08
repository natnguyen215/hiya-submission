# Demo video run-of-show (2:45)

## Before you record

**Pre-flight on the recording laptop (10 minutes):**

1. Get the latest code. Merge the PR into `main` and pull, or check out its branch.
2. Copy `.env.example` to `.env`. (`.env` is not in git.)
3. In `.env`, set `GEMINI_API_KEY`.
4. Run `python tasks.py install`, then `python tasks.py build`, then `python tasks.py run`.
5. Open the three pages from the README in Chrome.
6. In the parent window, hold push-to-talk and say "Beacon, what's a Parent PLUS loan?". This
   checks the microphone, the wake word and the audio together. The README's manual checklist
   has the other checks.

**Quota:** the free tier gives 500 Gemini requests per day. The quota resets at midnight Pacific
time. One take of the simulated call uses about 35 requests, and the live beat uses about 5. A
rehearsal and several takes fit in one day. Do not run the full eval on recording day: one run
uses about 100 requests.

**Setup:**

1. Keep `NOTABLE_GAP_MS` at its default (2000). Moment (c) needs its 3-second pause to show as
   long.
2. Put the observer (`/observer?room=demo`) in a Chrome window on the left two-thirds of the
   screen.
3. Put the counselor (`/call?room=demo&role=counselor`) in a second window on the right third.
4. Click once in the counselor window, so its "Click anywhere..." notice goes away.
5. In the observer, select `demo_call`, untick "Text only (no audio)", and click once in the
   observer.
6. Do one full rehearsal. Make sure that each moment lands. Then click **Reset**.
7. Record. With audio, the call runs about 5 minutes. In editing, speed up the parts between
   the highlights (2–4×).

Beacon's spoken lines come from Gemini, so their words change from take to take. Narrate the
idea, not the exact words.

## Run of show

| Time | On screen | Narration (suggested) |
|---|---|---|
| 0:00–0:15 | Title card, then the award letter in the Documents panel | "When a financial aid counselor says 'your aid package is $31,500,' a first-generation parent often hears 'it's covered.' $14,000 of it is loans. Families rarely ask. Beacon asks for them." |
| 0:15–0:25 | Press **Play**. Beacon's opening line plays. | "Beacon joins the call, says it's an AI assistant, and teaches its name. It works for the family's understanding, like a patient advocate." |
| 0:25–0:50 | Moment (a): Maria: "So it's covered." A card appears in the counselor window. Alex clarifies; the card turns green "Clarified". | "First it nudges the counselor privately, with a suggested clarification. Alex fixes it, so Beacon never says a word. That's the common case." |
| 0:50–1:15 | Moment (b): "Oh good, so we're verified?" Alex moves on to housing. Beacon, at the pause: "Quick check for Maria: ..." Alex answers. | "Here the counselor moves on. Beacon waits for a pause and asks one short question, on Maria's behalf, to the counselor. It asks; it doesn't answer for the school." |
| 1:15–1:30 | Moment (c): the **3.0s pause** badge before Maria's "...okay." | "This is something only voice carries: a three-second pause before 'okay.' Beacon treats hesitation as a signal. Alex sees the card and explains SAP." |
| 1:30–1:50 | Moment (e): "Beacon, what's a Parent PLUS loan?" Spoken answer; point at its Decision Log entry, "answer (documents G9)" or similar, which lists the cited lines (expand "data" for the full answer). | "The family can also ask Beacon directly. Answers come only from the award letter and a plain-language glossary, with citations." |
| 1:50–2:15 | Decision Log and Flags panel. Hover a flag: its evidence turns and document lines light up. Point at a ladder history (nudged → spoken) and a cooldown or skipped-analysis entry. | "Under the hood, Gemini only perceives: possible misunderstandings with exact quotes. Plain Python decides: it checks every quote, dedupes, waits for the counselor first, and keeps a cooldown. Every decision is logged with its reason." |
| 2:15–2:40 | The call ends. The Family Recap appears. Hover a reference chip (e.g. L20) to light up its document line. Press **Read aloud** for a few seconds, then show **Download .md**. | "After the call, the family gets a plain-language recap: free money, loans, work-study, what's left to pay, deadlines, and what's still unclear, every number cited. It can be read aloud." |
| 2:40–2:45 | Back to the two windows. | "Beacon: the question the family won't ask, asked at the right moment." |

## Live beat: counselor controls (about 15 s, recorded separately)

The simulation has no clicks, so record this beat live. Cut it in after moment (a), and trim the
sped-up parts to keep 2:45.

1. Click **Reset**. Then click **Start call** in the counselor window.
2. Open the parent window (`/call?room=demo&role=parent`) next to it.
3. As the counselor, say "Daniel's total aid package is $31,500."
4. As the parent, say "Oh, thank goodness, so it's covered."
5. When the card appears, click **I'll clarify**. The button changes to "Beacon will wait for
   you".
6. As the counselor, clarify in your own words. For example: "To be clear, $14,000 of that is
   loans you'd repay."
7. The card turns green and shows "Clarified".

Narration: "The counselor stays in control: one click tells Beacon 'I've got this,' another says
'that's not an issue.' Every dismissal is logged, so false alarms become tuning data."

## If something goes wrong on camera

The observer shows why:

- The status chip at the top shows "analyzer unavailable: ...".
- The Decision Log has an error entry, for example "analysis through t7 failed after ... ms:
  LLMError: rate limited (429)". Or the log shows a card that the evidence gate dropped.

What to do:

1. If the error says "retry in Nh", the daily quota is gone. Wait for the reset, or use another
   key.
2. Otherwise, click **Reset**, wait one minute (the per-minute quota), and run the take again.
