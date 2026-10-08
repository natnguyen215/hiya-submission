"""In-memory call rooms: connected tabs, shared state, broadcasting, the per-room analysis loop,
the speech queue, and the decision log. policy.py decides what Beacon does; this module carries
those decisions out and owns the timing (one analysis at a time, speaking only at a pause)."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import WebSocket
from pydantic import BaseModel

from . import analyzer, config, policy, wakeword
from .llm import LLM, GeminiLLM
from .models import (
    BeaconSay,
    ClientRole,
    DecisionLog,
    EndCall,
    ErrorMessage,
    Flag,
    FlagAction,
    FlagCard,
    FlagUpdated,
    LogEntry,
    PlaybackDone,
    PttStart,
    PttStop,
    RecapReady,
    ResetRoom,
    RoomState,
    Settings,
    SimTurn,
    Snapshot,
    StartCall,
    StatusMessage,
    Turn,
    TurnAdded,
    TurnMessage,
)

# One LLM client per process (the free-tier quota is per API key). Tests swap in a FakeLLM.
llm: LLM = GeminiLLM()


@dataclass
class Speech:
    text: str
    kind: Literal["opening", "summon", "flag"]
    flag_id: str | None = None


@dataclass
class Room:
    """A room's serializable state plus the runtime machinery that can't be serialized."""

    name: str
    state: RoomState = field(default_factory=RoomState)
    clients: dict[WebSocket, ClientRole] = field(default_factory=dict)
    speech_queue: list[Speech] = field(default_factory=list)
    summons_in_progress: int = 0
    analysis_task: asyncio.Task | None = None
    analysis_dirty: bool = False  # a turn arrived while an analysis was running
    speaker_task: asyncio.Task | None = None
    background: set[asyncio.Task] = field(default_factory=set)  # summon answers, recap
    last_activity: float = 0.0  # monotonic time of the last turn, push-to-talk release, or speech
    playback_done: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    log_path: Path | None = None
    analyzed_ok: int = 0  # transcript length covered by the last successful (or skipped) analysis


rooms: dict[str, Room] = {}


def get_room(name: str) -> Room:
    if name not in rooms:
        rooms[name] = Room(name=name)
    return rooms[name]


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------- sending


def _counselor_sees(flag: Flag) -> bool:
    """The counselor only gets cards for flags that reached the nudge stage."""
    return any(event.state == "nudged" for event in flag.history)


def _state_for(state: RoomState, role: ClientRole) -> RoomState:
    if role == "observer":
        return state
    flags = [f for f in state.flags if _counselor_sees(f)] if role == "counselor" else []
    return state.model_copy(update={"flags": flags, "log": []})


async def broadcast(room: Room, message: BaseModel, roles: set[str] | None = None) -> None:
    data = message.model_dump_json()
    # One broadcast at a time, so every tab receives messages in the order they were produced
    # (a newer status can't overtake an older one while a send to another tab is in progress).
    async with room.send_lock:
        for ws, role in list(room.clients.items()):
            if roles is None or role in roles:
                try:
                    await ws.send_text(data)
                except Exception:
                    room.clients.pop(ws, None)  # the tab went away mid-send


async def send_status(room: Room) -> None:
    room.state.status.speech_pending = len(room.speech_queue) + room.summons_in_progress
    await broadcast(room, StatusMessage(status=room.state.status))


def _settings() -> Settings:
    return Settings(
        counselor_name=config.COUNSELOR_NAME,
        parent_name=config.PARENT_NAME,
        notable_gap_ms=config.NOTABLE_GAP_MS,
        sim_max_wait_for_analysis_seconds=config.SIM_MAX_WAIT_FOR_ANALYSIS_SECONDS,
    )


async def send_snapshot(room: Room, ws: WebSocket, role: ClientRole) -> None:
    snapshot = Snapshot(role=role, state=_state_for(room.state, role), settings=_settings())
    await ws.send_text(snapshot.model_dump_json())


def _write_log_file(room: Room, record: dict) -> None:
    if room.log_path:
        with room.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


async def record(room: Room, entry: LogEntry) -> None:
    room.state.log.append(entry)
    _write_log_file(room, {"type": "log", **entry.model_dump()})
    await broadcast(room, DecisionLog(entry=entry), roles={"observer"})


async def log(room: Room, kind: str, message: str, **links) -> None:
    await record(room, LogEntry(at=now_ms(), kind=kind, message=message, **links))


async def execute(room: Room, actions: list[policy.Action]) -> None:
    """Carry out policy decisions."""
    for action in actions:
        match action:
            case policy.SendCard() | policy.UpdateFlag():
                flag = next(f for f in room.state.flags if f.id == action.flag_id)
                message = FlagCard(flag=flag) if isinstance(action, policy.SendCard) else FlagUpdated(flag=flag)
                audience = {"observer", "counselor"} if _counselor_sees(flag) else {"observer"}
                await broadcast(room, message, roles=audience)
            case policy.SpeakLine():
                enqueue_speech(room, Speech(text=action.text, kind="flag", flag_id=action.flag_id))
            case LogEntry():
                await record(room, action)


# ---------------------------------------------------------------- connections and messages


async def connect(room: Room, ws: WebSocket, role: ClientRole) -> None:
    room.clients[ws] = role
    await send_snapshot(room, ws, role)


async def disconnect(room: Room, ws: WebSocket) -> None:
    role = room.clients.pop(ws, None)
    if role and room.state.status.ptt_active == role:
        room.state.status.ptt_active = None  # a closed tab can't keep holding the floor
        await send_status(room)


async def handle(room: Room, ws: WebSocket, role: ClientRole, message: BaseModel) -> None:
    status = room.state.status
    match message:
        case TurnMessage() | SimTurn() if status.call_status != "live":
            await ws.send_text(ErrorMessage(message="Start the call first.").model_dump_json())
        case TurnMessage():
            if role == "observer":
                return
            previous = room.state.turns[-1] if room.state.turns else None
            gap = max(0, message.started_at - previous.ended_at) if previous else None
            await add_turn(room, role, message.text, message.started_at, message.ended_at, gap, message.source)
        case SimTurn():
            now = now_ms()
            await add_turn(room, message.role, message.text, now, now, message.gap_ms, "script")
        case PttStart() if role != "observer" and status.call_status == "live" and status.ptt_active is None:
            status.ptt_active = role  # first come, first served: one person holds the floor
            await send_status(room)
        case PttStop() if status.ptt_active == role:
            status.ptt_active = None
            room.last_activity = time.monotonic()
            await send_status(room)
        case PlaybackDone() if message.turn_id == status.speaking_turn_id:
            room.playback_done.set()
        case StartCall():
            await start_call(room, message.simulated)
        case EndCall():
            await end_call(room)
        case ResetRoom():
            await reset_room(room)
        case FlagAction():
            await flag_action(room, role, message)


async def flag_action(room: Room, role: ClientRole, message: FlagAction) -> None:
    """The counselor clicked "I'll clarify" or "Not an issue" on a nudge card.
    policy.counselor_action() validates and applies the click; this carries out the result."""
    latest = room.state.turns[-1].id if room.state.turns else ""
    if role != "counselor":
        await log(room, "ladder", f"ignored {message.action} on {message.flag_id}: only the counselor can act on a card, not the {role}", turn_id=latest)
        return
    actions = policy.counselor_action(room.state, message.flag_id, message.action, latest, now_ms())
    accepted = any(isinstance(action, policy.UpdateFlag) for action in actions)
    # The counselor has taken this flag over, so a line already queued for it must not be said.
    # Withdraw it before any await: after "I'll clarify" the flag is still nudged, and the speaker
    # loop would otherwise say the line while the messages below are being sent.
    withdrawn = accepted and any(s.flag_id == message.flag_id for s in room.speech_queue)
    if withdrawn:
        room.speech_queue = [s for s in room.speech_queue if s.flag_id != message.flag_id]
    await execute(room, actions)
    if not accepted:
        return  # the policy's log entry says why it was ignored
    flag = next(f for f in room.state.flags if f.id == message.flag_id)
    # Kept with the whole flag so dismissals can be collected later as labeled examples:
    # what Beacon flagged, and what the expert on the call said about it.
    _write_log_file(room, {"type": "counselor_feedback", "action": message.action, "flag": flag.model_dump(), "turn_id": latest})
    if withdrawn:
        await log(room, "speech", f"withdrew queued line for {flag.id}: the counselor answered the card first", flag_id=flag.id, turn_id=latest)
        await send_status(room)


async def add_turn(room: Room, role: str, text: str, started_at: int, ended_at: int, gap_ms: int | None, source: str) -> None:
    text = text.strip()
    if not text:
        return
    turn = Turn(
        id=f"t{len(room.state.turns) + 1}",
        role=role,
        text=text,
        started_at=started_at,
        ended_at=ended_at,
        gap_ms=gap_ms,
        source=source,
    )
    room.state.turns.append(turn)
    room.last_activity = time.monotonic()
    # Count a summon before any await, so the status that follows the turn already shows it.
    question = wakeword.find_summon(turn.text)
    if question:
        room.summons_in_progress += 1
        _start_background(room, _answer_summon(room, turn, question))
    _write_log_file(room, {"type": "turn", **turn.model_dump()})
    await broadcast(room, TurnAdded(turn=turn))

    # The conversation moved on, so a queued interjection may no longer fit. Drop it; the next
    # analysis sees the new turn and re-decides (the flag is still nudged).
    withdrawn = [s for s in room.speech_queue if s.kind == "flag"]
    if withdrawn:
        room.speech_queue = [s for s in room.speech_queue if s.kind != "flag"]
        ids = ", ".join(s.flag_id for s in withdrawn)
        await log(room, "speech", f"withdrew queued line for {ids}: {turn.id} arrived first; re-deciding", turn_id=turn.id)

    await send_status(room)
    request_analysis(room)


def _start_background(room: Room, coroutine) -> None:
    task = asyncio.create_task(coroutine)
    room.background.add(task)
    task.add_done_callback(room.background.discard)


# ---------------------------------------------------------------- analysis loop


def request_analysis(room: Room) -> None:
    """At most one analysis per room. Turns arriving meanwhile are picked up by one more pass,
    which also keeps the LLM call rate down."""
    if room.analysis_task and not room.analysis_task.done():
        room.analysis_dirty = True
        return
    room.analysis_task = asyncio.create_task(_analysis_loop(room))


async def _analysis_loop(room: Room) -> None:
    while True:
        room.analysis_dirty = False
        state, status = room.state, room.state.status
        if not policy.should_analyze(state, room.analyzed_ok):
            room.analyzed_ok = status.analyzed_turn_count = len(state.turns)
            last = state.turns[-1].id if state.turns else None
            await log(room, "analysis", f"skipped LLM for {last}: counselor turn, nothing open", turn_id=last)
        else:
            status.analysis = "running"
            await send_status(room)
            result = await analyzer.analyze(llm, state)
            last = state.turns[result.turn_count - 1].id
            if result.error:
                status.analysis, status.analysis_error = "error", f"analyzer unavailable: {result.error}"
                await log(room, "error", f"analysis through {last} failed after {result.latency_ms} ms: {result.error}", turn_id=last)
            else:
                status.analysis, status.analysis_error = "idle", None
                room.analyzed_ok = result.turn_count  # after an error it stays put, so those turns are retried
                message = f"analyzed t1–{last} in {result.latency_ms} ms: {result.output.notes}"
                await log(room, "analysis", message, turn_id=last, data=result.output.model_dump())
                await execute(room, policy.after_analysis(state, result.output, result.turn_count, now_ms()))
            status.analyzed_turn_count = result.turn_count
        await send_status(room)
        if not room.analysis_dirty:
            return


async def _answer_summon(room: Room, turn: Turn, question: str) -> None:
    """`question` is find_summon's extract, used only for the log; the LLM gets the whole turn."""
    await log(room, "summon", f"wake word in {turn.id}: “{question}”", turn_id=turn.id)
    try:
        answer = await analyzer.answer_summon(llm, room.state, turn)
        text = answer.answer
        source = f"documents {', '.join(answer.doc_refs)}" if answer.answered_from_documents else "not in documents"
        await log(room, "summon", f"answer ({source}): {text}", turn_id=turn.id, data=answer.model_dump())
    except Exception as exc:  # the parent still deserves a reply
        text = config.SUMMON_FAILED_LINE.format(counselor=config.COUNSELOR_NAME)
        await log(room, "error", f"summon answer failed: {type(exc).__name__}: {exc}", turn_id=turn.id)
    room.summons_in_progress -= 1
    enqueue_speech(room, Speech(text=text, kind="summon"))
    await send_status(room)


