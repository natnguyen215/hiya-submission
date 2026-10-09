// The Family Recap. All views show it after the call. It has plain-language sections, it can be
// read aloud, and it can be downloaded as Markdown.
import { useEffect, useRef, useState } from "react";
import { speak, stopSpeaking } from "./speech";
import type { Recap, RecapItem, RoomState } from "./types";

/** One line of the recap: an aid item, a task or a question. A field that it does not have is "". */
interface Entry {
  label: string;
  amount: string;
  note: string;
  deadline: string;
  refs: string[];
}

interface Section {
  key: string; // the React key and the CSS class (each section has its own color)
  title: string;
  entries: Entry[];
}

const UNVERIFIED_TITLE = "Numbers Beacon could not check against the documents:";

// The page, the spoken version and the Markdown all use this one list. So the three stay the same.
function sections(recap: Recap): Section[] {
  const money = (items: RecapItem[]): Entry[] => items.map((item) => ({ ...item, deadline: "" }));
  // Tasks and questions are only words: no amount or note.
  const words = (label: string, refs: string[], deadline = ""): Entry => {
    return { label, amount: "", note: "", deadline, refs };
  };
  // The heading says what the cost is, so do not show the item's label again.
  const cost = { ...recap.cost_of_attendance, label: "", deadline: "" };
  const result: Section[] = [
    { key: "cost", title: "Total cost for the year", entries: [cost] },
    { key: "grants", title: "Free money (grants) – you don't pay this back", entries: money(recap.grants) },
    { key: "loans", title: "Loans – must be repaid", entries: money(recap.loans) },
    {
      key: "work",
      title: "Work-study – earned through a campus job, paid as paychecks",
      entries: money(recap.work_study),
    },
    { key: "still", title: "What you may still need to pay or borrow", entries: money(recap.still_to_pay) },
    { key: "todo", title: "To do", entries: recap.todos.map((t) => words(t.task, t.refs, t.deadline)) },
  ];
  // If there is nothing to ask, do not show an empty section.
  if (recap.follow_ups.length > 0) {
    const entries = recap.follow_ups.map((f) => words(f.question, f.refs));
    result.push({ key: "follow-ups", title: "Still worth asking about", entries });
  }
  return result;
}

/** An entry as sentences. Examples: ["Pell Grant: $6,000.", "Free money."], ["Send forms.", "Deadline: July 15."]. */
function sentences({ label, amount, note, deadline }: Entry): string[] {
  const parts = [[label, amount].filter(Boolean).join(": "), note, deadline && `Deadline: ${deadline}`];
  return parts.filter(Boolean).map((part) => (/[.!?]$/.test(part) ? part : `${part}.`));
}

/** One paragraph for each section, for the speech engine. No reference ids. "$9,000" becomes "9,000 dollars". */
function spokenSections(recap: Recap, unverified: string[]): string[] {
  // A listener cannot see the warning on the screen. So say it before the numbers.
  const caveat =
    unverified.length > 0
      ? ["Some numbers could not be checked against the documents, so please check the written recap."]
      : [];
  return caveat.concat(sections(recap).map((section) => {
    const body = section.entries.length > 0 ? section.entries.flatMap(sentences).join(" ") : "None.";
    // Voices read "$" in different ways. All voices read the word "dollars" the same way.
    // The pattern accepts a comma only before three digits, so the comma in "$9,000, $6,000" stays a pause.
    return `${section.title}: ${body}`.replace(/\$(\d+(?:,\d{3})*(?:\.\d+)?)/g, "$1 dollars");
  }));
}

