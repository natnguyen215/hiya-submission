"""Unit tests for analyzer.py with a FakeLLM: prompt contents, retry on invalid output, failure
handling, and the recap number check."""

import asyncio
import json
import re

from helpers import make_state, output

from backend.app import analyzer, config
from backend.app.llm import FakeLLM, LLMError
from backend.app.models import Recap, RecapItem, SummonAnswer
from backend.app.triggers import TRIGGERS


def test_prompt_renders_llm_triggers_word_for_word_and_marks_pauses():
    state = make_state(("counselor", "He needs SAP."), ("parent", "...okay."))
    state.turns[1].gap_ms = 3100
    prompt = analyzer.build_analysis_prompt(state)
    for trigger in TRIGGERS:
        if trigger.detected_by != "llm":
            assert f"{trigger.name}:" not in prompt  # code-detected triggers are not the LLM's job
            continue
        assert f"{trigger.name}: {trigger.description}" in prompt
        for example in trigger.positive_examples:
            assert f"  Flag: {example}" in prompt
        for example in trigger.negative_examples:
            assert f"  Do not flag: {example}" in prompt
    assert "t2 PARENT (Maria) [after 3100 ms, LONG PAUSE]: ...okay." in prompt
    assert "{{" not in prompt  # every placeholder was filled


def test_invalid_output_is_retried_once():
    replies = iter(["not json", output().model_dump_json()])
    fake = FakeLLM(lambda prompt, schema: next(replies))
    result = asyncio.run(analyzer.analyze(fake, make_state(("parent", "Hi."))))
    assert result.error is None and len(fake.prompts) == 2

    result = asyncio.run(analyzer.analyze(FakeLLM(lambda prompt, schema: "{}"), make_state(("parent", "Hi."))))
    assert result.output == analyzer.EMPTY_OUTPUT
    assert "invalid AnalyzerOutput" in result.error


def test_llm_failure_never_raises():
    def fail(prompt, schema):
        raise LLMError("rate limited (429)")

    result = asyncio.run(analyzer.analyze(FakeLLM(fail), make_state(("parent", "Hi."))))
    assert "429" in result.error and result.turn_count == 1


def item(label, amount, refs):
    return RecapItem(label=label, amount=amount, note="", refs=refs)


def test_recap_numbers_are_checked_against_citations():
    recap = Recap(
        cost_of_attendance=item("Total cost", "$38,000", ["L3"]),
        grants=[item("Westbrook Grant", "$9,000", ["L10"]), item("Pell Grant", "$7,000", ["L11"])],
        loans=[],
        work_study=[item("Work-study", "$2,500", ["t2"])],
        still_to_pay=[],
        todos=[],
        follow_ups=[],
    )
    state = make_state(("counselor", "Hello."), ("counselor", "Work-study is $2,500."))
    assert analyzer.unverified_numbers(recap, state) == ["Pell Grant: 7000 not found in L11"]


def _six_word_phrases(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9$]+", text.lower().replace("’", "'").replace("'", ""))
    return {" ".join(words[i : i + 6]) for i in range(len(words) - 5)}


def test_prompt_examples_do_not_reuse_script_lines():
    # The eval would only measure memorization if the prompt's examples copied the scripts.
    template = (config.PROMPTS_DIR / "analyzer.txt").read_text(encoding="utf-8").split("## Documents")[0]
    examples = [e for t in TRIGGERS if t.detected_by == "llm" for e in t.positive_examples + t.negative_examples]
    prompt_phrases = _six_word_phrases(template + "\n".join(examples))
    for path in config.SCRIPTS_DIR.glob("*.json"):
        for line in json.loads(path.read_text(encoding="utf-8")):
            shared = prompt_phrases & _six_word_phrases(line["text"])
            assert not shared, f"{path.name} {line['id']} shares {shared} with the analyzer prompt"


def test_summon_prompt_is_filled_and_unknown_refs_are_removed():
    state = make_state(("parent", "Beacon, what is all the info that you have"))
    fake = FakeLLM(lambda prompt, schema: SummonAnswer(answer="Ok.", doc_refs=["G1", "X9"], answered_from_documents=True))
    answer = asyncio.run(analyzer.answer_summon(fake, state, state.turns[0]))
    assert answer.doc_refs == ["G1"]  # an id that isn't a document line is removed
    assert "{{" not in fake.prompts[0] and "Beacon, what is all the info that you have" in fake.prompts[0]
