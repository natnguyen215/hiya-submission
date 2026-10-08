# Demo video run-of-show (2:45)

**Setup before recording:** `make run` (or `python tasks.py run`) with a Gemini key in `.env`.
Chrome window 1: observer (`/observer?room=demo`), left two-thirds of the screen. Chrome window 2:
counselor (`/call?room=demo&role=counselor`), right third. Click once inside the counselor window
so its "Click anywhere..." audio notice goes away (in a simulation the observer plays every voice
anyway). In the observer pick `demo_call`, untick "Text only (no audio)", and click once in the
observer too. Do one full rehearsal run first to check that every moment lands. The full simulated
call runs about 5 minutes with audio, so record it once and speed up the stretches between
highlights (2–4×) in editing.

| Time | On screen | Narration (suggested) |
|---|---|---|
| 0:00–0:15 | Title card, then the award letter in the Documents panel | "When a financial aid counselor says 'your aid package is $31,500,' a first-generation parent often hears 'it's covered.' $14,000 of it is loans. Families rarely ask. Beacon asks for them." |
| 0:15–0:25 | Press **Play**. Beacon's opening line plays. | "Beacon joins the call, says it's an AI assistant, and teaches its name. It works for the family's understanding, like a patient advocate." |
| 0:25–0:50 | Moment (a): Maria: "So it's covered." A card appears in the counselor window. Alex clarifies; the card turns green "Clarified". | "First it nudges the counselor privately, with a suggested clarification. Alex fixes it, so Beacon never says a word. That's the common case." |
| 0:50–1:15 | Moment (b): "Oh good, so we're verified?" Alex moves on to housing. Beacon, at the pause: "Quick check for Maria: ..." Alex answers. | "Here the counselor moves on. Beacon waits for a pause and asks one short question, on Maria's behalf, to the counselor. It asks; it doesn't answer for the school." |
| 1:15–1:30 | Moment (c): the **3.0s pause** badge before Maria's "...okay." | "This is something only voice carries: a three-second pause before 'okay.' Beacon treats hesitation as a signal. Alex sees the card and explains SAP." |
| 1:30–1:50 | Moment (e): "Beacon, what's a Parent PLUS loan?" Spoken answer; point at its Decision Log entry, "answer (documents G9, L15)", which lists the cited lines (expand "data" for the full answer). | "The family can also ask Beacon directly. Answers come only from the award letter and a plain-language glossary, with citations." |
| 1:50–2:15 | Decision Log and Flags panel. Hover a flag: its evidence turns and document lines light up. Point at a ladder history (nudged → spoken) and a cooldown or skipped-analysis entry. | "Under the hood, Gemini only perceives: possible misunderstandings with exact quotes. Plain Python decides: it checks every quote, dedupes, waits for the counselor first, and keeps a cooldown. Every decision is logged with its reason." |
| 2:15–2:40 | The call ends. The Family Recap appears. Hover a reference chip (e.g. L20) to light up its document line. Press **Read aloud** for a few seconds, then show **Download .md**. | "After the call, the family gets a plain-language recap: free money, loans, work-study, what's left to pay, deadlines, and what's still unclear, every number cited. It can be read aloud." |
| 2:40–2:45 | Back to the two windows. | "Beacon: the question the family won't ask, asked at the right moment." |

**Live beat: counselor controls (about 15 s, recorded separately).** The simulation has no
clicks, so record this one live and cut it in after moment (a), trimming the sped-up stretches to
keep 2:45. Reset the room and click **Start call** in the counselor window, with the parent window
(`/call?room=demo&role=parent`) open beside it. Counselor: "Daniel's total aid package is $31,500."
Parent: "Oh, thank goodness, so it's covered." When the "so it's covered" card appears, click
**I'll clarify** (the button becomes "Beacon will wait for you"), then clarify in your own words
as the counselor, for example "To be clear, $14,000 of that is loans you'd repay." The card turns
green, "Clarified". Narration: "The counselor stays in control: one click tells Beacon 'I've got
this,' another says 'that's not an issue.' Every dismissal is logged, so false alarms become
tuning data."

**If something goes wrong on camera:** the observer says why. The status chip at the top shows
"analyzer unavailable: ..." and the Decision Log has an error entry such as "analysis through t7
failed after ... ms: LLMError: rate limited (429)", or a flag dropped by the evidence gate. Reset,
wait a minute for the free-tier quota, and run again.