function toMarkdown(recap: Recap, unverified: string[]): string {
  const lines = ["# Family Recap", ""];
  if (unverified.length > 0) {
    lines.push(`**${UNVERIFIED_TITLE}**`, "", ...unverified.map((problem) => `- ${problem}`), "");
  }
  for (const section of sections(recap)) {
    lines.push(`## ${section.title}`, "");
    if (section.entries.length === 0) lines.push("- None");
    for (const entry of section.entries) {
      const refs = entry.refs.length > 0 ? ` (${entry.refs.join(", ")})` : "";
      lines.push(`- ${sentences(entry).join(" ")}${refs}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

function download(markdown: string): void {
  const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "family-recap.md";
  link.click();
  // The browser reads the blob after click() returns. Free it when the download has had time to start.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

interface FamilyRecapProps {
  state: RoomState;
  onRefHover?: (ref: string | null) => void; // the observer highlights the cited turn or document line
}

export function FamilyRecap({ state, onRefHover }: FamilyRecapProps) {
  const { recap, recap_unverified: unverified } = state;
  const status = state.status.recap;
  if (status === "none") return null;
  if (status === "error") {
    return (
      <section className="recap-status recap-error">
        <h2>Family Recap</h2>
        <p>The Family Recap could not be generated.</p>
      </section>
    );
  }
  // recap_ready always comes before the status "ready". `!recap` is only for the type checker.
  if (status === "generating" || !recap) {
    return (
      <section className="recap-status">
        <h2>Family Recap</h2>
        <p>Writing the Family Recap…</p>
      </section>
    );
  }
  return (
    <section className="family-recap">
      <header className="recap-header">
        <h2>Family Recap</h2>
        <ReadAloud recap={recap} unverified={unverified} />
        <button onClick={() => download(toMarkdown(recap, unverified))}>Download .md</button>
      </header>
      {unverified.length > 0 && (
        <div className="recap-unverified">
          <strong>{UNVERIFIED_TITLE}</strong>
          <ul>
            {unverified.map((problem, i) => (
              <li key={i}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      {sections(recap).map((section) => (
        <section key={section.key} className={`recap-section recap-${section.key}`}>
          <h3>{section.title}</h3>
          {section.entries.length === 0 && <p className="empty">None.</p>}
          <ul>
            {section.entries.map((entry, i) => (
              <li key={i} className="recap-entry">
                <div className="recap-line">
                  {entry.label && <span className="recap-label">{entry.label}</span>}
                  {entry.amount && <span className="recap-amount">{entry.amount}</span>}
                  {entry.deadline && <span className="recap-deadline">Deadline: {entry.deadline}</span>}
                  {/* One flex item, so the chips stay together when the line wraps. */}
                  <span>
                    {entry.refs.map((ref, j) => (
                      <span
                        key={j}
                        className="ref"
                        onMouseEnter={() => onRefHover?.(ref)}
                        onMouseLeave={() => onRefHover?.(null)}
                      >
                        {ref}
                      </span>
                    ))}
                  </span>
                </div>
                {entry.note && <p className="recap-note">{entry.note}</p>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}

/** Reads the recap in Beacon's voice, one section at a time. Only in this tab: the server and other tabs do not know. */
function ReadAloud({ recap, unverified }: { recap: Recap; unverified: string[] }) {
  const [reading, setReading] = useState(false);
  // The current reading. Stop aborts it, so the loop does not go to the next section.
  const run = useRef<AbortController | null>(null);

  async function read() {
    const controller = new AbortController();
    run.current = controller;
    setReading(true);
    for (const paragraph of spokenSections(recap, unverified)) {
      await speak(paragraph, "beacon"); // resolves early if stop() cancels the speech
      if (controller.signal.aborted) return;
    }
    run.current = null;
    setReading(false);
  }

  function stop() {
    run.current?.abort();
    run.current = null;
    stopSpeaking();
    setReading(false);
  }

  // A reset or a new call removes the recap. Stop reading the old recap.
  useEffect(
    () => () => {
      if (!run.current) return;
      run.current.abort();
      stopSpeaking();
    },
    [],
  );

  return <button onClick={reading ? stop : read}>{reading ? "Stop reading" : "Read aloud"}</button>;
}