# ---------------------------------------------------------------- speaking


def enqueue_speech(room: Room, speech: Speech) -> None:
    if speech.flag_id and any(s.flag_id == speech.flag_id for s in room.speech_queue):
        return
    room.speech_queue.append(speech)
    if not room.speaker_task or room.speaker_task.done():
        room.speaker_task = asyncio.create_task(_speaker_loop(room))


async def _speaker_loop(room: Room) -> None:
    while room.speech_queue:
        # Turn-taking: never talk over someone holding push-to-talk, and wait for a short pause.
        quiet_for = time.monotonic() - room.last_activity
        if room.state.status.ptt_active or quiet_for < config.PAUSE_BEFORE_SPEAK_MS / 1000:
            await asyncio.sleep(0.1)
            continue
        speech = room.speech_queue.pop(0)
        flag = next((f for f in room.state.flags if f.id == speech.flag_id), None)
        if flag and flag.state != "nudged":
            await log(room, "speech", f"skipped line for {flag.id}: it is already {flag.state}", flag_id=flag.id)
            continue
        await _speak(room, speech)
    await send_status(room)


async def _speak(room: Room, speech: Speech) -> None:
    state, status = room.state, room.state.status
    now = now_ms()
    previous = state.turns[-1] if state.turns else None
    turn = Turn(
        id=f"t{len(state.turns) + 1}",
        role="beacon",
        text=speech.text,
        started_at=now,
        ended_at=now,
        gap_ms=max(0, now - previous.ended_at) if previous else None,
        source="beacon",
    )
    state.turns.append(turn)
    # Update state before any await, so no tab sees "idle" in between and a concurrent analysis
    # can't queue the same flag again.
    status.speaking_turn_id = turn.id
    flag_actions = policy.mark_spoken(state, speech.flag_id, turn.id, now) if speech.flag_id else []
    room.playback_done.clear()
    _write_log_file(room, {"type": "turn", **turn.model_dump()})
    await broadcast(room, TurnAdded(turn=turn))
    await broadcast(room, BeaconSay(turn_id=turn.id, text=speech.text))
    await send_status(room)
    await log(room, "speech", f"Beacon ({speech.kind}): {speech.text}", turn_id=turn.id, flag_id=speech.flag_id)
    words = len(speech.text.split())
    if words > config.SPOKEN_WORDS_WARNING:
        await log(room, "speech", f"warning: {words} words, over the {config.SPOKEN_WORDS_WARNING}-word limit (target: about 20)", turn_id=turn.id)
    await execute(room, flag_actions)

    # A tab with audio on reports when playback ends. If none does, don't block the call forever.
    timeout = 2 + words * config.PLAYBACK_FALLBACK_MS_PER_WORD / 1000
    try:
        await asyncio.wait_for(room.playback_done.wait(), timeout)
    except TimeoutError:
        await log(room, "speech", f"no tab reported playback of {turn.id}; continuing after {timeout:.0f}s", turn_id=turn.id)
    turn.ended_at = now_ms()
    status.speaking_turn_id = None
    room.last_activity = time.monotonic()
    await send_status(room)


