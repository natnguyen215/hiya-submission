"""All the settings that you can tune. To change a setting, set an environment variable with the
same name, or add a line to .env. You do not need to change the code."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _setting(name: str, default):
    """Read the environment variable, and convert it to the type of the default. A list is
    comma-separated."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    if isinstance(default, list):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return type(default)(raw)


# Paths
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"
PROMPTS_DIR = ROOT / "backend" / "prompts"
LOGS_DIR = ROOT / "logs"
CACHE_DIR = ROOT / ".cache"
WEB_DIST = ROOT / "web" / "dist"

# LLM
GEMINI_API_KEY = _setting("GEMINI_API_KEY", "")
GEMINI_MODEL = _setting("GEMINI_MODEL", "gemini-3.5-flash-lite")
# minimal | low | medium | high, or "none" for no thinking level (2.5 models do not accept one).
GEMINI_THINKING_LEVEL = _setting("GEMINI_THINKING_LEVEL", "low")
MIN_SECONDS_BETWEEN_LLM_CALLS = _setting("MIN_SECONDS_BETWEEN_LLM_CALLS", 4.0)
ANALYZER_TIMEOUT_SECONDS = _setting("ANALYZER_TIMEOUT_SECONDS", 15.0)
# A question to Beacon can need more time than an analysis.
SUMMON_TIMEOUT_SECONDS = _setting("SUMMON_TIMEOUT_SECONDS", 25.0)
RECAP_TIMEOUT_SECONDS = _setting("RECAP_TIMEOUT_SECONDS", 60.0)
# After a 429 error, all calls wait this long. Free-tier quotas reset each minute.
LLM_BACKOFF_SECONDS = _setting("LLM_BACKOFF_SECONDS", 20.0)

# Escalation ladder and turn-taking
ESCALATE_AFTER_COUNSELOR_TURNS = _setting("ESCALATE_AFTER_COUNSELOR_TURNS", 1)
STALE_AFTER_TURNS = _setting("STALE_AFTER_TURNS", 3)
# "I'll clarify" gives the counselor this number of more turns before Beacon can speak.
CLARIFY_GRACE_COUNSELOR_TURNS = _setting("CLARIFY_GRACE_COUNSELOR_TURNS", 1)
# Two, not one. Sometimes the analyzer finds an answer one analysis late. With one, the card can
# appear just after the counselor answered, and Beacon can then ask a question that has an answer.
# With ESCALATE_AFTER_COUNSELOR_TURNS = 1, Beacon asks after the third counselor turn with no answer.
UNANSWERED_AFTER_COUNSELOR_TURNS = _setting("UNANSWERED_AFTER_COUNSELOR_TURNS", 2)
SPEAK_COOLDOWN_SECONDS = _setting("SPEAK_COOLDOWN_SECONDS", 20.0)
PAUSE_BEFORE_SPEAK_MS = _setting("PAUSE_BEFORE_SPEAK_MS", 700)
# If no tab tells the server that Beacon finished, the server waits 2 s plus this time per word.
PLAYBACK_FALLBACK_MS_PER_WORD = _setting("PLAYBACK_FALLBACK_MS_PER_WORD", 800)
SPOKEN_WORDS_WARNING = _setting("SPOKEN_WORDS_WARNING", 25)

# Evidence gate: a quote is in a turn if it is this similar to a part of the turn. Small
# differences pass (punctuation, one word). A quote that the LLM made up does not pass.
QUOTE_MIN_SIMILARITY = _setting("QUOTE_MIN_SIMILARITY", 0.85)

# Signals and simulation
NOTABLE_GAP_MS = _setting("NOTABLE_GAP_MS", 2000)
# The pause before a voice turn includes the time to press the push-to-talk key. The server
# subtracts this time from voice turns only. Typed and script turns keep their full pause.
PTT_REACTION_MS = _setting("PTT_REACTION_MS", 600)
SIM_MAX_WAIT_FOR_ANALYSIS_SECONDS = _setting("SIM_MAX_WAIT_FOR_ANALYSIS_SECONDS", 12.0)

# Wake word: compare each group of 1-3 words (spaces removed) with these spellings.
# Do not add similar-sounding spellings. With them, "beckon" would match (it scores 0.83).
WAKE_WORD_VARIANTS = _setting("WAKE_WORD_VARIANTS", ["beacon"])
WAKE_WORD_MIN_SIMILARITY = _setting("WAKE_WORD_MIN_SIMILARITY", 0.85)

# Names and fixed lines
COUNSELOR_NAME = _setting("COUNSELOR_NAME", "Alex")
PARENT_NAME = _setting("PARENT_NAME", "Maria")
# The opening line says that an AI listens, and how to ask it: the name first, then a question.
OPENING_LINE = _setting(
    "OPENING_LINE",
    "Hi, I'm Beacon, an AI assistant listening to help keep things clear. "
    "Ask me about anything on the award letter: just start with my name.",
)
SUMMON_FAILED_LINE = _setting(
    "SUMMON_FAILED_LINE", "Sorry, I couldn't look that up just now. {counselor}, could you answer that?"
)
# A summon needs only the recent turns, to know what "that" or "it" means. The facts are in the documents.
SUMMON_CONTEXT_TURNS = _setting("SUMMON_CONTEXT_TURNS", 12)
# Code finds unanswered questions, not the LLM. So their text comes from these templates.
UNANSWERED_CARD = _setting(
    "UNANSWERED_CARD", "{parent} asked a question that hasn't been answered yet: “{question}”"
)
UNANSWERED_CLARIFICATION = _setting("UNANSWERED_CLARIFICATION", "Answer {parent}'s question before moving on.")
UNANSWERED_LINE = _setting("UNANSWERED_LINE", "Quick check: {parent} asked, “{question}” Could we cover that?")
