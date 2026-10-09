// The WebSocket protocol and shared state shapes. Mirrors backend/app/models.py; change both together.

export type Speaker = "counselor" | "parent";
export type Role = Speaker | "beacon";
export type ClientRole = Speaker | "observer";
export type FlagState = "nudged" | "resolved" | "spoken" | "recap" | "dismissed" | "dropped";
export type CardAction = "dismiss" | "will_clarify"; // the two buttons on the counselor's nudge card

export interface Turn {
  id: string;
  role: Role;
  text: string;
  started_at: number; // epoch ms
  ended_at: number;
  gap_ms: number | null; // silence before this turn
  source: "voice" | "typed" | "script" | "beacon";
}

export interface FlagEvent {
  state: FlagState;
  reason: string;
  turn_id: string | null;
}

export interface Flag {
  id: string;
  trigger: string;
  issue_key: string;
  severity: "interrupt" | "recap";
  evidence_turn_ids: string[];
  evidence_quotes: string[];
  counselor_card: string;
  suggested_clarification: string;
  spoken_line: string; // addressed to the counselor
  family_question: string; // the same question for the family to ask the aid office later (recap)
  doc_refs: string[];
  state: FlagState;
  created_at_turn: string;
  ladder_start_turn: string; // the ladder counts turns after this one; "I'll clarify" moves it
  ladder_start_ms: number; // epoch ms of the same moment; counselor turns that started earlier don't count
  grace_turns: number; // extra counselor turns before Beacon may speak
  counselor_action: "will_clarify" | "dismissed" | null; // the counselor's last click on the card
  history: FlagEvent[];
}

export interface ParentQuestion {
  text: string;
  asked_turn_id: string;
  answered_turn_id: string | null;
}

export interface LogEntry {
  at: number;
  kind: "call" | "analysis" | "flag" | "ladder" | "question" | "speech" | "summon" | "recap" | "error";
  message: string;
  turn_id: string | null;
  flag_id: string | null;
  data: Record<string, unknown> | null;
}

export interface RoomStatus {
  call_status: "idle" | "live" | "ended";
  simulated: boolean;
  ptt_active: Speaker | null;
  speaking_turn_id: string | null;
  speech_pending: number;
  analysis: "idle" | "running" | "error";
  analysis_error: string | null;
  analyzed_turn_count: number;
  recap: "none" | "generating" | "ready" | "error";
}

export interface RecapItem {
  label: string;
  amount: string;
  note: string;
  refs: string[];
}

export interface Recap {
  cost_of_attendance: RecapItem;
  grants: RecapItem[];
  loans: RecapItem[];
  work_study: RecapItem[];
  still_to_pay: RecapItem[];
  todos: { task: string; deadline: string; refs: string[] }[];
  follow_ups: { question: string; refs: string[] }[];
}

export interface RoomState {
  status: RoomStatus;
  turns: Turn[];
  flags: Flag[];
  parent_questions: ParentQuestion[];
  log: LogEntry[];
  last_spoken_at: number | null;
  recap: Recap | null;
  recap_unverified: string[];
}

export interface Settings {
  counselor_name: string;
  parent_name: string;
  notable_gap_ms: number;
  sim_max_wait_for_analysis_seconds: number;
}

export interface DocLine {
  doc: string;
  id: string;
  text: string;
}

export interface ScriptTurn {
  id: string;
  role: Speaker;
  text: string;
  pause_before_ms: number;
  expect?: { trigger: string | null; outcome: string; note: string };
}

export type ClientMessage =
  | { type: "join"; room: string; role: ClientRole }
  | { type: "turn"; text: string; started_at: number; ended_at: number; source: "voice" | "typed" }
  | { type: "sim_turn"; role: Speaker; text: string; gap_ms: number }
  | { type: "ptt_start" }
  | { type: "ptt_stop" }
  | { type: "beacon_playback_done"; turn_id: string }
  | { type: "flag_action"; flag_id: string; action: CardAction }
  | { type: "start_call"; simulated: boolean }
  | { type: "end_call" }
  | { type: "reset_room" };

export type ServerMessage =
  | { type: "snapshot"; role: ClientRole; state: RoomState; settings: Settings }
  | { type: "turn_added"; turn: Turn }
  | { type: "flag_card"; flag: Flag }
  | { type: "flag_updated"; flag: Flag }
  | { type: "beacon_say"; turn_id: string; text: string }
  | { type: "status"; status: RoomStatus }
  | { type: "decision_log"; entry: LogEntry }
  | { type: "recap_ready"; recap: Recap; unverified: string[] }
  | { type: "error"; message: string };
