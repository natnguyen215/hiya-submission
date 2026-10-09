// The connection to the room. Each tab has one WebSocket. The server messages update the local
// state. If the connection closes, the tab connects again.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ClientMessage, ClientRole, Flag, RoomState, ServerMessage, Settings } from "./types";

type BeaconSay = Extract<ServerMessage, { type: "beacon_say" }>;

interface Options {
  // Called once for each line that Beacon says. The tab decides if it plays the line.
  onBeaconSay?: (say: BeaconSay) => void;
}

function upsert(flags: Flag[], flag: Flag): Flag[] {
  return flags.some((f) => f.id === flag.id) ? flags.map((f) => (f.id === flag.id ? flag : f)) : [...flags, flag];
}

// A snapshot replaces the full state. Each other message changes one part of it.
function apply(state: RoomState | null, message: ServerMessage): RoomState | null {
  if (message.type === "snapshot") return message.state;
  if (!state) return null; // a change has no meaning before the first snapshot
  switch (message.type) {
    case "turn_added":
      // Turn ids follow the transcript order (t1, t2, ...). A known id is a turn that we have.
      if (state.turns.some((t) => t.id === message.turn.id)) return state;
      return { ...state, turns: [...state.turns, message.turn] };
    case "flag_card":
    case "flag_updated":
      return { ...state, flags: upsert(state.flags, message.flag) };
    case "status":
      return { ...state, status: message.status };
    case "decision_log":
      return { ...state, log: [...state.log, message.entry] };
    case "recap_ready":
      return { ...state, recap: message.recap, recap_unverified: message.unverified };
    default:
      return state;
  }
}

export function useRoom(room: string, role: ClientRole, { onBeaconSay }: Options = {}) {
  const [state, setState] = useState<RoomState | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  // Async code that runs for a long time (the simulation runner, audio callbacks) reads the room
  // from this ref. A value from React state would stay as it was when the closure was made.
  const stateRef = useRef<RoomState | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const errorTimer = useRef<number | undefined>(undefined);

  // The socket handler is made once per connection. This ref gives it the newest callback.
  const onBeaconSayRef = useRef(onBeaconSay);
  useEffect(() => {
    onBeaconSayRef.current = onBeaconSay;
  });

  const showError = useCallback((message: string) => {
    setLastError(message);
    clearTimeout(errorTimer.current);
    errorTimer.current = window.setTimeout(() => setLastError(null), 5000);
  }, []);

  useEffect(() => {
    let closedByUs = false;
    let retryTimer: number | undefined;

    function handle(message: ServerMessage) {
      if (message.type === "error") return showError(message.message);
      if (message.type === "beacon_say") return onBeaconSayRef.current?.(message);
      if (message.type === "snapshot") setSettings(message.settings);
      stateRef.current = apply(stateRef.current, message);
      setState(stateRef.current);
    }

    function connect() {
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      const socket = new WebSocket(`${protocol}://${location.host}/ws`);
      socketRef.current = socket;
      socket.onopen = () => {
        setConnected(true);
        socket.send(JSON.stringify({ type: "join", room, role } satisfies ClientMessage));
      };
      socket.onmessage = (event) => handle(JSON.parse(event.data) as ServerMessage);
      socket.onclose = () => {
        setConnected(false);
        // The server sends a full snapshot after each join. So a new connection gets the full state again.
        if (!closedByUs) retryTimer = window.setTimeout(connect, 1000);
      };
    }

    connect();
    return () => {
      closedByUs = true;
      clearTimeout(retryTimer);
      socketRef.current?.close();
    };
  }, [room, role, showError]);

  const send = useCallback(
    (message: ClientMessage) => {
      const socket = socketRef.current;
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
      else showError("Not connected to the server yet. Try again in a moment.");
    },
    [showError],
  );

  return { state, settings, connected, lastError, showError, send, stateRef };
}
