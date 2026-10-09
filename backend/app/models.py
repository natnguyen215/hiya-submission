"""The data shapes of the backend: the call state, the schemas that the LLM fills in, and the
WebSocket messages. web/src/types.ts has the same shapes for the browser. Change the two files
together."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Speaker = Literal["counselor", "parent"]
Role = Literal["counselor", "parent", "beacon"]
ClientRole = Literal["counselor", "parent", "observer"]
Severity = Literal["interrupt", "recap"]
FlagState = Literal["nudged", "resolved", "spoken", "recap", "dismissed", "dropped"]
CardAction = Literal["dismiss", "will_clarify"]  # the two buttons on the counselor's card


# ---------------------------------------------------------------- conversation state


class Turn(BaseModel):
    id: str  # "t1", "t2", ... in transcript order
    role: Role
    text: str
    started_at: int  # epoch ms
    ended_at: int  # epoch ms
    gap_ms: int | None  # the silence after the previous turn. None for the first turn.
    source: Literal["voice", "typed", "script", "beacon"]


class FlagEvent(BaseModel):
    state: FlagState
    reason: str
    turn_id: str | None  # the newest turn at the time of the change


class Flag(BaseModel):
    id: str  # "f1", "f2", ...
    trigger: str  # a name from triggers.TRIGGERS
    issue_key: str  # a short name for the issue, for dedupe. Example: "aid_package_includes_loans"
    severity: Severity
    evidence_turn_ids: list[str]
    evidence_quotes: list[str]
    counselor_card: str  # what the parent seems to misunderstand. Only the counselor sees it.
    suggested_clarification: str
    spoken_line: str  # what Beacon says aloud if the ladder escalates. It speaks to the counselor.
    family_question: str  # the same question, for the family to ask the aid office later (recap)
    doc_refs: list[str]
    state: FlagState
    # The ladder counts the turns after this turn. At first it is the newest turn when the card
    # appeared. "I'll clarify" moves it to the newest turn at the time of the click.
    ladder_start_turn: str
    # The time (epoch ms) of the same moment. A counselor turn counts only if it started at or
    # after this time. A turn that started before the card appeared does not count.
    ladder_start_ms: int
    grace_turns: int = 0  # more counselor turns before Beacon can speak ("I'll clarify" adds them)
    counselor_action: Literal["will_clarify", "dismissed"] | None = None  # the counselor's last click
    history: list[FlagEvent]


class ParentQuestion(BaseModel):
    text: str
    asked_turn_id: str
    answered_turn_id: str | None = None


class LogEntry(BaseModel):
    at: int  # epoch ms
    kind: Literal["call", "analysis", "flag", "ladder", "question", "speech", "summon", "recap", "error"]
    message: str
    turn_id: str | None = None
    flag_id: str | None = None
    data: dict | None = None


class RoomStatus(BaseModel):
    """What the room does now. Each tab shows some of it."""

    call_status: Literal["idle", "live", "ended"] = "idle"
    simulated: bool = False  # the observer's script runner drives the call and plays all audio
    ptt_active: Speaker | None = None  # the person who holds push-to-talk
    speaking_turn_id: str | None = None  # the Beacon turn that plays now
    speech_pending: int = 0  # Beacon lines in the queue, plus summon answers not ready yet
    analysis: Literal["idle", "running", "error"] = "idle"
    analysis_error: str | None = None
    # The turns that the last analysis covered, also if it failed. The simulation runner waits for
    # this number, so it must move on after a failure. (Room.analyzed_ok counts successes only.)
    analyzed_turn_count: int = 0
    recap: Literal["none", "generating", "ready", "error"] = "none"


# ---------------------------------------------------------------- LLM output schemas
# The order of the fields is important. The LLM writes the fields in order, so the evidence comes
# before the decision.


class NewFlag(BaseModel):
    trigger: str
    issue_key: str
    evidence_turn_ids: list[str]
    evidence_quotes: list[str]
    counselor_card: str
    severity: Severity
    suggested_clarification: str
    spoken_line: str
    family_question: str
    doc_refs: list[str]


class QuestionOpened(BaseModel):
    turn_id: str
    text: str


class QuestionAnswered(BaseModel):
    asked_turn_id: str
    answered_turn_id: str


class AnalyzerOutput(BaseModel):
    notes: str  # first: the LLM summarizes the newest turns before it decides about them
    new_flags: list[NewFlag]
    resolved_flag_ids: list[str]
    questions_opened: list[QuestionOpened]
    questions_answered: list[QuestionAnswered]


class SummonAnswer(BaseModel):
    answer: str  # spoken aloud
    answered_from_documents: bool
    doc_refs: list[str]


class RecapItem(BaseModel):
    label: str
    amount: str  # for example "$9,000". Empty if the item has no amount.
    note: str  # what it means, in plain words: "Free money. You don't pay it back."
    refs: list[str]  # document line ids (L.., G..) or turn ids (t..)


class RecapTodo(BaseModel):
    task: str
    deadline: str  # empty if there is no deadline
    refs: list[str]


class RecapFollowUp(BaseModel):
    question: str  # a question that the family must still ask, or a fact to check
    refs: list[str]  # flag ids (f..) or turn ids (t..)


class Recap(BaseModel):
    cost_of_attendance: RecapItem
    grants: list[RecapItem]
    loans: list[RecapItem]
    work_study: list[RecapItem]
    still_to_pay: list[RecapItem]
    todos: list[RecapTodo]
    follow_ups: list[RecapFollowUp]


class RoomState(BaseModel):
    status: RoomStatus = Field(default_factory=RoomStatus)
    turns: list[Turn] = []
    flags: list[Flag] = []
    parent_questions: list[ParentQuestion] = []
    log: list[LogEntry] = []
    last_spoken_at: int | None = None  # epoch ms of the last line for a flag (for the cooldown)
    recap: Recap | None = None
    recap_unverified: list[str] = []  # recap numbers that are not in their cited sources


# ---------------------------------------------------------------- WebSocket: client -> server


class Join(BaseModel):
    type: Literal["join"]
    room: str
    role: ClientRole


class TurnMessage(BaseModel):
    type: Literal["turn"]
    text: str
    started_at: int
    ended_at: int
    source: Literal["voice", "typed"]


class SimTurn(BaseModel):
    """A script line. The observer's simulation runner sends it for the counselor or the parent."""

    type: Literal["sim_turn"]
    role: Speaker
    text: str
    gap_ms: int  # the pause from the script. The real time is longer: the runner waits for analysis.


