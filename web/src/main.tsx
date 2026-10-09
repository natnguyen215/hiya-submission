// The entry point. The URL path selects the view (/call, /observer or the start page).
// ?room= selects the room.
import { createRoot } from "react-dom/client";
import { CallView } from "./CallView";
import { ObserverView } from "./ObserverView";
import "./styles.css";

const params = new URLSearchParams(location.search);
const room = params.get("room") || "demo";

function Landing() {
  const query = `room=${encodeURIComponent(room)}`;
  return (
    <main className="landing">
      <h1>★ Beacon</h1>
      <p>Asks the question the family won't ask. Open each view in its own tab (room “{room}”):</p>
      <ul>
        <li>
          <a href={`/call?${query}&role=counselor`}>Counselor call view</a>
        </li>
        <li>
          <a href={`/call?${query}&role=parent`}>Parent call view</a>
        </li>
        <li>
          <a href={`/observer?${query}`}>Observer dashboard</a>
        </li>
      </ul>
    </main>
  );
}

function App() {
  if (location.pathname === "/observer") return <ObserverView room={room} />;
  if (location.pathname === "/call") {
    return <CallView room={room} role={params.get("role") === "parent" ? "parent" : "counselor"} />;
  }
  return <Landing />;
}

// No <StrictMode>. In development it mounts each component two times, so each tab would open,
// close and open its WebSocket again. The server would see an extra join.
createRoot(document.getElementById("root")!).render(<App />);
