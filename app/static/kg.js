/* Local force-directed knowledge graph. No CDN. */
(function (global) {
  const COLORS = {
    requirement: "#6ee7c5",
    test: "#7dd3fc",
    document: "#c4b5fd",
    concept: "#fbbf24",
    gap: "#fb7185",
    unknown: "#93a0b5",
  };

  function renderKnowledgeGraph(canvas, graph) {
    if (!canvas || !graph) return;
    const nodes = (graph.nodes || []).map((n, i) => ({
      ...n,
      x: Math.cos((i / Math.max(graph.nodes.length, 1)) * Math.PI * 2) * 160 + canvas.width / 2,
      y: Math.sin((i / Math.max(graph.nodes.length, 1)) * Math.PI * 2) * 120 + canvas.height / 2,
      vx: 0,
      vy: 0,
    }));
    const index = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const edges = (graph.edges || []).filter((e) => index[e.source] && index[e.target]);
    const ctx = canvas.getContext("2d");
    let frames = 0;

    function tick() {
      frames += 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          let dx = a.x - b.x, dy = a.y - b.y;
          let d2 = dx * dx + dy * dy || 1;
          const force = 1800 / d2;
          dx *= force; dy *= force;
          a.vx += dx; a.vy += dy;
          b.vx -= dx; b.vy -= dy;
        }
      }
      for (const e of edges) {
        const a = index[e.source], b = index[e.target];
        const dx = b.x - a.x, dy = b.y - a.y;
        a.vx += dx * 0.01; a.vy += dy * 0.01;
        b.vx -= dx * 0.01; b.vy -= dy * 0.01;
      }
      const cx = canvas.width / 2, cy = canvas.height / 2;
      for (const n of nodes) {
        n.vx += (cx - n.x) * 0.002;
        n.vy += (cy - n.y) * 0.002;
        n.vx *= 0.85; n.vy *= 0.85;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(24, Math.min(canvas.width - 24, n.x));
        n.y = Math.max(24, Math.min(canvas.height - 24, n.y));
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = "#2a3140";
      ctx.lineWidth = 1;
      for (const e of edges) {
        const a = index[e.source], b = index[e.target];
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      for (const n of nodes) {
        ctx.beginPath();
        ctx.fillStyle = COLORS[n.kind] || COLORS.unknown;
        const r = n.kind === "concept" ? 5 : 8;
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#e8edf5";
        ctx.font = "11px ui-sans-serif, system-ui";
        ctx.fillText(n.label, n.x + 10, n.y + 4);
      }
      if (frames < 180) requestAnimationFrame(tick);
    }
    tick();
  }

  global.renderKnowledgeGraph = renderKnowledgeGraph;
})(window);
