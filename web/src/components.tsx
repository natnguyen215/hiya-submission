// Shared presentational pieces for the call and observer views: transcript, flag cards, status chips.
import { useEffect, useRef } from "react";
import type { ClientRole, Flag, FlagState, Role, RoomState, RoomStatus, Settings, Turn } from "./types";

export function speakerName(role: Role, settings: Settings): string {
  if (role === "counselor") return settings.counselor_name;
  if (role === "parent") return settings.parent_name;
  return "Beacon";
}

/** Keeps a scrolling list pinned to its newest entry whenever `count` changes. */
export function useScrollToEnd<T extends HTMLElement>(count: number) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const scrollToEnd = () => element.scrollTo({ top: element.scrollHeight });
    scrollToEnd();
    // Banners that appear below the list (Beacon speaking, the recap) shrink it, which would
    // push the newest entry out of view; follow resizes too.
    const observer = new ResizeObserver(scrollToEnd);
    observer.observe(element);
    return () => observer.disconnect();
  }, [count]);
  return ref;
}

interface TranscriptProps {
  turns: Turn[];
  settings: Settings;
  detailed?: boolean; // observer: turn ids and pause badges
  highlighted?: Set<string>; // turn ids to emphasize (evidence of the hovered flag)
}

export function Transcript({ turns, settings, detailed = false, highlighted }: TranscriptProps) {
  const ref = useScrollToEnd<HTMLOListElement>(turns.length);
  return (
    <ol className="transcript" ref={ref}>
      {turns.length === 0 && <li className="empty">No one has spoken yet.</li>}
      {turns.map((turn) => (
        <li key={turn.id} className={`turn turn-${turn.role}${highlighted?.has(turn.id) ? " highlighted" : ""}`}>
          <div className="turn-meta">
            {detailed && <span className="turn-id">{turn.id}</span>}
            <span className="speaker">
              {turn.role === "beacon" && "★ "}
              {speakerName(turn.role, settings)}
            </span>
            {/* Only human pauses are a signal (hesitation); the analyzer ignores Beacon's. */}
            {detailed && turn.role !== "beacon" && turn.gap_ms !== null && turn.gap_ms >= settings.notable_gap_ms && (
              <span className="badge badge-pause">{(turn.gap_ms / 1000).toFixed(1)}s pause</span>
            )}
          </div>
          <p className="turn-text">{turn.text}</p>
        </li>
      ))}
    </ol>
  );
}

const STATE_LABELS: Record<FlagState, string> = {
  nudged: "Needs clarifying",
  resolved: "Clarified",
  spoken: "Beacon asked",
  recap: "Saved for recap",
  dropped: "Dropped",
};

function StateBadge({ state }: { state: FlagState }) {
  return <span className={`badge state-${state}`}>{STATE_LABELS[state]}</span>;
}

export function FlagCard({ flag, detailed = false }: { flag: Flag; detailed?: boolean }) {
  return (
    <article className={`flag-card flag-${flag.state}`}>
      <header className="flag-header">
        {detailed && <span className="flag-id">{flag.id}</span>}
        {detailed && <span className="badge badge-trigger">{flag.trigger}</span>}
        {detailed && <span className="badge">{flag.severity}</span>}
        <StateBadge state={flag.state} />
      </header>
      <p className="flag-card-text">{flag.counselor_card}</p>
      <p className="flag-try">
        <strong>Try:</strong> {flag.suggested_clarification}
      </p>
      {detailed && (
        <dl className="flag-details">
          <dt>Evidence ({flag.evidence_turn_ids.join(", ")})</dt>
          {flag.evidence_quotes.map((quote, i) => (
            <dd key={i} className="quote">
              “{quote}”
            </dd>
          ))}
          <dt>Beacon would say</dt>
          <dd>{flag.spoken_line}</dd>
          <dt>Documents</dt>
          <dd>{flag.doc_refs.length > 0 ? flag.doc_refs.join(", ") : "none cited"}</dd>
          {/* The ladder counts turns after this one: the newest turn when the card appeared. */}
          <dt>Ladder (card shown after {flag.created_at_turn})</dt>
          <dd>
            <ol className="flag-history">
              {flag.history.map((event, i) => (
                <li key={i}>
                  <span className={`badge state-${event.state}`}>{event.state}</span> {event.reason}
                  {event.turn_id && <span className="ref">{event.turn_id}</span>}
                </li>
              ))}
            </ol>
          </dd>
        </dl>
      )}
    </article>
  );
}

const CALL_LABELS: Record<RoomStatus["call_status"], string> = {
  idle: "Waiting for the call to start",
  live: "Live",
  ended: "Ended",
};

function analysisLabel(status: RoomStatus): string {
  if (status.analysis === "error") return status.analysis_error ?? "analyzer unavailable";
  return status.analysis === "running" ? "Analyzing…" : "Analyzer idle";
}

/** Status chips. The parent sees only the call itself; the observer also sees the pipeline counters. */
export function StatusBar({ state, connected, role }: { state: RoomState; connected: boolean; role: ClientRole }) {
  const { status } = state;
  return (
    <div className="status-bar">
      {!connected && <span className="chip chip-error">Reconnecting…</span>}
      <span className={`chip call-${status.call_status}`}>{CALL_LABELS[status.call_status]}</span>
      {role !== "parent" && <span className={`chip analysis-${status.analysis}`}>{analysisLabel(status)}</span>}
      {role === "observer" && (
        <>
          <span className="chip">Speech pending: {status.speech_pending}</span>
          <span className="chip">
            Analyzed {status.analyzed_turn_count} / {state.turns.length} turns
          </span>
        </>
      )}
    </div>
  );
}
