import { useEffect, useMemo, useState } from "react";
import KnowledgeGraph from "./Graph";
import Terminal, { type LogLine } from "./Terminal";
import { downloadExcel, fetchHealth, startJob, watchJob } from "./api";
import type { Health, Report, Verdict } from "./types";

const ACCEPT = ".pdf,.xlsx,.xlsm,.xls,.pptx,.ppt,.docx,.doc,.txt,.md,.csv,.png,.jpg,.jpeg,.webp";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [reqFiles, setReqFiles] = useState<File[]>([]);
  const [testFiles, setTestFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<Verdict | "all">("all");
  const [q, setQ] = useState("");
  const [logs, setLogs] = useState<LogLine[]>([]);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ ok: false, error: "API unreachable" }));
  }, []);

  const rows = useMemo(() => {
    if (!report) return [];
    return report.matches.filter((m) => {
      if (filter !== "all" && m.verdict !== filter) return false;
      const blob = `${m.test_id} ${m.requirement_id} ${m.rationale}`.toLowerCase();
      return !q || blob.includes(q.toLowerCase());
    });
  }, [report, filter, q]);

  const selectedMeta = useMemo(() => {
    if (!report || !selected) return null;
    return report.knowledge_graph.nodes.find((n) => n.id === selected) || null;
  }, [report, selected]);

  async function run() {
    setErr("");
    setBusy(true);
    setLogs([]);
    setReport(null);
    try {
      const id = await startJob(reqFiles, testFiles);
      watchJob(
        id,
        (line) => setLogs((prev) => [...prev, line]),
        (r, error) => {
          setBusy(false);
          if (error) setErr(error);
          if (r) {
            setReport(r);
            setSelected(null);
          }
        }
      );
    } catch (e) {
      setBusy(false);
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="app">
      <aside className="rail">
        <p className="eyebrow">Local · Ollama · knowledge graph</p>
        <h1>Req–Test Matcher</h1>
        <p className="lede">
          Map tests onto requirements, catch wrong expected results, and explore the graph.
          Nothing leaves this machine.
        </p>

        <div className={`pulse ${health?.ok ? "ok" : "bad"}`}>
          {health?.ok ? (
            <>
              Ollama <code>{health.host}</code>
              <br />
              {health.chat_model}
              {!health.chat_present ? " — pull this model" : ""}
            </>
          ) : (
            <>Ollama down. {health?.error || "Start ollama serve."}</>
          )}
        </div>

        <Drop label="Requirements" files={reqFiles} onChange={setReqFiles} />
        <Drop label="Test cases" files={testFiles} onChange={setTestFiles} />

        <button className="primary" disabled={busy || !reqFiles.length || !testFiles.length} onClick={run}>
          {busy ? "Agents working…" : "Run swarm"}
        </button>
        {busy && <p className="hint">Watch the terminal for live agent steps. This stays on your machine.</p>}
        {err && <p className="error">{err}</p>}

        {report && (
          <button className="ghost" onClick={() => downloadExcel(report).catch((e) => setErr(String(e)))}>
            Download Excel workbook
          </button>
        )}
      </aside>

      <main className="stage">
        <Terminal lines={logs} live={busy} />
        {!report && !busy && (
          <div className="empty">
            <h2>No run yet</h2>
            <p>Drop requirement and test documents, then run the swarm. The graph is zoomable and draggable.</p>
          </div>
        )}
        {busy && !report && (
          <div className="empty slim">
            <div className="spinner" />
            <h2>Swarm running</h2>
            <p>Short status lines appear in the terminal above.</p>
          </div>
        )}
        {report && (
          <>
            <section className="kpis">
              <Kpi n={report.requirements.length} l="Requirements" />
              <Kpi n={report.test_cases.length} l="Test cases" />
              <Kpi n={report.wrong_tests.length} l="Wrong" tone="bad" />
              <Kpi n={report.orphan_tests.length} l="Orphan" />
              <Kpi n={report.uncovered_requirements.length} l="Uncovered" />
              <Kpi n={report.knowledge_graph.node_count} l="Graph nodes" />
            </section>
            <p className="summary">{report.summary}</p>
            <KnowledgeGraph
              nodes={report.knowledge_graph?.nodes ?? []}
              edges={report.knowledge_graph?.edges ?? []}
              selectedId={selected}
              onSelect={setSelected}
            />
            {selectedMeta && (
              <div className="inspect">
                <strong>{selectedMeta.label}</strong>
                <span className="pill">{selectedMeta.kind}</span>
                {selectedMeta.verdict && <span className={`pill ${selectedMeta.verdict}`}>{selectedMeta.verdict}</span>}
                <p>{selectedMeta.title || selectedMeta.id}</p>
              </div>
            )}
            <div className="table-bar">
              <h2>Traceability</h2>
              <input placeholder="Filter rows…" value={q} onChange={(e) => setQ(e.target.value)} />
              <select value={filter} onChange={(e) => setFilter(e.target.value as Verdict | "all")}>
                <option value="all">All verdicts</option>
                {["aligned", "partial", "wrong", "orphan", "uncovered"].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Test</th>
                    <th>Requirement</th>
                    <th>Verdict</th>
                    <th>Score</th>
                    <th>Why</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((m, i) => (
                    <tr
                      key={`${m.test_id}-${m.requirement_id}-${i}`}
                      onClick={() => setSelected(m.test_id !== "—" ? `TC:${m.test_id}` : m.requirement_id ? `REQ:${m.requirement_id}` : null)}
                    >
                      <td>{m.test_id}</td>
                      <td>{m.requirement_id || "—"}</td>
                      <td><span className={`pill ${m.verdict}`}>{m.verdict}</span></td>
                      <td>{m.score.toFixed(2)}</td>
                      <td>{m.rationale}{m.issues?.length ? ` (${m.issues.join("; ")})` : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details className="swarm">
              <summary>Agent swarm log</summary>
              <ol>
                {report.agent_trace.map((t, i) => (
                  <li key={i}>
                    <strong>{t.agent}</strong> — {t.action}
                    <div className="muted">{t.detail}</div>
                  </li>
                ))}
              </ol>
            </details>
          </>
        )}
      </main>
    </div>
  );
}

function Kpi({ n, l, tone }: { n: number; l: string; tone?: string }) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <b>{n}</b>
      <span>{l}</span>
    </div>
  );
}

function Drop({ label, files, onChange }: { label: string; files: File[]; onChange: (f: File[]) => void }) {
  return (
    <label className="drop">
      <span>{label}</span>
      <small>{files.length ? files.map((f) => f.name).join(", ") : "PDF, Excel, PPT, Word, images"}</small>
      <input type="file" multiple accept={ACCEPT} onChange={(e) => onChange([...e.target.files || []])} />
    </label>
  );
}
