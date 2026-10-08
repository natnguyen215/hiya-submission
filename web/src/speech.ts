// Browser speech: push-to-talk recognition, text-to-speech with a distinct voice for the counselor, the parent and Beacon, and the per-tab "play Beacon audio" setting.
import { useState } from "react";
import type { ClientRole, Role } from "./types";

interface VoiceStyle {
  voice: SpeechSynthesisVoice | null;
  pitch: number;
  rate: number;
}

// Used when the machine has fewer than three voices, so the three speakers still sound different.
const FALLBACK_STYLES: Record<Role, { pitch: number; rate: number }> = {
  counselor: { pitch: 0.8, rate: 1.0 },
  parent: { pitch: 1.3, rate: 1.05 },
  beacon: { pitch: 1.0, rate: 0.9 },
};

// A voice's name is the only hint of how it sounds, and Maria should not get a male voice.
const FEMALE_VOICE = /female|zira|aria|jenny|samantha|susan|hazel|karen|moira|tessa|victoria/i;

let styles: Promise<Record<Role, VoiceStyle>> | null = null;
let cancellation = 0;

// Chrome can garbage-collect an utterance that nothing references while it is still speaking, and
// then its end event never fires. Holding the current one here prevents that.
let currentUtterance: SpeechSynthesisUtterance | null = null;

function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    const voices = speechSynthesis.getVoices();
    if (voices.length > 0) return resolve(voices);
    // Chrome fills the list asynchronously and announces it with voiceschanged. The timeout covers
    // browsers that never fire it (we then speak with the default voice).
    const done = () => resolve(speechSynthesis.getVoices());
    speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 2000);
  });
}

async function pickStyles(): Promise<Record<Role, VoiceStyle>> {
  const all = await loadVoices();
  const english = all.filter((v) => v.lang.toLowerCase().startsWith("en"));
  const pool = english.length > 0 ? english : all;
  const parent = pool.find((v) => FEMALE_VOICE.test(v.name)) ?? pool[0] ?? null;
  const others = pool.filter((v) => v !== parent);
  const voices: Record<Role, SpeechSynthesisVoice | null> = {
    counselor: others[0] ?? parent,
    parent,
    beacon: others[1] ?? others[0] ?? parent,
  };
  const distinct = new Set(Object.values(voices)).size === 3;
  const style = (who: Role): VoiceStyle => ({
    voice: voices[who],
    ...(distinct ? { pitch: 1, rate: 1 } : FALLBACK_STYLES[who]),
  });
  return { counselor: style("counselor"), parent: style("parent"), beacon: style("beacon") };
}

/** Speak `text` in `who`'s voice. Always resolves, even on errors, so callers never stall the call. */
export async function speak(text: string, who: Role): Promise<void> {
  if (!("speechSynthesis" in window)) return;
  const beforeLoading = cancellation;
  styles ??= pickStyles();
  const { voice, pitch, rate } = (await styles)[who];
  // Stop can happen while Chrome is loading voices, before an utterance exists to cancel.
  if (beforeLoading !== cancellation) return;
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.pitch = pitch;
    utterance.rate = rate;
    // Safety net for a browser that never reports the end: generous for the spoken length.
    const timer = setTimeout(finish, 4000 + text.split(" ").length * 700);
    function finish() {
      clearTimeout(timer);
      if (currentUtterance === utterance) currentUtterance = null;
      resolve();
    }
    utterance.onend = finish;
    // Fires for stopSpeaking() and for Chrome's "not-allowed" before the user has clicked the page.
    utterance.onerror = finish;
    currentUtterance = utterance;
    speechSynthesis.speak(utterance);
  });
}

export function stopSpeaking(): void {
  cancellation += 1;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

// Chrome's recognizer is prefixed and missing from TypeScript's DOM types, so declare the parts we use.
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  // `results` is every segment of the current run so far (final ones first), each a list of guesses.
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => Recognition;
  }
}

/** False outside Chrome: push-to-talk is unavailable there, and typing still works. */
export const canListen = window.webkitSpeechRecognition !== undefined;

// People let go of the key while the last syllable is still sounding, and recognition.stop() closes
// the microphone at once ("beacon" arrived as "beac"). Listening this much longer catches the ending.
const RELEASE_TAIL_MS = 400;

export interface Listening {
  /** Stops listening. Resolves with everything said (possibly ""), even after an error. */
  stop(): Promise<string>;
}

/**
 * Starts push-to-talk recognition (call only when `canListen`). `onText` gets the running text while
 * the key is held; `onError` gets problems worth showing the user.
 */
export function startListening(onText: (text: string) => void, onError: (message: string) => void): Listening {
  const recognition = new window.webkitSpeechRecognition!();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = true;

  let kept: string[] = []; // what earlier runs heard (Chrome ends runs on its own; see onend)
  let heard: string[] = []; // the current run's segments
  let held = true;
  let denied = false;
  let finish: (text: string) => void = () => {};
  const ended = new Promise<string>((resolve) => {
    finish = resolve;
  });
  const text = () => [...kept, ...heard].map((segment) => segment.trim()).filter(Boolean).join(" ");

  recognition.onresult = (event) => {
    heard = Array.from(event.results, (result) => result[0].transcript);
    // Only while held: after release the turn is on its way, and a late result (from a recognizer
    // that outlived the safety net in stop()) would leave stale text on screen.
    if (held) onText(text());
  };
  recognition.onerror = (event) => {
    // Silence, and recognition cut short: nothing the user needs to hear about.
    if (event.error === "no-speech" || event.error === "aborted") return;
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      denied = true; // Chrome won't ask again in this tab, so restarting would only fail again
      onError("Microphone permission was denied");
    } else {
      onError(`Speech recognition error: ${event.error}`);
    }
  };
  recognition.onend = () => {
    // A segment that isn't final by now never will be; keep it as the best guess we have.
    kept = [...kept, ...heard];
    heard = [];
    // Chrome ends recognition on its own (silence, about a minute, network). Still held: keep listening.
    if (held && !denied) recognition.start();
    else finish(text());
  };
  recognition.start();

  return {
    stop() {
      held = false;
      // The last final results arrive after stop() but before `end`, so the text is ready in onend.
      setTimeout(() => recognition.stop(), RELEASE_TAIL_MS);
      // Safety net, as in speak(): without an `end`, this tab would never release the floor and
      // Beacon (which waits for nobody to be holding push-to-talk) would never speak again.
      setTimeout(() => finish(text()), 3000);
      return ended;
    },
  };
}

/** Whether this tab plays Beacon's voice. Remembered per role, so a reload keeps the choice. */
export function useBeaconAudioSetting(role: ClientRole): [boolean, (on: boolean) => void] {
  const key = `beacon.playAudio.${role}`;
  const [on, setOn] = useState(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved !== null) return saved === "on";
    } catch {
      // Storage can be blocked (privacy settings); fall back to the default below.
    }
    // One tab should play Beacon in a live call; the counselor's is the natural one.
    return role === "counselor";
  });
  function update(next: boolean) {
    setOn(next);
    try {
      localStorage.setItem(key, next ? "on" : "off");
    } catch {
      // Not remembered across reloads, but still applies to this tab.
    }
  }
  return [on, update];
}
