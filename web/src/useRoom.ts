// The room connection: one WebSocket per tab, server messages folded into local state, reconnect on drop.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ClientMessage, ClientRole, Flag, RoomState, ServerMessage, Settings } from "./types";

type BeaconSay = Extract<ServerMessage, { type: "beacon_say" }>;

interface Options {
  // Called once per line Beacon says, so the tab can decide whether to play it.
  onBeaconSay?: (say: BeaconSay) => void;
}

function upsert(flags: Flag[], flag: Flag): Flag[] {
  return flags.some((f) => f.id === flag.id) ? flags.map((f) => (f.id === flag.id ? flag : f)) : [...flags, flag];
}

// A snapshot replaces everything; every other message is an increment on top of the last snapshot.
function apply(state: RoomState | null, message: ServerMessage): RoomState | null {
  if (message.type === "snapshot") return message.state;
  if (!state) return null; // increments mean nothing until the first snapshot arrives
  switch (message.type) {
    case "turn_added":
      // Turn ids are positional (t1, t2, ...), so a known id means we already have this turn.
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
  // Long-running async code (the simulation runner, audio callbacks) reads the room through this
  // ref: a value captured from React state would be frozen at the render that created the closure.
  const stateRef = useRef<RoomState | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const errorTimer = useRef<number | undefined>(undefined);

  // The socket handler is created once per connection, so it calls whatever callback the latest render passed.
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
        // The server answers every join with a full snapshot, so reconnecting is all it takes to resync.
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