# ---------------------------------------------------------------- call lifecycle


def _cancel_tasks(room: Room) -> None:
    for task in [room.analysis_task, room.speaker_task, *room.background]:
        if task:
            task.cancel()
    room.analysis_task = room.speaker_task = None
    room.analysis_dirty = False
    room.speech_queue = []
    room.summons_in_progress = 0


async def start_call(room: Room, simulated: bool) -> None:
    if room.state.status.call_status == "live":
        return
    if room.state.status.call_status == "ended":
        await reset_room(room)
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    room.log_path = config.LOGS_DIR / f"{room.name}-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    room.state.status.call_status = "live"
    room.state.status.simulated = simulated
    await log(room, "call", f"call started ({'simulated' if simulated else 'live'}); log file {room.log_path.name}")
    enqueue_speech(room, Speech(text=config.OPENING_LINE, kind="opening"))
    await send_status(room)


async def end_call(room: Room) -> None:
    state, status = room.state, room.state.status
    if status.call_status != "live":
        return
    _cancel_tasks(room)
    status.call_status, status.ptt_active, status.speaking_turn_id = "ended", None, None
    status.analysis, status.recap = "idle", "generating"
    await execute(room, policy.end_of_call(state, now_ms()))
    await log(room, "call", f"call ended after {len(state.turns)} turns; generating the recap")
    await send_status(room)
    _start_background(room, _make_recap(room))


async def _make_recap(room: Room) -> None:
    state = room.state
    try:
        recap = await analyzer.generate_recap(llm, state)
    except Exception as exc:
        state.status.recap = "error"
        await log(room, "error", f"recap failed: {type(exc).__name__}: {exc}")
        await send_status(room)
        return
    state.recap = recap
    # Add missing open issues first, so the number check covers those follow-ups too.
    for ref in analyzer.add_missing_follow_ups(recap, state):
        await log(room, "recap", f"the recap left out open issue {ref}; added it")
    state.recap_unverified = analyzer.unverified_numbers(recap, state)
    for problem in state.recap_unverified:
        await log(room, "recap", f"unverified number: {problem}")
    state.status.recap = "ready"
    await log(room, "recap", f"recap ready ({len(state.recap_unverified)} unverified numbers)")
    await broadcast(room, RecapReady(recap=recap, unverified=state.recap_unverified))
    await send_status(room)


async def reset_room(room: Room) -> None:
    _cancel_tasks(room)
    room.state = RoomState()
    room.log_path = None
    room.last_activity = 0.0
    room.analyzed_ok = 0
    for ws, role in list(room.clients.items()):
        await send_snapshot(room, ws, role)
