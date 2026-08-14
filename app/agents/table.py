"""Table agent: Excel, CSV, and markdown tables."""

from __future__ import annotations

from app.agents.base import Blackboard
from app.extract import _heuristic_table_items
from app.ingest import ParsedDoc
from app.llm import chat_llm, parse_json_payload
from langchain_core.messages import HumanMessage, SystemMessage

SYS = """You are the Table Agent. You only read tabular content (spreadsheets, CSV, markdown tables).
Return JSON: {"markdown":"normalized pipe table of all rows"} 
Preserve IDs, headers, expected results, and requirement links. Local-only, no cloud."""


def _docs_for_lane(docs: list[ParsedDoc], lane: str) -> list[ParsedDoc]:
    return [d for d in docs if d.modality in {lane, "mixed"}]


class TableAgent:
    name = "table_agent"
    role = "Normalize spreadsheets and pipe tables"

    def run(self, board: Blackboard) -> None:
        count = 0
        llm = chat_llm()
        for lane, docs in (("req", board.req_docs), ("test", board.test_docs)):
            for doc in _docs_for_lane(docs, "table"):
                heuristic = _heuristic_table_items(doc, "requirement" if lane == "req" else "test")
                body = doc.text[:9000]
                payload = None
                try:
                    resp = llm.invoke(
                        [
                            SystemMessage(content=SYS),
                            HumanMessage(content=f"File {doc.source_name}:\n{body}"),
                        ]
                    )
                    payload = parse_json_payload(getattr(resp, "content", "") or "")
                except Exception:
                    payload = None
                md = ""
                if isinstance(payload, dict):
                    md = str(payload.get("markdown") or "")
                if not md:
                    md = doc.text
                key = f"{lane}:{doc.source_name}"
                extra = ""
                if heuristic:
                    extra = "\n".join(f"{i.id} | {i.title} | {i.text}" for i in heuristic)
                    md = md + "\n" + extra
                board.table_text[key] = md
                count += 1
        board.log(self.name, self.role, "tables_normalized", f"{count} tabular documents")
