"""Unpack nested files and hand work to specialist modality agents."""

from __future__ import annotations

from pathlib import Path

from app.agents.base import Blackboard
from app.ingest import flatten_docs, ingest_file


class EmbeddedDocAgent:
    name = "embedded_doc_agent"
    role = "Unpack nested PDF/Office attachments and classify modality"

    def run(self, board: Blackboard) -> None:
        req_docs = flatten_docs([ingest_file(Path(p)) for p in board.req_paths])
        test_docs = flatten_docs([ingest_file(Path(p)) for p in board.test_paths])
        board.req_docs = req_docs
        board.test_docs = test_docs
        nested = sum(1 for d in req_docs + test_docs if d.parent_name)
        images = sum(len(d.images) for d in req_docs + test_docs)
        board.log(
            self.name,
            self.role,
            "unpacked",
            f"{len(req_docs)} requirement docs, {len(test_docs)} test docs, "
            f"{nested} nested, {images} images. Modalities: "
            + ", ".join(f"{d.source_name}={d.modality}" for d in req_docs + test_docs),
        )
