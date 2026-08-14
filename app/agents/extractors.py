"""Requirement and test-case extractor agents consume the merged specialist corpus."""

from __future__ import annotations

from pathlib import Path

from app.agents.base import Blackboard
from app.extract import extract_items
from app.ingest import ParsedDoc


def _merged_docs(board: Blackboard, lane: str) -> list[ParsedDoc]:
    source_docs = board.req_docs if lane == "req" else board.test_docs
    by_name = {d.source_name: d for d in source_docs}
    names = set()
    for key in list(board.table_text) + list(board.semantic_text) + list(board.vision_text):
        if key.startswith(lane + ":"):
            names.add(key.split(":", 1)[1])
    names |= {d.source_name for d in source_docs}
    out: list[ParsedDoc] = []
    for name in sorted(names):
        parts = []
        for store in (board.table_text, board.semantic_text, board.vision_text):
            blob = store.get(f"{lane}:{name}")
            if blob:
                parts.append(blob)
        origin = by_name.get(name)
        text = "\n\n".join(parts) if parts else (origin.text if origin else "")
        if not text.strip():
            continue
        out.append(
            ParsedDoc(
                path=origin.path if origin else Path(name),
                source_name=name,
                parent_name=origin.parent_name if origin else "",
                text=text,
                kind="swarm-merged",
                images=origin.images if origin else [],
                modality=origin.modality if origin else "semantic",
            )
        )
    return out


class RequirementExtractorAgent:
    name = "requirement_extractor_agent"
    role = "Turn requirement corpus into structured REQ items"

    def run(self, board: Blackboard) -> None:
        docs = _merged_docs(board, "req")
        board.requirements = extract_items(docs, "requirement")
        board.log(
            self.name,
            self.role,
            "extracted",
            f"{len(board.requirements)} requirements from {len(docs)} merged docs",
        )


class TestExtractorAgent:
    name = "test_extractor_agent"
    role = "Turn test corpus into structured TC items"

    def run(self, board: Blackboard) -> None:
        docs = _merged_docs(board, "test")
        board.test_cases = extract_items(docs, "test")
        board.log(
            self.name,
            self.role,
            "extracted",
            f"{len(board.test_cases)} test cases from {len(docs)} merged docs",
        )
