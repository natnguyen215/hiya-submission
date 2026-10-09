// The call screen for the counselor or the parent: the transcript, push-to-talk and typed turns,
// the counselor's private Beacon panel, and the Family Recap.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { FlagCard, StatusBar, Transcript, speakerName } from "./components";
import { FamilyRecap } from "./Recap";
import { canListen, speak, startListening, useBeaconAudioSetting, type Listening } from "./speech";
import type { ClientMessage, Speaker } from "./types";
import { useRoom } from "./useRoom";

export function CallView({ room, role }: { room: string; role: Speaker }) {
  const [playAudio, setPlayAudio] = useBeaconAudioSetting(role);
  const [playingHere, setPlayingHere] = useState(false);
  const interacted = useHasInteracted();
  const { state, settings, connected, lastError, showError, send, stateRef } = useRoom(room, role, {
    // This runs later, when a message arrives. So it can use `send` and `stateRef` from this call.
    onBeaconSay(say) {
      // In a simulated call, the observer plays all voices. The call tabs stay silent.
      if (!playAudio || stateRef.current?.status.simulated) return;
      setPlayingHere(true);
      speak(say.text, "beacon").then(() => {
        setPlayingHere(false);
        send({ type: "beacon_playback_done", turn_id: say.turn_id });
      });
    },
  });

  if (!state || !settings) return <p className="connecting">Connecting to room “{room}”…</p>;

  const { status } = state;
  const live = status.call_status === "live";
  // Push-to-talk stays off while this is true. If not, the microphone would hear Beacon.
  // playingHere is necessary if the server stopped waiting (timeout) but this tab still plays.
  const beaconSpeaking = status.speaking_turn_id !== null || playingHere;
  // If the other person holds push-to-talk, this person must wait. Two people cannot talk at the same time.
  const otherTalking =
    status.ptt_active && status.ptt_active !== role ? speakerName(status.ptt_active, settings) : null;
  const name = role === "counselor" ? settings.counselor_name : settings.parent_name;

  return (
    <div className={`call-view call-${role}`}>
      <header className="topbar">
        <span className={`role-badge role-${role}`}>
          {role === "counselor" ? "Counselor" : "Parent"} · {name}
        </span>
        <StatusBar state={state} connected={connected} role={role} />
        <div className="topbar-actions">
          <label className="toggle">
            <input type="checkbox" checked={playAudio} onChange={(e) => setPlayAudio(e.target.checked)} />
            Play Beacon audio here
          </label>
          {role === "counselor" &&
            (live ? (
              <button onClick={() => send({ type: "end_call" })}>End call</button>
            ) : (
              <button className="primary" onClick={() => send({ type: "start_call", simulated: false })}>
                Start call
              </button>
            ))}
        </div>
      </header>
      {playAudio && !interacted && (
        <div className="notice">Click anywhere in this tab once so it can play Beacon's voice</div>
      )}
      {lastError && <div className="toast">{lastError}</div>}

      <div className="call-body">
        <main className="panel call-main">
          <Transcript turns={state.turns} settings={settings} />
          {beaconSpeaking && <div className="speaking-banner">★ Beacon is speaking…</div>}
          <FamilyRecap state={state} />
          <PushToTalk
            live={live}
            disabled={!live || beaconSpeaking || otherTalking !== null}
            otherTalking={otherTalking}
            onSend={send}
            onError={showError}
          />
          <TypedTurn disabled={!live} onSend={send} />
        </main>

        {role === "counselor" && (
          <aside className="panel nudges">
            <h2 className="beacon-heading">★ Beacon</h2>
            <p className="hint">Only you can see these. {settings.parent_name} can't.</p>
            {state.flags.length === 0 && <p className="empty">Nothing to clarify yet.</p>}
            {[...state.flags].reverse().map((flag) => (
              <FlagCard
                key={flag.id}
                flag={flag}
                onAction={(action) => send({ type: "flag_action", flag_id: flag.id, action })}
              />
            ))}
          </aside>
        )}
      </div>
    </div>
  );
}

/** True after the user clicks or presses a key in this tab. Before that, Chrome does not let the tab speak. */
function useHasInteracted(): boolean {
  // Other browsers do not have this API. Then we cannot know, so do not show the notice.
  const [interacted, setInteracted] = useState(() => navigator.userActivation?.hasBeenActive ?? true);
  useEffect(() => {
    if (interacted) return;
    const done = () => setInteracted(true);
    window.addEventListener("pointerdown", done);
    window.addEventListener("keydown", done);
    return () => {
      window.removeEventListener("pointerdown", done);
      window.removeEventListener("keydown", done);
    };
  }, [interacted]);
  return interacted;
}

