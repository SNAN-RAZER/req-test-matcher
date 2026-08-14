"""Semantic agent: prose, slides, and narrative PDFs."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import Blackboard
from app.llm import chat_llm, parse_json_payload

SYS = """You are the Semantic Agent. Summarize and structure narrative text for later extraction.
Return JSON: {"clean_text":"..."} with IDs, shall-statements, steps, and expected results preserved.
Drop headers/footers/page numbers. Local-only."""


class SemanticAgent:
    name = "semantic_agent"
    role = "Process narrative text and slides"

    def run(self, board: Blackboard) -> None:
        llm = chat_llm()
        n = 0
        for lane, docs in (("req", board.req_docs), ("test", board.test_docs)):
            for doc in docs:
                if doc.modality not in {"semantic", "mixed"}:
                    continue
                text = (doc.text or "").strip()
                if not text:
                    continue
                cleaned = text
                try:
                    resp = llm.invoke(
                        [
                            SystemMessage(content=SYS),
                            HumanMessage(content=f"File {doc.source_name} parent={doc.parent_name}:\n{text[:9000]}"),
                        ]
                    )
                    payload = parse_json_payload(getattr(resp, "content", "") or "")
                    if isinstance(payload, dict) and payload.get("clean_text"):
                        cleaned = str(payload["clean_text"])
                except Exception:
                    cleaned = text
                board.semantic_text[f"{lane}:{doc.source_name}"] = cleaned
                n += 1
        board.log(self.name, self.role, "prose_cleaned", f"{n} narrative documents")
