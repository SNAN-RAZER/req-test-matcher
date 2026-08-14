# Req-Test Matcher

Private LAN app: a **swarm of specialist agents** builds a **knowledge graph** of requirements and tests, then flags wrong tests. No vector RAG. All inference is Ollama on this machine.

## Why a graph, not RAG

RAG would embed chunks and retrieve by cosine similarity. This app instead creates nodes and edges:

- `REQ` / `TC` / `DOC` / `CONCEPT`
- `extracted_from`, `nested_in`, `cites`, `mentions`, `tests`, `contradicts`, `aligned`, `wrong`, `uncovered`

A test is matched to requirements by **graph neighborhood** (shared concepts, explicit IDs, nested documents), then the judge agent labels the edge.

The graph is saved at `data/kg/latest.json`.

## Agent swarm

| Agent | Job |
|---|---|
| **embedded_doc_agent** | Nested PDF/Office attachments |
| **table_agent** | Excel, CSV, markdown tables |
| **semantic_agent** | Narrative PDF / PPT / Word |
| **vision_agent** | Screenshots (`llava:7b`) |
| **requirement_extractor_agent** | REQ nodes |
| **test_extractor_agent** | TC nodes |
| **knowledge_graph_agent** | Local NetworkX graph + relations |
| **judge_agent** | Walk the graph → aligned / wrong / orphan |
| **coverage_agent** | Requirements with no covering tests |

## Setup (Debian / Ubuntu)

Do **not** run `pip install` with system `python3`. This distro blocks it (`externally-managed-environment`). Use a venv, and call `python3` (there is no `python` command):

```bash
cd ~/Projects/req-test-matcher
sudo apt install -y python3 python3-venv python3-full
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.main
```

Or:

```bash
chmod +x run.sh
./run.sh
```

Then open http://127.0.0.1:8080

## React UI + Excel export

The UI is React (Vite). Build it once, then the API serves it:

```bash
sudo apt install -y npm
cd ~/Projects/req-test-matcher/web
npm install
npm run build
cd ..
.venv/bin/python -m app.main
```

During UI work you can run two processes:

```bash
.venv/bin/python -m app.main          # API on :8080
cd web && npm run dev                 # UI on :5173, proxies /api
```

After a match, use **Download Excel workbook**. Sheets: Summary, Traceability, Requirements, Test cases, Wrong tests, Uncovered, graph nodes/edges, agent log.

The graph is interactive: zoom, pan, drag nodes, click a node or table row, toggle kinds.

Ollama models:

```bash
ollama pull llama3.1:8b
ollama pull llava:7b   # optional, vision
```
