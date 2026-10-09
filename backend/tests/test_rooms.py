"""Focused regressions for room turn-taking and the speech queue; no network or LLM calls."""

import asyncio
import json

from helpers import make_state, new_flag, output

from backend.app import config, policy, rooms
from backend.app.llm import FakeLLM
from backend.app.models import PttStart, PttStop, StatusMessage, TurnMessage


class Socket:
    def __init__(self):
        self.fail = False
        self.messages = []

    async def send_text(self, text):
        if self.fail:
            raise RuntimeError("closed socket")
        self.messages.append(json.loads(text))


def test_only_the_holding_socket_can_release_push_to_talk():
    async def run():
        room = rooms.Room(name="ptt")
        room.state.status.call_status = "live"
        holder, other, observer = Socket(), Socket(), Socket()
        room.clients = {holder: "parent", other: "parent", observer: "observer"}
        await rooms.handle(room, holder, "parent", PttStart(type="ptt_start"))
        await rooms.handle(room, other, "parent", PttStop(type="ptt_stop"))
        assert room.state.status.ptt_active == "parent"
        await rooms.disconnect(room, other)
        assert room.state.status.ptt_active == "parent"

        # A failed broadcast must release the floor too, even before the receive loop exits.
        holder.fail = True
        await rooms.broadcast(room, StatusMessage(status=room.state.status))
        await rooms.disconnect(room, holder)
        assert room.state.status.ptt_active is None
        assert observer.messages[-1]["status"]["ptt_active"] is None
        assert room.last_activity > 0

    asyncio.run(run())


def test_a_queued_line_for_a_dismissed_flag_is_not_spoken(monkeypatch):
    """flag_action() withdraws the line itself; this is the speaker loop's own check behind it."""
    monkeypatch.setattr(config, "PAUSE_BEFORE_SPEAK_MS", 0)

    async def run():
        room = rooms.Room(name="dismissed")
        room.state = make_state(("counselor", "Daniel's total aid package is $31,500."), ("parent", "So it's covered."))
        policy.after_analysis(room.state, output([new_flag(["t1", "t2"], ["So it's covered"])]), 2, 0)
        room.speech_queue.append(rooms.Speech(text="Quick check for Maria.", kind="flag", flag_id="f1"))
        policy.counselor_action(room.state, "f1", "dismiss", "t2", 0)
        await rooms._speaker_loop(room)
        assert [t.role for t in room.state.turns] == ["counselor", "parent"]
        assert room.state.log[-1].message == "skipped line for f1: it is already dismissed"

    asyncio.run(run())


def test_voice_gaps_leave_out_the_time_to_press_the_key(monkeypatch):
    monkeypatch.setattr(rooms, "llm", FakeLLM(lambda prompt, schema: output()))
    monkeypatch.setattr(config, "PTT_REACTION_MS", 600)

    async def run():
        room = rooms.Room(name="gaps")
        room.state.status.call_status = "live"
        sent = [
            ("counselor", 1_000, 2_000, "typed"),
            ("parent", 4_000, 5_000, "voice"),  # 2000 ms after t1, 600 of them reaching for the key
            ("counselor", 5_300, 6_000, "voice"),  # 300 ms: never below zero
            ("parent", 9_000, 9_500, "typed"),  # typed turns keep the whole gap
        ]
        for role, started, ended, source in sent:
            message = TurnMessage(type="turn", text="Hello.", started_at=started, ended_at=ended, source=source)
            await rooms.handle(room, Socket(), role, message)
        assert [t.gap_ms for t in room.state.turns] == [None, 1400, 0, 3000]
        rooms._cancel_tasks(room)

    asyncio.run(run())
