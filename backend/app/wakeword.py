"""Detects the wake word ("Beacon") in a turn and extracts the question addressed to it."""

import re
from difflib import SequenceMatcher

from . import config

# Speech recognition rarely adds "?", so a question is recognized by how it starts.
QUESTION_WORDS = {
    "what", "whats", "how", "hows", "why", "when", "where", "wheres", "who", "whos", "which",
    "tell", "explain", "define", "remind",
}
# "Beacon, can you..." is a question but "Beacon can help later" is not: an auxiliary only
# starts a question when a subject follows it.
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
    """Return the question addressed to Beacon, or None if the turn is not a summon.

    Recognition may split the name ("bea con"), so windows of 1-3 words are joined and fuzzy
    matched. The question is the text after the wake word, or before it if nothing follows
    ("What's SAP, Beacon?").
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
