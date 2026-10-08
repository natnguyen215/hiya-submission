// The demo and debugging dashboard: whole room state, decision log, documents, and the simulation runner.
import { useEffect, useRef, useState } from "react";
import { FlagCard, StatusBar, Transcript, useScrollToEnd } from "./components";
import { FamilyRecap } from "./Recap";
import { runSimulation } from "./simulate";
import { speak, stopSpeaking, useBeaconAudioSetting } from "./speech";
import type { DocLine, LogEntry, ScriptTurn } from "./types";
import { useRoom } from "./useRoom";

// The same scripts the offline eval runs (eval/run.py's SCRIPTS); the demo video uses demo_call.
const SCRIPTS = [
  "demo_call",
  "control_call",
  "demo_call_stt_noise",
  "adversarial_clean",
  "live_regressions",
  "live_patterns",
  "summon_checks",
];

interface Progress {
  text: string;
  expect?: ScriptTurn["expect"];
}

export function ObserverView({ room }: { room: string }) {
  const [playAudio, setPlayAudio] = useBeaconAudioSetting("observer");
  const [scriptName, setScriptName] = useState(SCRIPTS[0]);
  const [textOnly, setTextOnly] = useState(true);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [hoveredFlagId, setHoveredFlagId] = useState<string | null>(null);
  const [hoveredRef, setHoveredRef] = useState<string | null>(null); // a recap reference: t12, L10, ...
  const [documents, setDocuments] = useState<DocLine[]>([]);
  // The running simulation's stop handle. A ref, not state, so the audio callback sees it the
  // moment a run starts rather than after the next render.
  const simulation = useRef<AbortController | null>(null);

  const { state, settings, connected, lastError, send, stateRef } = useRoom(room, "observer", {
    // Runs later, on a socket message, so it can use `send` returned by this same call.
    onBeaconSay(say) {
      const done = () => send({ type: "beacon_playback_done", turn_id: say.turn_id });
      // While simulating, this tab plays every voice (the call tabs stay silent). In text-only mode
      // nobody needs to hear it, so report it played at once and let the script continue. (The
      // checkbox is locked during a run, so `textOnly` is the running script's setting.)
      if (simulation.current && textOnly) done();
      else if (simulation.current || playAudio) speak(say.text, "beacon").then(done);
    },
  });

  // Fetched once the socket is up rather than on mount, so a tab opened before the backend was
  // ready still gets the documents when it reconnects.
  useEffect(() => {
    if (!connected || documents.length > 0) return;
    fetch("/api/documents")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(setDocuments)
      .catch((error) => console.error("Could not load documents", error));
  }, [connected, documents.length]);

  // A hovered flag's evidence and citations, or a hovered recap reference, are often far up their
  // lists; bring them into view.
  useEffect(() => {
    if (!hoveredFlagId && !hoveredRef) return;
    revealInList(document.querySelector(".turn.highlighted"));
    revealInList(document.querySelector(".documents .cited"));
  }, [hoveredFlagId, hoveredRef]);

  async function play() {
    if (!settings) return;
    const controller = new AbortController();
    simulation.current = controller;
    setRunning(true);
    setProgress({ text: `Loading ${scriptName}…` });
    try {
      // The signal lets Stop cancel the download too, before the runner resets the room.
      const response = await fetch(`/api/scripts/${scriptName}`, { signal: controller.signal });
      if (!response.ok) throw new Error(`could not load ${scriptName} (HTTP ${response.status})`);
      const script: ScriptTurn[] = await response.json();
      await runSimulation(script, {
        send,
        stateRef,
        settings,
        textOnly,
        signal: controller.signal,
        onProgress: (text, expect) => setProgress({ text, expect }),
      });
    } catch (error) {
      setProgress({ text: controller.signal.aborted ? "Stopped." : `Simulation failed: ${String(error)}` });
    } finally {
      simulation.current = null;
      setRunning(false);
    }
  }

  function stop() {
    simulation.current?.abort();
    stopSpeaking();
  }

  if (!state || !settings) return <p className="connecting">Connecting to room “{room}”…</p>;

  const { status } = state;
  const hovered = state.flags.find((f) => f.id === hoveredFlagId);
  // A recap reference is either a turn id or a document line id; each list highlights the ids it has.
  const highlightedTurns = new Set(hoveredRef ? [hoveredRef] : hovered?.evidence_turn_ids);
  const highlightedLines = new Set(hoveredRef ? [hoveredRef] : hovered?.doc_refs);

  return (
    <div className="observer-view">
      <header className="topbar">
        <span className="role-badge role-observer">★ Beacon · Observer</span>
        <span className="chip">Room: {room}</span>
        <StatusBar state={state} connected={connected} role="observer" />
        {status.speaking_turn_id && <span className="chip chip-speaking">★ Beacon is speaking…</span>}
      </header>
      {lastError && <div className="toast">{lastError}</div>}

      <section className="controls">
        <div className="control-group">
          <button className="primary" onClick={() => send({ type: "start_call", simulated: false })}>
            Start call
          </button>
          <button onClick={() => send({ type: "end_call" })}>End call</button>
          <button onClick={() => send({ type: "reset_room" })}>Reset</button>
          <label className="toggle">
            <input type="checkbox" checked={playAudio} onChange={(e) => setPlayAudio(e.target.checked)} />
            Play Beacon audio here
          </label>
        </div>
        <div className="control-group">
          <span className="control-label">Simulation</span>
          <select value={scriptName} onChange={(e) => setScriptName(e.target.value)} disabled={running}>
            {SCRIPTS.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
          <button className="primary" onClick={play} disabled={running || !connected}>
            Play
          </button>
          <button onClick={stop} disabled={!running}>
            Stop
          </button>
          <label className="toggle">
            <input type="checkbox" checked={textOnly} onChange={(e) => setTextOnly(e.target.checked)} disabled={running} />
            Text only (no audio)
          </label>
        </div>
        {progress && (
          <div className="progress">
            <span>{progress.text}</span>
            {progress.expect && (
              <span className="expect">
                Expect {progress.expect.trigger ?? "no trigger"} → {progress.expect.outcome}. {progress.expect.note}
              </span>
            )}
          </div>
        )}
      </section>

      <FamilyRecap state={state} onRefHover={setHoveredRef} />

      <div className="observer-grid">
        <section className="panel area-transcript">
          <h2>Transcript</h2>
          <Transcript turns={state.turns} settings={settings} detailed highlighted={highlightedTurns} />
        </section>

        <section className="panel area-flags">
          <h2>Flags ({state.flags.length})</h2>
          <div className="scroll">
            {state.flags.length === 0 && <p className="empty">No flags yet.</p>}
            {[...state.flags].reverse().map((flag) => (
              <div key={flag.id} onMouseEnter={() => setHoveredFlagId(flag.id)} onMouseLeave={() => setHoveredFlagId(null)}>
                <FlagCard flag={flag} detailed />
              </div>
            ))}
          </div>
        </section>

        <section className="panel area-documents">
          <h2>Documents</h2>
          <Documents lines={documents} cited={highlightedLines} />
        </section>

        <section className="panel area-log">
          <h2>Decision Log</h2>
          <DecisionLog entries={state.log} />
        </section>
      </div>
    </div>
  );
}

/**
 * Scrolls the transcript or document list just enough to show `element`. Not scrollIntoView: that
 * also scrolls the page, which moves the hovered flag or reference out from under the pointer and ends the hover.
 */
function revealInList(element: Element | null) {
  const list = element?.closest(".transcript, .documents");
  if (!element || !list) return;
  const top = element.getBoundingClientRect().top - list.getBoundingClientRect().top; // from the list's visible top
  const bottom = top + element.getBoundingClientRect().height;
  if (top < 0) list.scrollTop += top;
  // An element taller than the list shows its top.
  else if (bottom > list.clientHeight) list.scrollTop += Math.min(top, bottom - list.clientHeight);
}

function DecisionLog({ entries }: { entries: LogEntry[] }) {
  const ref = useScrollToEnd<HTMLOListElement>(entries.length);
  return (
    <ol className="log" ref={ref}>
      {entries.length === 0 && <li className="empty">Nothing logged yet.</li>}
      {/* The log only grows (a reset replaces it whole), so an entry's index is a stable key. */}
      {entries.map((entry, i) => (
        <li key={i} className={`log-entry log-${entry.kind}`}>
          <time>{new Date(entry.at).toTimeString().slice(0, 8)}</time>
          <span className="badge log-kind">{entry.kind}</span>
          <span className="log-message">
            {entry.message}
            {entry.turn_id && <span className="ref">{entry.turn_id}</span>}
            {entry.flag_id && <span className="ref">{entry.flag_id}</span>}
          </span>
          {entry.data && (
            <details className="log-data">
              <summary>data</summary>
              <pre>{JSON.stringify(entry.data, null, 2)}</pre>
            </details>
          )}
        </li>
      ))}
    </ol>
  );
}

function Documents({ lines, cited }: { lines: DocLine[]; cited: Set<string> }) {
  const docNames = [...new Set(lines.map((line) => line.doc))];
  return (
    <div className="scroll documents">
      {lines.length === 0 && <p className="empty">Loading documents…</p>}
      {docNames.map((doc) => (
        <section key={doc}>
          <h3>{doc}</h3>
          <ul>
            {/* The glossary bolds its terms in Markdown; here the asterisks are just noise. */}
            {lines
              .filter((line) => line.doc === doc)
              .map((line) => (
                <li key={line.id} className={cited.has(line.id) ? "cited" : undefined}>
                  <span className="line-id">{line.id}</span> {line.text.replaceAll("**", "")}
                </li>
              ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
