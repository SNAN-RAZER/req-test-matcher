from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["error", "warning", "info"]
Verdict = Literal["aligned", "partial", "wrong", "orphan", "uncovered"]


class ExtractedItem(BaseModel):
    id: str
    title: str = ""
    text: str
    source_file: str = ""
    parent_file: str = ""
    extra: dict = Field(default_factory=dict)


class MatchResult(BaseModel):
    test_id: str
    requirement_id: str | None = None
    score: float = 0.0
    verdict: Verdict = "orphan"
    rationale: str = ""
    issues: list[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    agent: str
    role: str
    action: str
    detail: str = ""


class GraphSnapshot(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


class AnalysisReport(BaseModel):
    requirements: list[ExtractedItem]
    test_cases: list[ExtractedItem]
    matches: list[MatchResult]
    uncovered_requirements: list[str] = Field(default_factory=list)
    wrong_tests: list[MatchResult] = Field(default_factory=list)
    orphan_tests: list[MatchResult] = Field(default_factory=list)
    summary: str = ""
    model: str = ""
    files_processed: list[str] = Field(default_factory=list)
    agent_trace: list[AgentTrace] = Field(default_factory=list)
    vision_model: str = ""
    knowledge_graph: GraphSnapshot = Field(default_factory=GraphSnapshot)
