// The observer dashboard, for the demo and for debugging: the full room state, the decision log,
// the documents, and the simulation runner.
import { useEffect, useRef, useState } from "react";
import { FlagCard, StatusBar, Transcript, useScrollToEnd } from "./components";
import { FamilyRecap } from "./Recap";
import { readingTimeMs, runSimulation, SIM_SPEECH_SPEED } from "./simulate";
import { speak, stopSpeaking, useBeaconAudioSetting } from "./speech";
import type { DocLine, LogEntry, ScriptTurn } from "./types";
import { useRoom } from "./useRoom";

// The scripts to show in a demo. The demo video uses demo_short. The other scripts in
// data/scripts are test cases for the eval (eval/run.py), so this list does not show them.
const SCRIPTS = ["demo_short", "demo_call", "control_call"];

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
  const [hoveredRef, setHoveredRef] = useState<string | null>(null); // a reference in the recap: t12, L10, ...
  const [documents, setDocuments] = useState<DocLine[]>([]);
  // The stop handle of the running simulation. It is a ref, not state, so the audio callback
  // sees it at once when a run starts, not after the next render.
  const simulation = useRef<AbortController | null>(null);

  const { state, settings, connected, lastError, send, stateRef } = useRoom(room, "observer", {
    // This runs later, when a message arrives. So it can use `send` from this call.
    onBeaconSay(say) {
      const done = () => send({ type: "beacon_playback_done", turn_id: say.turn_id });
      // During a simulation, this tab plays all voices (the call tabs stay silent). In text-only
      // mode, nobody must hear it. So report "done" after the time to read the line, and the
      // script continues. (The server's fallback wait is longer, so it does not end the line first.)
      // (The checkbox is locked during a run, so `textOnly` is the setting of the running script.)
      if (simulation.current && textOnly) setTimeout(done, readingTimeMs(say.text));
      else if (simulation.current) speak(say.text, "beacon", SIM_SPEECH_SPEED).then(done);
      else if (playAudio) speak(say.text, "beacon").then(done);
    },
  });

  // Get the documents when the socket connects, not on mount. A tab that opened before the
  // backend was ready then gets the documents when it connects again.
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

  // Scroll the lists to show the evidence and citations of the flag under the pointer, or the
  // recap reference under the pointer.
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
      // With the signal, Stop also cancels the download, before the runner resets the room.
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
  // A recap reference is a turn id or a document line id. Each list highlights the ids that it has.
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
          {/* The hover ends when the pointer leaves the list, not a card. If not, the gap between
              two cards turns the highlight off and on again, and the lists jump. */}
          <div className="scroll" onMouseLeave={() => setHoveredFlagId(null)}>
            {state.flags.length === 0 && <p className="empty">No flags yet.</p>}
            {[...state.flags].reverse().map((flag) => (
              <div key={flag.id} onMouseEnter={() => setHoveredFlagId(flag.id)}>
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
 * Scrolls the transcript or the document list just enough to show `element`.
 * Not scrollIntoView: it also scrolls the page. Then the item under the pointer moves away, and the hover stops.
 */
function revealInList(element: Element | null) {
  const list = element?.closest(".transcript, .documents");
  if (!element || !list) return;
  const top = element.getBoundingClientRect().top - list.getBoundingClientRect().top; // from the top of the visible list
  const bottom = top + element.getBoundingClientRect().height;
  if (top < 0) list.scrollTop += top;
  // If the element is taller than the list, show its top.
  else if (bottom > list.clientHeight) list.scrollTop += Math.min(top, bottom - list.clientHeight);
}

function DecisionLog({ entries }: { entries: LogEntry[] }) {
  const ref = useScrollToEnd<HTMLOListElement>(entries.length);
  return (
    <ol className="log" ref={ref}>
      {entries.length === 0 && <li className="empty">Nothing logged yet.</li>}
      {/* The log only gets longer (a reset replaces all of it), so the index is a stable key. */}
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
            {/* The glossary uses Markdown bold for its terms. Remove the asterisks here. */}
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
