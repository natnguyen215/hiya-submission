"""The one list of things Beacon watches for. Adding a trigger means adding an entry here: an
LLM-detected trigger is rendered into the analyzer prompt automatically (name, description,
examples and evidence rule) and policy.py reads its evidence rule from here; a code-detected
trigger documents which function detects it."""

from typing import Literal

from pydantic import BaseModel


class Trigger(BaseModel):
    name: str
    detected_by: Literal["llm", "code"]
    description: str
    positive_examples: list[str]  # should raise the trigger
    negative_examples: list[str]  # look similar but should not
    # The evidence gate requires a cited parent turn, and the LLM can be skipped after counselor
    # turns, only while every LLM trigger is shown by the parent's reply.
    needs_parent_evidence: bool = True


TRIGGERS = [
    Trigger(
        name="MISREAD_TERM",
        detected_by="llm",
        description=(
            "The parent's own words show a wrong understanding of something the counselor said "
            "(a term, an amount, a status, or a requirement)."
        ),
        positive_examples=[
            "Counselor: Your subsidized loan won't build interest while he's enrolled at least "
            "half-time. / Parent: Oh nice, so there's no interest on it ever.",
            "Counselor: The scholarship is renewable if he keeps a 3.0. / Parent: Great, so it's "
            "guaranteed all four years.",
        ],
        negative_examples=[
            "Parent restates correctly: So the grants we never pay back, but the loans we do.",
            "Parent asks a clarifying question instead of assuming: Wait, is the loan part of that "
            "number?",
        ],
    ),
    Trigger(
        name="UNEXPLAINED_JARGON",
        detected_by="llm",
        description=(
            "The counselor used a term or acronym a first-generation family likely doesn't know, "
            "did not explain it, and the parent responded passively ('okay', 'mm-hm', 'got it'), "
            "hesitated, or changed the subject. A long pause before the reply strengthens this."
        ),
        positive_examples=[
            "Counselor: He'll need to finish entrance counseling and sign the MPN before "
            "disbursement. / Parent (after a long pause): ...Mm-hm.",
        ],
        negative_examples=[
            "Counselor explains right away: The COA, the cost of attendance, is the full yearly "
            "cost including housing. / Parent: Okay.",
            "'Mm-hm' after a simple logistics sentence: Counselor: You'll get an email with a link. "
            "/ Parent: Mm-hm.",
            "The parent engages with substance, so the term didn't block understanding.",
        ],
    ),
    Trigger(
        name="UNANSWERED_QUESTION",
        detected_by="code",
        description=(
            "The analyzer only reports which parent questions were asked and which were answered. "
            "policy.py counts counselor turns and raises this when a question stays unanswered for "
            "UNANSWERED_AFTER_COUNSELOR_TURNS counselor turns."
        ),
        positive_examples=[
            "Parent: Does the work-study have to be paid back? / Counselor: Next, the portal... / "
            "(no answer)",
        ],
        negative_examples=[
            "Parent: Is that per year? / Counselor: Yes, per year.",
        ],
    ),
    Trigger(
        name="SUMMON",
        detected_by="code",
        description=(
            "A turn contains the wake word followed by a question. wakeword.find_summon() detects "
            "it; analyzer.answer_summon() answers from the documents. Skips the ladder and cooldown."
        ),
        positive_examples=["Beacon, what's a Parent PLUS loan?", "Beacon, what does SAP mean?"],
        negative_examples=["Could you pass the can of peas?", "He'll live on campus."],
    ),
]

LLM_TRIGGER_NAMES = [t.name for t in TRIGGERS if t.detected_by == "llm"]
PARENT_EVIDENCED = {t.name for t in TRIGGERS if t.detected_by == "llm" and t.needs_parent_evidence}
