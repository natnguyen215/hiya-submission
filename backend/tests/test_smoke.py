"""Smoke tests: three WebSocket clients with the real app and a FakeLLM. They test broadcasts, who
sees flag cards, escalation to beacon_say, the counselor's card buttons, and a summon during the
cooldown."""

import json
import time
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from helpers import new_flag, output

from backend.app import config, rooms
from backend.app.llm import FakeLLM
from backend.app.main import app
from backend.app.models import AnalyzerOutput, SummonAnswer


def fake_llm_reply(prompt, schema):
    if schema is SummonAnswer:
        return SummonAnswer(answer="A Parent PLUS loan is one you borrow; it's optional.", answered_from_documents=True, doc_refs=["G9"])
    if schema is AnalyzerOutput and "so it's covered" in prompt:  # dedupe ignores the repeats
        return output([new_flag(["t2", "t3"], ["so it's covered", "aid package is $31,500"])])
    return output()


@pytest.fixture
def connect(monkeypatch, tmp_path):
    """Yields join(room, role) -> an open WebSocket that has received its snapshot."""
    monkeypatch.setattr(config, "PAUSE_BEFORE_SPEAK_MS", 0)
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(rooms, "llm", FakeLLM(fake_llm_reply))
    rooms.rooms.clear()
    # One TestClient context is one event loop for all WebSockets, as in a real server.
    # The ExitStack closes all sockets if an assertion fails. If a message never comes,
    # receive_until waits, and the timeout in pytest.ini makes the test fail.
    with TestClient(app) as client, ExitStack() as sockets:

        def join(room, role):
            ws = sockets.enter_context(client.websocket_connect("/ws"))
            ws.send_json({"type": "join", "room": room, "role": role})
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot" and snapshot["role"] == role
            return ws

        yield join


def receive_until(ws, message_type, where=lambda message: True):
    """Read messages until one of the given type (that also passes `where`) arrives; return it and
    everything before it."""
    seen = []
    while True:
        message = ws.receive_json()
        seen.append(message)
        if message["type"] == message_type and where(message):
            return message, seen


def typed(text):
    """A typed turn, stamped like the browser does: started at the first keystroke (just now). The
    ladder only counts a counselor turn that started after the card appeared."""
    now = rooms.now_ms()
    return {"type": "turn", "text": text, "started_at": now, "ended_at": now, "source": "typed"}


def start_call(counselor, everyone):
    counselor.send_json({"type": "start_call", "simulated": False})
    for ws in everyone:
        say, _ = receive_until(ws, "beacon_say")
    assert "I'm Beacon" in say["text"]
    counselor.send_json({"type": "beacon_playback_done", "turn_id": say["turn_id"]})


def test_turns_broadcast_cards_go_to_counselor_and_observer_and_escalation_speaks(connect):
    counselor, parent, observer = (connect("smoke", r) for r in ("counselor", "parent", "observer"))
    everyone = (counselor, parent, observer)
    start_call(counselor, everyone)

    counselor.send_json(typed("Daniel's total aid package is $31,500."))
    for ws in everyone:
        added, _ = receive_until(ws, "turn_added")
        assert added["turn"]["role"] == "counselor"

    parent.send_json(typed("Oh, thank goodness, so it's covered."))
    card, _ = receive_until(counselor, "flag_card")
    assert card["flag"]["state"] == "nudged"
    receive_until(observer, "flag_card")

    # The counselor moves on and does not clarify, so Beacon asks at the next pause.
    counselor.send_json(typed("Next, housing is $16,500."))
    say, _ = receive_until(observer, "beacon_say")
    assert say["text"] == "Quick check for Maria: how much of that is loans?"
    _, parent_messages = receive_until(parent, "beacon_say")
    assert "flag_card" not in [m["type"] for m in parent_messages]
    updated, _ = receive_until(counselor, "flag_updated")
    assert updated["flag"]["state"] == "spoken"


