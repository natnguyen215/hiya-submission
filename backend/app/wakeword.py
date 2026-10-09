"""Finds the wake word ("Beacon") in a turn, and the question to Beacon."""

import re
from difflib import SequenceMatcher

from . import config

# Speech recognition does not often add "?". So the first word shows that it is a question.
QUESTION_WORDS = {
    "what", "whats", "how", "hows", "why", "when", "where", "wheres", "who", "whos", "which",
    "tell", "explain", "define", "remind",
}
# "Beacon, can you..." is a question, but "Beacon can help later" is not. A word such as "can"
# starts a question only if a subject ("you", "it", ...) comes after it.
AUXILIARIES = {"is", "are", "do", "does", "did", "can", "could", "should", "would", "will"}
SUBJECTS = {
    "i", "you", "we", "it", "they", "he", "she", "there", "this", "that", "these", "those",
    "the", "my", "our", "your", "his", "her", "their", "any",
}


def _is_question(rest: list[str], text: str) -> bool:
    if len(rest) < 2:
        return False
    if "?" in text or rest[0] in QUESTION_WORDS:
        return True
    return rest[0] in AUXILIARIES and rest[1] in SUBJECTS


def _words(text: str) -> list[str]:
    text = text.lower().replace("’", "'").replace("'", "")
    return re.findall(r"[a-z0-9]+", text)


def _is_wake_word(chunk: str) -> bool:
    for variant in config.WAKE_WORD_VARIANTS:
        target = variant.replace(" ", "").lower()
        if SequenceMatcher(None, chunk, target).ratio() >= config.WAKE_WORD_MIN_SIMILARITY:
            return True
    return False


def find_summon(text: str) -> str | None:
    """Return the question to Beacon. Return None if the turn is not a summon.

    Speech recognition can split the name ("bea con"). So each group of 1-3 words is joined and
    compared with the wake word. The question is the text after the wake word. If no text comes
    after it, the question is the text before it ("What's SAP, Beacon?").
    """
    words = _words(text)
    for start in range(len(words)):
        for size in (1, 2, 3):
            if start + size > len(words):
                break
            if _is_wake_word("".join(words[start : start + size])):
                rest = words[start + size :] or words[:start]
                return " ".join(rest) if _is_question(rest, text) else None
    return None
