import { useEffect, useRef } from "react";

export type LogLine = {
  ts?: string;
  agent?: string;
  action?: string;
  detail?: string;
  type?: string;
};

export default function Terminal({ lines, live }: { lines: LogLine[]; live: boolean }) {
  const scroller = useRef<HTMLDivElement>(null);
  const pin = useRef(true);

  useEffect(() => {
    const el = scroller.current;
    if (el && pin.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <section className="term" aria-label="Run log (read only)">
      <header className="term-bar">
        <span className="term-dots" aria-hidden="true" />
        <span>activity</span>
        <span className="term-live">{live ? "live · read only" : "idle"}</span>
      </header>
      <div
        className="term-body"
        ref={scroller}
        tabIndex={0}
        onScroll={(e) => {
          const el = e.currentTarget;
          pin.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {lines.length === 0 && <div className="term-muted">waiting for a run…</div>}
        {lines.map((ln, i) => (
          <div key={i} className={`term-line ${ln.action === "failed" ? "err" : ""}`}>
            <span className="term-ts">{ln.ts || ""}</span>
            <span className="term-ag">{ln.agent || "sys"}</span>
            <span className="term-act">{ln.action || ""}</span>
            <span className="term-dt">{ln.detail || ""}</span>
          </div>
        ))}
        {live && <div className="term-cursor">█</div>}
      </div>
    </section>
  );
}
