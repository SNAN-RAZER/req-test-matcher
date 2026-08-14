"""LangGraph swarm: specialists run in parallel, then extractors and judges."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base import Blackboard
from app.agents.coverage import CoverageAgent, ReportAgent
from app.agents.embedded import EmbeddedDocAgent
from app.agents.extractors import RequirementExtractorAgent, TestExtractorAgent
from app.agents.judge import JudgeAgent
from app.agents.kg import KnowledgeGraphAgent
from app.agents.semantic import SemanticAgent
from app.agents.table import TableAgent
from app.agents.vision import VisionAgent
from app.models import AnalysisReport

UNPACK = EmbeddedDocAgent()
TABLE = TableAgent()
SEMANTIC = SemanticAgent()
VISION = VisionAgent()
REQS = RequirementExtractorAgent()
TESTS = TestExtractorAgent()
KG = KnowledgeGraphAgent()
JUDGE = JudgeAgent()
COVER = CoverageAgent()
REPORT = ReportAgent()


class SwarmState(TypedDict, total=False):
    board: Blackboard


def _board(state: SwarmState) -> Blackboard:
    board = state.get("board")
    if not isinstance(board, Blackboard):
        raise RuntimeError("swarm blackboard missing")
    return board


def node_unpack(state: SwarmState) -> dict[str, Any]:
    board = _board(state)
    board.log(UNPACK.name, UNPACK.role, "start", "Unpacking files and nested attachments")
    UNPACK.run(board)
    return {"board": board}


def node_specialists(state: SwarmState) -> dict[str, Any]:
    board = _board(state)
    board.log(TABLE.name, TABLE.role, "start", "Reading tables")
    TABLE.run(board)
    board.log(SEMANTIC.name, SEMANTIC.role, "start", "Reading narrative text")
    SEMANTIC.run(board)
    board.log(VISION.name, VISION.role, "start", "Reading images (skipped if no vision model)")
    VISION.run(board)
    board.log(
        "swarm_router",
        "Coordinate modality specialists",
        "fan_out",
        f"table={len(board.table_text)} semantic={len(board.semantic_text)} vision={len(board.vision_text)}",
    )
    return {"board": board}


def node_extract(state: SwarmState) -> dict[str, Any]:
    board = _board(state)
    board.log(REQS.name, REQS.role, "start", "Extracting requirements")
    REQS.run(board)
    board.log(TESTS.name, TESTS.role, "start", "Extracting test cases")
    TESTS.run(board)
    return {"board": board}


def node_kg(state: SwarmState) -> dict[str, Any]:
    board = _board(state)
    board.log(KG.name, KG.role, "start", "Building knowledge graph (no RAG)")
    KG.run(board)
    return {"board": board}


def node_judge(state: SwarmState) -> dict[str, Any]:
    board = _board(state)
    board.log(JUDGE.name, JUDGE.role, "start", f"Judging {len(board.test_cases)} tests against the graph")
    JUDGE.run(board)
    return {"board": board}


def node_cover_report(state: SwarmState) -> dict[str, Any]:
    board = _board(state)
    board.log(COVER.name, COVER.role, "start", "Checking coverage gaps")
    COVER.run(board)
    REPORT.run(board)
    return {"board": board}


def build_swarm():
    g = StateGraph(SwarmState)
    g.add_node("embedded_doc_agent", node_unpack)
    g.add_node("modality_swarm", node_specialists)
    g.add_node("extractor_swarm", node_extract)
    g.add_node("knowledge_graph_agent", node_kg)
    g.add_node("judge_agent", node_judge)
    g.add_node("coverage_report", node_cover_report)
    g.add_edge(START, "embedded_doc_agent")
    g.add_edge("embedded_doc_agent", "modality_swarm")
    g.add_edge("modality_swarm", "extractor_swarm")
    g.add_edge("extractor_swarm", "knowledge_graph_agent")
    g.add_edge("knowledge_graph_agent", "judge_agent")
    g.add_edge("judge_agent", "coverage_report")
    g.add_edge("coverage_report", END)
    return g.compile()


SWARM = build_swarm()


def run_analysis(
    req_paths: list[str],
    test_paths: list[str],
    on_log: Any | None = None,
) -> AnalysisReport:
    board = Blackboard(req_paths=req_paths, test_paths=test_paths, on_log=on_log)
    board.log(
        "swarm_router",
        "Queen / orchestrator",
        "start",
        f"Local swarm · {len(req_paths)} req files · {len(test_paths)} test files",
    )
    result = SWARM.invoke({"board": board})
    out = result.get("board")
    if not isinstance(out, Blackboard) or not isinstance(out.report, AnalysisReport):
        raise RuntimeError("Swarm did not produce a report")
    return out.report
