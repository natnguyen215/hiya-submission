// The call screen for the counselor or the parent: shared transcript, push-to-talk and typed turns, the counselor's private Beacon panel, and the Family Recap.
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
    // Runs later, on a socket message, so it can use `send` and `stateRef` returned by this same call.
    onBeaconSay(say) {
      // In a simulated call the observer plays every voice, so call tabs stay silent.
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
  // Push-to-talk must stay off while this is true, or the microphone would transcribe Beacon. The
  // local flag matters when the server gave up waiting (its playback timeout) while this tab still plays.
  const beaconSpeaking = status.speaking_turn_id !== null || playingHere;
  // The other person holding push-to-talk has the floor, so two people don't talk over each other.
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

/** Whether the user has clicked or pressed a key in this tab yet. Until then Chrome won't let the tab speak. */
function useHasInteracted(): boolean {
  // Without the API (not Chrome) we can't tell, so don't nag.
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
  live: boolean; // the call is on, so Space is the talk key even while a new press is refused
  disabled: boolean; // a new press is refused; one already held always finishes
  otherTalking: string | null; // name of the other person holding push-to-talk
  onSend: (message: ClientMessage) => void;
  onError: (message: string) => void;
}

/** The spoken path for a turn: hold the button or the spacebar, speak, release. */
function PushToTalk({ live, disabled, otherTalking, onSend, onError }: PushToTalkProps) {
  const [phase, setPhase] = useState<"idle" | "listening" | "sending">("idle");
  const [heard, setHeard] = useState("");
  // The press in progress, from press until its turn is sent. A ref, so a release (and a second
  // release event, e.g. pointerup then pointerleave) sees it without waiting for a render.
  const press = useRef<{ listening: Listening; startedAt: number; released: boolean } | null>(null);

  function start() {
    // One press at a time: the previous one may still be waiting for its final text.
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
    // The turn goes before ptt_stop: Beacon may speak a moment after ptt_stop, and by then the
    // server must already have this turn (it also withdraws a queued line when a turn arrives).
    if (text) onSend({ type: "turn", text, started_at: current.startedAt, ended_at: endedAt, source: "voice" });
    onSend({ type: "ptt_stop" });
    press.current = null;
    setHeard("");
    setPhase("idle");
  }

  // No dependency list: re-subscribing after every render keeps the handlers on the current props.
  useEffect(() => {
    function down(event: KeyboardEvent) {
      if (event.code !== "Space") return;
      // Form controls keep their own Space: a space in the text box, a tick in the checkbox.
      if (event.target instanceof Element && event.target.matches("input, select, textarea")) return;
      // When this tab can't talk, Space stays Space, e.g. it presses Read aloud or Download .md after the call.
      if (!(live && canListen) && !press.current) return;
      event.preventDefault(); // no page scroll, and no click on a focused button such as End call
      // Repeats too: a hold that began while a press was refused (Beacon speaking) starts once it is allowed.
      // start() ignores them while a press is in progress, so one hold is still one turn.
      start();
    }
    function up(event: KeyboardEvent) {
      if (event.code === "Space") stop();
    }
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    // Leaving the tab mid-press (alt-tab, another tab) means the keyup or pointerup never arrives
    // here. Release now: a press that never ends holds the floor, and Beacon could never speak again.
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
        // Never disabled while held: a disabled button gets no pointer events, so the release would be lost.
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

/** The typed path for a turn: works without a microphone, so it doubles as the debug path. */
function TypedTurn({ disabled, onSend }: { disabled: boolean; onSend: (message: ClientMessage) => void }) {
  const [text, setText] = useState("");
  // When this turn began (first keystroke); the server measures the pause before the turn from it.
  const startedAt = useRef<number | null>(null);

  function change(value: string) {
    if (startedAt.current === null) startedAt.current = Date.now();
    if (value === "") startedAt.current = null; // erased everything: the turn hasn't started after all
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
