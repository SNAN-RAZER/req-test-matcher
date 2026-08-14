export type Verdict = "aligned" | "partial" | "wrong" | "orphan" | "uncovered";

export type MatchRow = {
  test_id: string;
  requirement_id: string | null;
  score: number;
  verdict: Verdict;
  rationale: string;
  issues: string[];
};

export type Item = {
  id: string;
  title: string;
  text: string;
  source_file: string;
  parent_file: string;
};

export type GraphNode = {
  id: string;
  kind: string;
  label: string;
  title?: string;
  verdict?: string;
};

export type GraphEdge = { source: string; target: string; rel: string };

export type Report = {
  requirements: Item[];
  test_cases: Item[];
  matches: MatchRow[];
  uncovered_requirements: string[];
  wrong_tests: MatchRow[];
  orphan_tests: MatchRow[];
  summary: string;
  model: string;
  vision_model: string;
  files_processed: string[];
  agent_trace: { agent: string; role: string; action: string; detail: string }[];
  knowledge_graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    node_count: number;
    edge_count: number;
  };
};

export type Health = {
  ok: boolean;
  host?: string;
  error?: string;
  chat_model?: string;
  vision_model?: string;
  chat_present?: boolean;
  vision_present?: boolean;
};
