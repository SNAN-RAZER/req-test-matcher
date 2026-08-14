"""Knowledge-graph agent: build a local entity/relation graph instead of RAG."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import Blackboard
from app.config import settings
from app.knowledge import KnowledgeGraph
from app.llm import chat_llm, parse_json_payload

REL_SYS = """You are the Knowledge Graph Agent. Extract relations between test cases and requirements.
Return ONLY JSON:
{"relations":[{"from_type":"TC","from_id":"TC-001","to_type":"REQ","to_id":"REQ-001","rel":"tests|cites|contradicts|unrelated"}]}
Use contradicts when the test expected result fights the requirement.
Local only. Do not invent IDs that are not in the lists."""


class KnowledgeGraphAgent:
    name = "knowledge_graph_agent"
    role = "Build a local knowledge graph (no vector RAG)"

    def run(self, board: Blackboard) -> None:
        kg = KnowledgeGraph()
        for req in board.requirements:
            kg.add_requirement(req)
        for tc in board.test_cases:
            kg.add_test(tc)

        llm = chat_llm()
        req_list = ", ".join(r.id for r in board.requirements) or "(none)"
        tc_blob = "\n".join(f"{t.id}: {t.title} :: {t.text[:400]}" for t in board.test_cases)[:7000]
        req_blob = "\n".join(f"{r.id}: {r.title} :: {r.text[:400]}" for r in board.requirements)[:7000]
        extra = 0
        try:
            resp = llm.invoke(
                [
                    SystemMessage(content=REL_SYS),
                    HumanMessage(
                        content=f"REQUIREMENT IDS: {req_list}\n\nREQUIREMENTS:\n{req_blob}\n\nTEST CASES:\n{tc_blob}"
                    ),
                ]
            )
            payload = parse_json_payload(getattr(resp, "content", "") or "") or {}
            for rel in payload.get("relations") or []:
                if not isinstance(rel, dict):
                    continue
                ft = str(rel.get("from_type") or "TC").upper()
                tt = str(rel.get("to_type") or "REQ").upper()
                if ft == "TEST":
                    ft = "TC"
                if tt == "REQUIREMENT":
                    tt = "REQ"
                name = str(rel.get("rel") or "related").lower()
                if name == "unrelated":
                    continue
                kg.add_relation(ft, str(rel.get("from_id") or ""), tt, str(rel.get("to_id") or ""), name)
                extra += 1
        except Exception:
            extra = 0

        board.kg = kg
        snap = kg.snapshot()
        path = settings.kg_dir / "latest.json"
        kg.save(path)
        board.log(
            self.name,
            self.role,
            "graph_built",
            f"{snap['node_count']} nodes, {snap['edge_count']} edges, {extra} LLM relations. Saved {path}",
        )
