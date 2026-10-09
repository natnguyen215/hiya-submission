// Speech in the browser: push-to-talk speech recognition, text-to-speech with a different voice
// for the counselor, the parent and Beacon, and the "Play Beacon audio here" setting of each tab.
import { useState } from "react";
import type { ClientRole, Role } from "./types";

interface VoiceStyle {
  voice: SpeechSynthesisVoice | null;
  pitch: number;
  rate: number;
}

// Used if the computer has fewer than three voices, so that the three speakers sound different.
const FALLBACK_STYLES: Record<Role, { pitch: number; rate: number }> = {
  counselor: { pitch: 0.8, rate: 1.0 },
  parent: { pitch: 1.3, rate: 1.05 },
  beacon: { pitch: 1.0, rate: 0.9 },
};

// Only the name of a voice tells how it sounds. Maria must not get a male voice.
const FEMALE_VOICE = /female|zira|aria|jenny|samantha|susan|hazel|karen|moira|tessa|victoria/i;

let styles: Promise<Record<Role, VoiceStyle>> | null = null;
let cancellation = 0;

// Chrome can delete an utterance that has no reference while it speaks. Then its end event does
// not fire. This reference prevents that.
let currentUtterance: SpeechSynthesisUtterance | null = null;

function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  return new Promise((resolve) => {
    const voices = speechSynthesis.getVoices();
    if (voices.length > 0) return resolve(voices);
    // Chrome loads the voices later and then fires voiceschanged. Some browsers never fire it.
    // After the timeout, speak with the default voice.
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

/** Speaks `text` in the voice of `who`. Always resolves, also after an error, so the call does not stop. */
export async function speak(text: string, who: Role): Promise<void> {
  if (!("speechSynthesis" in window)) return;
  const beforeLoading = cancellation;
  styles ??= pickStyles();
  const { voice, pitch, rate } = (await styles)[who];
  // Stop can come while Chrome loads the voices, before there is an utterance to cancel.
  if (beforeLoading !== cancellation) return;
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice;
    utterance.pitch = pitch;
    utterance.rate = rate;
    // For a browser that does not report the end. The time is more than the line needs.
    const timer = setTimeout(finish, 4000 + text.split(" ").length * 700);
    function finish() {
      clearTimeout(timer);
      if (currentUtterance === utterance) currentUtterance = null;
      resolve();
    }
    utterance.onend = finish;
    // Fires after stopSpeaking(), and for Chrome's "not-allowed" before the user clicks in the page.
    utterance.onerror = finish;
    currentUtterance = utterance;
    speechSynthesis.speak(utterance);
  });
}

export function stopSpeaking(): void {
  cancellation += 1;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

// TypeScript does not know Chrome's speech recognizer (webkitSpeechRecognition). These are the parts we use.
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  // `results` has all segments of the current run (final ones first). Each segment is a list of guesses.
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

/** False if the browser is not Chrome. Then push-to-talk is not available, but typing works. */
export const canListen = window.webkitSpeechRecognition !== undefined;

// People release the key before the last syllable ends. recognition.stop() closes the microphone at
// once, so "beacon" became "beac". The recognizer listens this much longer to get the full word.
const RELEASE_TAIL_MS = 400;

export interface Listening {
  /** Stops listening. Resolves with all the text (it can be ""), also after an error. */
  stop(): Promise<string>;
}

/**
 * Starts push-to-talk recognition. Call it only if `canListen` is true.
 * `onText` gets the text while the key is down. `onError` gets problems to show to the user.
 */
export function startListening(onText: (text: string) => void, onError: (message: string) => void): Listening {
  const recognition = new window.webkitSpeechRecognition!();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = true;

  let kept: string[] = []; // the text of earlier runs (Chrome can end a run itself; see onend)
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
    // Only while the key is down. After the release, the turn is sent. A late result would put
    // old text on the screen.
    if (held) onText(text());
  };
  recognition.onerror = (event) => {
    // Silence, or a stopped recognition: the user does not need to know.
    if (event.error === "no-speech" || event.error === "aborted") return;
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      denied = true; // Chrome does not ask again in this tab, so a restart would fail again
      onError("Microphone permission was denied");
    } else {
      onError(`Speech recognition error: ${event.error}`);
    }
  };
  recognition.onend = () => {
    // A segment that is not final now will not become final. Keep it: it is the best guess.
    kept = [...kept, ...heard];
    heard = [];
    // Chrome can end the recognition itself (silence, about one minute, network). If the key is
    // still down, start again.
    if (held && !denied) recognition.start();
    else finish(text());
  };
  recognition.start();

  return {
    stop() {
      held = false;
      // The last results arrive after stop() and before `end`. So the text is ready in onend.
      setTimeout(() => recognition.stop(), RELEASE_TAIL_MS);
      // If `end` never comes, this tab would hold push-to-talk forever. Then Beacon could not
      // speak again, because it waits until nobody holds push-to-talk.
      setTimeout(() => finish(text()), 3000);
      return ended;
    },
  };
}

/** If this tab plays Beacon's voice. The browser keeps the choice for each role, also after a reload. */
export function useBeaconAudioSetting(role: ClientRole): [boolean, (on: boolean) => void] {
  const key = `beacon.playAudio.${role}`;
  const [on, setOn] = useState(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved !== null) return saved === "on";
    } catch {
      // Privacy settings can block storage. Then use the default below.
    }
    // In a live call, one tab plays Beacon. The default is the counselor's tab.
    return role === "counselor";
  });
  function update(next: boolean) {
    setOn(next);
    try {
      localStorage.setItem(key, next ? "on" : "off");
    } catch {
      // A reload loses the choice, but it applies to this tab now.
    }
  }
  return [on, update];
}