interface PushToTalkProps {
  live: boolean; // the call is live, so Space is the talk key (also when a new press is refused)
  disabled: boolean; // a new press is refused. A press that started always finishes.
  otherTalking: string | null; // the name of the other person, if they hold push-to-talk
  onSend: (message: ClientMessage) => void;
  onError: (message: string) => void;
}

/** A spoken turn: hold the button or the space bar, speak, and release. */
function PushToTalk({ live, disabled, otherTalking, onSend, onError }: PushToTalkProps) {
  const [phase, setPhase] = useState<"idle" | "listening" | "sending">("idle");
  const [heard, setHeard] = useState("");
  // The current press, from the press until its turn is sent. It is a ref, so a release event
  // sees it at once (also a second release event, such as pointerup then pointerleave).
  const press = useRef<{ listening: Listening; startedAt: number; released: boolean } | null>(null);

  function start() {
    // One press at a time. The previous press can still wait for its final text.
    if (!canListen || disabled || press.current) return;
    onSend({ type: "ptt_start" });
    press.current = { listening: startListening(setHeard, onError), startedAt: Date.now(), released: false };
    setPhase("listening");
  }

  async function stop() {
    const current = press.current;
    if (!current || current.released) return;
    current.released = true;
    const endedAt = Date.now();
    setPhase("sending");
    const text = await current.listening.stop();
    // Send the turn before ptt_stop. Beacon can speak soon after ptt_stop, so the server must have
    // the turn first. (A new turn also removes a line from Beacon's queue.)
    if (text) onSend({ type: "turn", text, started_at: current.startedAt, ended_at: endedAt, source: "voice" });
    onSend({ type: "ptt_stop" });
    press.current = null;
    setHeard("");
    setPhase("idle");
  }

  // No dependency list. The handlers are added again after each render, so they use the current props.
  useEffect(() => {
    function down(event: KeyboardEvent) {
      if (event.code !== "Space") return;
      // Form controls keep their own Space: a space in the text box, a tick in the checkbox.
      if (event.target instanceof Element && event.target.matches("input, select, textarea")) return;
      // If this tab cannot talk, Space does its usual work, such as a click on "Read aloud" after the call.
      if (!(live && canListen) && !press.current) return;
      event.preventDefault(); // no page scroll, and no click on a button with focus, such as End call
      // Key repeats also come here. If a press was refused (Beacon was speaking), the held key
      // starts the press when it is permitted. start() ignores repeats during a press: one hold is one turn.
      start();
    }
    function up(event: KeyboardEvent) {
      if (event.code === "Space") stop();
    }
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    // If the user leaves the tab during a press, keyup and pointerup do not come. So release now.
    // A press that does not end holds push-to-talk forever, and Beacon could not speak again.
    window.addEventListener("blur", stop);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", stop);
    };
  });

  let label = "Hold to talk (or hold Space)";
  if (phase === "listening") label = "Listening… release to send";
  else if (phase === "sending") label = "Sending…";
  else if (otherTalking) label = `${otherTalking} is talking…`;

  return (
    <>
      {heard && <p className="heard">{heard}</p>}
      <button
        className={`talk${phase === "listening" ? " listening" : ""}`}
        // Not disabled while held: a disabled button gets no pointer events, so the release would be lost.
        disabled={phase === "sending" || (phase === "idle" && (disabled || !canListen))}
        title={canListen ? undefined : "Speech recognition needs Chrome. You can still type."}
        onPointerDown={start}
        onPointerUp={stop}
        onPointerLeave={stop}
        onPointerCancel={stop}
      >
        {label}
      </button>
    </>
  );
}

/** A typed turn. It works without a microphone, so it is also good for tests. */
function TypedTurn({ disabled, onSend }: { disabled: boolean; onSend: (message: ClientMessage) => void }) {
  const [text, setText] = useState("");
  // When the turn started (the first key). The server uses it to find the pause before the turn.
  const startedAt = useRef<number | null>(null);

  function change(value: string) {
    if (startedAt.current === null) startedAt.current = Date.now();
    if (value === "") startedAt.current = null; // the text is empty again, so the turn has not started
    setText(value);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    const now = Date.now();
    onSend({ type: "turn", text, started_at: startedAt.current ?? now, ended_at: now, source: "typed" });
    setText("");
    startedAt.current = null;
  }

  return (
    <form className="composer" onSubmit={submit}>
      <input
        value={text}
        onChange={(e) => change(e.target.value)}
        disabled={disabled}
        placeholder={disabled ? "The call isn't live" : "Type what you say, then press Enter"}
      />
      <button type="submit" className="primary" disabled={disabled || !text.trim()}>
        Send
      </button>
    </form>
  );
}