class PttStart(BaseModel):
    type: Literal["ptt_start"]


class PttStop(BaseModel):
    type: Literal["ptt_stop"]


class PlaybackDone(BaseModel):
    type: Literal["beacon_playback_done"]
    turn_id: str


class FlagAction(BaseModel):
    """The counselor clicked "I'll clarify" or "Not an issue" on a card."""

    type: Literal["flag_action"]
    flag_id: str
    action: CardAction


class StartCall(BaseModel):
    type: Literal["start_call"]
    simulated: bool = False


class EndCall(BaseModel):
    type: Literal["end_call"]


class ResetRoom(BaseModel):
    type: Literal["reset_room"]


ClientMessage = Annotated[
    Join | TurnMessage | SimTurn | PttStart | PttStop | PlaybackDone | FlagAction | StartCall | EndCall | ResetRoom,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------- WebSocket: server -> client


class Settings(BaseModel):
    """The config values that the browser needs."""

    counselor_name: str
    parent_name: str
    notable_gap_ms: int
    sim_max_wait_for_analysis_seconds: float


class Snapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    role: ClientRole
    state: RoomState  # filtered for the role. The parent never sees flags or the decision log.
    settings: Settings


class TurnAdded(BaseModel):
    type: Literal["turn_added"] = "turn_added"
    turn: Turn


class FlagCard(BaseModel):
    type: Literal["flag_card"] = "flag_card"
    flag: Flag


class FlagUpdated(BaseModel):
    type: Literal["flag_updated"] = "flag_updated"
    flag: Flag


class BeaconSay(BaseModel):
    type: Literal["beacon_say"] = "beacon_say"
    turn_id: str
    text: str


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    status: RoomStatus


class DecisionLog(BaseModel):
    type: Literal["decision_log"] = "decision_log"
    entry: LogEntry


class RecapReady(BaseModel):
    type: Literal["recap_ready"] = "recap_ready"
    recap: Recap
    unverified: list[str]


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str
