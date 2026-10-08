"""Integration smoke test: three WebSocket clients against the real app with a FakeLLM. Covers
broadcasting, who sees flag cards, escalation to beacon_say, and summon skipping the cooldown."""

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
    if schema is AnalyzerOutput and "so it's covered" in prompt:  # repeats are ignored by dedupe
        return output([new_flag(["t2", "t3"], ["so it's covered", "aid package is $31,500"])])
    return output()


@pytest.fixture
def connect(monkeypatch, tmp_path):
    """Yields join(room, role) -> an open WebSocket that has received its snapshot."""
    monkeypatch.setattr(config, "PAUSE_BEFORE_SPEAK_MS", 0)
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(rooms, "llm", FakeLLM(fake_llm_reply))
    rooms.rooms.clear()
    # One TestClient context = one event loop shared by every WebSocket, like a real server.
    # The ExitStack closes every socket when an assertion fails; a message that never arrives
    # would block in receive_until, which pytest.ini's timeout turns into a failure.
    with TestClient(app) as client, ExitStack() as sockets:

        def join(room, role):
            ws = sockets.enter_context(client.websocket_connect("/ws"))
            ws.send_json({"type": "join", "room": room, "role": role})
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot" and snapshot["role"] == role
            return ws

        yield join


def receive_until(ws, message_type):
    """Read messages until one of the given type arrives; return it and everything before it."""
    seen = []
    while True:
        message = ws.receive_json()
        seen.append(message)
        if message["type"] == message_type:
            return message, seen


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

    counselor.send_json({"type": "turn", "text": "Daniel's total aid package is $31,500.", "started_at": 1, "ended_at": 2, "source": "typed"})
    for ws in everyone:
        added, _ = receive_until(ws, "turn_added")
        assert added["turn"]["role"] == "counselor"

    parent.send_json({"type": "turn", "text": "Oh, thank goodness, so it's covered.", "started_at": 3, "ended_at": 4, "source": "typed"})
    card, _ = receive_until(counselor, "flag_card")
    assert card["flag"]["state"] == "nudged"
    receive_until(observer, "flag_card")

    # The counselor moves on without clarifying, so Beacon asks at the next pause.
    counselor.send_json({"type": "turn", "text": "Next, housing is $16,500.", "started_at": 5, "ended_at": 6, "source": "typed"})
    say, _ = receive_until(observer, "beacon_say")
    assert say["text"] == "Quick check for Maria: how much of that is loans?"
    _, parent_messages = receive_until(parent, "beacon_say")
    assert "flag_card" not in [m["type"] for m in parent_messages]
    updated, _ = receive_until(counselor, "flag_updated")
    assert updated["flag"]["state"] == "spoken"


def test_summon_skips_the_cooldown(connect):
    counselor, parent = (connect("summon", r) for r in ("counselor", "parent"))
    start_call(counselor, (counselor, parent))
    rooms.get_room("summon").state.last_spoken_at = rooms.now_ms()  # cooldown is active

    parent.send_json({"type": "turn", "text": "Beacon, what's a Parent PLUS loan?", "started_at": 1, "ended_at": 2, "source": "typed"})
    say, _ = receive_until(parent, "beacon_say")
    assert "Parent PLUS" in say["text"]


def test_turns_are_rejected_before_the_call_starts(connect):
    parent = connect("early", "parent")
    parent.send_json({"type": "turn", "text": "Hello?", "started_at": 1, "ended_at": 2, "source": "typed"})
    assert parent.receive_json() == {"type": "error", "message": "Start the call first."}
