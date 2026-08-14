"""Coverage agent finds requirements with no tests; report agent assembles the matrix."""

from __future__ import annotations

from app.agents.base import Blackboard
from app.config import settings
from app.models import AnalysisReport, GraphSnapshot, MatchResult


class CoverageAgent:
    name = "coverage_agent"
    role = "Find uncovered requirements"

    def run(self, board: Blackboard) -> None:
        covered = {
            m.requirement_id
            for m in board.matches
            if m.requirement_id and m.verdict in {"aligned", "partial"}
        }
        uncovered = [r.id for r in board.requirements if r.id not in covered]
        for uid in uncovered:
            board.matches.append(
                MatchResult(
                    test_id="—",
                    requirement_id=uid,
                    verdict="uncovered",
                    rationale="No aligned or partial test case covers this requirement.",
                    issues=["Missing coverage"],
                )
            )
            if board.kg is not None:
                board.kg.add_node(f"REQ:{uid}", kind="requirement", label=uid)
                board.kg.add_node("GAP:uncovered", kind="gap", label="uncovered")
                board.kg.add_edge(f"REQ:{uid}", "GAP:uncovered", "uncovered")
        board.log(self.name, self.role, "gaps", f"{len(uncovered)} uncovered requirements")


class ReportAgent:
    name = "report_agent"
    role = "Publish the swarm traceability report"

    def run(self, board: Blackboard) -> None:
        matches = board.matches
        wrong = [m for m in matches if m.verdict == "wrong"]
        orphans = [m for m in matches if m.verdict == "orphan"]
        uncovered = [m.requirement_id for m in matches if m.verdict == "uncovered" and m.requirement_id]
        files = []
        for d in board.req_docs + board.test_docs:
            label = d.source_name
            if d.parent_name:
                label = f"{d.parent_name} → {d.source_name}"
            files.append(f"{label} [{d.modality}]")
        aligned_n = sum(1 for m in matches if m.verdict == "aligned")
        summary = (
            f"Swarm: {len(board.requirements)} requirements, {len(board.test_cases)} test cases. "
            f"{aligned_n} aligned, {len(wrong)} wrong, {len(orphans)} orphan tests, "
            f"{len(uncovered)} uncovered requirements. Knowledge graph (not RAG)."
        )
        kg_snap = GraphSnapshot()
        if board.kg is not None:
            raw = board.kg.snapshot()
            kg_snap = GraphSnapshot(**raw)
            board.kg.save(settings.kg_dir / "latest.json")
        board.report = AnalysisReport(
            requirements=board.requirements,
            test_cases=board.test_cases,
            matches=matches,
            uncovered_requirements=uncovered,
            wrong_tests=wrong,
            orphan_tests=orphans,
            summary=summary,
            model=settings.ollama_chat_model,
            vision_model=settings.ollama_vision_model,
            files_processed=files,
            agent_trace=board.traces,
            knowledge_graph=kg_snap,
        )
        board.log(self.name, self.role, "published", summary)
