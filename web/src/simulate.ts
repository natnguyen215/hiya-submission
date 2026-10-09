// The script runner. It sends a script to the room, one line at a time. Before each line, it
// waits for the analysis of the previous line and for Beacon to finish speaking.
import { speak } from "./speech";
import type { ClientMessage, RoomState, RoomStatus, ScriptTurn, Settings } from "./types";

const POLL_MS = 100;
// A text-only run waits about as long as a person needs to read each line. Without this wait,
// the lines appear as fast as the analysis runs, and the viewer cannot follow the call.
const READ_MS_BASE = 1500;
const READ_MS_PER_WORD = 300;

/** The time to read a line on screen. A text-only run uses it instead of the spoken audio. */
export function readingTimeMs(text: string): number {
  return READ_MS_BASE + READ_MS_PER_WORD * text.split(/\s+/).filter(Boolean).length;
}

interface SimulationOptions {
  send: (message: ClientMessage) => void;
  stateRef: { readonly current: RoomState | null };
  settings: Settings;
  textOnly: boolean; // do not speak the counselor's and the parent's lines
  signal: AbortSignal; // the Stop button aborts the run
  onProgress: (text: string, expect?: ScriptTurn["expect"]) => void;
}

/** Resolves after `ms`. Rejects at once if the run stops. */
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
 * Checks every 100 ms until `check()` is true. Rejects after `timeoutMs`.
 * A poll is sufficient: each condition below stays true when it becomes true (the turn exists,
 * the analysis caught up, Beacon is quiet). So the poll cannot miss it.
 */
async function waitUntil(check: () => boolean, signal: AbortSignal, timeoutMs = Infinity): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  signal.throwIfAborted();
  while (!check()) {
    if (Date.now() >= deadline) throw new Error("Timed out waiting for the server's analysis.");
    await sleep(POLL_MS, signal);
  }
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
  // If a person ends or resets the call, stop at once. Do not wait for a turn that the server refused.
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
  // Wait for the snapshot after the reset. If not, the checks below can use the previous call's
  // state. (An idle room has no turns: the server accepts turns only during a live call.)
  await waitUntil(() => room().status.call_status === "idle", signal);
  send({ type: "start_call", simulated: true });
  await waitUntil(() => room().status.call_status === "live", signal);

  onProgress("Waiting for Beacon's opening line…");
  // The opening line is done when it is in the transcript and nothing is in the queue or playing.
  // The check of the transcript is necessary: the first status message can still show Beacon idle.
  await waitDuringCall(() => room().turns.some((t) => t.role === "beacon") && beaconIdle(room().status));

  for (const [index, line] of script.entries()) {
    const step = (phase: string) => onProgress(`Line ${index + 1} of ${script.length} · ${phase}`, line.expect);

    step("pausing");
    await sleep(line.pause_before_ms, signal);
    step(`${line.role} speaking`);
    if (textOnly) await sleep(readingTimeMs(line.text), signal);
    else {
      await speak(line.text, line.role);
      signal.throwIfAborted(); // Stop cancels the speech, so speak() ends early
    }

    const before = room().turns.length;
    send({ type: "sim_turn", role: line.role, text: line.text, gap_ms: line.pause_before_ms });
    step("waiting for the server");
    // The line's position in the transcript (from 1), which is how analyzed_turn_count counts.
    // Look only after `before`, to skip an earlier line with the same text.
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
    // This check is safe just after the analysis. The status message that moves
    // analyzed_turn_count also includes the analysis's line in speech_pending.
    await waitDuringCall(() => beaconIdle(room().status));
  }

  send({ type: "end_call" });
  onProgress("Finished: the call has ended.");
}
