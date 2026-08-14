import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphEdge, GraphNode } from "./types";

const COLORS: Record<string, string> = {
  requirement: "#3dd6c6",
  test: "#7eb8ff",
  document: "#c9a6ff",
  concept: "#e7b549",
  gap: "#ff7a90",
  unknown: "#8b93a7",
};

type SimNode = GraphNode & { x: number; y: number; vx: number; vy: number };

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
};

export default function KnowledgeGraph({ nodes, edges, selectedId, onSelect }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sim = useRef<SimNode[]>([]);
  const selectedRef = useRef(selectedId);
  const hoverRef = useRef<string | null>(null);
  const kindsRef = useRef<Record<string, boolean>>({});
  const [hover, setHover] = useState<string | null>(null);
  const [kinds, setKinds] = useState<Record<string, boolean>>({
    requirement: true,
    test: true,
    document: true,
    concept: true,
    gap: true,
  });
  const view = useRef({ x: 0, y: 0, k: 1 });
  const drag = useRef<{ id?: string; pan?: boolean; lx: number; ly: number } | null>(null);

  selectedRef.current = selectedId;
  hoverRef.current = hover;
  kindsRef.current = kinds;

  const linkIndex = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const e of edges) {
      if (!m.has(e.source)) m.set(e.source, []);
      if (!m.has(e.target)) m.set(e.target, []);
      m.get(e.source)!.push(e.target);
      m.get(e.target)!.push(e.source);
    }
    return m;
  }, [edges]);

  useEffect(() => {
    sim.current = nodes.map((n, i) => {
      const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
      return { ...n, x: Math.cos(a) * 180, y: Math.sin(a) * 140, vx: 0, vy: 0 };
    });
  }, [nodes]);

  useEffect(() => {
    let frames = 0;
    let raf = 0;
    const tick = () => {
      const list = sim.current;
      const kindOn = kindsRef.current;
      if (frames < 240 && !drag.current?.id) {
        for (let i = 0; i < list.length; i++) {
          for (let j = i + 1; j < list.length; j++) {
            const a = list[i];
            const b = list[j];
            let dx = a.x - b.x;
            let dy = a.y - b.y;
            const d2 = dx * dx + dy * dy || 0.01;
            const f = 1400 / d2;
            a.vx += dx * f;
            a.vy += dy * f;
            b.vx -= dx * f;
            b.vy -= dy * f;
          }
        }
        for (const e of edges) {
          const a = list.find((n) => n.id === e.source);
          const b = list.find((n) => n.id === e.target);
          if (!a || !b) continue;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          a.vx += dx * 0.012;
          a.vy += dy * 0.012;
          b.vx -= dx * 0.012;
          b.vy -= dy * 0.012;
        }
        for (const n of list) {
          n.vx += -n.x * 0.004;
          n.vy += -n.y * 0.004;
          n.vx *= 0.82;
          n.vy *= 0.82;
          n.x += n.vx;
          n.y += n.vy;
        }
        frames += 1;
      }
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (canvas && ctx) {
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, rect.width, rect.height);
        ctx.save();
        ctx.translate(rect.width / 2 + view.current.x, rect.height / 2 + view.current.y);
        ctx.scale(view.current.k, view.current.k);
        const byId = Object.fromEntries(list.map((n) => [n.id, n]));
        const sel = selectedRef.current;
        ctx.lineWidth = 1 / view.current.k;
        for (const e of edges) {
          if (kindOn[byId[e.source]?.kind] === false || kindOn[byId[e.target]?.kind] === false) continue;
          const a = byId[e.source];
          const b = byId[e.target];
          if (!a || !b) continue;
          const hot = sel && (e.source === sel || e.target === sel);
          ctx.strokeStyle = hot ? "#f3efe7" : "rgba(243,239,231,0.18)";
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        for (const n of list) {
          if (kindOn[n.kind] === false) continue;
          const r = n.kind === "concept" ? 5 : 8;
          const active = n.id === sel || n.id === hoverRef.current;
          ctx.beginPath();
          ctx.fillStyle = COLORS[n.kind] || COLORS.unknown;
          const dim = Boolean(sel && n.id !== sel && !linkIndex.get(sel)?.includes(n.id));
          ctx.globalAlpha = dim ? 0.28 : 1;
          ctx.arc(n.x, n.y, active ? r + 2 : r, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.fillStyle = "#f3efe7";
          ctx.font = `${12 / view.current.k}px ui-sans-serif, system-ui, sans-serif`;
          ctx.fillText(n.label, n.x + 10, n.y + 4);
        }
        ctx.restore();
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [edges, linkIndex]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      view.current.k = Math.min(4, Math.max(0.25, view.current.k * (ev.deltaY < 0 ? 1.08 : 0.92)));
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, []);

  function toWorld(ev: React.MouseEvent) {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    return {
      x: (ev.clientX - rect.left - rect.width / 2 - view.current.x) / view.current.k,
      y: (ev.clientY - rect.top - rect.height / 2 - view.current.y) / view.current.k,
    };
  }

  function hit(ev: React.MouseEvent) {
    const p = toWorld(ev);
    let best: SimNode | null = null;
    let bestD = 14 / view.current.k;
    for (const n of sim.current) {
      if (kinds[n.kind] === false) continue;
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d < bestD) {
        best = n;
        bestD = d;
      }
    }
    return best;
  }

  return (
    <div className="graph-wrap">
      <div className="graph-toolbar">
        {Object.keys(kinds).map((k) => (
          <label key={k} className="chip">
            <input type="checkbox" checked={kinds[k]} onChange={() => setKinds((s) => ({ ...s, [k]: !s[k] }))} />
            <span className="dot" style={{ background: COLORS[k] }} />
            {k}
          </label>
        ))}
        <span className="hint">Scroll zoom · drag empty space to pan · drag a node · click to inspect</span>
      </div>
      <canvas
        ref={canvasRef}
        className="graph-canvas"
        onMouseDown={(ev) => {
          const n = hit(ev);
          if (n) {
            drag.current = { id: n.id, lx: ev.clientX, ly: ev.clientY };
            onSelect(n.id);
          } else {
            drag.current = { pan: true, lx: ev.clientX, ly: ev.clientY };
            onSelect(null);
          }
        }}
        onMouseMove={(ev) => {
          setHover(hit(ev)?.id ?? null);
          const d = drag.current;
          if (!d) return;
          if (d.id) {
            const node = sim.current.find((x) => x.id === d.id);
            if (node) {
              const p = toWorld(ev);
              node.x = p.x;
              node.y = p.y;
              node.vx = 0;
              node.vy = 0;
            }
          } else if (d.pan) {
            view.current.x += ev.clientX - d.lx;
            view.current.y += ev.clientY - d.ly;
            d.lx = ev.clientX;
            d.ly = ev.clientY;
          }
        }}
        onMouseUp={() => {
          drag.current = null;
        }}
        onMouseLeave={() => {
          drag.current = null;
          setHover(null);
        }}
      />
    </div>
  );
}
