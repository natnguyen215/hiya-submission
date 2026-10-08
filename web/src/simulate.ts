// The demo script runner: plays a scripted call into the room line by line, pacing each line on the server's analysis and Beacon's speech.
import { speak } from "./speech";
import type { ClientMessage, RoomState, RoomStatus, ScriptTurn, Settings } from "./types";

const POLL_MS = 100;

interface SimulationOptions {
  send: (message: ClientMessage) => void;
  stateRef: { readonly current: RoomState | null };
  settings: Settings;
  textOnly: boolean; // skip the persona voices (Beacon's audio is the observer's call)
  signal: AbortSignal; // Stop aborts it
  onProgress: (text: string, expect?: ScriptTurn["expect"]) => void;
}

/** Resolves after `ms`, or rejects as soon as the run is stopped. */
function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(signal.reason);
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Polls until `check()` is true or `timeoutMs` passes. Polling (rather than reacting to each
 * message) is enough because every condition below describes where the room settles (the turn
 * exists, analysis caught up, Beacon is quiet), not a passing moment a 100 ms poll could miss.
 */
async function waitUntil(check: () => boolean, signal: AbortSignal, timeoutMs = Infinity): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!check() && Date.now() < deadline) await sleep(POLL_MS, signal);
}

function beaconIdle(status: RoomStatus): boolean {
  return status.speech_pending === 0 && status.speaking_turn_id === null;
}

export async function runSimulation(script: ScriptTurn[], options: SimulationOptions): Promise<void> {
  const { send, stateRef, settings, textOnly, signal, onProgress } = options;
  const room = (): RoomState => {
    if (!stateRef.current) throw new Error("Not connected to the room.");
    return stateRef.current;
  };
  // Waits during the call also fail fast if someone ends or resets it, instead of waiting forever
  // for a turn the server rejected.
  const waitDuringCall = (check: () => boolean, timeoutMs?: number) =>
    waitUntil(
      () => {
        if (room().status.call_status !== "live") throw new Error("The call is no longer live.");
        return check();
      },
      signal,
      timeoutMs,
    );

  onProgress("Resetting the room…");
  send({ type: "reset_room" });
  // Wait for the reset's snapshot, or the checks below could pass on the previous call's state.
  // (An idle room never has turns: the server only accepts turns while the call is live.)
  await waitUntil(() => room().status.call_status === "idle", signal);
  send({ type: "start_call", simulated: true });
  await waitUntil(() => room().status.call_status === "live", signal);

  onProgress("Waiting for Beacon's opening line…");
  // The opening is over once it is in the transcript and nothing is queued or playing. Checking the
  // transcript avoids racing the first status message, which may still show an idle speaker.
  await waitDuringCall(() => room().turns.some((t) => t.role === "beacon") && beaconIdle(room().status));

  for (const [index, line] of script.entries()) {
    const step = (phase: string) => onProgress(`Line ${index + 1} of ${script.length} · ${phase}`, line.expect);

    step("pausing");
    await sleep(line.pause_before_ms, signal);
    if (!textOnly) {
      step(`${line.role} speaking`);
      await speak(line.text, line.role);
      signal.throwIfAborted(); // Stop cancels speech, which ends speak() early
    }

    const before = room().turns.length;
    send({ type: "sim_turn", role: line.role, text: line.text, gap_ms: line.pause_before_ms });
    step("waiting for the server");
    // The line's 1-based position in the transcript, the unit analyzed_turn_count counts in.
    // Searching past `before` skips anything already there, e.g. an identical earlier line.
    let position = 0;
    await waitDuringCall(() => {
      const found = room().turns.findIndex((t, i) => i >= before && t.role === line.role && t.text === line.text.trim());
      position = found + 1;
      return found >= 0;
    });

    step("waiting for analysis");
    await waitDuringCall(
      () => room().status.analyzed_turn_count >= position,
      settings.sim_max_wait_for_analysis_seconds * 1000,
    );

    step("waiting for Beacon");
    // Safe to check right after the analysis: the server counts any line that analysis decided on
    // in speech_pending in the same status message that advances analyzed_turn_count.
    await waitDuringCall(() => beaconIdle(room().status));
  }

  send({ type: "end_call" });
  onProgress("Finished: the call has ended.");
}
