"""Focused regressions for room turn-taking and log filenames; no network or LLM calls."""

import asyncio
import json

from helpers import make_state, new_flag, output

from backend.app import config, policy, rooms
from backend.app.models import PttStart, PttStop, SimTurn, StatusMessage


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


def test_push_to_talk_is_rejected_during_assistant_playback():
    async def run():
        room = rooms.Room(name="speaking")
        room.state.status.call_status = "live"
        room.state.status.speaking_turn_id = "t1"
        await rooms.handle(room, Socket(), "parent", PttStart(type="ptt_start"))
        assert room.state.status.ptt_active is None

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


def test_room_names_are_safe_in_log_filenames(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")

    async def run():
        room = rooms.Room(name="family/aid:room")
        try:
            await rooms.start_call(room, simulated=False)
            assert room.log_path.parent == config.LOGS_DIR
            assert room.log_path.is_file()
            assert ":" not in room.log_path.name
        finally:
            rooms._cancel_tasks(room)

    asyncio.run(run())


def test_call_tabs_cannot_submit_script_turns_as_another_persona():
    async def run():
        room = rooms.Room(name="roles")
        room.state.status.call_status = "live"
        for role in ("parent", "counselor"):
            message = SimTurn(type="sim_turn", role="parent", text="Spoofed turn", gap_ms=0)
            await rooms.handle(room, Socket(), role, message)
        assert room.state.turns == []

    asyncio.run(run())
