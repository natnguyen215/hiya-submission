"""Unit tests for analyzer.py with a FakeLLM: prompt contents, retry on invalid output, failure
handling, and the recap number check."""

import asyncio

from helpers import make_state, output

from backend.app import analyzer, config
from backend.app.llm import FakeLLM, LLMError
from backend.app.models import ParentQuestion, Recap, RecapFollowUp, RecapItem, SummonAnswer


def test_prompt_includes_triggers_examples_and_pauses():
    state = make_state(("counselor", "He needs SAP."), ("parent", "...okay."))
    state.turns[1].gap_ms = 3100
    prompt = analyzer.build_analysis_prompt(state)
    assert "MISREAD_TERM" in prompt and "UNEXPLAINED_JARGON" in prompt
    assert "UNANSWERED_QUESTION:" not in prompt  # code-detected triggers are not the LLM's job
    assert "Do not flag:" in prompt
    assert "t2 PARENT (Maria) [after 3100 ms, LONG PAUSE]: ...okay." in prompt
    assert "{{" not in prompt  # every placeholder was filled


def test_invalid_output_is_retried_once():
    replies = iter(["not json", output().model_dump_json()])
    fake = FakeLLM(lambda prompt, schema: next(replies))
    result = asyncio.run(analyzer.analyze(fake, make_state(("parent", "Hi."))))
    assert result.error is None and len(fake.prompts) == 2


def test_invalid_twice_becomes_an_empty_result_with_an_error():
    fake = FakeLLM(lambda prompt, schema: "{}")
    result = asyncio.run(analyzer.analyze(fake, make_state(("parent", "Hi."))))
    assert result.output == analyzer.EMPTY_OUTPUT
    assert "invalid AnalyzerOutput" in result.error


def test_llm_failure_never_raises():
    def fail(prompt, schema):
        raise LLMError("rate limited (429)")

    result = asyncio.run(analyzer.analyze(FakeLLM(fail), make_state(("parent", "Hi."))))
    assert "429" in result.error and result.turn_count == 1


def test_summon_timeout_is_independent_of_analyzer_timeout(monkeypatch):
    monkeypatch.setattr(config, "ANALYZER_TIMEOUT_SECONDS", 11.0)
    monkeypatch.setattr(config, "SUMMON_TIMEOUT_SECONDS", 37.0)
    timeouts = []

    class RecordingLLM(FakeLLM):
        async def generate_json(self, prompt, schema, timeout_s):
            timeouts.append(timeout_s)
            return await super().generate_json(prompt, schema, timeout_s)

    answer = SummonAnswer(answer="The documents cover aid and requirements.", doc_refs=[], answered_from_documents=True)
    fake = RecordingLLM(lambda prompt, schema: answer if schema is SummonAnswer else output())
    state = make_state(("parent", "Beacon, what is all the info that you have?"))
    assert asyncio.run(analyzer.analyze(fake, state)).error is None
    assert asyncio.run(analyzer.answer_summon(fake, state, state.turns[0])) == answer
    assert timeouts == [11.0, 37.0]


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


def test_open_issues_the_recap_left_out_are_added():
    recap = Recap(
        cost_of_attendance=item("Total cost", "$38,000", ["L3"]),
        grants=[],
        loans=[],
        work_study=[],
        still_to_pay=[],
        todos=[],
        follow_ups=[RecapFollowUp(question="What is SAP?", refs=["t9"])],
    )
    state = make_state(("parent", "Is that per year?"))
    state.parent_questions.append(ParentQuestion(text="Is that per year?", asked_turn_id="t1"))
    assert analyzer.add_missing_follow_ups(recap, state) == ["t1"]
    assert recap.follow_ups[-1].question == "Is that per year?"
