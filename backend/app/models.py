"""Data shapes shared by the backend: conversation state, the schemas the LLM must fill, and the
WebSocket protocol. web/src/types.ts mirrors this file; change both together."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Speaker = Literal["counselor", "parent"]
Role = Literal["counselor", "parent", "beacon"]
ClientRole = Literal["counselor", "parent", "observer"]
Severity = Literal["interrupt", "recap"]
FlagState = Literal["nudged", "resolved", "spoken", "recap", "dismissed", "dropped"]
CardAction = Literal["dismiss", "will_clarify"]  # the two buttons on the counselor's nudge card


# ---------------------------------------------------------------- conversation state


class Turn(BaseModel):
    id: str  # "t1", "t2", ... in transcript order
    role: Role
    text: str
    started_at: int  # epoch ms
    ended_at: int  # epoch ms
    gap_ms: int | None  # silence since the previous turn ended; None for the first turn
    source: Literal["voice", "typed", "script", "beacon"]


class FlagEvent(BaseModel):
    state: FlagState
    reason: str
    turn_id: str | None  # latest turn when the transition happened


class Flag(BaseModel):
    id: str  # "f1", "f2", ...
    trigger: str  # a name from triggers.TRIGGERS
    issue_key: str  # short stable key used for dedupe, e.g. "aid_package_includes_loans"
    severity: Severity
    evidence_turn_ids: list[str]
    evidence_quotes: list[str]
    counselor_card: str  # what seems misunderstood (shown privately to the counselor)
    suggested_clarification: str
    spoken_line: str  # what Beacon says aloud if the ladder escalates
    doc_refs: list[str]
    state: FlagState
    created_at_turn: str  # latest turn when the card appeared
    # The ladder counts turns after this one. It starts as created_at_turn; the counselor's
    # "I'll clarify" moves it to the newest turn and adds grace_turns.
    ladder_start_turn: str
    grace_turns: int = 0  # extra counselor turns before Beacon may speak
    counselor_action: Literal["will_clarify", "dismissed"] | None = None  # the counselor's last click on the card
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
    """Everything a tab needs to know about what the room is doing right now."""

    call_status: Literal["idle", "live", "ended"] = "idle"
    simulated: bool = False  # the observer's script runner drives the call and plays all audio
    ptt_active: Speaker | None = None  # who is holding push-to-talk
    speaking_turn_id: str | None = None  # Beacon turn currently being played
    speech_pending: int = 0  # queued Beacon lines plus summon answers being prepared
    analysis: Literal["idle", "running", "error"] = "idle"
    analysis_error: str | None = None
    analyzed_turn_count: int = 0  # transcript length covered by the last finished analysis
    recap: Literal["none", "generating", "ready", "error"] = "none"


# ---------------------------------------------------------------- LLM output schemas
# Field order matters: models generate fields in order, so judgment fields come after evidence.


class NewFlag(BaseModel):
    trigger: str
    issue_key: str
    evidence_turn_ids: list[str]
    evidence_quotes: list[str]
    counselor_card: str
    severity: Severity
    suggested_clarification: str
    spoken_line: str
    doc_refs: list[str]


class QuestionOpened(BaseModel):
    turn_id: str
    text: str


class QuestionAnswered(BaseModel):
    asked_turn_id: str
    answered_turn_id: str


class AnalyzerOutput(BaseModel):
    notes: str  # first, so the model summarizes the latest turns before it judges them
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
    amount: str  # e.g. "$9,000"; empty when the item has no amount
    note: str  # plain-language meaning, e.g. "Free money. You don't pay it back."
    refs: list[str]  # document line ids (L.., G..) or turn ids (t..)


class RecapTodo(BaseModel):
    task: str
    deadline: str  # empty when there is none
    refs: list[str]


class RecapFollowUp(BaseModel):
    question: str  # something the family should still ask or double-check
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
    last_spoken_at: int | None = None  # epoch ms of the last non-summon interjection (cooldown)
    recap: Recap | None = None
    recap_unverified: list[str] = []  # recap numbers code could not find in their cited sources


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
    """A scripted line sent by the observer's simulation runner on behalf of a persona."""

    type: Literal["sim_turn"]
    role: Speaker
    text: str
    gap_ms: int  # the script's planted pause; real elapsed time includes waiting for analysis


class PttStart(BaseModel):
    type: Literal["ptt_start"]


class PttStop(BaseModel):
    type: Literal["ptt_stop"]


class PlaybackDone(BaseModel):
    type: Literal["beacon_playback_done"]
    turn_id: str


class FlagAction(BaseModel):
    """The counselor clicked "I'll clarify" or "Not an issue" on a nudge card."""

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
    """The few config values the browser needs."""

    counselor_name: str
    parent_name: str
    notable_gap_ms: int
    sim_max_wait_for_analysis_seconds: float


class Snapshot(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    role: ClientRole
    state: RoomState  # filtered for the role: the parent never sees flags or the decision log
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