def open_card(counselor, parent, observer):
    """Start a call and plant the "so it's covered" misunderstanding; return the nudged flag."""
    start_call(counselor, (counselor, parent, observer))
    counselor.send_json(typed("Daniel's total aid package is $31,500."))
    receive_until(counselor, "turn_added")
    parent.send_json(typed("Oh, thank goodness, so it's covered."))
    card, _ = receive_until(counselor, "flag_card")
    receive_until(observer, "flag_card")
    return card["flag"]


def test_counselor_dismisses_a_card_and_beacon_stays_silent(connect):
    counselor, parent, observer = (connect("dismiss", r) for r in ("counselor", "parent", "observer"))
    flag = open_card(counselor, parent, observer)

    counselor.send_json({"type": "flag_action", "flag_id": flag["id"], "action": "dismiss"})
    for ws in (counselor, observer):
        updated, _ = receive_until(ws, "flag_updated")
        assert (updated["flag"]["state"], updated["flag"]["counselor_action"]) == ("dismissed", "dismissed")

    # The counselor moves on. Nothing is open, so there is no analysis and Beacon says nothing.
    counselor.send_json(typed("Next, housing is $16,500."))
    _, observer_messages = receive_until(observer, "decision_log", lambda m: "skipped LLM for t4" in m["entry"]["message"])
    assert "beacon_say" not in [m["type"] for m in observer_messages]
    _, parent_messages = receive_until(parent, "turn_added", lambda m: m["turn"]["id"] == "t4")
    assert not {"flag_card", "flag_updated", "decision_log", "error"} & {m["type"] for m in parent_messages}

    # The log file has the click and the full flag, as a labeled example for tuning.
    records = [json.loads(line) for line in rooms.get_room("dismiss").log_path.read_text(encoding="utf-8").splitlines()]
    [feedback] = [r for r in records if r["type"] == "counselor_feedback"]
    assert (feedback["action"], feedback["turn_id"], feedback["flag"]["state"]) == ("dismiss", "t3", "dismissed")
    assert feedback["flag"]["evidence_quotes"] == flag["evidence_quotes"]


def test_will_clarify_withdraws_a_queued_interjection(connect):
    counselor, parent, observer = (connect("clarify", r) for r in ("counselor", "parent", "observer"))
    flag = open_card(counselor, parent, observer)
    room = rooms.get_room("clarify")

    # The parent holds push-to-talk, so Beacon's line stays in the queue.
    parent.send_json({"type": "ptt_start"})
    receive_until(observer, "status", lambda m: m["status"]["ptt_active"] == "parent")
    counselor.send_json(typed("Next, housing is $16,500."))
    receive_until(observer, "status", lambda m: m["status"]["speech_pending"] == 1)

    counselor.send_json({"type": "flag_action", "flag_id": flag["id"], "action": "will_clarify"})
    updated, _ = receive_until(counselor, "flag_updated")
    assert (updated["flag"]["state"], updated["flag"]["counselor_action"]) == ("nudged", "will_clarify")
    assert updated["flag"]["ladder_start_turn"] == "t4"
    receive_until(observer, "decision_log", lambda m: "withdrew queued line for f1" in m["entry"]["message"])
    assert room.speech_queue == []

    # Nobody holds push-to-talk now. The speaker loop (it checks every 100 ms) has nothing to say.
    parent.send_json({"type": "ptt_stop"})
    time.sleep(0.3)
    counselor.send_json({"type": "end_call"})
    _, seen = receive_until(observer, "status", lambda m: m["status"]["call_status"] == "ended")
    assert "beacon_say" not in [m["type"] for m in seen]
    assert [t.role for t in room.state.turns].count("beacon") == 1  # only the opening line


def test_summon_skips_the_cooldown(connect):
    counselor, parent = (connect("summon", r) for r in ("counselor", "parent"))
    start_call(counselor, (counselor, parent))
    rooms.get_room("summon").state.last_spoken_at = rooms.now_ms()  # the cooldown is active

    parent.send_json(typed("Beacon, what's a Parent PLUS loan?"))
    say, _ = receive_until(parent, "beacon_say")
    assert "Parent PLUS" in say["text"]


def test_turns_are_rejected_before_the_call_starts(connect):
    parent = connect("early", "parent")
    parent.send_json(typed("Hello?"))
    assert parent.receive_json() == {"type": "error", "message": "Start the call first."}
