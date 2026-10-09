"""Reads the documents (the award letter and the glossary). Each numbered line has an id, such as
"L14" or "G9". The code uses the ids to check and show citations."""

import re

from pydantic import BaseModel

from . import config

DOCUMENT_FILES = ["award_letter.md", "glossary.md"]
NUMBERED_LINE = re.compile(r"^- ([A-Z]\d+) (.+)$")


class DocLine(BaseModel):
    doc: str
    id: str
    text: str


def _load() -> tuple[str, dict[str, DocLine]]:
    full_text, lines = [], {}
    for name in DOCUMENT_FILES:
        content = (config.DATA_DIR / name).read_text(encoding="utf-8")
        full_text.append(f"=== {name} ===\n{content.strip()}")
        for raw in content.splitlines():
            match = NUMBERED_LINE.match(raw.strip())
            if match:
                lines[match.group(1)] = DocLine(doc=name, id=match.group(1), text=match.group(2))
    return "\n\n".join(full_text), lines


# Read once, at import. The documents do not change while the server runs.
DOCUMENTS_TEXT, LINES = _load()
